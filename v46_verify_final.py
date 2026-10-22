"""Independent final verification gate for the V46 conditioning chain."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

ROOT = Path(r"D:/VTP")


def sha256(path):
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    bad = []
    for group in ("inputs", "outputs"):
        for p, expected in data.get(group, {}).items():
            q = Path(p)
            if not q.exists():
                bad.append(f"missing:{p}")
            elif sha256(q) != expected:
                bad.append(f"hash:{p}")
    return bad


def main():
    base = ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m_V41.asc"
    out = ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m_V46.asc"
    audit = ROOT / "V46_audit_20260930"
    applied = audit / "V46_applied_cells.csv"
    conditioning_manifest = audit / "V46_conditioning_manifest.json"
    osm_manifest = ROOT / "V46_inputs/osm_historical_20211125/historical_osm_manifest.json"
    jrc_manifest = ROOT / "V46_inputs/JRC_GSW1_3_occurrence_1984_2020_manifest.json"
    hydro_manifest = ROOT / "V46_hydro_evidence_20260930/V46_hydro_evidence_manifest.json"
    seed_manifest = ROOT / "V46_seed55_historical_validated_20260930/V46_seed55_validation_manifest.json"
    seed_core = ROOT / "V46_seed55_historical_validated_20260930/V46_seed55_historical_validated_core.tif"
    topology_manifest = ROOT / "V46_topology_20260930/V46_topology_manifest.json"
    topology_csv = ROOT / "V46_topology_20260930/V46_topology_components.csv"

    required = [
        base,
        out,
        applied,
        conditioning_manifest,
        osm_manifest,
        jrc_manifest,
        hydro_manifest,
        seed_manifest,
        seed_core,
        topology_manifest,
        topology_csv,
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError("missing final artifacts: " + ", ".join(missing))

    osm = json.loads(osm_manifest.read_text(encoding="utf-8"))
    jrc = json.loads(jrc_manifest.read_text(encoding="utf-8"))
    applied_df = pd.read_csv(applied)
    topology_df = pd.read_csv(topology_csv)

    with rasterio.open(base) as a, rasterio.open(out) as b, rasterio.open(seed_core) as s:
        if a.shape != b.shape or a.transform != b.transform or a.nodata != b.nodata:
            raise RuntimeError("output grid metadata changed")
        if s.shape != a.shape or s.transform != a.transform or s.crs != a.crs:
            raise RuntimeError("validated seed grid mismatch")
        x = a.read(1).astype("float64")
        y = b.read(1).astype("float64")
        seed = s.read(1) > 0

    diff = y - x
    changed = np.abs(diff) > 0.001
    expected = np.zeros(changed.shape, bool)
    expected[applied_df.row.astype(int), applied_df.col.astype(int)] = True
    applied_inside_seed = bool(np.all(seed[applied_df.row.astype(int), applied_df.col.astype(int)]))

    allowed_decisions = {"AUTO_APPROVE_STRICT", "REVIEW_APPROVE_BOUNDED"}
    topology_by_component = topology_df.set_index("component_id")
    topology_rows = topology_by_component.loc[sorted(set(applied_df.component_id.astype(int)))]
    topology_ok = bool(
        topology_rows.topology_method.eq("DIRECT_D8_TRACE").all()
        and topology_rows.decision.isin(allowed_decisions).all()
    )

    strict = applied_df[applied_df.decision == "AUTO_APPROVE_STRICT"]
    bounded = applied_df[applied_df.decision == "REVIEW_APPROVE_BOUNDED"]
    checks = {
        "base_sha256_expected": sha256(base)
        == "9fb70773a96fc2d52521aa803c3aa08537a5e379d9592754541365ad32e15488",
        "osm_snapshot_exact": osm.get("snapshot_utc") == "2021-11-25T00:00:00Z",
        "osm_no_post_snapshot_way": (
            osm.get("returned_way_timestamp_max") is None
            or osm["returned_way_timestamp_max"] <= osm["snapshot_utc"]
        ),
        "jrc_pre2021": jrc.get("temporal_coverage") == "1984-2020",
        "validated_seed_is_55_cells": int(seed.sum()) == 55,
        "all_applied_inside_validated_seed": applied_inside_seed,
        "diff_matches_audit_rows": bool(np.array_equal(changed, expected)),
        "all_changes_lowering": bool(np.all(diff[changed] < 0)),
        "all_applied_decisions_allowed": bool(applied_df.decision.isin(allowed_decisions).all()),
        "all_applied_components_have_direct_d8_topology": topology_ok,
        "strict_cut_cap_1m": strict.empty or bool((strict.cut_depth_m <= 1.000001).all()),
        "bounded_cut_cap_3m": bounded.empty or bool((bounded.cut_depth_m <= 3.000001).all()),
        "all_applied_have_reason": bool(applied_df.reason_code.notna().all()),
        "all_applied_reason_has_direct_d8": bool(
            applied_df.reason_code.astype(str).str.contains("DIRECT_D8", case=False).all()
        ),
        "all_applied_have_osm": bool((applied_df.osm_way_id > 0).all()),
        "all_applied_have_hydrorivers": bool((applied_df.hydrorivers_id > 0).all()),
        "sentinel_not_in_applied_reason": not applied_df.reason_code.astype(str).str.contains(
            "SENTINEL", case=False
        ).any(),
    }

    manifests = [
        conditioning_manifest,
        hydro_manifest,
        seed_manifest,
        topology_manifest,
    ]
    manifest_errors = {str(p): verify_manifest(p) for p in manifests}
    checks["all_manifest_hashes_match"] = not any(manifest_errors.values())

    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "manifest_errors": manifest_errors,
        "base_sha256": sha256(base),
        "v46_sha256": sha256(out),
        "validated_seed_cells": int(seed.sum()),
        "modified_cells": int(changed.sum()),
        "modified_components": int(applied_df.component_id.nunique()),
        "strict_cells": int(len(strict)),
        "bounded_cells": int(len(bounded)),
        "cut_min_m": float((-diff[changed]).min()),
        "cut_median_m": float(np.median(-diff[changed])),
        "cut_max_m": float((-diff[changed]).max()),
    }
    report_path = audit / "V46_final_verification.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
