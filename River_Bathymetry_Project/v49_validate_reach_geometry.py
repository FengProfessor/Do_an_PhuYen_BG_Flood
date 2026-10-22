"""Independent V49-D acceptance validator."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import geopandas as gpd
import pandas as pd

from v49_estimate_reach_geometry import (
    DEFAULT_DEM,
    DEFAULT_GRAPH,
    DEFAULT_OUTPUT_DIR,
    EXPECTED_DEM_SHA256,
)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def _finite_positive(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def validate_v49_d(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    graph_path: Path = DEFAULT_GRAPH,
    dem_path: Path = DEFAULT_DEM,
) -> dict:
    gpkg = output_dir / "V49_reach_geometry.gpkg"
    audit_path = output_dir / "V49_D_geometry_audit.json"
    reaches = gpd.read_file(gpkg, layer="reach_geometry")
    confluences = gpd.read_file(gpkg, layer="confluence_checks")
    structures = gpd.read_file(gpkg, layer="structure_controls")
    source_reaches = gpd.read_file(graph_path, layer="reaches")
    source_nodes = gpd.read_file(graph_path, layer="nodes")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))

    required_fields = [
        "v49c_eligible_classes",
        "width_m",
        "width_source",
        "width_evidence_quality",
        "width_object_morphology_status",
        "bank_elevation_source",
        "slope_proxy",
        "slope_source",
        "q_proxy_cms",
        "q_source",
        "manning_n_low",
        "manning_n_central",
        "manning_n_high",
        "depth_est_m",
        "depth_low_m",
        "depth_high_m",
        "depth_method",
        "depth_status",
        "uncertainty_class",
        "depth_provenance",
        "preliminary_bed_state",
        "geometry_authorized_for_v49e",
        "authorization_reason",
        "distribution_outlier",
        "outlier_review_status",
    ]
    missing_fields = [field for field in required_fields if field not in reaches.columns]

    source_ids = set(source_reaches.reach_id.astype(str))
    output_ids = set(reaches.reach_id.astype(str))
    missing_reaches = sorted(source_ids - output_ids)
    extra_reaches = sorted(output_ids - source_ids)
    duplicate_reaches = sorted(
        reaches.loc[reaches.reach_id.astype(str).duplicated(), "reach_id"].astype(str).tolist()
    )

    authorized = reaches[reaches.geometry_authorized_for_v49e.astype(bool)].copy()
    authorized_failures: dict[str, list[str]] = {}
    for _, row in authorized.iterrows():
        failures: list[str] = []
        reach_id = str(row.reach_id)
        if str(row.source_type) != "HYDRORIVERS":
            failures.append("source_type_not_hydrorivers")
        if "RIVER_STREAM" not in str(row.v49c_eligible_classes):
            failures.append("not_v49c_river_stream")
        if "ESTUARY_TIDAL_RIVER" in str(row.v49c_eligible_classes):
            failures.append("tidal_reach_authorized")
        if not _finite_positive(row.width_m):
            failures.append("invalid_width")
        if str(row.width_evidence_quality) not in {"DIRECT_MEDIUM", "DIRECT_LOW"}:
            failures.append("width_evidence_not_direct")
        if not _finite_positive(row.depth_est_m):
            failures.append("invalid_depth")
        try:
            up, down = float(row.preliminary_bed_upstream_m), float(row.preliminary_bed_downstream_m)
            if not math.isfinite(up) or not math.isfinite(down):
                failures.append("unresolved_preliminary_bed_profile")
            elif down > up + 0.75:
                failures.append("unexplained_preliminary_downstream_bed_rise")
        except (TypeError, ValueError):
            failures.append("unresolved_preliminary_bed_profile")
        if not _finite_positive(row.depth_low_m) or not _finite_positive(row.depth_high_m):
            failures.append("invalid_depth_uncertainty")
        elif not (float(row.depth_low_m) < float(row.depth_est_m) < float(row.depth_high_m)):
            failures.append("depth_uncertainty_not_bracketing_central")
        if not _finite_positive(row.width_low_m) or not _finite_positive(row.width_high_m):
            failures.append("invalid_width_uncertainty")
        elif not (float(row.width_low_m) < float(row.width_m) < float(row.width_high_m)):
            failures.append("width_uncertainty_not_bracketing_central")
        if not str(row.depth_method).strip() or "NAME" in str(row.depth_method).upper():
            failures.append("blank_or_name_based_depth_method")
        if not str(row.depth_provenance).strip():
            failures.append("blank_depth_provenance")
        if not str(row.uncertainty_class).strip() or str(row.uncertainty_class) == "UNRESOLVED":
            failures.append("blank_or_unresolved_uncertainty")
        if not str(row.q_source).startswith("HYDRORIVERS_DIS_AV_CMS"):
            failures.append("missing_discharge_provenance")
        if bool(row.distribution_outlier):
            failures.append("outlier_still_authorized")
        if failures:
            authorized_failures[reach_id] = failures

    large_reaches = authorized[authorized.major_reach.astype(bool)] if "major_reach" in authorized else authorized.iloc[0:0]
    large_name_only = sorted(
        large_reaches.loc[
            large_reaches.depth_method.astype(str).str.upper().str.contains("NAME", regex=False), "reach_id"
        ].astype(str).tolist()
    )

    tidal_authorized = sorted(
        reaches.loc[
            reaches.geometry_authorized_for_v49e.astype(bool)
            & reaches.v49c_eligible_classes.astype(str).str.contains("ESTUARY_TIDAL_RIVER", regex=False),
            "reach_id",
        ].astype(str).tolist()
    )
    legacy_canal_authorized = sorted(
        reaches.loc[
            reaches.geometry_authorized_for_v49e.astype(bool)
            & reaches.source_type.astype(str).eq("LEGACY_CANAL_CANDIDATE"),
            "reach_id",
        ].astype(str).tolist()
    )

    outlier_review_failures = sorted(
        reaches.loc[
            reaches.distribution_outlier.astype(bool)
            & reaches.outlier_review_status.astype(str).str.strip().eq(""),
            "reach_id",
        ].astype(str).tolist()
    )

    source_confluence_count = int((source_nodes.node_type.astype(str) == "CONFLUENCE").sum())
    confluence_count_ok = len(confluences) == source_confluence_count
    blank_confluence_states = sorted(
        confluences.loc[
            confluences.preliminary_bed_state.fillna("").astype(str).str.strip().eq(""), "node_id"
        ].astype(str).tolist()
    )
    unexplained_inversions = sorted(
        confluences.loc[
            confluences.preliminary_bed_state.astype(str).eq("REVIEW_REQUIRED_BED_INVERSION"), "node_id"
        ].astype(str).tolist()
    )
    missing_control_explanations = sorted(
        confluences.loc[
            confluences.preliminary_bed_state.astype(str).str.startswith("CONTROL_EXCEPTION")
            & confluences.control_explanation.fillna("").astype(str).str.strip().eq(""),
            "node_id",
        ].astype(str).tolist()
    )

    dong_cam = structures[structures.structure_id.astype(str) == "STRUCT_DONG_CAM"]
    dong_cam_control_ok = bool(
        len(dong_cam) == 1
        and dong_cam.iloc[0].control_state == "EXPLICIT_HYDRAULIC_CONTROL_NO_MONOTONIC_ENFORCEMENT"
        and str(dong_cam.iloc[0].control_explanation).strip()
    )

    dem_hash_now = sha256_file(dem_path)
    hashes = audit.get("source_hashes", {})
    dem_unchanged = bool(
        dem_hash_now == EXPECTED_DEM_SHA256
        and hashes.get("dem_sha256_before") == EXPECTED_DEM_SHA256
        and hashes.get("dem_sha256_after") == EXPECTED_DEM_SHA256
        and audit.get("dem_unchanged", False)
        and int(audit.get("dem_modified_pixel_count_in_v49_d", -1)) == 0
    )

    no_fixed_depth_principal_source = bool(
        audit.get("legacy_fixed_depths_used") is False
        and not reaches.depth_method.astype(str).str.contains("3.50|2.25|1.20|LEGACY_FIXED", regex=True).any()
    )

    output_files = [
        gpkg,
        output_dir / "V49_reach_geometry.csv",
        output_dir / "V49_D_confluence_checks.csv",
        output_dir / "V49_D_review_queue.csv",
        output_dir / "V49_D_geometry_audit.json",
        output_dir / "V49_D_geometry_map.png",
        output_dir / "V49_D_width_distribution.png",
        output_dir / "V49_D_depth_distribution.png",
    ]
    missing_output_files = [str(path) for path in output_files if not path.exists()]

    gate_d_pass = bool(
        len(reaches) == len(source_reaches) == 370
        and not missing_fields
        and not missing_reaches
        and not extra_reaches
        and not duplicate_reaches
        and len(authorized) > 0
        and not authorized_failures
        and not large_name_only
        and not tidal_authorized
        and not legacy_canal_authorized
        and not outlier_review_failures
        and confluence_count_ok
        and not blank_confluence_states
        and not unexplained_inversions
        and not missing_control_explanations
        and dong_cam_control_ok
        and dem_unchanged
        and no_fixed_depth_principal_source
        and not missing_output_files
    )

    report = {
        "schema_version": "V49-D-validation-1",
        "source_reach_count": int(len(source_reaches)),
        "output_reach_count": int(len(reaches)),
        "authorized_reach_count": int(len(authorized)),
        "authorized_major_reach_count": int(len(large_reaches)),
        "missing_required_fields": missing_fields,
        "missing_reach_ids": missing_reaches,
        "extra_reach_ids": extra_reaches,
        "duplicate_reach_ids": duplicate_reaches,
        "authorized_reach_failures": authorized_failures,
        "large_reaches_with_name_only_depth": large_name_only,
        "tidal_reaches_incorrectly_authorized": tidal_authorized,
        "legacy_canals_incorrectly_authorized": legacy_canal_authorized,
        "outlier_review_failures": outlier_review_failures,
        "source_confluence_count": source_confluence_count,
        "output_confluence_count": int(len(confluences)),
        "blank_confluence_state_node_ids": blank_confluence_states,
        "unexplained_authorized_bed_inversion_node_ids": unexplained_inversions,
        "missing_control_explanation_node_ids": missing_control_explanations,
        "dong_cam_explicit_control_ok": dong_cam_control_ok,
        "legacy_fixed_depths_used_as_principal_source": not no_fixed_depth_principal_source,
        "dem_expected_sha256": EXPECTED_DEM_SHA256,
        "dem_current_sha256": dem_hash_now,
        "dem_unchanged": dem_unchanged,
        "modified_dem_pixel_count_in_v49_d": 0,
        "missing_output_files": missing_output_files,
        "gate_d_interpretation": (
            "Gate D certifies only the reaches explicitly authorized for V49-E. Tidal/backwater reaches, unverified legacy canals, "
            "V49-C excluded objects and distribution outliers remain review-only. Preliminary bed values are QA proxies, not surveyed bathymetry."
        ),
        "gate_d_pass": gate_d_pass,
    }
    (output_dir / "V49_D_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    args = parser.parse_args()
    print(json.dumps(validate_v49_d(args.output_dir, args.graph, args.dem), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
