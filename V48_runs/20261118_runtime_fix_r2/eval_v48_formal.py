import os
import sys
import json
import argparse
import numpy as np
import netCDF4 as nc
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def evaluate_v48(
    nc_path=r"D:\VTP\V48_runs\20261004_runtime_fix_r1\results\V48_FORMAL_BASE_R1.nc",
    sar_path=r"D:\VTP\05-Du-lieu-GIS\DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif",
    water_path=r"D:\VTP\05-Du-lieu-GIS\water_density_30m.tif",
    hand_path=r"D:\VTP\BG_Flood_Project\BG_Flood\Teamwork_Validation\PhuYen_HAND_30m.tif",
    frame_idx=33,
    depth_thresh=0.3,
    hand_thresh=3.5,
    water_thresh=0.5,
    out_dir=r"D:\VTP\V48_runs\20261004_runtime_fix_r1\results",
    arm_name="BASE"
):
    print(f"=== V48 Formal Evaluation Pipeline ===")
    print(f"Arm: {arm_name}")
    print(f"NetCDF: {nc_path}")
    print(f"Target frame: {frame_idx}")
    print(f"Depth threshold: {depth_thresh} m")
    
    if not os.path.exists(nc_path):
        raise FileNotFoundError(f"NetCDF not found: {nc_path}")
    
    ds = nc.Dataset(nc_path, 'r')
    num_frames = len(ds.variables['time'])
    print(f"Total frames available: {num_frames}")
    if frame_idx >= num_frames:
        print(f"Warning: frame {frame_idx} not yet reached. Evaluating latest available frame {num_frames-1} instead.")
        actual_frame = num_frames - 1
    else:
        actual_frame = frame_idx

    t_s = float(ds.variables['time'][actual_frame])
    t_h = t_s / 3600.0
    print(f"Evaluating Frame {actual_frame} (t = {t_s:.1f} s / {t_h:.2f} h)")

    # Read simulated water depth h (shape: ny, nx)
    h_sim = ds.variables['h'][actual_frame, :, :].filled(0.0)
    # Check if upside down
    # In BG_Flood NetCDF, coordinate y is often descending or ascending.
    # Let's verify shape:
    ny, nx = h_sim.shape
    print(f"Simulated h grid shape: {h_sim.shape}")
    ds.close()

    # 1. Read SAR
    with rasterio.open(sar_path) as src:
        sar_data = src.read(1)
        sar_meta = src.meta
        sar_tf = src.transform
        sar_crs = src.crs

    print(f"SAR grid shape: {sar_data.shape}, CRS: {sar_crs}")

    # Align SAR to 2100x2100 if needed (it is already 2100x2100)
    if sar_data.shape != (ny, nx):
        print(f"Resampling SAR from {sar_data.shape} to ({ny}, {nx})...")
        sar_aligned = np.full((ny, nx), 255, dtype=np.uint8)
        dst_tf = from_bounds(270000.0, 1415000.0, 333000.0, 1478000.0, nx, ny)
        reproject(
            source=sar_data,
            destination=sar_aligned,
            src_transform=sar_tf,
            src_crs=sar_crs,
            dst_transform=dst_tf,
            dst_crs='EPSG:32649',
            resampling=Resampling.nearest
        )
    else:
        sar_aligned = sar_data

    # 2. Read Permanent Water Mask
    with rasterio.open(water_path) as src:
        water_raw = src.read(1)
        water_tf = src.transform
        water_crs = src.crs

    water_aligned = np.full((ny, nx), 0.0, dtype=np.float32)
    dst_tf = from_bounds(270000.0, 1415000.0, 333000.0, 1478000.0, nx, ny)
    reproject(
        source=water_raw.astype(np.float32),
        destination=water_aligned,
        src_transform=water_tf,
        src_crs=water_crs,
        dst_transform=dst_tf,
        dst_crs='EPSG:32649',
        resampling=Resampling.nearest
    )

    # 3. Read HAND
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

    # Orientation check: In BG_Flood, NetCDF y[0] is typically row 0.
    # Let's ensure top-down orientation matches rasterio (north up).
    # In GIS EPSG:32649, row 0 is y_max (1478000), row 2099 is y_min (1415000).
    # In BG_Flood NetCDF, y usually starts at y_min and goes to y_max. If so, we need to flipud h_sim.
    with nc.Dataset(nc_path, 'r') as ds_check:
        y_coords = ds_check.variables['y'][:]
        if y_coords[0] < y_coords[-1]:
            print("NetCDF y is ascending (y[0] is south, y[-1] is north). Flipping vertically to match raster north-up...")
            h_sim = np.flipud(h_sim)
        else:
            print("NetCDF y is descending (already north-up).")

    # Evaluation Mask:
    # lineage-verified observation pixels with class in {0,1}
    # water_density <= 0.5
    # HAND >= 0.0
    valid_obs = np.isin(sar_aligned, [0, 1])
    not_perm_water = (water_aligned <= water_thresh)
    valid_hand = (hand_aligned >= 0.0)

    eval_mask = valid_obs & not_perm_water & valid_hand

    obs_wet = (sar_aligned == 1) & eval_mask
    sim_wet = (h_sim > depth_thresh) & eval_mask

    tp = np.logical_and(sim_wet, obs_wet)
    fp = np.logical_and(sim_wet, ~obs_wet)
    fn = np.logical_and(~sim_wet, obs_wet)
    tn = np.logical_and(~sim_wet, ~obs_wet) & eval_mask

    n_tp = int(np.sum(tp))
    n_fp = int(np.sum(fp))
    n_fn = int(np.sum(fn))
    n_tn = int(np.sum(tn))
    n_total = n_tp + n_fp + n_fn + n_tn

    precision = n_tp / (n_tp + n_fp) if (n_tp + n_fp) > 0 else 0.0
    recall = n_tp / (n_tp + n_fn) if (n_tp + n_fn) > 0 else 0.0
    csi = n_tp / (n_tp + n_fp + n_fn) if (n_tp + n_fp + n_fn) > 0 else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    cell_area_km2 = 0.0009
    obs_area_km2 = (n_tp + n_fn) * cell_area_km2
    sim_area_km2 = (n_tp + n_fp) * cell_area_km2
    area_bias = (sim_area_km2 - obs_area_km2) / obs_area_km2 if obs_area_km2 > 0 else 0.0

    # HAND check: percentage of simulated flood in HAND <= hand_thresh
    sim_wet_total = (h_sim > depth_thresh) & not_perm_water
    sim_wet_valid_hand = sim_wet_total & (hand_aligned >= 0.0)
    sim_wet_in_floodplain = sim_wet_total & (hand_aligned >= 0.0) & (hand_aligned <= hand_thresh)
    hand_ratio = np.sum(sim_wet_in_floodplain) / np.sum(sim_wet_valid_hand) if np.sum(sim_wet_valid_hand) > 0 else 0.0

    metrics = {
        "arm": arm_name,
        "evaluated_frame": actual_frame,
        "sim_time_sec": t_s,
        "sim_time_hours": t_h,
        "contingency": {
            "TP": n_tp,
            "FP": n_fp,
            "FN": n_fn,
            "TN": n_tn,
            "total_evaluated_cells": n_total
        },
        "precision": precision,
        "recall": recall,
        "csi_iou": csi,
        "f1": f1,
        "observed_area_km2": obs_area_km2,
        "simulated_area_km2": sim_area_km2,
        "area_bias": area_bias,
        "hand_floodplain_ratio_le_3_5m": hand_ratio,
        "depth_threshold_m": depth_thresh,
        "water_density_threshold": water_thresh,
        "hand_floodplain_threshold_m": hand_thresh,
        "preregistration": "V48_SAR_preregistration_R1.json"
    }

    print("\n--- Evaluation Results ---")
    print(f"CSI (IoU): {csi*100:.2f}%")
    print(f"Recall: {recall*100:.2f}%")
    print(f"Precision: {precision*100:.2f}%")
    print(f"F1 Score: {f1*100:.2f}%")
    print(f"Observed Flood: {obs_area_km2:.2f} km² ({n_tp + n_fn} cells)")
    print(f"Simulated Flood: {sim_area_km2:.2f} km² ({n_tp + n_fp} cells)")
    print(f"Area Bias: {area_bias*100:+.2f}%")
    print(f"HAND <= {hand_thresh}m Consistency: {hand_ratio*100:.2f}%")

    # Save JSON
    out_json = os.path.join(out_dir, f"SAR_vs_V48_{arm_name}_frame_{actual_frame}_metrics.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved metrics JSON: {out_json}")

    # Generate 4-color contingency map
    out_png = os.path.join(out_dir, f"SAR_vs_V48_{arm_name}_frame_{actual_frame}_contingency.png")
    fig, ax = plt.subplots(figsize=(12, 12), dpi=300)
    
    # Base background: Light Gray
    rgb = np.full((ny, nx, 3), 245, dtype=np.uint8)
    rgb[eval_mask] = [235, 238, 240]               # Evaluated Domain (TN)
    rgb[water_aligned > water_thresh] = [52, 73, 94] # Permanent Water (Dark Navy)
    
    # Contingency colors
    rgb[fn] = [52, 152, 219]   # Blue: False Negative (SAR flood, Sim dry)
    rgb[fp] = [231, 76, 60]    # Red: False Positive (Sim flood, SAR dry)
    rgb[tp] = [46, 204, 113]   # Green: True Positive (Both agree flood)

    ax.imshow(rgb)
    ax.axis('off')
    
    title_text = (
        f"V48 {arm_name} vs Sentinel-1 SAR Contingency Map — Frame {actual_frame} (t = {t_h:.1f}h)\n"
        f"CSI = {csi*100:.2f}% | Precision = {precision*100:.2f}% | Recall = {recall*100:.2f}% | HAND <= 3.5m = {hand_ratio*100:.2f}%\n"
        f"Observed: {obs_area_km2:.1f} km² | Simulated: {sim_area_km2:.1f} km² (Depth > {depth_thresh}m)"
    )
    ax.set_title(title_text, fontsize=11, fontweight='bold', pad=12)

    patches = [
        mpatches.Patch(color='#2ECC71', label=f'True Positive ({n_tp:,} cells / {n_tp*cell_area_km2:.1f} km²)'),
        mpatches.Patch(color='#3498DB', label=f'False Negative ({n_fn:,} cells / {n_fn*cell_area_km2:.1f} km²)'),
        mpatches.Patch(color='#E74C3C', label=f'False Positive ({n_fp:,} cells / {n_fp*cell_area_km2:.1f} km²)'),
        mpatches.Patch(color='#34495E', label='Permanent Water Excluded'),
        mpatches.Patch(color='#EBEEF0', label=f'True Negative ({n_tn:,} cells)'),
    ]
    ax.legend(handles=patches, loc='lower right', framealpha=0.92, fontsize=9)

    plt.tight_layout()
    plt.savefig(out_png, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved Contingency PNG: {out_png}")

    return metrics, out_json, out_png

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nc", default=r"D:\VTP\V48_runs\20261004_runtime_fix_r1\results\V48_FORMAL_BASE_R1.nc")
    parser.add_argument("--frame", type=int, default=33)
    parser.add_argument("--arm", default="BASE")
    args = parser.parse_args()
    evaluate_v48(nc_path=args.nc, frame_idx=args.frame, arm_name=args.arm)
