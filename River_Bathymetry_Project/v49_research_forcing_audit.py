"""Offline V49 forcing research; never opens simulation NetCDF or changes inputs."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fiona
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize

ROOT = Path("D:/VTP")
PROJECT = ROOT / "River_Bathymetry_Project"
OUT = PROJECT / "V49_RESEARCH_20261014"
RUNTIME = ROOT / "V48_runs/20261004_runtime_fix_r1"
G = PROJECT / "V49_G_20261013"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def integral(series: np.ndarray, start: float, end: float) -> float:
    """Exact integral of the piecewise linear forcing on a covered interval."""
    assert series[0, 0] <= start < end <= series[-1, 0]
    inner = series[(series[:, 0] > start) & (series[:, 0] < end), 0]
    times = np.r_[start, inner, end]
    values = np.interp(times, series[:, 0], series[:, 1])
    return float(np.sum(np.diff(times) * (values[:-1] + values[1:]) / 2))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rain23 = ROOT / "Scenarios/rain_v23_era5_spatial.txt"
    rain34 = ROOT / "Scenarios/rain_v34_era5_x2.txt"
    raw_path = ROOT / "V45_runs/20260928_engine_r1/work/V45_openmeteo_era5_16point_20211125_20211203_v21_raw.json"
    ref_manifest_path = ROOT / "V45_runs/20260928_engine_r1/results/V45_openmeteo_era5_16point_20211125_20211203_v21_manifest.json"
    epoch_path = ROOT / "V48_RUN_EPOCH_PROVENANCE_20261002.json"
    objects_path = PROJECT / "V49_R3_20261013/C/V49_waterbody_classification.gpkg"
    central_path = G / "V49_G_CENTRAL_hydraulic_bed.asc"
    accepted_path = PROJECT / "V49_R3_20261013/E/V49_E_hydraulic_bed.tif"
    base_path = ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
    river_names = ["xa_lu_BaHa_Nov2021_V40_sync.txt", "xa_lu_BanThach_V43.txt",
                   "xa_lu_KyLo_V40_sync.txt", "xa_lu_TuyAn_V40_sync.txt"]
    static_paths = [rain23, rain34, raw_path, ref_manifest_path, epoch_path,
                    objects_path, central_path, accepted_path, base_path,
                    ROOT / "BG_Flood_Project/BG_Flood/prep_v34.py",
                    PROJECT / "v49_runtime_observer.py",
                    PROJECT / "v49_validate_hydraulic_validation.py",
                    PROJECT / "v49_evaluate_hydraulic_validation.py",
                    RUNTIME / "python/bg_flood/updateforcing.py"]
    static_paths += [G / f"BG_param_V49_G_{arm}.txt" for arm in ("BASE", "CENTRAL", "LOW", "HIGH")]
    static_paths += [RUNTIME / name for name in river_names]
    before = {str(p): digest(p) for p in static_paths}
    v23, v34 = np.loadtxt(rain23), np.loadtxt(rain34)
    assert v23.shape == v34.shape == (144, 2)
    assert np.all(np.diff(v34[:, 0]) > 0)
    assert np.array_equal(v23[:, 0], v34[:, 0])
    scaling_error = float(np.max(np.abs(v34[:, 1] - 2 * v23[:, 1])))
    assert scaling_error <= 5.1e-11
    epoch_info = json.loads(epoch_path.read_text(encoding="utf-8"))
    epoch = datetime.fromisoformat(epoch_info["conclusion"]["model_t0_utc"].replace("Z", "+00:00"))
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    ref_manifest = json.loads(ref_manifest_path.read_text(encoding="utf-8"))
    assert digest(raw_path) == ref_manifest["raw_json_sha256"]
    assert len(raw) == 16
    # Each API timestamp is the END of the preceding one-hour accumulation.
    validity = [epoch + timedelta(hours=i) for i in range(1, 121)]
    reference = []
    for point in raw:
        assert point["utc_offset_seconds"] == 0
        assert point["hourly_units"]["precipitation"] == "mm"
        lookup = dict(zip(point["hourly"]["time"], point["hourly"]["precipitation"], strict=True))
        reference.append([lookup[t.strftime("%Y-%m-%dT%H:%M")] for t in validity])
    reference = np.asarray(reference, dtype=float)
    assert np.all(np.isfinite(reference)) and np.all(reference >= 0)
    native_hourly = np.array([integral(v34, i * 3600, (i + 1) * 3600) * 1000 for i in range(120)])
    native23_hourly = np.array([integral(v23, i * 3600, (i + 1) * 3600) * 1000 for i in range(120)])
    ref_hourly = reference.mean(axis=0)
    rows = []
    for i in range(120):
        rows.append({"hour": i + 1, "start_utc": (epoch + timedelta(hours=i)).isoformat(),
                     "end_utc": validity[i].isoformat(), "v23_linear_mm": native23_hourly[i],
                     "v34_linear_mm": native_hourly[i], "archived_16point_mean_mm": ref_hourly[i],
                     "archived_point_min_mm": float(reference[:, i].min()),
                     "archived_point_max_mm": float(reference[:, i].max())})
    with (OUT / "V49_forcing_hourly_UTC.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with rasterio.open(central_path) as src:
        central = src.read(1).astype(np.float64)
        valid = (src.read_masks(1) > 0) & np.isfinite(central) & (central > -4) & (central < 9998)
        transform, crs, bounds = src.transform, src.crs, src.bounds
        cell_area = abs(transform.a * transform.e - transform.b * transform.d)
    with rasterio.open(base_path) as src:
        assert src.shape == central.shape and src.transform == transform and src.crs == crs
        base = src.read(1).astype(np.float64)
        assert np.array_equal(valid, (src.read_masks(1) > 0) & np.isfinite(base) & (base > -4) & (base < 9998))
    with rasterio.open(accepted_path) as src:
        assert src.shape == central.shape and src.transform == transform and src.crs == crs
        accepted = src.read(1).astype(np.float64)
    ascii_error = float(np.max(np.abs(central[valid] - accepted[valid])))
    # GDAL AAIGrid reads back float32: decimal serialization can shift a small
    # value by one float32 ULP. Keep raw differences separate from real edits.
    assert ascii_error <= 1e-6, "ASCII differs from accepted E by more than the declared one-micrometre audit tolerance"
    with fiona.open(objects_path, layer="classified_objects") as src:
        assert str(src.crs).upper() == str(crs).upper()
        ocean_geometries = [feature["geometry"] for feature in src if feature["properties"]["final_class"] == "OCEAN"]
    assert len(ocean_geometries) == 1
    ocean = rasterize([(geom, 1) for geom in ocean_geometries], out_shape=central.shape,
                      transform=transform, all_touched=False, dtype="uint8").astype(bool) & valid
    outside_ocean = valid & ~ocean
    h0 = np.where(valid, np.maximum(1.0 - central, 0.0), 0)
    h0_base = np.where(valid, np.maximum(1.0 - base, 0.0), 0)
    grid = {"crs": str(crs), "cell_area_m2": cell_area, "valid_cells": int(valid.sum()),
            "valid_area_km2": float(valid.sum() * cell_area / 1e6),
            "ocean_inventory_cells": int(ocean.sum()),
            "ocean_inventory_area_km2": float(ocean.sum() * cell_area / 1e6),
            "outside_ocean_area_km2": float(outside_ocean.sum() * cell_area / 1e6),
            "cold_start_total_m3": float(h0.sum() * cell_area),
            "cold_start_ocean_m3": float(h0[ocean].sum() * cell_area),
            "cold_start_outside_ocean_m3": float(h0[outside_ocean].sum() * cell_area),
            "cold_start_central_minus_base_m3": float((h0 - h0_base).sum() * cell_area),
            "accepted_e_changed_terrain_cells": int((valid & (accepted != base)).sum()),
            "ascii_changed_cells_above_1micrometre": int((valid & (np.abs(central - base) > 1e-6)).sum()),
            "ascii_nonidentical_float_cells": int((valid & (central != base)).sum()),
            "ascii_minus_accepted_max_abs_m": ascii_error,
            "lowering_volume_m3": float(np.maximum(base[valid] - accepted[valid], 0).sum() * cell_area),
            "note": "Ocean partition uses existing R3 inventory pixel centers; outside-ocean includes inland water and coastal cells, not solely dry land."}
    converter = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    requested_lat = list(map(float, ref_manifest["request_parameters"]["latitude"].split(",")))
    requested_lon = list(map(float, ref_manifest["request_parameters"]["longitude"].split(",")))
    point_rows = []
    for i, point in enumerate(raw):
        x, y = converter.transform(point["longitude"], point["latitude"])
        rx, ry = converter.transform(requested_lon[i], requested_lat[i])
        inside = lambda a, b: bounds.left <= a < bounds.right and bounds.bottom < b <= bounds.top
        point_rows.append({"point": i, "requested_lat": requested_lat[i], "requested_lon": requested_lon[i],
                           "returned_lat": point["latitude"], "returned_lon": point["longitude"],
                           "requested_center_in_domain": inside(rx, ry), "returned_center_in_domain": inside(x, y),
                           "returned_120h_mm": float(reference[i].sum())})
    with (OUT / "V49_archived_reference_points.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(point_rows[0]))
        writer.writeheader()
        writer.writerows(point_rows)
    rivers = {}
    for name in river_names:
        series = np.loadtxt(RUNTIME / name)
        rivers[name] = {"rows": len(series), "q_min_m3_s": float(series[:, 1].min()),
                        "q_max_m3_s": float(series[:, 1].max()),
                        "input_integral_120h_m3": integral(series, 0, 432000)}
    budget_path = G / "results/V49_G_CENTRAL_discrete_budget.json"
    budget = json.loads(budget_path.read_text(encoding="utf-8"))
    state = json.loads((G / "V49_G_EXECUTION_STATE.json").read_text(encoding="utf-8"))
    (OUT / "V49_CENTRAL_budget_snapshot.json").write_text(json.dumps(budget, indent=2), encoding="utf-8")
    (OUT / "V49_execution_snapshot.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    analytical_rain = integral(v34, 0, budget["simulated_time_s"]) * grid["valid_cells"] * cell_area
    known_added = budget["rain_volume_m3"] + budget["river_volume_m3"]
    comparison = {"simulated_time_s": budget["simulated_time_s"], "all_domain_analytic_rain_m3": analytical_rain,
                  "runtime_rain_m3": budget["rain_volume_m3"],
                  "rain_relative_discrete_minus_linear": (budget["rain_volume_m3"] - analytical_rain) / analytical_rain,
                  "initial_budget_minus_static_m3": budget["initial_volume_m3"] - grid["cold_start_total_m3"],
                  "clamp_added_over_positive_rain_river_pct": 100 * budget["clamp_added_volume_m3"] / known_added,
                  "infiltration_over_rain_pct": -100 * budget["infiltration_volume_m3"] / budget["rain_volume_m3"],
                  "note": "Infiltration ratio includes marine rainfall and is diagnostic only; cell-step negative counts are not unique cells."}
    after = {str(p): digest(p) for p in static_paths}
    assert after == before, "An audited static input changed during the offline audit"
    summary = {"schema": "V49-offline-forcing-research-1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
               "integrity_audit_pass": True, "scientific_validation_complete": False,
               "hydraulic_promotion_ready": False, "scope": "Offline inputs and atomic JSON only; no active NetCDF, no new hydraulic run",
               "epoch_utc": epoch.isoformat(), "rain_scaling_max_error_m_s": scaling_error,
               "v23_native_linear_120h_mm": float(native23_hourly.sum()),
               "v34_native_linear_120h_mm": float(native_hourly.sum()),
               "archived_reference_mean_120h_mm": float(ref_hourly.sum()),
               "v34_minus_archived_reference_pct": 100 * (native_hourly.sum() / ref_hourly.sum() - 1),
               "archived_reference_identity": "Open-Meteo ERA5 derivative retrieved 2026-09-28; not original V23 response, raw CDS or station truth",
               "requested_point_centers_in_model_domain": sum(r["requested_center_in_domain"] for r in point_rows),
               "returned_point_centers_in_model_domain": sum(r["returned_center_in_domain"] for r in point_rows),
               "reference_point_count": 16, "grid": grid, "river_input_integrals": rivers,
               "live_budget_diagnostics": comparison, "static_input_hashes": before,
               "static_input_hashes_unchanged_after": True}
    (OUT / "V49_forcing_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    hours = np.arange(1, 121)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, layout="constrained")
    axes[0].plot(hours - 0.5, native_hourly, label="V34 x2: frozen linear forcing", color="#1565c0")
    axes[0].plot(hours - 0.5, ref_hourly, label="Archived ERA5 derivative: mean of 16 points", color="#b45f06")
    axes[0].set_ylabel("Water per one-hour interval (mm)")
    axes[0].legend(loc="upper left", fontsize=9)
    for values, label, color in [(native_hourly, "V34 x2", "#1565c0"), (native23_hourly, "V23 x1", "#00897b"),
                                  (ref_hourly, "Archived reference", "#b45f06")]:
        axes[1].plot(np.r_[0, hours], np.r_[0, np.cumsum(values)], label=f"{label}: {values.sum():.2f} mm", color=color)
    axes[1].set_ylabel("Cumulative rainfall (mm)")
    axes[1].set_xlabel("Simulated hours since 2021-11-26 00:00 UTC+7")
    axes[1].legend(loc="upper left", fontsize=9)
    for ax in axes:
        ax.grid(alpha=0.25)
        ax.set_xlim(0, 120)
    fig.suptitle("V49 forcing audit: common UTC window, 120 hours\nArchived derivative comparison; not rain-gauge validation", fontsize=13)
    fig.savefig(OUT / "V49_rainfall_forcing_comparison.png", dpi=160)
    plt.close(fig)
    print(json.dumps({k: summary[k] for k in ("integrity_audit_pass", "epoch_utc", "v23_native_linear_120h_mm",
                     "v34_native_linear_120h_mm", "archived_reference_mean_120h_mm", "v34_minus_archived_reference_pct",
                     "requested_point_centers_in_model_domain", "returned_point_centers_in_model_domain", "grid",
                     "live_budget_diagnostics")}, indent=2))


if __name__ == "__main__":
    main()
