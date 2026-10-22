from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(r"D:\VTP")
GIS = ROOT / "05-Du-lieu-GIS"
DIRECT_ROOT = ROOT / "V48_closed_loop_direct_20261002"
SUMMARY = DIRECT_ROOT / "V48_closed_loop_direct_summary.json"
BASE = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
SOURCE_TIF = DIRECT_ROOT / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_DIRECT_CANDIDATE.tif"
SOURCE_ASC = DIRECT_ROOT / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_DIRECT_CANDIDATE.asc"
SOURCE_PRJ = DIRECT_ROOT / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_DIRECT_CANDIDATE.prj"

FINAL_TIF = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.tif"
FINAL_ASC = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.asc"
FINAL_PRJ = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.prj"
MANIFEST = ROOT / "V48_CLOSED_LOOP_FROZEN_RELEASE_20261002.json"

EPS = 1e-7


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def raster_payload(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as ds:
        return ds.read(1), {
            "shape": [ds.height, ds.width],
            "transform": list(ds.transform)[:6],
            "crs": str(ds.crs),
            "nodata": ds.nodata,
        }


def main() -> None:
    required = [SUMMARY, BASE, SOURCE_TIF, SOURCE_ASC, SOURCE_PRJ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing closed-loop release input(s): {missing}")

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if summary.get("status") != "PASS_CLOSED_LOOP_DIRECT_CONVERGED_CANDIDATE_PRE_SAR":
        raise RuntimeError(f"Closed-loop candidate is not releasable: {summary.get('status')}")
    if summary.get("convergence", {}).get("final_strict_components") != 0:
        raise RuntimeError("Closed-loop candidate has non-zero final STRICT components")
    invariants = summary.get("invariants", {})
    for key in (
        "extrapolation_used",
        "only_lowering_vs_base",
        "max_cumulative_cut_le_1m",
        "max_cumulative_modified_cells_per_component_le_4",
        "final_baseline_auto_approve_strict_zero",
    ):
        expected = False if key == "extrapolation_used" else True
        if invariants.get(key) is not expected:
            raise RuntimeError(f"Closed-loop invariant failed: {key}={invariants.get(key)!r}")

    candidate = summary.get("candidate", {})
    if sha256(SOURCE_TIF) != candidate.get("tif_sha256"):
        raise RuntimeError("Candidate GeoTIFF hash does not match direct closed-loop summary")
    if sha256(SOURCE_ASC) != candidate.get("asc_sha256"):
        raise RuntimeError("Candidate ASC hash does not match direct closed-loop summary")
    if sha256(SOURCE_PRJ) != candidate.get("prj_sha256"):
        raise RuntimeError("Candidate PRJ hash does not match direct closed-loop summary")

    base, base_meta = raster_payload(BASE)
    source, source_meta = raster_payload(SOURCE_TIF)
    if source_meta != base_meta:
        raise RuntimeError("Closed-loop candidate grid/CRS/nodata differs from V48 base")
    valid = np.ones(base.shape, dtype=bool)
    if base_meta["nodata"] is not None:
        valid &= base != base_meta["nodata"]
    diff = base.astype(np.float64) - source.astype(np.float64)
    if np.any(diff[valid] < -EPS):
        raise RuntimeError("Closed-loop candidate raises one or more valid terrain cells")
    changed = valid & (diff > EPS)
    changed_cells = int(np.count_nonzero(changed))
    max_cut = float(diff[changed].max()) if changed_cells else 0.0
    expected_changed = int(summary["convergence"]["final_changed_cells_vs_base"])
    expected_max = float(summary["convergence"]["final_max_cumulative_cut_m"])
    if changed_cells != expected_changed:
        raise RuntimeError(f"Changed-cell mismatch: raster={changed_cells}, summary={expected_changed}")
    if abs(max_cut - expected_max) > 1e-5:
        raise RuntimeError(f"Max-cut mismatch: raster={max_cut}, summary={expected_max}")
    if max_cut > 1.0 + 1e-6:
        raise RuntimeError(f"Closed-loop max cumulative cut exceeds 1 m: {max_cut}")

    for src, dst in ((SOURCE_TIF, FINAL_TIF), (SOURCE_ASC, FINAL_ASC), (SOURCE_PRJ, FINAL_PRJ)):
        shutil.copyfile(src, dst)
        if sha256(src) != sha256(dst):
            raise RuntimeError(f"Frozen copy hash mismatch: {dst}")

    release = {
        "status": "V48_CLOSED_LOOP_FROZEN_PRE_SAR_RELEASE",
        "date": "2026-10-02",
        "sentinel1_2021_used_for_conditioning": False,
        "bg_flood_run": False,
        "formal_sar_evaluation_run": False,
        "source_summary": {"path": str(SUMMARY), "sha256": sha256(SUMMARY)},
        "base": {"path": str(BASE), "sha256": sha256(BASE)},
        "source_candidate": {
            "tif": str(SOURCE_TIF), "tif_sha256": sha256(SOURCE_TIF),
            "asc": str(SOURCE_ASC), "asc_sha256": sha256(SOURCE_ASC),
            "prj": str(SOURCE_PRJ), "prj_sha256": sha256(SOURCE_PRJ),
        },
        "frozen": {
            "tif": str(FINAL_TIF), "tif_sha256": sha256(FINAL_TIF),
            "asc": str(FINAL_ASC), "asc_sha256": sha256(FINAL_ASC),
            "prj": str(FINAL_PRJ), "prj_sha256": sha256(FINAL_PRJ),
        },
        "convergence": summary["convergence"],
        "verified": {
            "final_strict_components_zero": True,
            "only_lowering_vs_base": True,
            "changed_cells_vs_base": changed_cells,
            "max_cumulative_cut_m": max_cut,
            "frozen_bytes_equal_candidate": True,
            "legacy_pre_closed_loop_frozen_overwritten": False,
        },
    }
    MANIFEST.write_text(json.dumps(release, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(release, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
