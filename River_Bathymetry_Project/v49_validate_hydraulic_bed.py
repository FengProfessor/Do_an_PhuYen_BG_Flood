"""Independent acceptance validator for V49-E hydraulic-bed synthesis."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import mapping

from v49_estimate_reach_geometry import DEFAULT_DEM, EXPECTED_DEM_SHA256
from v49_synthesize_hydraulic_bed import (
    AUTHORIZED_CLASS,
    DEFAULT_C1_EVIDENCE,
    DEFAULT_C1_GATE,
    DEFAULT_GEOMETRY,
    DEFAULT_LEGACY_NETWORK,
    DEFAULT_OUTPUT_DIR,
    MODIFICATION_EPS_M,
    authorized_reach_ids,
    boolish,
    load_protected_mask,
    reach_corridor_mask,
    sha256_file,
    split_pipe,
)


def _finite_positive(value: object) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def validate_v49_e(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    geometry_path: Path = DEFAULT_GEOMETRY,
    c1_gate_path: Path = DEFAULT_C1_GATE,
    c1_evidence_path: Path = DEFAULT_C1_EVIDENCE,
    dem_path: Path = DEFAULT_DEM,
    legacy_network_path: Path = DEFAULT_LEGACY_NETWORK,
) -> dict:
    reaches = gpd.read_file(geometry_path, layer="reach_geometry")
    gate = pd.read_csv(c1_gate_path)
    objects = gpd.read_file(c1_evidence_path, layer="audited_water_objects")
    expected_ids = authorized_reach_ids(reaches, gate)
    expected = reaches[reaches.reach_id.astype(str).isin(expected_ids)].copy()
    object_index = objects.set_index(objects.object_id.astype(str), drop=False)

    gpkg = output_dir / "V49_E_hydraulic_bed.gpkg"
    dem_out_path = output_dir / "V49_E_hydraulic_bed.tif"
    delta_path = output_dir / "V49_E_delta_z.tif"
    mask_path = output_dir / "V49_E_authorized_mask.tif"
    volume_path = output_dir / "V49_E_modification_volume_by_reach.csv"
    adjustment_path = output_dir / "V49_E_longitudinal_adjustments.csv"
    confluence_path = output_dir / "V49_E_confluence_checks.csv"
    audit_path = output_dir / "V49_E_hydraulic_bed_audit.json"
    map_path = output_dir / "V49_E_delta_z_map.png"
    required_outputs = [
        gpkg,
        dem_out_path,
        delta_path,
        mask_path,
        volume_path,
        adjustment_path,
        confluence_path,
        audit_path,
        map_path,
    ]
    missing_outputs = [str(path) for path in required_outputs if not path.exists()]
    if missing_outputs:
        report = {
            "schema_version": "V49-E-validation-1",
            "missing_output_files": missing_outputs,
            "gate_e_pass": False,
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "V49_E_validation_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return report

    output_reaches = gpd.read_file(gpkg, layer="authorized_reaches")
    output_ids = sorted(output_reaches.reach_id.astype(str).tolist())
    duplicate_output_ids = sorted(
        output_reaches.loc[output_reaches.reach_id.astype(str).duplicated(), "reach_id"].astype(str).tolist()
    )
    missing_authorized = sorted(set(expected_ids) - set(output_ids))
    extra_authorized = sorted(set(output_ids) - set(expected_ids))

    evidence_failures: dict[str, list[str]] = {}
    for _, reach in expected.iterrows():
        rid = str(reach.reach_id)
        failures: list[str] = []
        if not boolish(reach.geometry_authorized_for_v49e):
            failures.append("not_v49d_authorized")
        if split_pipe(reach.v49c_eligible_classes) != [AUTHORIZED_CLASS]:
            failures.append("not_unambiguous_river_stream")
        if not _finite_positive(reach.width_m) or not _finite_positive(reach.depth_est_m):
            failures.append("invalid_width_or_depth")
        for object_id in split_pipe(reach.v49c_object_ids):
            if object_id not in object_index.index:
                failures.append(f"missing_object:{object_id}")
                continue
            obj = object_index.loc[object_id]
            if str(obj.fixed_water_status) != "CONFIRMED_PERSISTENT":
                failures.append(f"nonpersistent_object:{object_id}")
            if not boolish(obj.automatic_carving_allowed_by_c1):
                failures.append(f"c1_blocked_object:{object_id}")
        if failures:
            evidence_failures[rid] = failures

    with rasterio.open(dem_path) as src:
        base = src.read(1).astype(np.float32)
        base_profile = src.profile.copy()
        transform = src.transform
        nodata = src.nodata
        pixel_area_m2 = abs(float(transform.a * transform.e - transform.b * transform.d))
    with rasterio.open(dem_out_path) as src:
        out = src.read(1).astype(np.float32)
        output_profile = src.profile.copy()
    with rasterio.open(delta_path) as src:
        delta = src.read(1).astype(np.float32)
        delta_profile = src.profile.copy()
    with rasterio.open(mask_path) as src:
        saved_mask = src.read(1).astype(bool)
        mask_profile = src.profile.copy()

    grids_match = bool(
        base.shape == out.shape == delta.shape == saved_mask.shape
        and base_profile.get("crs") == output_profile.get("crs") == delta_profile.get("crs") == mask_profile.get("crs")
        and base_profile.get("transform")
        == output_profile.get("transform")
        == delta_profile.get("transform")
        == mask_profile.get("transform")
    )
    valid = np.isfinite(base)
    if nodata is not None:
        valid &= base != nodata
    protected = load_protected_mask(legacy_network_path, base.shape)
    expected_mask = np.zeros(base.shape, dtype=bool)
    for _, reach in expected.iterrows():
        object_ids = split_pipe(reach.v49c_object_ids)
        associated_objects = objects[objects.object_id.astype(str).isin(object_ids)]
        class_mask = rasterize(
            [(mapping(geom), 1) for geom in associated_objects.geometry if geom is not None and not geom.is_empty],
            out_shape=base.shape,
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=False,
        ).astype(bool)
        expected_mask |= (
            reach_corridor_mask(reach.geometry, float(reach.width_m), base.shape, transform) & class_mask
        )
    expected_mask &= valid & ~protected
    authorized_mask_mismatch_count = int(np.logical_xor(saved_mask, expected_mask).sum())

    modified = valid & (np.abs(out - base) > MODIFICATION_EPS_M)
    raised_pixels = int((valid & (out > base + MODIFICATION_EPS_M)).sum())
    outside_mask_modified = int((modified & ~expected_mask).sum())
    protected_modified = int((modified & protected).sum())
    delta_negative = int((delta < -MODIFICATION_EPS_M).sum())
    delta_outside_mask = int(((delta > MODIFICATION_EPS_M) & ~expected_mask).sum())
    reconstruction_error = np.zeros(base.shape, dtype=np.float32)
    reconstruction_error[valid] = np.abs((base[valid] - out[valid]) - delta[valid])
    max_reconstruction_error_m = float(reconstruction_error[valid].max(initial=0.0))

    volume = pd.read_csv(volume_path)
    volume_ids = sorted(volume.reach_id.astype(str).tolist())
    volume_rows_complete = bool(volume_ids == expected_ids)
    volume_classes_ok = bool((volume.water_class.astype(str) == AUTHORIZED_CLASS).all())
    volume_positive = bool(
        (pd.to_numeric(volume.modified_pixel_count, errors="coerce") > 0).all()
        and (pd.to_numeric(volume.lowering_volume_m3, errors="coerce") > 0.0).all()
    )
    max_lowering_within_v49d_depth = bool(
        (
            pd.to_numeric(volume.max_lowering_m, errors="coerce")
            <= pd.to_numeric(volume.depth_est_m, errors="coerce") + 2.0e-5
        ).all()
    )
    raster_volume_m3 = float(delta[valid].sum(dtype=np.float64) * pixel_area_m2)
    table_volume_m3 = float(pd.to_numeric(volume.lowering_volume_m3, errors="coerce").sum())
    volume_difference_m3 = abs(raster_volume_m3 - table_volume_m3)
    volume_consistent = volume_difference_m3 <= max(1.0e-3, abs(raster_volume_m3) * 1.0e-8)

    adjustments = pd.read_csv(adjustment_path)
    adjustment_required = {
        "reach_id",
        "chainage_m",
        "original_target_bed_m",
        "adjusted_target_bed_m",
        "adjustment_m",
        "reason",
        "evidence_or_control",
    }
    adjustment_schema_ok = adjustment_required.issubset(adjustments.columns)
    adjustment_trace_ok = bool(
        adjustments.empty
        or (
            adjustments.reason.fillna("").astype(str).str.strip().ne("").all()
            and adjustments.evidence_or_control.fillna("").astype(str).str.strip().ne("").all()
        )
    )

    confluences = pd.read_csv(confluence_path)
    unresolved_confluences = (
        sorted(
            confluences.loc[
                confluences.final_bed_state.astype(str).str.startswith("REVIEW_REQUIRED"), "node_id"
            ].astype(str).tolist()
        )
        if not confluences.empty
        else []
    )
    blank_confluence_explanations = (
        sorted(
            confluences.loc[
                confluences.control_explanation.fillna("").astype(str).str.strip().eq(""), "node_id"
            ].astype(str).tolist()
        )
        if not confluences.empty
        else []
    )

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_ids = sorted(str(x) for x in audit.get("authorized_reach_ids", []))
    audit_consistent = bool(
        audit_ids == expected_ids
        and audit.get("global_monotonic_filter_used") is False
        and audit.get("legacy_named_branch_depth_used") is False
        and int(audit.get("outside_authorized_mask_modified_pixel_count", -1)) == 0
        and int(audit.get("protected_structure_modified_pixel_count", -1)) == 0
    )
    source_dem_hash = sha256_file(dem_path)
    source_dem_unchanged = bool(
        source_dem_hash == EXPECTED_DEM_SHA256
        and audit.get("source_hashes", {}).get("dem_sha256_before") == EXPECTED_DEM_SHA256
        and audit.get("source_hashes", {}).get("dem_sha256_after") == EXPECTED_DEM_SHA256
        and audit.get("source_dem_unchanged") is True
    )

    gate_e_pass = bool(
        expected_ids
        and not duplicate_output_ids
        and not missing_authorized
        and not extra_authorized
        and not evidence_failures
        and grids_match
        and authorized_mask_mismatch_count == 0
        and int(modified.sum()) > 0
        and raised_pixels == 0
        and outside_mask_modified == 0
        and protected_modified == 0
        and delta_negative == 0
        and delta_outside_mask == 0
        and max_reconstruction_error_m <= 2.0e-5
        and volume_rows_complete
        and volume_classes_ok
        and volume_positive
        and max_lowering_within_v49d_depth
        and volume_consistent
        and adjustment_schema_ok
        and adjustment_trace_ok
        and not unresolved_confluences
        and not blank_confluence_explanations
        and audit_consistent
        and source_dem_unchanged
    )
    report = {
        "schema_version": "V49-E-validation-1",
        "expected_authorized_reach_ids": expected_ids,
        "output_authorized_reach_ids": output_ids,
        "duplicate_output_reach_ids": duplicate_output_ids,
        "missing_authorized_reach_ids": missing_authorized,
        "extra_authorized_reach_ids": extra_authorized,
        "authorized_evidence_failures": evidence_failures,
        "grids_match": grids_match,
        "authorized_mask_mismatch_pixel_count": authorized_mask_mismatch_count,
        "modified_pixel_count": int(modified.sum()),
        "raised_pixel_count": raised_pixels,
        "outside_authorized_mask_modified_pixel_count": outside_mask_modified,
        "protected_structure_modified_pixel_count": protected_modified,
        "negative_delta_pixel_count": delta_negative,
        "delta_outside_authorized_mask_pixel_count": delta_outside_mask,
        "max_dem_minus_output_vs_delta_error_m": max_reconstruction_error_m,
        "volume_rows_complete": volume_rows_complete,
        "volume_classes_ok": volume_classes_ok,
        "volume_positive_per_reach": volume_positive,
        "max_lowering_within_v49d_depth": max_lowering_within_v49d_depth,
        "raster_lowering_volume_m3": raster_volume_m3,
        "table_lowering_volume_m3": table_volume_m3,
        "volume_difference_m3": volume_difference_m3,
        "volume_consistent": volume_consistent,
        "longitudinal_adjustment_schema_ok": adjustment_schema_ok,
        "forced_longitudinal_adjustment_count": int(len(adjustments)),
        "longitudinal_adjustments_traceable": adjustment_trace_ok,
        "unresolved_confluence_node_ids": unresolved_confluences,
        "blank_confluence_explanation_node_ids": blank_confluence_explanations,
        "audit_consistent": audit_consistent,
        "source_dem_expected_sha256": EXPECTED_DEM_SHA256,
        "source_dem_current_sha256": source_dem_hash,
        "source_dem_unchanged": source_dem_unchanged,
        "missing_output_files": missing_outputs,
        "gate_e_interpretation": (
            "Gate E certifies only the C.1 ∩ D authorized reach set. It verifies lowering-only raster synthesis, "
            "strict invariance outside independently reconstructed reach corridors, Dong Cam protected-mask invariance, "
            "per-reach modification volume, confluence/control traceability, and source-DEM integrity."
        ),
        "gate_e_pass": gate_e_pass,
    }
    (output_dir / "V49_E_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--c1-gate", type=Path, default=DEFAULT_C1_GATE)
    parser.add_argument("--c1-evidence", type=Path, default=DEFAULT_C1_EVIDENCE)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    parser.add_argument("--legacy-network", type=Path, default=DEFAULT_LEGACY_NETWORK)
    args = parser.parse_args()
    print(
        json.dumps(
            validate_v49_e(
                output_dir=args.output_dir,
                geometry_path=args.geometry,
                c1_gate_path=args.c1_gate,
                c1_evidence_path=args.c1_evidence,
                dem_path=args.dem,
                legacy_network_path=args.legacy_network,
            ),
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
