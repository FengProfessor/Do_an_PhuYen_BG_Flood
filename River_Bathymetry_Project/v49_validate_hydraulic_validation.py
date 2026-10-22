"""Independent validator for V49-G hydraulic-validation preparation and run state.

This validator deliberately separates two questions:

1. Is the matched BASE/CENTRAL/LOW/HIGH experiment prepared reproducibly?
2. Has Gate G actually been earned by completed matched runs and hydraulic evidence?

The first can PASS while the second remains PENDING.  Missing long-running
BG_Flood results must never be converted into a Gate-G PASS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import netCDF4 as nc
import numpy as np
import rasterio

from v49_estimate_reach_geometry import DEFAULT_DEM, EXPECTED_DEM_SHA256
from v49_prepare_hydraulic_validation import (
    BASE_RESULT,
    CANONICAL_MINMASK,
    CENTRAL_DEM,
    DEFAULT_OUTPUT_DIR,
    EXPECTED_CENTRAL_SHA256,
    EXPECTED_LEGACY_SHA256,
    FORBIDDEN_DIRS,
    LEGACY_DEM,
    _grid_signature,
    _normalized_config,
    _same_grid,
    is_historical_dir,
)
from v49_synthesize_hydraulic_bed import MODIFICATION_EPS_M, sha256_file


REQUIRED_RESULT_VARIABLES = {"time", "zs", "h", "zb", "u", "v"}


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _inspect_result(path: Path, observation_elapsed_s: float, max_offset_s: float, endtime_s: float) -> dict:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "status": "MISSING",
            "sar_frame_available": False,
            "complete_to_endtime": False,
        }

    try:
        with nc.Dataset(path, "r") as ds:
            variable_names = set(ds.variables.keys())
            missing_variables = sorted(REQUIRED_RESULT_VARIABLES - variable_names)
            times = np.asarray(np.ma.filled(ds.variables["time"][:], np.nan), dtype=float) if "time" in ds.variables else np.array([])
    except Exception as exc:  # pragma: no cover - exercised only by damaged external NetCDF files
        return {
            "path": str(path),
            "exists": True,
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
            "sar_frame_available": False,
            "complete_to_endtime": False,
        }

    valid_time_axis = bool(times.ndim == 1 and times.size and np.isfinite(times).all() and np.all(np.diff(times) > 0))
    if valid_time_axis:
        nearest_index = int(np.argmin(np.abs(times - observation_elapsed_s)))
        nearest_time_s = float(times[nearest_index])
        nearest_offset_s = float(abs(nearest_time_s - observation_elapsed_s))
        sar_frame_available = nearest_offset_s <= max_offset_s
        last_time_s = float(times[-1])
    else:
        nearest_index = None
        nearest_time_s = None
        nearest_offset_s = None
        sar_frame_available = False
        last_time_s = None

    variables_complete = not missing_variables
    complete_to_endtime = bool(last_time_s is not None and last_time_s >= endtime_s - 1.0)
    if not variables_complete:
        status = "INVALID_VARIABLE_SET"
    elif not valid_time_axis:
        status = "INVALID_TIME_AXIS"
    elif sar_frame_available:
        status = "AVAILABLE_FOR_PREREGISTERED_SAR_FRAME"
    else:
        status = "AVAILABLE_BUT_NO_PREREGISTERED_SAR_FRAME"

    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "status": status,
        "missing_required_variables": missing_variables,
        "frame_count": int(times.size),
        "time_axis_valid": valid_time_axis,
        "first_time_s": float(times[0]) if valid_time_axis else None,
        "last_time_s": last_time_s,
        "last_time_h": float(last_time_s / 3600.0) if last_time_s is not None else None,
        "nearest_sar_frame_index": nearest_index,
        "nearest_sar_frame_time_s": nearest_time_s,
        "nearest_sar_frame_offset_s": nearest_offset_s,
        "sar_frame_available": bool(sar_frame_available and variables_complete),
        "complete_to_endtime": complete_to_endtime,
    }


def _hash_matches(path: Path, expected: str) -> bool:
    return path.exists() and sha256_file(path) == expected


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_frozen_references(manifest: dict) -> dict:
    """Verify every live input pin, including solver, forcing and observation.

    Preparation booleans and audit-to-manifest string comparisons are not
    substitutes for reading the referenced input files again.
    """
    checks = {}
    hashes = {}

    def visit(value, label):
        if isinstance(value, dict):
            if "sha256" in value or "path" in value:
                raw_path = value.get("path")
                expected = value.get("sha256")
                if raw_path and expected:
                    path = Path(raw_path)
                    key = str(path.resolve())
                    if key not in hashes:
                        hashes[key] = sha256_file(path) if path.is_file() else None
                    checks[label] = {
                        "path": str(path),
                        "expected_sha256": expected,
                        "actual_sha256": hashes[key],
                        "pass": hashes[key] == expected,
                    }
                else:
                    checks[label] = {"path": raw_path, "pass": False, "reason": "MALFORMED_PIN"}
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    visit(child, f"{label}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{label}[{index}]")

    groups = ("terrain", "engine_semantics", "forcing", "sentinel1", "v48_r1_contract")
    for group in groups:
        value = manifest.get(group)
        if not isinstance(value, dict) or not value:
            checks[group] = {"pass": False, "reason": "MISSING_INPUT_GROUP"}
        else:
            previous_count = len(checks)
            visit(value, group)
            if len(checks) == previous_count:
                checks[group] = {"pass": False, "reason": "MISSING_INPUT_PINS"}
    return {
        "checks": checks,
        "reference_count": len(checks),
        "failed_references": [label for label, check in checks.items() if not check["pass"]],
        "pass": bool(checks) and all(check["pass"] for check in checks.values()),
    }


def inspect_published_evidence(register_path: Path) -> dict:
    """Expose new published references without upgrading their spatial/datum quality."""
    if not register_path.is_file():
        return {"available": False, "qualifies_for_exact_wse_acceptance": False}
    register = _load_json(register_path)
    checks = []
    for reference in register.get("sources", []) + register.get("output_tables", []):
        path = Path(reference.get("path", ""))
        actual = sha256_file(path) if path.is_file() else None
        okay = bool(reference.get("sha256")) and actual == reference.get("sha256")
        rows = None
        if okay and "row_count" in reference:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = sum(1 for _ in csv.DictReader(stream))
            okay = rows == reference["row_count"]
        checks.append({"path": str(path), "sha256_matches": actual == reference.get("sha256"),
                       "row_count": rows, "pass": bool(okay)})
    sources_ok = bool(checks) and all(r["pass"] for r in checks)
    return {"available": sources_ok, "register_path": str(register_path), "integrity_checks": checks,
            "reported_reservoir_curve_count": register.get("published_reservoir_curve_count"),
            "reported_minor_reservoir_reference_count": register.get("minor_reservoir_capacity_reference_count"),
            "reported_peak_count": register.get("official_reported_peak_count"),
            "reported_coarse_high_water_mark_count": register.get("published_high_water_mark_count"),
            "qualifies_for_exact_wse_acceptance": False,
            "interpretation": "Published reference tables and coarse diagnostics are available; exact station/survey coordinates, vertical datum reconciliation, observation conflicts and full event window remain unresolved."}


def validate_v49_g(output_dir: Path = DEFAULT_OUTPUT_DIR, dem_path: Path = DEFAULT_DEM) -> dict:
    manifest_path = output_dir / "V49_G_PREPARATION_MANIFEST.json"
    validation_path = output_dir / "V49_G_validation_report.json"
    if not manifest_path.exists():
        result = {
            "schema_version": "V49-G-validation-1",
            "status": "BLOCKED_MISSING_PREPARATION_MANIFEST",
            "preparation_pass": False,
            "gate_g_pass": False,
            "hydraulic_promotion_ready": False,
            "missing_outputs": [str(manifest_path)],
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        validation_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    manifest = _load_json(manifest_path)
    terrain = manifest.get("terrain", {})
    configs = manifest.get("configs", {})
    ascii_outputs = manifest.get("ascii_outputs", {})
    live_frozen_references = verify_frozen_references(manifest)

    required_files = [
        Path(terrain.get(arm, {}).get("path", ""))
        for arm in ("BASE", "CENTRAL", "LOW", "HIGH", "LEGACY_FIVE_BRANCH")
    ] + [
        Path(configs.get(arm, {}).get("path", "")) for arm in ("BASE", "CENTRAL", "LOW", "HIGH")
    ] + [
        Path(ascii_outputs.get(arm, {}).get("path", "")) for arm in ("BASE", "CENTRAL", "LOW", "HIGH")
    ]
    missing_files = [str(path) for path in required_files if not str(path) or not path.exists()]

    live_source_hash = sha256_file(dem_path) if dem_path.exists() else None
    source_dem_unchanged = live_source_hash == EXPECTED_DEM_SHA256
    central_hash_ok = _hash_matches(CENTRAL_DEM, EXPECTED_CENTRAL_SHA256)
    legacy_hash_ok = _hash_matches(LEGACY_DEM, EXPECTED_LEGACY_SHA256)

    live_grids: dict[str, dict] = {}
    for arm in ("BASE", "CENTRAL", "LOW", "HIGH", "LEGACY_FIVE_BRANCH"):
        path_value = terrain.get(arm, {}).get("path")
        path = Path(path_value) if path_value else None
        if path is not None and path.exists():
            live_grids[arm] = _grid_signature(path)

    comparable_grids_match = bool(
        all(arm in live_grids for arm in ("BASE", "CENTRAL", "LOW", "HIGH"))
        and all(_same_grid(live_grids["BASE"], live_grids[arm]) for arm in ("CENTRAL", "LOW", "HIGH"))
    )
    comparable_minmask_safe = bool(
        all(live_grids.get(arm, {}).get("valid_cells_le_canonical_minmask", -1) == 0 for arm in ("BASE", "CENTRAL", "LOW", "HIGH"))
    )
    legacy_requires_diagnostic_only = bool(
        live_grids.get("LEGACY_FIVE_BRANCH", {}).get("valid_cells_le_canonical_minmask", 0) > 0
    )

    ordering = {
        "low_le_central_violation_pixels": None,
        "central_le_high_violation_pixels": None,
        "pass": False,
    }
    comparable_paths = {
        arm: Path(terrain.get(arm, {}).get("path", "")) for arm in ("BASE", "CENTRAL", "LOW", "HIGH")
    }
    if all(path.exists() for path in comparable_paths.values()):
        arrays: dict[str, np.ndarray] = {}
        for arm, path in comparable_paths.items():
            with rasterio.open(path) as src:
                arrays[arm] = src.read(1).astype(np.float32)
        low_dz = arrays["BASE"] - arrays["LOW"]
        central_dz = arrays["BASE"] - arrays["CENTRAL"]
        high_dz = arrays["BASE"] - arrays["HIGH"]
        tol = 2.0e-5
        ordering = {
            "low_le_central_violation_pixels": int((low_dz > central_dz + tol).sum()),
            "central_le_high_violation_pixels": int((central_dz > high_dz + tol).sum()),
        }
        ordering["pass"] = bool(
            ordering["low_le_central_violation_pixels"] == 0
            and ordering["central_le_high_violation_pixels"] == 0
        )

    variant_audits_ok = True
    variant_audit_checks: dict[str, dict] = {}
    for arm in ("LOW", "HIGH"):
        audit_path = output_dir / f"V49_G_{arm}_terrain_audit.json"
        expected = manifest.get("variant_audits", {}).get(arm, {})
        if not audit_path.exists():
            variant_audits_ok = False
            variant_audit_checks[arm] = {"exists": False, "pass": False}
            continue
        audit = _load_json(audit_path)
        check = {
            "exists": True,
            "variant_invariance_pass": audit.get("variant_invariance_pass") is True,
            "outside_authorized_mask_zero": int(audit.get("outside_authorized_mask_modified_pixel_count", -1)) == 0,
            "protected_structure_modified_zero": int(audit.get("protected_structure_modified_pixel_count", -1)) == 0,
            "raised_pixels_zero": int(audit.get("raised_pixel_count", -1)) == 0,
            "source_hash_unchanged": audit.get("source_dem_sha256_before") == EXPECTED_DEM_SHA256
            and audit.get("source_dem_sha256_after") == EXPECTED_DEM_SHA256,
            "output_hash_matches_manifest": audit.get("output_dem_sha256") == expected.get("output_dem_sha256"),
        }
        check["pass"] = bool(all(check.values()))
        variant_audit_checks[arm] = check
        variant_audits_ok &= check["pass"]

    ascii_checks: dict[str, dict] = {}
    ascii_outputs_ok = True
    for arm in ("BASE", "CENTRAL", "LOW", "HIGH"):
        info = ascii_outputs.get(arm, {})
        path = Path(info.get("path", ""))
        exists = path.exists()
        hash_ok = exists and sha256_file(path) == info.get("sha256")
        roundtrip_ok = arm == "BASE" or (
            info.get("grid_roundtrip_ok") is True
            and float(info.get("max_value_roundtrip_error_m", 1.0)) <= 2.0e-5
        )
        ascii_checks[arm] = {"exists": exists, "sha256_matches_manifest": hash_ok, "roundtrip_ok": roundtrip_ok}
        ascii_outputs_ok &= bool(exists and hash_ok and roundtrip_ok)

    config_checks: dict[str, dict] = {}
    normalized_hashes: list[str] = []
    configs_ok = True
    for arm in ("BASE", "CENTRAL", "LOW", "HIGH"):
        info = configs.get(arm, {})
        path = Path(info.get("path", ""))
        exists = path.exists()
        if exists:
            text = path.read_text(encoding="utf-8")
            live_sha = sha256_file(path)
            normalized_sha = hashlib.sha256(_normalized_config(text).encode("utf-8")).hexdigest()
            normalized_hashes.append(normalized_sha)
        else:
            live_sha = None
            normalized_sha = None
        check = {
            "exists": exists,
            "sha256_matches_manifest": live_sha == info.get("sha256"),
            "normalized_sha256_matches_manifest": normalized_sha == info.get("normalized_sha256"),
        }
        check["pass"] = bool(all(check.values()))
        config_checks[arm] = check
        configs_ok &= check["pass"]
    normalized_configs_identical = bool(len(normalized_hashes) == 4 and len(set(normalized_hashes)) == 1)

    epoch = _parse_utc(str(manifest["run_epoch_utc"]))
    observation_time = _parse_utc(str(manifest["sentinel1"]["acquisition_midpoint_utc"]))
    observation_elapsed_s = float((observation_time - epoch).total_seconds())
    max_offset_s = float(manifest["sentinel1"]["frame_selection_rule"]["maximum_allowed_offset_s"])
    endtime_s = float(manifest["parameters"]["endtime_s"])

    execution_path = output_dir / "V49_G_EXECUTION_STATE.json"
    execution = _load_json(execution_path) if execution_path.exists() else {}
    new_base = Path(configs.get("BASE", {}).get("planned_result", ""))
    base_completed = execution.get("runs", {}).get("BASE", {}).get("status") in {
        "SIMULATION_COMPLETED_PENDING_EVALUATION", "COMPLETED"
    }
    result_paths = {"BASE": new_base if base_completed and new_base.is_file() else BASE_RESULT}
    for arm in ("CENTRAL", "LOW", "HIGH"):
        result_paths[arm] = Path(configs.get(arm, {}).get("planned_result", ""))
    run_state = {}
    for arm, path in result_paths.items():
        running = execution.get("runs", {}).get(arm, {}).get("status") == "RUNNING"
        if running and (arm != "BASE" or path != BASE_RESULT):
            run_state[arm] = {"path": str(path), "exists": path.is_file(), "status": "RUNNING",
                              "sar_frame_available": False, "complete_to_endtime": False}
        else:
            run_state[arm] = _inspect_result(path, observation_elapsed_s, max_offset_s, endtime_s)

    base_metrics_path = output_dir / "SAR_vs_V48_BASE_frame_33_metrics.json"
    base_metrics = _load_json(base_metrics_path) if base_metrics_path.exists() else None
    base_metrics_valid = bool(
        base_metrics
        and base_metrics.get("arm") == "BASE"
        and int(base_metrics.get("evaluated_frame", -1)) == 33
        and abs(float(base_metrics.get("depth_threshold_m", -1.0)) - float(manifest["sentinel1"]["wet_depth_threshold_m"])) < 1.0e-12
        and abs(float(base_metrics.get("water_density_threshold", -1.0)) - float(manifest["sentinel1"]["permanent_water_threshold"])) < 1.0e-12
    )

    preparation_checks = {
        "manifest_preparation_pass": manifest.get("preparation_pass") is True,
        "live_frozen_solver_forcing_terrain_observation_hashes_match": live_frozen_references["pass"],
        "required_preparation_files_present": not missing_files,
        "source_dem_unchanged": source_dem_unchanged,
        "central_hash_matches_accepted_v49e": central_hash_ok,
        "legacy_hash_matches_frozen_diagnostic": legacy_hash_ok,
        "comparable_grids_match": comparable_grids_match,
        "comparable_arms_safe_under_canonical_minmask": comparable_minmask_safe,
        "legacy_requires_diagnostic_only_policy": legacy_requires_diagnostic_only,
        "sensitivity_ordering_pass": ordering["pass"],
        "variant_audits_pass": variant_audits_ok,
        "ascii_outputs_pass": ascii_outputs_ok,
        "configs_match_manifest": configs_ok,
        "normalized_configs_identical_except_terrain_and_output": normalized_configs_identical,
        "base_sar_metrics_available_and_frozen": base_metrics_valid,
    }
    preparation_pass = bool(all(preparation_checks.values()))

    matched_new_runs_available = bool(
        all(run_state[arm].get("sar_frame_available") is True for arm in ("CENTRAL", "LOW", "HIGH"))
    )
    matched_run_set_available = bool(run_state["BASE"].get("sar_frame_available") is True and matched_new_runs_available)

    metric_availability = manifest.get("metric_availability", {})
    published_evidence = inspect_published_evidence(
        Path(__file__).resolve().parent / "V49_PUBLIC_EVIDENCE_20261013" / "V49_PUBLIC_EVIDENCE_REGISTER.json")
    missing_external_hydraulic_evidence = [
        key
        for key in ("gauge_wse_timing", "surveyed_high_water_marks", "known_wet_dry_points")
        if str(metric_availability.get(key, "")).startswith("UNAVAILABLE")
    ]

    blocking_reasons: list[str] = []
    if not preparation_pass:
        blocking_reasons.append("V49-G preparation integrity validation failed")
    if not matched_new_runs_available:
        blocking_reasons.append("CENTRAL/LOW/HIGH matched BG_Flood results are not yet available at the preregistered SAR frame")
    if missing_external_hydraulic_evidence:
        blocking_reasons.append(
            "Exact gauge/survey coordinates and vertical datum are not verified; published peaks and coarse high-water marks support limited diagnostics only"
        )
    blocking_reasons.append(
        "No matched CENTRAL/LOW/HIGH hydraulic metric comparison and explicit Gate-G acceptance decision has been produced"
    )

    gate_g_pass = False
    hydraulic_promotion_ready = False
    if not preparation_pass:
        status = "BLOCKED_PREPARATION_VALIDATION_FAILED"
    elif not matched_run_set_available:
        status = "PREPARED_PENDING_MATCHED_BG_FLOOD_RUNS"
    else:
        status = "MATCHED_RUNS_AVAILABLE_PENDING_HYDRAULIC_EVALUATION"

    result = {
        "schema_version": "V49-G-validation-1",
        "status": status,
        "canonical_minmask": CANONICAL_MINMASK,
        "preparation_checks": preparation_checks,
        "preparation_pass": preparation_pass,
        "missing_preparation_files": missing_files,
        "source_dem_expected_sha256": EXPECTED_DEM_SHA256,
        "source_dem_current_sha256": live_source_hash,
        "live_frozen_references": live_frozen_references,
        "live_grid_checks": {
            "comparable_grids_match": comparable_grids_match,
            "comparable_minmask_safe": comparable_minmask_safe,
            "legacy_valid_cells_le_canonical_minmask": live_grids.get("LEGACY_FIVE_BRANCH", {}).get(
                "valid_cells_le_canonical_minmask"
            ),
            "legacy_diagnostic_only_required": legacy_requires_diagnostic_only,
        },
        "sensitivity_ordering": ordering,
        "variant_audit_checks": variant_audit_checks,
        "ascii_checks": ascii_checks,
        "config_checks": config_checks,
        "run_state": run_state,
        "matched_run_set_available_at_preregistered_sar_frame": matched_run_set_available,
        "base_sar_metrics_path": str(base_metrics_path),
        "base_sar_metrics_valid": base_metrics_valid,
        "base_sar_metrics": base_metrics,
        "missing_external_hydraulic_evidence": missing_external_hydraulic_evidence,
        "published_external_evidence_context": published_evidence,
        "blocking_reasons": blocking_reasons,
        "gate_g_interpretation": (
            "Preparation PASS proves that the V49-G sensitivity terrains and matched BG_Flood configurations are reproducible. "
            "Gate G remains pending until matched CENTRAL/LOW/HIGH simulations and their hydraulic/observation comparisons exist. "
            "Large added storage, self-consistency, or the presence of output files alone cannot promote the V49 hydraulic DEM."
        ),
        "gate_g_pass": gate_g_pass,
        "hydraulic_promotion_ready": hydraulic_promotion_ready,
    }
    if not is_historical_dir(output_dir):
        validation_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    args = parser.parse_args()
    result = validate_v49_g(args.output_dir, args.dem)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    raise SystemExit(0 if result["preparation_pass"] else 1)


if __name__ == "__main__":
    main()
