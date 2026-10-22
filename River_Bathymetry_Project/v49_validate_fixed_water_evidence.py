"""Independent acceptance validator for V49-C.1."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

import geopandas as gpd
import pandas as pd

from v49_fixed_water_evidence_audit import (
    DEFAULT_DEM,
    DEFAULT_GEOMETRY,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PBF,
    DEFAULT_PBF_MD5,
    EXPECTED_DEM_SHA256,
    JRC_PATHS,
    VALID_STATUSES,
    sha256_file,
)


def verify_evidence_sources(audit: dict, pbf_path: Path = DEFAULT_PBF,
                            md5_path: Path = DEFAULT_PBF_MD5,
                            jrc_paths: dict = JRC_PATHS) -> dict:
    """Read the actual observation files; stored success flags are insufficient."""
    recorded = audit.get("source_hashes", {})
    paths = {**jrc_paths, "geofabrik_pbf_sha256": pbf_path}
    checks = {}
    for key, path in paths.items():
        actual = sha256_file(path) if path.is_file() else None
        expected = recorded.get(key)
        checks[key] = {"path": str(path), "actual_sha256": actual,
                       "expected_sha256": expected,
                       "pass": bool(expected) and actual == expected}
    md5_tokens = md5_path.read_text(encoding="utf-8").split() if md5_path.is_file() else []
    expected_md5 = md5_tokens[0].lower() if md5_tokens else None
    actual_md5 = None
    if pbf_path.is_file():
        digest = hashlib.md5()
        with pbf_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_md5 = digest.hexdigest()
    md5_ok = bool(expected_md5) and actual_md5 == expected_md5 == audit.get("geofabrik_md5_expected")
    return {"checks": checks, "geofabrik_md5_ok": md5_ok,
            "pass": md5_ok and all(check["pass"] for check in checks.values())}


def review_rows_block_automatic_carving(review_queue: pd.DataFrame) -> bool:
    """A resolved, empty queue is valid; every existing unresolved row must block."""
    return bool("blocks_v49e" in review_queue
                and review_queue.blocks_v49e.astype(str).str.lower().eq("true").all())


def validate_v49_c1(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    geometry_path: Path = DEFAULT_GEOMETRY,
    dem_path: Path = DEFAULT_DEM,
) -> dict:
    gpkg = output_dir / "V49_C1_fixed_water_evidence.gpkg"
    objects = gpd.read_file(gpkg, layer="audited_water_objects")
    reach_gate = gpd.read_file(gpkg, layer="v49e_reach_gate")
    d_reaches = gpd.read_file(geometry_path, layer="reach_geometry")
    audit = json.loads((output_dir / "V49_C1_audit.json").read_text(encoding="utf-8"))
    review_queue_path = output_dir / "V49_C1_review_queue.csv"
    review_queue = pd.read_csv(review_queue_path) if review_queue_path.exists() else pd.DataFrame()

    required_object_fields = {
        "object_id", "fixed_water_status", "fixed_water_reason",
        "jrc_occurrence_p50", "jrc_recurrence_p50", "jrc_2024_permanent_fraction",
        "jrc_transition_histogram", "current_osm_channel_m", "current_osm_names",
        "current_osm_polygon_dominant_type", "current_osm_polygon_overlap_fraction",
        "automatic_carving_allowed_by_c1",
    }
    missing_object_fields = sorted(required_object_fields - set(objects.columns))
    invalid_statuses = sorted(set(objects.fixed_water_status.astype(str)) - VALID_STATUSES)
    duplicate_objects = objects.loc[objects.object_id.duplicated(), "object_id"].astype(str).tolist()
    blank_reasons = objects.loc[objects.fixed_water_reason.fillna("").str.strip().eq(""), "object_id"].astype(str).tolist()

    d_auth = set(d_reaches.loc[d_reaches.geometry_authorized_for_v49e.astype(bool), "reach_id"].astype(str))
    c1_auth = set(reach_gate.loc[reach_gate.c1_authorized_for_v49e.astype(bool), "reach_id"].astype(str))
    promoted = sorted(c1_auth - d_auth)
    bad_c1_auth = []
    for _, row in reach_gate[reach_gate.c1_authorized_for_v49e.astype(bool)].iterrows():
        statuses = [x.strip() for x in str(row.c1_object_statuses).split("|") if x.strip()]
        if not statuses or any(s != "CONFIRMED_PERSISTENT" for s in statuses):
            bad_c1_auth.append(str(row.reach_id))

    dem_ok = (sha256_file(dem_path) == EXPECTED_DEM_SHA256
              and audit.get("source_hashes", {}).get("dem_sha256_before") == EXPECTED_DEM_SHA256
              and audit.get("source_hashes", {}).get("dem_sha256_after") == EXPECTED_DEM_SHA256)
    source_integrity = verify_evidence_sources(audit)
    geofabrik_hash_ok = source_integrity["geofabrik_md5_ok"]
    source_counts_ok = len(objects) == 81 and len(reach_gate) == 370
    required_review_fields = {
        "review_priority", "object_id", "fixed_water_status", "review_issue",
        "affected_v49d_authorized_reaches", "blocks_prior_v49d_authorization",
        "blocks_v49e", "fixed_water_reason",
    }
    missing_review_fields = sorted(required_review_fields - set(review_queue.columns))
    expected_review_ids = set(
        objects.loc[
            objects.fixed_water_status.isin({"CONFLICT_REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE"}),
            "object_id",
        ].astype(str)
    )
    actual_review_ids = set(review_queue.object_id.astype(str)) if "object_id" in review_queue else set()
    missing_review_objects = sorted(expected_review_ids - actual_review_ids)
    extra_review_objects = sorted(actual_review_ids - expected_review_ids)
    duplicate_review_objects = (
        review_queue.loc[review_queue.object_id.duplicated(), "object_id"].astype(str).tolist()
        if "object_id" in review_queue else []
    )
    review_rows_block_v49e = review_rows_block_automatic_carving(review_queue)
    output_files = [
        gpkg,
        output_dir / "V49_C1_fixed_water_audit.csv",
        output_dir / "V49_C1_v49e_reach_gate.csv",
        review_queue_path,
        output_dir / "V49_C1_audit.json",
    ]
    missing_files = [str(p) for p in output_files if not p.exists()]
    gate_c1_pass = bool(
        source_counts_ok
        and not missing_object_fields
        and not invalid_statuses
        and not duplicate_objects
        and not blank_reasons
        and not promoted
        and not bad_c1_auth
        and dem_ok
        and geofabrik_hash_ok
        and source_integrity["pass"]
        and not missing_review_fields
        and not missing_review_objects
        and not extra_review_objects
        and not duplicate_review_objects
        and review_rows_block_v49e
        and not missing_files
    )
    report = {
        "phase": "V49-C.1",
        "gate_c1_pass": gate_c1_pass,
        "object_count": int(len(objects)),
        "reach_count": int(len(reach_gate)),
        "v49d_authorized_count": len(d_auth),
        "c1_authorized_count": len(c1_auth),
        "c1_authorized_reach_ids": sorted(c1_auth),
        "promoted_beyond_v49d": promoted,
        "authorized_with_nonpersistent_object": bad_c1_auth,
        "missing_object_fields": missing_object_fields,
        "invalid_statuses": invalid_statuses,
        "duplicate_objects": duplicate_objects,
        "blank_reasons": blank_reasons,
        "dem_integrity_ok": dem_ok,
        "geofabrik_md5_ok": geofabrik_hash_ok,
        "source_integrity": source_integrity,
        "review_queue_count": int(len(review_queue)),
        "missing_review_fields": missing_review_fields,
        "missing_review_objects": missing_review_objects,
        "extra_review_objects": extra_review_objects,
        "duplicate_review_objects": duplicate_review_objects,
        "review_rows_block_v49e": review_rows_block_v49e,
        "missing_files": missing_files,
    }
    (output_dir / "V49_C1_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(validate_v49_c1(), ensure_ascii=False, indent=2))
