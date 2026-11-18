#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V48 Formal Differential Evaluator: CONDITIONED vs BASE (R3)
===========================================================
Calculates Delta h(x, y) = h_CONDITIONED(x, y) - h_BASE(x, y) at Frame 33 (102.0h / 367,200s),
applies the identical Common Evaluation Mask from V48_SAR_preregistration_R1.json:
    Domain valid & SAR in {0, 1} & water_density <= 0.5 & HAND >= 0.0 m,
computes quantitative flow transfer across the 66 lowered levee cells and Tuy Hoa plain,
evaluates contingency metric shifts (Delta CSI, Delta Recall, Delta Precision, Delta F1),
and produces:
    - results/V48_DIFF_CONDITIONED_vs_BASE_frame_33.json
    - results/V48_DIFF_depth_map_frame_33.png (300 DPI 2-panel publication map)
"""

import os
import sys
import json
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import netCDF4 as nc
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import matplotlib.patches as mpatches

ROOT = Path(__file__).resolve().parent

DEFAULT_NC_BASE = ROOT / "results" / "V48_FORMAL_BASE_R1.nc"
DEFAULT_NC_COND = ROOT / "results" / "V48_FORMAL_CONDITIONED_R1.nc"
DEFAULT_SAR = Path(r"D:\VTP\05-Du-lieu-GIS\DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif")
DEFAULT_WATER = Path(r"D:\VTP\05-Du-lieu-GIS\water_density_30m.tif")
DEFAULT_HAND = Path(r"D:\VTP\BG_Flood_Project\BG_Flood\Teamwork_Validation\PhuYen_HAND_30m.tif")
DEFAULT_CELLS_CSV = Path(r"D:\VTP\V48_closed_loop_direct_20261002\V48_closed_loop_direct_applied_cells.csv")
DEFAULT_METRICS_BASE = ROOT / "results" / "SAR_vs_V48_BASE_frame_33_metrics.json"
DEFAULT_METRICS_COND = ROOT / "results" / "SAR_vs_V48_CONDITIONED_frame_33_metrics.json"
DEFAULT_OUT_DIR = ROOT / "results"


def load_netcdf_frame(nc_path, frame_idx):
    """
    Load water depth h from NetCDF at specified frame, vertically aligned to North-up raster.
    """
    nc_path = Path(nc_path)
    if not nc_path.is_file():
        raise FileNotFoundError(f"NetCDF dataset not found: {nc_path}")

    with nc.Dataset(nc_path, 'r') as ds:
        num_frames = len(ds.variables['time'])
        if frame_idx >= num_frames:
            raise IndexError(
                f"Requested frame {frame_idx} exceeds available frames ({num_frames}) in {nc_path}"
            )
        sim_time_sec = float(ds.variables['time'][frame_idx])
        raw_h = ds.variables['h'][frame_idx, :, :]
        if hasattr(raw_h, 'filled'):
            h_arr = raw_h.filled(0.0).astype(np.float32)
        else:
            h_arr = np.nan_to_num(raw_h, nan=0.0).astype(np.float32)

        # Check y coordinate orientation
        y_coords = ds.variables['y'][:]
        if y_coords[0] < y_coords[-1]:
            # Ascending coordinate: y[0] is South, y[-1] is North -> flip vertically
            h_aligned = np.flipud(h_arr)
        else:
            h_aligned = h_arr

        # Also retrieve terrain elevation zb if present for sanity verification
        zb_aligned = None
        if 'zb' in ds.variables:
            raw_zb = ds.variables['zb'][0, :, :]
            if hasattr(raw_zb, 'filled'):
                zb_arr = raw_zb.filled(np.nan).astype(np.float32)
            else:
                zb_arr = np.array(raw_zb, dtype=np.float32)
            if y_coords[0] < y_coords[-1]:
                zb_aligned = np.flipud(zb_arr)
            else:
                zb_aligned = zb_arr

    return h_aligned, zb_aligned, sim_time_sec


def load_and_align_gis_layers(sar_path, water_path, hand_path, target_shape=(2100, 2100)):
    """
    Loads and reprojects SAR, water density, and HAND layers to the standard 2100x2100 domain.
    Domain bounds: x = [270000.0, 333000.0], y = [1415000.0, 1478000.0], EPSG:32649.
    """
    ny, nx = target_shape
    dst_tf = from_bounds(270000.0, 1415000.0, 333000.0, 1478000.0, nx, ny)

    # 1. SAR
    with rasterio.open(sar_path) as src:
        sar_raw = src.read(1)
        sar_tf = src.transform
        sar_crs = src.crs

    if sar_raw.shape == (ny, nx):
        sar_aligned = sar_raw.astype(np.uint8)
    else:
        sar_aligned = np.full((ny, nx), 255, dtype=np.uint8)
        reproject(
            source=sar_raw,
            destination=sar_aligned,
            src_transform=sar_tf,
            src_crs=sar_crs,
            dst_transform=dst_tf,
            dst_crs='EPSG:32649',
            resampling=Resampling.nearest
        )

    # 2. Water Density
    with rasterio.open(water_path) as src:
        water_raw = src.read(1)
        water_tf = src.transform
        water_crs = src.crs

    water_aligned = np.full((ny, nx), 0.0, dtype=np.float32)
    reproject(
        source=water_raw.astype(np.float32),
        destination=water_aligned,
        src_transform=water_tf,
        src_crs=water_crs,
        dst_transform=dst_tf,
        dst_crs='EPSG:32649',
        resampling=Resampling.nearest
    )

    # 3. HAND
    with rasterio.open(hand_path) as src:
        hand_raw = src.read(1)
        hand_tf = src.transform
        hand_crs = src.crs

    hand_aligned = np.full((ny, nx), -9999.0, dtype=np.float32)
    reproject(
        source=hand_raw.astype(np.float32),
        destination=hand_aligned,
        src_transform=hand_tf,
        src_crs=hand_crs,
        dst_transform=dst_tf,
        dst_crs='EPSG:32649',
        src_nodata=-9999.0,
        dst_nodata=-9999.0,
        resampling=Resampling.nearest
    )

    return sar_aligned, water_aligned, hand_aligned


def run_differential_analysis(
    nc_base=DEFAULT_NC_BASE,
    nc_cond=DEFAULT_NC_COND,
    sar_path=DEFAULT_SAR,
    water_path=DEFAULT_WATER,
    hand_path=DEFAULT_HAND,
    applied_cells_csv=DEFAULT_CELLS_CSV,
    metrics_base_json=DEFAULT_METRICS_BASE,
    metrics_cond_json=DEFAULT_METRICS_COND,
    frame_idx=33,
    depth_thresh=0.3,
    hand_thresh=3.5,
    water_thresh=0.5,
    out_dir=DEFAULT_OUT_DIR
):
    """
    Executes complete differential analysis between CONDITIONED and BASE arms.
    """
    nc_base = Path(nc_base)
    nc_cond = Path(nc_cond)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print("V48 FORMAL DIFFERENTIAL HYDRODYNAMIC EVALUATION: CONDITIONED vs BASE")
    print("================================================================================")
    print(f"Base NetCDF:        {nc_base}")
    print(f"Conditioned NetCDF: {nc_cond}")
    print(f"Evaluation Frame:   {frame_idx}")
    print(f"Depth Threshold:    {depth_thresh} m")
    print(f"Output Directory:   {out_dir}")

    # 1. Load water depths
    h_base, zb_base, t_base_s = load_netcdf_frame(nc_base, frame_idx)
    h_cond, zb_cond, t_cond_s = load_netcdf_frame(nc_cond, frame_idx)

    ny, nx = h_base.shape
    t_hours = t_base_s / 3600.0
    print(f"Loaded simulated depth grids: {ny}x{nx} (t = {t_base_s:.1f} s / {t_hours:.2f} h)")

    # 2. Compute differential depth Delta h
    delta_h = h_cond - h_base

    # 3. Load and align GIS layers
    sar_aligned, water_aligned, hand_aligned = load_and_align_gis_layers(
        sar_path, water_path, hand_path, target_shape=(ny, nx)
    )

    # Common Evaluation Mask from preregistration:
    # 1. Lineage-verified SAR in {0, 1}
    # 2. Permanent water density <= 0.5
    # 3. HAND >= 0.0 m
    valid_obs = np.isin(sar_aligned, [0, 1])
    not_perm_water = (water_aligned <= water_thresh)
    valid_hand = (hand_aligned >= 0.0)
    eval_mask = valid_obs & not_perm_water & valid_hand

    # 4. Statistical Flow Transfer at the 66 Lowered Levee Cells
    df_cells = pd.read_csv(applied_cells_csv)
    c_rows = df_cells['row'].values
    c_cols = df_cells['col'].values
    num_levee_cells = len(df_cells)

    h_base_cells = h_base[c_rows, c_cols]
    h_cond_cells = h_cond[c_rows, c_cols]
    dh_cells = delta_h[c_rows, c_cols]

    levee_cell_stats = {
        "applied_cells_count": int(num_levee_cells),
        "cumulative_dem_cut_sum_m": float(df_cells['cumulative_cut_m'].sum()),
        "cumulative_dem_cut_max_m": float(df_cells['cumulative_cut_m'].max()),
        "total_excavated_volume_m3": float(df_cells['cumulative_cut_m'].sum() * 900.0),
        "base_cells_wet_gt_0p001m": int(np.sum(h_base_cells > 0.001)),
        "base_cells_wet_gt_0p10m": int(np.sum(h_base_cells > 0.10)),
        "base_cells_wet_gt_0p30m": int(np.sum(h_base_cells > 0.30)),
        "base_cells_wet_gt_0p50m": int(np.sum(h_base_cells > 0.50)),
        "base_cells_wet_gt_1p00m": int(np.sum(h_base_cells > 1.00)),
        "base_mean_depth_m": float(np.mean(h_base_cells)),
        "base_max_depth_m": float(np.max(h_base_cells)),
        "base_min_depth_m": float(np.min(h_base_cells)),
        "cond_cells_wet_gt_0p001m": int(np.sum(h_cond_cells > 0.001)),
        "cond_cells_wet_gt_0p10m": int(np.sum(h_cond_cells > 0.10)),
        "cond_cells_wet_gt_0p30m": int(np.sum(h_cond_cells > 0.30)),
        "cond_cells_wet_gt_0p50m": int(np.sum(h_cond_cells > 0.50)),
        "cond_cells_wet_gt_1p00m": int(np.sum(h_cond_cells > 1.00)),
        "cond_mean_depth_m": float(np.mean(h_cond_cells)),
        "cond_max_depth_m": float(np.max(h_cond_cells)),
        "cond_min_depth_m": float(np.min(h_cond_cells)),
        "delta_h_mean_m": float(np.mean(dh_cells)),
        "delta_h_max_m": float(np.max(dh_cells)),
        "delta_h_min_m": float(np.min(dh_cells)),
        "delta_volume_levee_cells_m3": float(np.sum(dh_cells) * 900.0)
    }

    # 5. Spatial Flow Transfer across Tuy Hoa Floodplain and Domain
    # Tuy Hoa Corridor Bounding Box: X in [295.5, 322.5] km, Y in [1437.5, 1458.5] km
    # Row range: [650, 1350], Col range: [850, 1750]
    box_row_min, box_row_max = 650, 1350
    box_col_min, box_col_max = 850, 1750
    tuyhoa_box_mask = np.zeros((ny, nx), dtype=bool)
    tuyhoa_box_mask[box_row_min:box_row_max, box_col_min:box_col_max] = True

    # Tuy Hoa geomorphological floodplain: Corridor box & not perm water & HAND <= 3.5m & HAND >= 0.0m
    tuyhoa_floodplain_mask = tuyhoa_box_mask & not_perm_water & (hand_aligned >= 0.0) & (hand_aligned <= hand_thresh)

    # Broad geomorphological floodplain full domain: HAND in [0.0, 3.5] & not perm water
    domain_floodplain_mask = not_perm_water & (hand_aligned >= 0.0) & (hand_aligned <= hand_thresh)

    def compute_region_transfer(mask, region_name):
        dh_reg = delta_h[mask]
        pos_dh = dh_reg[dh_reg > 0.001]
        neg_dh = dh_reg[dh_reg < -0.001]
        return {
            "region_name": region_name,
            "total_cells": int(np.sum(mask)),
            "area_km2": float(np.sum(mask) * 0.0009),
            "cells_deepened_gt_1mm": int(len(pos_dh)),
            "cells_shallowed_lt_neg_1mm": int(len(neg_dh)),
            "net_volume_change_m3": float(np.sum(dh_reg) * 900.0),
            "positive_volume_gain_m3": float(np.sum(pos_dh) * 900.0) if len(pos_dh) > 0 else 0.0,
            "negative_volume_loss_m3": float(np.sum(neg_dh) * 900.0) if len(neg_dh) > 0 else 0.0,
            "mean_delta_h_m": float(np.mean(dh_reg)) if len(dh_reg) > 0 else 0.0,
            "max_delta_h_m": float(np.max(dh_reg)) if len(dh_reg) > 0 else 0.0,
            "min_delta_h_m": float(np.min(dh_reg)) if len(dh_reg) > 0 else 0.0
        }

    tuyhoa_fp_stats = compute_region_transfer(tuyhoa_floodplain_mask, "Tuy Hoa Corridor Floodplain (HAND <= 3.5m)")
    tuyhoa_box_stats = compute_region_transfer(tuyhoa_box_mask & not_perm_water, "Tuy Hoa Corridor Bounding Box")
    domain_fp_stats = compute_region_transfer(domain_floodplain_mask, "Full Domain Floodplain (HAND <= 3.5m)")
    eval_domain_stats = compute_region_transfer(eval_mask, "Common Evaluation Mask Domain")

    # Wet area thresholds (h > depth_thresh)
    base_wet = (h_base > depth_thresh) & eval_mask
    cond_wet = (h_cond > depth_thresh) & eval_mask
    newly_flooded = cond_wet & (~base_wet)
    drained_cells = (~cond_wet) & base_wet

    eval_domain_stats["newly_flooded_cells_gt_thresh"] = int(np.sum(newly_flooded))
    eval_domain_stats["newly_flooded_area_km2"] = float(np.sum(newly_flooded) * 0.0009)
    eval_domain_stats["drained_cells_gt_thresh"] = int(np.sum(drained_cells))
    eval_domain_stats["drained_area_km2"] = float(np.sum(drained_cells) * 0.0009)

    flow_transfer_summary = {
        "tuyhoa_floodplain_hand_le_3p5m": tuyhoa_fp_stats,
        "tuyhoa_corridor_box": tuyhoa_box_stats,
        "domain_floodplain_hand_le_3p5m": domain_fp_stats,
        "evaluation_domain": eval_domain_stats
    }

    # 6. Direct and Preregistered Contingency Metrics Comparison
    obs_wet = (sar_aligned == 1) & eval_mask
    tp_b = int(np.sum(base_wet & obs_wet))
    fp_b = int(np.sum(base_wet & (~obs_wet)))
    fn_b = int(np.sum((~base_wet) & obs_wet))
    tn_b = int(np.sum((~base_wet) & (~obs_wet) & eval_mask))
    total_eval = tp_b + fp_b + fn_b + tn_b

    prec_b = tp_b / (tp_b + fp_b) if (tp_b + fp_b) > 0 else 0.0
    rec_b = tp_b / (tp_b + fn_b) if (tp_b + fn_b) > 0 else 0.0
    csi_b = tp_b / (tp_b + fp_b + fn_b) if (tp_b + fp_b + fn_b) > 0 else 0.0
    f1_b = 2.0 * prec_b * rec_b / (prec_b + rec_b) if (prec_b + rec_b) > 0 else 0.0
    sim_area_b = (tp_b + fp_b) * 0.0009
    obs_area = (tp_b + fn_b) * 0.0009

    tp_c = int(np.sum(cond_wet & obs_wet))
    fp_c = int(np.sum(cond_wet & (~obs_wet)))
    fn_c = int(np.sum((~cond_wet) & obs_wet))
    tn_c = int(np.sum((~cond_wet) & (~obs_wet) & eval_mask))

    prec_c = tp_c / (tp_c + fp_c) if (tp_c + fp_c) > 0 else 0.0
    rec_c = tp_c / (tp_c + fn_c) if (tp_c + fn_c) > 0 else 0.0
    csi_c = tp_c / (tp_c + fp_c + fn_c) if (tp_c + fp_c + fn_c) > 0 else 0.0
    f1_c = 2.0 * prec_c * rec_c / (prec_c + rec_c) if (prec_c + rec_c) > 0 else 0.0
    sim_area_c = (tp_c + fp_c) * 0.0009

    metrics_comparison = {
        "base_metrics": {
            "contingency": {"TP": tp_b, "FP": fp_b, "FN": fn_b, "TN": tn_b, "total": total_eval},
            "precision": prec_b,
            "recall": rec_b,
            "csi_iou": csi_b,
            "f1": f1_b,
            "simulated_area_km2": sim_area_b,
            "observed_area_km2": obs_area,
            "area_bias": (sim_area_b - obs_area) / obs_area if obs_area > 0 else 0.0
        },
        "conditioned_metrics": {
            "contingency": {"TP": tp_c, "FP": fp_c, "FN": fn_c, "TN": tn_c, "total": total_eval},
            "precision": prec_c,
            "recall": rec_c,
            "csi_iou": csi_c,
            "f1": f1_c,
            "simulated_area_km2": sim_area_c,
            "observed_area_km2": obs_area,
            "area_bias": (sim_area_c - obs_area) / obs_area if obs_area > 0 else 0.0
        },
        "delta_metrics": {
            "delta_TP": tp_c - tp_b,
            "delta_FP": fp_c - fp_b,
            "delta_FN": fn_c - fn_b,
            "delta_TN": tn_c - tn_b,
            "delta_csi": csi_c - csi_b,
            "delta_recall": rec_c - rec_b,
            "delta_precision": prec_c - prec_b,
            "delta_f1": f1_c - f1_b,
            "delta_simulated_area_km2": sim_area_c - sim_area_b
        }
    }

    # Cross-reference with external JSON files if available
    metrics_base_json = Path(metrics_base_json)
    metrics_cond_json = Path(metrics_cond_json)
    if metrics_base_json.is_file():
        try:
            with open(metrics_base_json, "r", encoding="utf-8") as f:
                metrics_comparison["external_base_json"] = json.load(f)
        except Exception as e:
            metrics_comparison["external_base_json_error"] = str(e)

    if metrics_cond_json.is_file():
        try:
            with open(metrics_cond_json, "r", encoding="utf-8") as f:
                metrics_comparison["external_cond_json"] = json.load(f)
        except Exception as e:
            metrics_comparison["external_cond_json_error"] = str(e)

    # 7. Assemble Complete Differential Report
    report_dict = {
        "report_type": "V48_DIFFERENTIAL_CONDITIONED_VS_BASE",
        "evaluation_contract": "V48_SAR_preregistration_R1.json",
        "evaluated_frame": frame_idx,
        "sim_time_sec": t_base_s,
        "sim_time_hours": t_hours,
        "netcdf_base": str(nc_base),
        "netcdf_conditioned": str(nc_cond),
        "wet_depth_threshold_m": depth_thresh,
        "water_density_threshold": water_thresh,
        "hand_floodplain_threshold_m": hand_thresh,
        "levee_66_cells_statistics": levee_cell_stats,
        "flow_transfer_statistics": flow_transfer_summary,
        "comparative_contingency_metrics": metrics_comparison
    }

    out_json_path = out_dir / f"V48_DIFF_CONDITIONED_vs_BASE_frame_{frame_idx}.json"
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)
    print(f"[OK] Wrote differential metrics JSON: {out_json_path}")

    # 8. Render 300 DPI 2-Panel Differential Depth Map
    out_png_path = out_dir / f"V48_DIFF_depth_map_frame_{frame_idx}.png"
    render_differential_map(
        delta_h=delta_h,
        water_aligned=water_aligned,
        water_thresh=water_thresh,
        c_cols=c_cols,
        c_rows=c_rows,
        frame_idx=frame_idx,
        t_hours=t_hours,
        out_png=out_png_path
    )
    print(f"[OK] Rendered 300 DPI 2-panel map: {out_png_path}")

    return report_dict, out_json_path, out_png_path


def render_differential_map(delta_h, water_aligned, water_thresh, c_cols, c_rows, frame_idx, t_hours, out_png):
    """
    Renders 300 DPI publication-grade 2-panel differential map:
      Panel 1: Full domain Delta h with diverging colormap and 66 levee breach locations.
      Panel 2: Zoom on Tuy Hoa plain corridor / Ba River estuary.
    """
    fig = plt.figure(figsize=(19, 9.5), dpi=300)

    # Mask out permanent water
    dh_display = np.copy(delta_h)
    dh_display[water_aligned > water_thresh] = np.nan

    vmax = 1.0
    vmin = -1.0
    norm = TwoSlopeNorm(vcenter=0.0, vmin=vmin, vmax=vmax)
    # coolwarm_r: Blue for positive (water deepened), Red for negative (water receded)
    cmap = plt.colormaps['coolwarm_r']

    # --- Subplot 1: Full Domain ---
    ax1 = fig.add_subplot(1, 2, 1)
    im1 = ax1.imshow(
        dh_display,
        cmap=cmap,
        norm=norm,
        extent=[270000.0, 333000.0, 1415000.0, 1478000.0]
    )
    # Scatter 66 levee cells in UTM coords
    x_cells_all = 270000.0 + (c_cols + 0.5) * 30.0
    y_cells_all = 1478000.0 - (c_rows + 0.5) * 30.0
    ax1.scatter(
        x_cells_all,
        y_cells_all,
        color='gold',
        s=16,
        edgecolors='black',
        linewidth=0.6,
        label=f'66 Lowered Levee Cells (N={len(c_rows)})',
        zorder=5
    )

    # Tuy Hoa corridor bounding box outline: [295.5..322.5 km, 1437.5..1458.5 km]
    rect = plt.Rectangle(
        (295500.0, 1437500.0),
        27000.0,
        21000.0,
        linewidth=1.8,
        edgecolor='#9B59B6',
        facecolor='none',
        linestyle='--',
        label='Tuy Hoa Corridor Zoom Box',
        zorder=4
    )
    ax1.add_patch(rect)

    ax1.set_title(
        f"Panel 1: Full Domain Flood Depth Differential $\\Delta h$\n"
        f"$\\Delta h = h_{{COND}} - h_{{BASE}}$ at Frame {frame_idx} ($t = {t_hours:.1f}\\text{{ h}}$ / $367,200\\text{{ s}}$)",
        fontsize=11, fontweight='bold', pad=8
    )
    ax1.set_xlabel('UTM Easting X (m)', fontsize=9)
    ax1.set_ylabel('UTM Northing Y (m)', fontsize=9)
    ax1.legend(loc='lower left', fontsize=8, framealpha=0.92)
    cbar1 = plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.03)
    cbar1.set_label('Depth Change $\\Delta h$ (m)\n[Blue = Deepened (+) | Red = Receded (-)]', fontsize=9, fontweight='bold')

    # --- Subplot 2: Zoom on Tuy Hoa Corridor ---
    ax2 = fig.add_subplot(1, 2, 2)
    dh_zoom = dh_display[650:1350, 850:1750]
    im2 = ax2.imshow(
        dh_zoom,
        cmap=cmap,
        norm=norm,
        extent=[295500.0, 322500.0, 1437500.0, 1458500.0]
    )

    zoom_mask = (c_rows >= 650) & (c_rows < 1350) & (c_cols >= 850) & (c_cols < 1750)
    x_cells_zoom = 270000.0 + (c_cols[zoom_mask] + 0.5) * 30.0
    y_cells_zoom = 1478000.0 - (c_rows[zoom_mask] + 0.5) * 30.0
    ax2.scatter(
        x_cells_zoom,
        y_cells_zoom,
        color='gold',
        s=32,
        edgecolors='black',
        linewidth=0.8,
        label=f'Lowered Levees in Corridor (N={int(np.sum(zoom_mask))})',
        zorder=5
    )

    ax2.set_title(
        f"Panel 2: Tuy Hoa Corridor & Lower Ba River Estuary Zoom\n"
        f"Detail of Hydraulic Conveyance Across Lowered Levee Segments",
        fontsize=11, fontweight='bold', pad=8
    )
    ax2.set_xlabel('UTM Easting X (m)', fontsize=9)
    ax2.set_ylabel('UTM Northing Y (m)', fontsize=9)
    ax2.legend(loc='lower left', fontsize=8, framealpha=0.92)
    cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.03)
    cbar2.set_label('Depth Change $\\Delta h$ (m)\n[Blue = Deepened (+) | Red = Receded (-)]', fontsize=9, fontweight='bold')

    plt.suptitle(
        "V48 R1 FORMAL DIFFERENTIAL HYDRODYNAMIC ANALYSIS: CONDITIONED vs BASE\n"
        "Quantitative Verification of Levee Breaching on Flood Volume Transfer to Tuy Hoa Plain",
        fontsize=13, fontweight='bold', y=0.98
    )
    plt.tight_layout()
    plt.savefig(out_png, dpi=300, bbox_inches='tight')
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="V48 Differential Analysis CONDITIONED vs BASE (R3)")
    parser.add_argument("--nc-base", default=str(DEFAULT_NC_BASE), help="Path to BASE NetCDF output")
    parser.add_argument("--nc-cond", default=str(DEFAULT_NC_COND), help="Path to CONDITIONED NetCDF output")
    parser.add_argument("--sar", default=str(DEFAULT_SAR), help="Path to Sentinel-1 SAR Otsu GeoTIFF")
    parser.add_argument("--water", default=str(DEFAULT_WATER), help="Path to Permanent Water Density GeoTIFF")
    parser.add_argument("--hand", default=str(DEFAULT_HAND), help="Path to HAND GeoTIFF")
    parser.add_argument("--cells-csv", default=str(DEFAULT_CELLS_CSV), help="Path to 66 applied cells CSV")
    parser.add_argument("--metrics-base", default=str(DEFAULT_METRICS_BASE), help="Path to BASE metrics JSON")
    parser.add_argument("--metrics-cond", default=str(DEFAULT_METRICS_COND), help="Path to CONDITIONED metrics JSON")
    parser.add_argument("--frame", type=int, default=33, help="Target evaluation frame (default: 33)")
    parser.add_argument("--depth-thresh", type=float, default=0.3, help="Flood wet depth threshold in meters")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory for reports and figures")
    args = parser.parse_args()

    run_differential_analysis(
        nc_base=args.nc_base,
        nc_cond=args.nc_cond,
        sar_path=args.sar,
        water_path=args.water,
        hand_path=args.hand,
        applied_cells_csv=args.cells_csv,
        metrics_base_json=args.metrics_base,
        metrics_cond_json=args.metrics_cond,
        frame_idx=args.frame,
        depth_thresh=args.depth_thresh,
        out_dir=args.out_dir
    )


if __name__ == "__main__":
    main()
