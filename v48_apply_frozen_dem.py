from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


ROOT = Path(r"D:\VTP")
GIS = ROOT / "05-Du-lieu-GIS"
RESEARCH = ROOT / "V48_research_20261002"
AUDIT = ROOT / "V48_audit_20261002"
BASE_SOURCE = GIS / "PhuYen_DEM_30m.tif"
BASE_COPY = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
DRAFT = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_DRAFT.tif"
FROZEN = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.tif"
FROZEN_ASC = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.asc"
CUTS = RESEARCH / "final_selection/V48_final_cut_cells.csv"
SELECTION = RESEARCH / "final_selection/V48_final_selection_summary.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    cuts = pd.read_csv(CUTS)
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    if selection["status"] != "PASS_FINAL_PRE_SAR_SELECTION_FROZEN":
        raise RuntimeError("Final V48 selection is not frozen")
    if bool(selection["selection_rule"]["sentinel1_2021_used"]):
        raise RuntimeError("Sentinel-1 leakage flag is set")
    if len(cuts) != int(selection["counts"]["final_cut_cells"]):
        raise RuntimeError("Selection/cut count mismatch")
    if cuts.duplicated(["row", "col"]).any():
        raise RuntimeError("Duplicate final cut cell")
    if not (cuts.decision == "AUTO_APPROVE_STRICT").all():
        raise RuntimeError("Non-strict cut entered final V48")

    # Freeze a byte-identical named copy of the provenance-locked source.
    shutil.copy2(BASE_SOURCE, BASE_COPY)
    if sha256(BASE_COPY) != sha256(BASE_SOURCE):
        raise RuntimeError("V48 base copy is not byte-identical to raw Copernicus source")

    with rasterio.open(BASE_SOURCE) as src:
        base = src.read(1).astype(np.float64)
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
        nodata = src.nodata
        shape = src.shape

    out = base.copy()
    audit_rows = []
    for rec in cuts.itertuples(index=False):
        r, c = int(rec.row), int(rec.col)
        if not (0 <= r < shape[0] and 0 <= c < shape[1]):
            raise RuntimeError(f"Cut outside DEM grid: {r},{c}")
        original = float(base[r, c])
        proposed = float(rec.proposed_z_m)
        if nodata is not None and original == nodata:
            raise RuntimeError(f"Cut targets nodata: {r},{c}")
        if not np.isfinite(original) or not np.isfinite(proposed):
            raise RuntimeError(f"Non-finite cut value: {r},{c}")
        if abs(original - float(rec.original_z_m)) > 1e-5:
            raise RuntimeError(f"Base/cut provenance mismatch at {r},{c}")
        cut = original - proposed
        if cut <= 0.0 or cut > 1.000001:
            raise RuntimeError(f"Final cut outside strict bound at {r},{c}: {cut}")
        out[r, c] = proposed
        audit_rows.append(
            {
                "component_id": int(rec.component_id),
                "row": r,
                "col": c,
                "x": float(rec.x),
                "y": float(rec.y),
                "original_z_m": original,
                "conditioned_z_m": proposed,
                "cut_depth_m": cut,
                "osm_way_id": int(rec.osm_way_id),
                "hydrorivers_id": int(rec.hydrorivers_id),
                "upstream_area_buffer_max_km2": float(rec.upstream_area_buffer_max_km2),
                "decision": str(rec.decision),
                "reason_code": str(rec.reason_code),
            }
        )

    diff = out - base
    changed = np.abs(diff) > 1e-9
    expected = np.zeros(shape, dtype=bool)
    expected[cuts.row.astype(int), cuts.col.astype(int)] = True
    if not np.array_equal(changed, expected):
        raise RuntimeError(f"Changed mask mismatch: {changed.sum()} vs {expected.sum()}")
    if np.any(diff[changed] >= 0):
        raise RuntimeError("V48 contains a non-lowering modification")
    valid = np.isfinite(base)
    if nodata is not None:
        valid &= base != nodata
    if np.any(~np.isfinite(out[valid])):
        raise RuntimeError("NaN/Inf introduced")

    tif_profile = profile.copy()
    tif_profile.update(driver="GTiff", dtype="float32", count=1, compress="deflate")
    with rasterio.open(DRAFT, "w", **tif_profile) as dst:
        dst.write(out.astype(np.float32), 1)
        dst.update_tags(
            V48_STATUS="CONDITIONED_DRAFT_PRE_SAR",
            BASE_SHA256=sha256(BASE_SOURCE),
            SELECTION_SHA256=sha256(SELECTION),
            SENTINEL1_2021_USED_FOR_CONDITIONING="false",
            CONDITIONING_METHOD="local constrained strict cuts only; no global fill; no epsilon ramp",
        )

    # Verify the draft before freezing it byte-for-byte.
    with rasterio.open(DRAFT) as chk:
        reread = chk.read(1).astype(np.float64)
        if chk.shape != shape or chk.transform != transform or chk.crs != crs or chk.nodata != nodata:
            raise RuntimeError("Draft grid metadata mismatch")
    roundtrip_diff = reread - base
    roundtrip_changed = np.abs(roundtrip_diff) > 1e-6
    if not np.array_equal(roundtrip_changed, expected):
        raise RuntimeError("Draft roundtrip changed-mask mismatch")
    if float(np.max(np.abs(reread[expected] - out[expected]))) > 1e-5:
        raise RuntimeError("Draft roundtrip proposed values changed unexpectedly")

    shutil.copy2(DRAFT, FROZEN)
    if sha256(FROZEN) != sha256(DRAFT):
        raise RuntimeError("Frozen GeoTIFF is not byte-identical to verified draft")

    asc_profile = profile.copy()
    asc_profile.update(driver="AAIGrid", dtype="float32", count=1, nodata=nodata)
    with rasterio.open(FROZEN_ASC, "w", **asc_profile) as dst:
        dst.write(out.astype(np.float32), 1)
    prj = FROZEN_ASC.with_suffix(".prj")
    if crs is not None:
        prj.write_text(crs.to_wkt("WKT1_ESRI"), encoding="utf-8")

    applied_path = AUDIT / "V48_applied_cells.csv"
    pd.DataFrame(audit_rows).to_csv(applied_path, index=False, encoding="utf-8-sig")
    cell_area = abs(transform.a * transform.e)
    cut_depths = -diff[changed]
    summary = {
        "status": "V48_CONDITIONED_FROZEN_CREATED_PRE_SAR",
        "base": {
            "source": str(BASE_SOURCE),
            "source_sha256": sha256(BASE_SOURCE),
            "named_copy": str(BASE_COPY),
            "named_copy_sha256": sha256(BASE_COPY),
            "byte_identical": True,
        },
        "frozen": {
            "draft": str(DRAFT),
            "draft_sha256": sha256(DRAFT),
            "tif": str(FROZEN),
            "tif_sha256": sha256(FROZEN),
            "asc": str(FROZEN_ASC),
            "asc_sha256": sha256(FROZEN_ASC),
            "prj": str(prj),
            "prj_sha256": sha256(prj),
        },
        "selection": {
            "components": int(cuts.component_id.nunique()),
            "modified_cells": int(changed.sum()),
            "modified_area_km2": float(changed.sum() * cell_area / 1e6),
            "cut_depth_min_m": float(cut_depths.min()),
            "cut_depth_median_m": float(np.median(cut_depths)),
            "cut_depth_max_m": float(cut_depths.max()),
            "excavation_volume_m3": float(cut_depths.sum() * cell_area),
        },
        "invariants": {
            "grid_transform_preserved": True,
            "crs_preserved": True,
            "nodata_preserved": True,
            "only_selected_cells_modified": True,
            "only_lowering": True,
            "global_priority_flood_applied_to_final_dem": False,
            "epsilon_ramp_applied_to_final_dem": False,
            "negative_elevations_clipped": False,
            "sentinel1_2021_used_for_conditioning": False,
        },
        "selection_summary": str(SELECTION),
        "selection_summary_sha256": sha256(SELECTION),
        "applied_cells": str(applied_path),
        "applied_cells_sha256": sha256(applied_path),
    }
    summary_path = AUDIT / "V48_conditioning_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    evidence = [
        BASE_SOURCE,
        CUTS,
        SELECTION,
        RESEARCH / "candidate_sensitivity/V48_candidate_sensitivity_summary.json",
        RESEARCH / "topology_cap_sensitivity/V48_topology_cap_sensitivity_summary.json",
        RESEARCH / "source_holdout/V48_source_holdout_summary.json",
        RESEARCH / "hydro_evidence_raw/V46_hydro_evidence_manifest.json",
        ROOT / "V47_copernicus_provenance_20261001.json",
    ]
    outputs = [BASE_COPY, DRAFT, FROZEN, FROZEN_ASC, prj, applied_path, summary_path]
    manifest = {
        "algorithm": str(Path(__file__)),
        "algorithm_sha256": sha256(Path(__file__)),
        "inputs": {str(p): sha256(p) for p in evidence},
        "outputs": {str(p): sha256(p) for p in outputs},
        "sentinel1_2021_used": False,
    }
    manifest_path = AUDIT / "V48_conditioning_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
