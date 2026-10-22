"""Evaluate completed G runs at the frozen SAR time without frame fallback."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import netCDF4 as nc
import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import reproject, Resampling

from v49_prepare_hydraulic_validation import BASE_RESULT, DEFAULT_OUTPUT_DIR, assert_not_historical_dir
from v49_estimate_reach_geometry import DEFAULT_DEM
from v49_runtime_observer import atomic_json
from v49_synthesize_hydraulic_bed import sha256_file
from v49_validate_hydraulic_validation import validate_v49_g


WATER = Path(r"D:\VTP\05-Du-lieu-GIS\water_density_30m.tif")
HAND = Path(r"D:\VTP\BG_Flood_Project\BG_Flood\Teamwork_Validation\PhuYen_HAND_30m.tif")


def nearest_frame(times, target, max_offset):
    values = np.asarray(np.ma.filled(np.ma.asarray(times, dtype=float), np.nan), dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all() or np.any(np.diff(values) <= 0):
        raise ValueError("Output times must be finite and strictly increasing")
    index = int(np.argmin(np.abs(values - target)))
    offset = float(abs(values[index] - target))
    if offset > max_offset:
        raise ValueError(f"No model frame within the frozen SAR time tolerance: {offset}s")
    return index, offset


def verify_result_coordinates(x, y, shape, transform):
    if transform.b != 0 or transform.d != 0:
        raise ValueError("Rotated reference grid is not supported")
    expected_x = transform.c + (np.arange(shape[1]) + .5) * transform.a
    expected_y = transform.f + (np.arange(shape[0]) + .5) * transform.e
    def matches(values, expected):
        values = np.asarray(values, dtype=float)
        return (values.ndim == 1 and values.size == expected.size and np.isfinite(values).all()
                and (np.allclose(values, expected, rtol=0., atol=.1)
                     or np.allclose(values[::-1], expected, rtol=0., atol=.1)))
    if not matches(x, expected_x) or not matches(y, expected_y):
        raise ValueError("Result coordinates do not match the frozen DEM cell centers")


def contingency(observed, simulated, mask, pixel_area_km2):
    tp = int((mask & observed & simulated).sum())
    fp = int((mask & ~observed & simulated).sum())
    fn = int((mask & observed & ~simulated).sum())
    tn = int((mask & ~observed & ~simulated).sum())
    divide = lambda a, b: float(a / b) if b else None
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": divide(tp, tp + fp), "recall": divide(tp, tp + fn),
            "csi_iou": divide(tp, tp + fp + fn), "f1": divide(2 * tp, 2 * tp + fp + fn),
            "observed_area_km2": (tp + fn) * pixel_area_km2,
            "simulated_area_km2": (tp + fp) * pixel_area_km2,
            "area_bias": divide(fp - fn, tp + fn)}


def aligned(path, shape, transform, crs, dtype, nodata):
    data = np.full(shape, nodata, dtype=dtype)
    with rasterio.open(path) as source:
        reproject(source=rasterio.band(source, 1), destination=data,
                  src_transform=source.transform, src_crs=source.crs,
                  src_nodata=source.nodata, dst_transform=transform, dst_crs=crs,
                  dst_nodata=nodata, resampling=Resampling.nearest)
    return data


def evaluate_run(path, arm, manifest, output_dir):
    output_dir = Path(output_dir).resolve()
    assert_not_historical_dir(output_dir)
    target = (datetime.fromisoformat(manifest["sentinel1"]["acquisition_midpoint_utc"].replace("Z", "+00:00"))
              - datetime.fromisoformat(manifest["run_epoch_utc"].replace("Z", "+00:00"))).total_seconds()
    with rasterio.open(DEFAULT_DEM) as base:
        shape, transform, crs = base.shape, base.transform, base.crs
        area = abs(transform.a * transform.e - transform.b * transform.d)
    with nc.Dataset(path) as dataset:
        required = {"time", "h", "zs", "zb", "u", "v", "x", "y"}
        missing = required - set(dataset.variables)
        if missing:
            raise ValueError(f"Missing result variables: {sorted(missing)}")
        times = np.asarray(np.ma.filled(dataset.variables["time"][:], np.nan), dtype=float)
        index, offset = nearest_frame(times, target, manifest["sentinel1"]["frame_selection_rule"]["maximum_allowed_offset_s"])
        x = np.asarray(dataset.variables["x"][:], dtype=float)
        y = np.asarray(dataset.variables["y"][:], dtype=float)
        verify_result_coordinates(x, y, shape, transform)
        arrays = {}
        masked_count = 0
        for name in ("h", "zs", "zb", "u", "v"):
            variable = dataset.variables[name]
            raw = variable[:] if variable.ndim == 2 else variable[index]
            if name == "h":
                masked_count = int(np.ma.getmaskarray(raw).sum())
            value = np.asarray(np.ma.filled(raw, np.nan), dtype=np.float32)
            if y[0] < y[-1]:
                value = np.flipud(value)
            if x[0] > x[-1]:
                value = np.fliplr(value)
            arrays[name] = value
        complete = bool(times[-1] >= manifest["parameters"]["endtime_s"] - 1.0)
    sar = aligned(Path(manifest["sentinel1"]["path"]), shape, transform, crs, "uint8", 255)
    water = aligned(WATER, shape, transform, crs, "float32", -9999.0)
    hand = aligned(HAND, shape, transform, crs, "float32", -9999.0)
    mask = np.isin(sar, [0, 1]) & (water <= manifest["sentinel1"]["permanent_water_threshold"]) & (hand >= 0.0)
    # Preserve the preregistered mask. Expose missing modeled values rather than
    # silently changing the evaluation domain between scenarios.
    h = arrays["h"]
    metrics = contingency(sar == 1, np.nan_to_num(h) > manifest["sentinel1"]["wet_depth_threshold_m"], mask, area / 1e6)
    wet = np.isfinite(h) & (h > 0.3)
    speed = np.hypot(arrays["u"], arrays["v"])
    finite_speed = speed[wet & np.isfinite(speed)]
    valid = np.isfinite(h) & np.isfinite(arrays["zs"]) & np.isfinite(arrays["zb"])
    budget_path = output_dir / "results" / f"V49_G_{arm}_discrete_budget.json"
    budget = json.loads(budget_path.read_text(encoding="utf-8")) if budget_path.exists() else None
    report = {
        "schema_version": "V49-G-arm-evaluation-1", "arm": arm, "result": str(path),
        "result_sha256": sha256_file(path), "evaluated_frame": index, "sim_time_s": float(times[index]),
        "sar_frame_offset_s": offset, "complete_to_120h": complete, "metrics": metrics,
        "missing_simulated_values_in_preregistered_mask": int((mask & ~np.isfinite(h)).sum()),
        "modeled_masked_depth_cells": masked_count,
        "velocity": {"wet_cell_count": int(wet.sum()), "finite_wet_speed_count": int(finite_speed.size),
                     "speed_p50_m_s": float(np.percentile(finite_speed, 50)) if finite_speed.size else None,
                     "speed_p95_m_s": float(np.percentile(finite_speed, 95)) if finite_speed.size else None,
                     "speed_p99_m_s": float(np.percentile(finite_speed, 99)) if finite_speed.size else None,
                     "speed_max_m_s": float(finite_speed.max()) if finite_speed.size else None},
        "numerical_consistency": {
            "negative_depth_cells": int((h[np.isfinite(h)] < -1e-6).sum()),
            "wse_minus_bed_and_depth_max_error_m": float(np.max(np.abs(arrays["zs"][valid] - arrays["zb"][valid] - h[valid]))) if valid.any() else None},
        "discrete_budget": budget,
        "observed_wse_metrics": {"status": "UNAVAILABLE_NO_VERIFIED_DATUM_AND_GAUGE_SERIES"},
        "observed_timing_metrics": {"status": "UNAVAILABLE_NO_VERIFIED_TIMESTAMPED_GAUGE_SERIES"},
        "hydraulic_promotion_ready": False,
    }
    from v49_evaluate_external_evidence import EVIDENCE, evaluate_coarse_high_water_marks
    if (EVIDENCE / "V49_HWM_DIAGNOSTIC_PREREGISTRATION.json").is_file():
        report["additional_published_hwm_diagnostic"] = evaluate_coarse_high_water_marks(path)
    atomic_json(output_dir / f"V49_G_{arm}_hydraulic_metrics.json", report)
    return report


def evaluate_available_runs(output_dir=DEFAULT_OUTPUT_DIR):
    output_dir = Path(output_dir).resolve()
    assert_not_historical_dir(output_dir)
    preparation = validate_v49_g(output_dir)
    if not preparation["preparation_pass"]:
        raise RuntimeError("Cannot evaluate after frozen input integrity failure")
    manifest = json.loads((output_dir / "V49_G_PREPARATION_MANIFEST.json").read_text(encoding="utf-8"))
    state_path = output_dir / "V49_G_EXECUTION_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    reports = {}
    pending = []
    for arm in ("BASE", "CENTRAL", "LOW", "HIGH"):
        path = Path(manifest["configs"][arm]["planned_result"])
        running = state.get("runs", {}).get(arm, {}).get("status") == "RUNNING"
        if arm == "BASE" and (not path.exists() or running):
            path = BASE_RESULT
        elif not path.exists() or running:
            pending.append(arm)
            continue
        reports[arm] = evaluate_run(path, arm, manifest, output_dir)
    summary = {"schema_version": "V49-G-matched-metrics-1", "status": "PENDING_MATCHED_RUNS" if pending else "MATCHED_METRICS_AVAILABLE_PENDING_HYDRAULIC_REVIEW",
               "available_arms": list(reports), "pending_arms": pending, "arms": reports,
               "all_arms_complete_to_120h": len(reports) == 4 and all(r["complete_to_120h"] for r in reports.values()),
               "gate_g_pass": False, "hydraulic_promotion_ready": False,
               "interpretation": "Matching an observed extent does not resolve missing bathymetry coverage or replace field evidence"}
    if "BASE" in reports:
        base = reports["BASE"]["metrics"]
        summary["difference_from_base"] = {
            arm: {key: report["metrics"][key] - base[key] for key in ("csi_iou", "f1", "precision", "recall", "simulated_area_km2")
                  if report["metrics"][key] is not None and base[key] is not None}
            for arm, report in reports.items() if arm != "BASE"}
    atomic_json(output_dir / "V49_G_matched_hydraulic_metrics.json", summary)
    pd.DataFrame([{"arm": arm, **report["metrics"], "complete_to_120h": report["complete_to_120h"]}
                  for arm, report in reports.items()]).to_csv(output_dir / "V49_G_matched_extent_metrics.csv", index=False)
    return summary


if __name__ == "__main__":
    result = evaluate_available_runs()
    print(json.dumps({key: result[key] for key in ("status", "available_arms", "pending_arms", "gate_g_pass")}, ensure_ascii=True))
