"""Audit preserved interrupted frames and make explicitly partial diagnostics.

Never modifies frozen inputs, original simulation files or execution state.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fiona
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import netCDF4 as nc
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
from shapely.geometry import shape

ROOT = Path("D:/VTP")
P = ROOT / "River_Bathymetry_Project"
G = P / "V49_G_20261013"
OUT = P / "V49_G_POWERLOSS_RECOVERY_20261014"
RAW = OUT / "RAW"
BASE = ROOT / "V48_runs/20261004_runtime_fix_r1/results/V48_FORMAL_BASE_R1.nc"
VARS = ("h", "zs", "zb", "u", "v")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def normalized_config(path):
    lines = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^(bathy|outfile)\s*=", line, flags=re.I):
            line = line.split("=", 1)[0].strip() + " = <ARM>;"
        lines.append(line)
    return "\n".join(lines)


def aligned(path, grid):
    target = np.full(grid["shape"], -9999., dtype="float32")
    with rasterio.open(path) as src:
        reproject(source=rasterio.band(src, 1), destination=target,
                  src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                  dst_transform=grid["transform"], dst_crs=grid["crs"], dst_nodata=-9999.,
                  resampling=Resampling.nearest)
    return target


def read_frame(dataset, i, grid):
    x, y = dataset.variables["x"][:], dataset.variables["y"][:]
    t = grid["transform"]
    ex = t.c + (np.arange(grid["shape"][1]) + .5) * t.a
    ey = t.f + (np.arange(grid["shape"][0]) + .5) * t.e
    assert np.allclose(x if x[0] < x[-1] else x[::-1], ex, atol=.1, rtol=0)
    assert np.allclose(y if y[0] > y[-1] else y[::-1], ey, atol=.1, rtol=0)
    arrays = {}
    for name in VARS:
        raw = dataset.variables[name][i]
        a = np.asarray(np.ma.filled(raw, np.nan), dtype="float32")
        if y[0] < y[-1]:
            a = np.flipud(a)
        if x[0] > x[-1]:
            a = np.fliplr(a)
        assert a.shape == grid["shape"]
        arrays[name] = a
    return arrays


def raster(path, values, grid, description):
    data = np.where(np.isfinite(values), values, -9999).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1],
                       count=1, crs=grid["crs"], transform=grid["transform"],
                       dtype="float32", nodata=-9999, compress="deflate", tiled=True) as dst:
        dst.write(data, 1)
        dst.set_band_description(1, description)
        dst.update_tags(scope="Interrupted partial run; not Gate-G acceptance", units="m")
    with rasterio.open(path) as check:
        assert check.shape == grid["shape"] and check.transform == grid["transform"]
        assert check.crs == grid["crs"]


def main():
    OUT.mkdir(exist_ok=True)
    manifest = json.loads((RAW / "V49_G_PREPARATION_MANIFEST.json").read_text())
    budget = json.loads((RAW / "V49_G_CENTRAL_discrete_budget.json").read_text())
    preservation = json.loads((OUT / "V49_RAW_PRESERVATION_REGISTER.json").read_text())
    for item in preservation:
        assert sha(item["copy"]) == item["sha256"], item["copy"]
    frozen = json.loads((P / "V49_RESEARCH_20261014/V49_forcing_audit.json").read_text())
    for path, expected in frozen["static_input_hashes"].items():
        assert sha(path) == expected, f"Frozen research input changed: {path}"
    base_hash = sha(BASE)
    assert base_hash == manifest["existing_base_result"]["sha256"]
    old_config = ROOT / "V48_runs/20261004_runtime_fix_r1/BG_param_PhuYen_30m_V48_FORMAL_BASE_R1.txt"
    assert normalized_config(old_config) == normalized_config(G / "BG_param_V49_G_CENTRAL.txt")
    with rasterio.open(G / "V49_G_CENTRAL_hydraulic_bed.asc") as src:
        bed = src.read(1).astype(float)
        valid = (src.read_masks(1) > 0) & np.isfinite(bed) & (bed > -4) & (bed < 9998)
        grid = {"shape": src.shape, "transform": src.transform, "crs": src.crs,
                "bounds": src.bounds, "area": abs(src.transform.a * src.transform.e)}
    with fiona.open(P / "V49_R3_20261013/C/V49_waterbody_classification.gpkg", layer="classified_objects") as objects:
        ocean_shapes = [f["geometry"] for f in objects if f["properties"]["final_class"] == "OCEAN"]
    ocean = rasterize([(geom, 1) for geom in ocean_shapes], out_shape=grid["shape"],
                      transform=grid["transform"], dtype="uint8").astype(bool) & valid
    non_ocean = valid & ~ocean
    water = aligned(ROOT / "05-Du-lieu-GIS/water_density_30m.tif", grid)
    hand = aligned(ROOT / "BG_Flood_Project/BG_Flood/Teamwork_Validation/PhuYen_HAND_30m.tif", grid)
    analysis = non_ocean & np.isfinite(water) & (water >= 0) & (water <= .5) & (hand >= 0)
    regions = {}
    with fiona.open(P / "V49_R3_20261013/D/V49_reach_geometry.gpkg", layer="reach_geometry") as reaches:
        assert str(reaches.crs) == str(grid["crs"])
        for f in reaches:
            rid = f["properties"]["reach_id"]
            if rid in ("HR_41349822", "HR_41352752"):
                geom = shape(f["geometry"])
                regions[rid] = {"geometry": geom, "mask": rasterize([(geom.buffer(500), 1)],
                    out_shape=grid["shape"], transform=grid["transform"], dtype="uint8").astype(bool) & non_ocean}
    assert len(regions) == 2
    (OUT / "V49_EXPLORATORY_PARTIAL_ANALYSIS_DESIGN.json").write_text(json.dumps({
        "scope": "Exploratory analysis after known interruption, not preregistered Gate G",
        "comparison": "Historical frozen V48 BASE paired at nearest output time; max offset 1 second",
        "temporary_water_candidate_mask": "valid non-ocean AND 0<=water_density<=0.5 AND HAND>=0; no SAR scoring",
        "depth_threshold_m": .3, "local_aoi": "500 m buffer of each of the two authorized D reaches, native raster cell centers",
        "local_aoi_reach_ids": list(regions), "difference_diagnostics_m": [.0001, .001, .01],
        "promotion": False}, indent=2), encoding="utf-8")
    rows, local_rows, failures = [], [], []
    max_saved = np.full(grid["shape"], -np.inf, dtype="float32")
    last = last_base = None
    with nc.Dataset(RAW / "V49_G_CENTRAL.nc", "r") as c, nc.Dataset(BASE, "r") as b:
        times, bt = np.asarray(c.variables["time"][:], dtype=float), np.asarray(b.variables["time"][:], dtype=float)
        assert np.isfinite(times).all() and np.all(np.diff(times) > 0)
        assert set(VARS) <= set(c.variables) and set(VARS) <= set(b.variables)
        for i, time_s in enumerate(times):
            try:
                ca = read_frame(c, i, grid)
                counts = {name: int((valid & ~np.isfinite(a)).sum()) for name, a in ca.items()}
                assert not any(counts.values()), counts
                bi = int(np.argmin(np.abs(bt - time_s)))
                offset = float(abs(bt[bi] - time_s))
                assert offset <= 1.0
                ba = read_frame(b, bi, grid)
                assert all(np.isfinite(a[valid]).all() for a in ba.values())
                h, bh = ca["h"], ba["h"]
                delta = h.astype(float) - bh.astype(float)
                wet = valid & (h > .3)
                abs_delta = np.abs(delta)
                speed = np.hypot(ca["u"], ca["v"])
                consistency = np.abs(ca["zs"].astype(float) - ca["zb"].astype(float) - h.astype(float))
                row = {"frame": i, "time_s": float(time_s), "time_h": float(time_s / 3600),
                       "base_frame": bi, "base_time_s": float(bt[bi]), "pair_offset_s": offset,
                       "all_variables_finite_on_domain": True,
                       "negative_depth_cells": int((valid & (h < -1e-6)).sum()),
                       "depth_at_100m_cap_cells": int((valid & (h >= 99.999)).sum()),
                       "wse_bed_depth_max_abs_error_m": float(consistency[valid].max()),
                       "central_volume_all_m3": float(h[valid].sum(dtype=float) * grid["area"]),
                       "central_volume_outside_ocean_m3": float(h[non_ocean].sum(dtype=float) * grid["area"]),
                       "central_wet_area_outside_ocean_km2": int((non_ocean & wet).sum()) * .0009,
                       "central_temporary_water_candidate_km2": int((analysis & wet).sum()) * .0009,
                       "base_temporary_water_candidate_km2": int((analysis & (bh > .3)).sum()) * .0009,
                       "wet_status_changed_candidate_km2": int((analysis & ((h > .3) != (bh > .3))).sum()) * .0009,
                       "central_max_depth_outside_ocean_m": float(h[non_ocean].max()),
                       "speed_max_m_s": float(speed[valid].max()),
                       "speed_p99_wet_m_s": float(np.percentile(speed[wet], 99)) if wet.any() else None,
                       "depth_difference_max_abs_m": float(abs_delta[valid].max()),
                       "depth_difference_mean_abs_outside_ocean_m": float(abs_delta[non_ocean].mean()),
                       "depth_difference_gt_1mm_outside_ocean_cells": int((non_ocean & (abs_delta > .001)).sum()),
                       "depth_difference_gt_1cm_outside_ocean_cells": int((non_ocean & (abs_delta > .01)).sum())}
                for rid, region in regions.items():
                    m = region["mask"]
                    local_rows.append({"frame": i, "time_h": time_s / 3600, "reach_id": rid,
                        "aoi_cells": int(m.sum()), "aoi_area_km2": int(m.sum()) * .0009,
                        "central_wet_area_km2": int((m & wet).sum()) * .0009,
                        "base_wet_area_km2": int((m & (bh > .3)).sum()) * .0009,
                        "central_max_depth_m": float(h[m].max()),
                        "depth_difference_max_abs_m": float(abs_delta[m].max()),
                        "depth_difference_mean_abs_m": float(abs_delta[m].mean()),
                        "depth_difference_gt_1mm_cells": int((m & (abs_delta > .001)).sum())})
                rows.append(row)
                max_saved = np.maximum(max_saved, h)
                last, last_base = ca, ba
                print(f"Verified frame {i}: {time_s/3600:.3f} h; BASE offset {offset:.4f} s", flush=True)
            except Exception as exc:
                failures.append({"frame": i, "time_s": float(time_s), "error": f"{type(exc).__name__}: {exc}"})
        variable_inventory = {k: {"dtype": str(v.dtype), "dimensions": v.dimensions} for k, v in c.variables.items()}
    assert rows, "No complete finite spatial frame could be recovered"
    for filename, values in [("V49_partial_frame_metrics.csv", rows), ("V49_partial_reach_metrics.csv", local_rows)]:
        with (OUT / filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    last_time = rows[-1]["time_s"]
    raster(OUT / "V49_CENTRAL_last_saved_depth_33h.tif", last["h"], grid, "Depth at last verified saved frame; partial run")
    raster(OUT / "V49_CENTRAL_max_depth_saved_frames_3h_33h.tif", max_saved, grid, "Maximum over VERIFIED SAVED FRAMES only; not continuous or full-event maximum")
    raster(OUT / "V49_CENTRAL_minus_BASE_depth_last_saved.tif", last["h"].astype(float) - last_base["h"].astype(float), grid, "Depth difference to historical BASE at nearest time; exploratory")
    log = (RAW / "V49_G_CENTRAL_run.log").read_text(encoding="utf-8", errors="replace")
    match = re.findall(r"t = ([\d.]+)/([\d.]+)s.*?elapsed = ([\d.]+)s", log)
    log_time = float(match[-1][0])
    epoch = datetime.fromisoformat(manifest["run_epoch_utc"].replace("Z", "+00:00"))
    sar_target = (datetime.fromisoformat(manifest["sentinel1"]["acquisition_midpoint_utc"].replace("Z", "+00:00")) - epoch).total_seconds()
    closure = budget["current_volume_m3"] - budget["initial_volume_m3"] - sum(budget[f"{k}_volume_m3"] for k in ("rain", "river", "infiltration", "flux_divergence", "boundary_reset")) - budget["accumulated_signed_update_residual_m3"]
    report = {"schema": "V49-interrupted-result-salvage-1", "analysis_created_utc": datetime.now(timezone.utc).isoformat(),
              "status": "PARTIAL_FRAMES_RECOVERED_NOT_GATE_G", "power_loss_reported_by_user": True,
              "preservation_files": len(preservation), "all_preserved_hashes_verified": True,
              "frozen_input_files_verified": len(frozen["static_input_hashes"]),
              "original_central_sha256": preservation[0]["sha256"], "historical_base_sha256": base_hash,
              "normalized_historical_base_and_central_configs_match": True,
              "available_frame_count": len(times), "verified_frame_count": len(rows), "failed_frame_checks": failures,
              "last_saved_time_s": last_time, "last_saved_time_h": last_time / 3600,
              "last_saved_event_time_UTC7": (epoch + timedelta(seconds=last_time)).astimezone(timezone(timedelta(hours=7))).isoformat(),
              "last_logged_time_s": log_time, "last_logged_time_h": log_time / 3600,
              "unsaved_tail_s": log_time - last_time, "unsaved_tail_h": (log_time - last_time) / 3600,
              "log_end_progress_pct": 100 * log_time / 432000,
              "saved_end_progress_pct": 100 * last_time / 432000,
              "sar_required_time_s": sar_target, "sar_required_time_h": sar_target / 3600,
              "sar_frame_available": abs(last_time - sar_target) <= 5400,
              "complete_to_120h": False, "LOW_HIGH_new_BASE_status": "NOT_STARTED",
              "exact_restart_checkpoint_available": False, "variable_inventory": variable_inventory,
              "recomputed_budget_unexplained_residual_m3": closure,
              "budget_snapshot_time_h": budget["simulated_time_s"] / 3600,
              "budget_snapshot_is_at_last_saved_frame": False,
              "last_saved_metrics": rows[-1], "max_frame_pair_offset_s": max(r["pair_offset_s"] for r in rows),
              "last_frame_local_metrics": [r for r in local_rows if r["frame"] == rows[-1]["frame"]],
              "analysis_mask_area_km2": int(analysis.sum()) * .0009,
              "scope": "Exploratory early-event numerical and terrain sensitivity; no Sentinel score or surveyed bathymetry validation",
              "gate_g_pass": False, "hydraulic_promotion_ready": False}
    (OUT / "V49_POWERLOSS_SALVAGE_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # Maps use the same non-ocean mask and explicit depth/difference legends.
    extent = [grid["bounds"].left / 1000, grid["bounds"].right / 1000,
              grid["bounds"].bottom / 1000, grid["bounds"].top / 1000]
    fig, axes = plt.subplots(1, 2, figsize=(13, 7), layout="constrained")
    depth = np.where(non_ocean & (last["h"] > .3), last["h"], np.nan)
    im = axes[0].imshow(depth, extent=extent, origin="upper", cmap="Blues", vmin=.3, vmax=5)
    fig.colorbar(im, ax=axes[0], label="Depth (m); display saturates above 5 m", shrink=.75)
    axes[0].set_title(f"CENTRAL: last verified frame {last_time/3600:.2f} h\nOcean excluded; display h > 0.30 m")
    delta = np.where(non_ocean, last["h"].astype(float) - last_base["h"].astype(float), np.nan)
    lim = max(.01, float(np.nanmax(np.abs(delta))))
    im = axes[1].imshow(delta, extent=extent, origin="upper", cmap="RdBu_r", norm=TwoSlopeNorm(0, -lim, lim))
    fig.colorbar(im, ax=axes[1], label="CENTRAL minus historical BASE depth (m)", shrink=.75)
    axes[1].set_title("Exploratory comparison at nearly identical times\nSame grid/forcing; incomplete event")
    for ax in axes:
        ax.set_facecolor("#ededed")
        for rid, region in regions.items():
            point = region["geometry"].centroid
            ax.plot(point.x / 1000, point.y / 1000, "o", color="#ef6c00", ms=4)
            ax.annotate(rid.replace("HR_", ""), (point.x / 1000, point.y / 1000), fontsize=7, xytext=(4, 4), textcoords="offset points")
        ax.set_xlabel("UTM easting (km), EPSG:32649")
        ax.set_ylabel("UTM northing (km)")
    fig.suptitle("V49 recovered results — last saved event time 27 Nov 2021, 09:00 UTC+7", fontsize=13)
    fig.savefig(OUT / "V49_recovered_33h_depth_and_difference.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, layout="constrained")
    th = [r["time_h"] for r in rows]
    for key, label, color in [("central_temporary_water_candidate_km2", "CENTRAL", "#1565c0"),
                              ("base_temporary_water_candidate_km2", "Historical BASE", "#b45f06")]:
        axes[0].plot(th, [r[key] for r in rows], label=label, color=color)
    axes[0].set_ylabel("Temporary-water candidate area (km²)")
    axes[0].legend()
    axes[1].plot(th, [r["depth_difference_max_abs_m"] for r in rows], color="#6a1b9a")
    axes[1].set_ylabel("Max absolute depth difference (m)")
    axes[1].set_xlabel("Simulated hours; saved frames only, interrupted before 36 h")
    for ax in axes:
        ax.grid(alpha=.25)
    fig.suptitle("Recovered 3–33 h diagnostics; no SAR validation\nArea excludes ocean, water_density > 0.5 and negative HAND", fontsize=12)
    fig.savefig(OUT / "V49_recovered_early_event_diagnostics.png", dpi=150)
    plt.close(fig)
    print(json.dumps({k: report[k] for k in ("verified_frame_count", "failed_frame_checks", "last_saved_time_h",
          "last_logged_time_h", "unsaved_tail_h", "max_frame_pair_offset_s", "last_saved_metrics", "last_frame_local_metrics")}, indent=2))


if __name__ == "__main__":
    main()
