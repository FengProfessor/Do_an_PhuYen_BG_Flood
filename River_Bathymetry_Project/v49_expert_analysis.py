# -*- coding: utf-8 -*-
"""Quantitative extraction script for multi-expert comparative analysis:
V49 Method 1 (Scope B1 CENTRAL) vs V48 BASE vs Sentinel-1 SAR.
"""

import json
import numpy as np
import netCDF4 as nc
import rasterio
from rasterio.warp import reproject, Resampling
from pathlib import Path

ROOT = Path("D:/VTP")
RUN_DIR = ROOT / "River_Bathymetry_Project" / "V49_Method1_Runs"
BASE_NC = ROOT / "V48_runs" / "20261004_runtime_fix_r1" / "results" / "V48_FORMAL_BASE_R1.nc"
V49_NC = RUN_DIR / "results" / "V49_Method1_ScopeB1_CENTRAL.nc"
BASE_DEM = ROOT / "05-Du-lieu-GIS" / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
SAR_TIF = ROOT / "05-Du-lieu-GIS" / "DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif"
WATER_TIF = ROOT / "05-Du-lieu-GIS" / "water_density_30m.tif"
HAND_TIF = ROOT / "BG_Flood_Project" / "BG_Flood" / "Teamwork_Validation" / "PhuYen_HAND_30m.tif"
DELTAZ_TIF = ROOT / "River_Bathymetry_Project" / "V49_Method1_DHG_Clamped" / "rasters" / "V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_DeltaZ_CENTRAL.tif"

def aligned(path, shape, transform, crs, dtype, nodata, src_nodata=None):
    data = np.full(shape, nodata, dtype=dtype)
    with rasterio.open(path) as src:
        s_nd = src.nodata if src_nodata is None else src_nodata
        reproject(
            source=rasterio.band(src, 1),
            destination=data,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=s_nd,
            dst_transform=transform,
            dst_crs=crs,
            dst_nodata=nodata,
            resampling=Resampling.nearest,
        )
    return data

def main():
    print("Loading DEM and GIS rasters...", flush=True)
    with rasterio.open(BASE_DEM) as src:
        shape = src.shape
        transform = src.transform
        crs = src.crs
        dem = src.read(1).astype(np.float32)
        dx = float(transform.a)
        dy = float(abs(transform.e))
        pixel_area_km2 = (dx * dy) / 1e6
        x_min = float(transform.c)
        y_max = float(transform.f)

    sar = aligned(SAR_TIF, shape, transform, crs, "uint8", 255)
    water = aligned(WATER_TIF, shape, transform, crs, "float32", -9999.0)
    hand = aligned(HAND_TIF, shape, transform, crs, "float32", -9999.0)
    deltaz = aligned(DELTAZ_TIF, shape, transform, crs, "float32", 0.0, src_nodata=-9999.0)

    eval_mask = np.isin(sar, [0, 1]) & (water <= 0.5) & (hand >= 0.0)
    obs_wet = (sar == 1) & eval_mask

    print("Opening NetCDFs...", flush=True)
    ds_base = nc.Dataset(str(BASE_NC), 'r')
    ds_v49 = nc.Dataset(str(V49_NC), 'r')

    times_s = ds_v49.variables['time'][:]
    times_h = times_s / 3600.0

    # Index 33 is 102.0h (closest to SAR at 101.61h)
    target_time_s = 101.61425 * 3600.0
    idx_sar = int(np.argmin(np.abs(times_s - target_time_s)))
    print(f"SAR match index: {idx_sar} (t = {times_h[idx_sar]:.2f}h)", flush=True)

    # Read variables at SAR frame
    h_base = np.squeeze(np.asarray(ds_base.variables['h'][idx_sar, :, :], dtype=np.float32))
    h_v49 = np.squeeze(np.asarray(ds_v49.variables['h'][idx_sar, :, :], dtype=np.float32))
    u_base = np.squeeze(np.asarray(ds_base.variables['u'][idx_sar, :, :], dtype=np.float32))
    v_base = np.squeeze(np.asarray(ds_base.variables['v'][idx_sar, :, :], dtype=np.float32))
    u_v49 = np.squeeze(np.asarray(ds_v49.variables['u'][idx_sar, :, :], dtype=np.float32))
    v_v49 = np.squeeze(np.asarray(ds_v49.variables['v'][idx_sar, :, :], dtype=np.float32))
    zb_base = np.squeeze(np.asarray(ds_base.variables['zb'][0, :, :], dtype=np.float32))
    zb_v49 = np.squeeze(np.asarray(ds_v49.variables['zb'][0, :, :], dtype=np.float32))

    y_vals = ds_v49.variables['y'][:]
    flip = bool(y_vals[0] < y_vals[-1])
    if flip:
        h_base = np.flipud(h_base)
        h_v49 = np.flipud(h_v49)
        u_base = np.flipud(u_base)
        v_base = np.flipud(v_base)
        u_v49 = np.flipud(u_v49)
        v_v49 = np.flipud(v_v49)
        zb_base = np.flipud(zb_base)
        zb_v49 = np.flipud(zb_v49)

    vel_base = np.sqrt(u_base**2 + v_base**2)
    vel_v49 = np.sqrt(u_v49**2 + v_v49**2)
    zs_base = zb_base + h_base
    zs_v49 = zb_v49 + h_v49

    # Peak flood frame: find max total volume or max inundated area across all frames
    print("Scanning time series for peak flood...", flush=True)
    area_times_base = []
    area_times_v49 = []

    for i in range(len(times_s)):
        hb = np.asarray(ds_base.variables['h'][i, :, :], dtype=np.float32)
        hv = np.asarray(ds_v49.variables['h'][i, :, :], dtype=np.float32)
        area_times_base.append(float((hb > 0.3).sum() * pixel_area_km2))
        area_times_v49.append(float((hv > 0.3).sum() * pixel_area_km2))

    # Look for peak in the range t = 60h to 96h (hydrological peak of the 2021 event)
    # Event peak was around t = 75h - 84h
    idx_peak = int(np.argmax(area_times_v49[:32])) # before t = 96h
    print(f"Hydrological peak flood index: {idx_peak} (t = {times_h[idx_peak]:.2f}h), Inundated Area: V48={area_times_base[idx_peak]:.1f}km2, V49={area_times_v49[idx_peak]:.1f}km2", flush=True)

    # Read variables at peak frame
    h_base_pk = np.squeeze(np.asarray(ds_base.variables['h'][idx_peak, :, :], dtype=np.float32))
    h_v49_pk = np.squeeze(np.asarray(ds_v49.variables['h'][idx_peak, :, :], dtype=np.float32))
    u_base_pk = np.squeeze(np.asarray(ds_base.variables['u'][idx_peak, :, :], dtype=np.float32))
    v_base_pk = np.squeeze(np.asarray(ds_base.variables['v'][idx_peak, :, :], dtype=np.float32))
    u_v49_pk = np.squeeze(np.asarray(ds_v49.variables['u'][idx_peak, :, :], dtype=np.float32))
    v_v49_pk = np.squeeze(np.asarray(ds_v49.variables['v'][idx_peak, :, :], dtype=np.float32))
    if flip:
        h_base_pk = np.flipud(h_base_pk)
        h_v49_pk = np.flipud(h_v49_pk)
        u_base_pk = np.flipud(u_base_pk)
        v_base_pk = np.flipud(v_base_pk)
        u_v49_pk = np.flipud(u_v49_pk)
        v_v49_pk = np.flipud(v_v49_pk)

    vel_base_pk = np.sqrt(u_base_pk**2 + v_base_pk**2)
    vel_v49_pk = np.sqrt(u_v49_pk**2 + v_v49_pk**2)
    zs_base_pk = zb_base + h_base_pk
    zs_v49_pk = zb_v49 + h_v49_pk

    # -------------------------------------------------------------
    # 1. HYDRAULIC & RIVER DYNAMICS ANALYSIS
    # -------------------------------------------------------------
    # Channel cells from DeltaZ raster (W >= 60m 41 reaches + 66 cuts)
    channel_mask = (deltaz > 0.01)
    n_mod = int(channel_mask.sum())
    mod_vol_m3 = float(deltaz[channel_mask].sum() * dx * dy)
    print(f"Dredged Channel Mask: {n_mod} cells ({n_mod*pixel_area_km2:.2f} km2), volume = {mod_vol_m3/1e6:.2f}M m3", flush=True)

    # In-channel metrics at t = 102h
    ch_h_base_mean = float(np.nanmean(h_base[channel_mask]))
    ch_h_v49_mean = float(np.nanmean(h_v49[channel_mask]))
    ch_vel_base_mean = float(np.nanmean(vel_base[channel_mask]))
    ch_vel_v49_mean = float(np.nanmean(vel_v49[channel_mask]))
    ch_vel_base_max = float(np.nanmax(vel_base[channel_mask]))
    ch_vel_v49_max = float(np.nanmax(vel_v49[channel_mask]))
    ch_zs_base_mean = float(np.nanmean(zs_base[channel_mask]))
    ch_zs_v49_mean = float(np.nanmean(zs_v49[channel_mask]))

    # In-channel metrics at Peak
    ch_pk_vel_base_mean = float(np.nanmean(vel_base_pk[channel_mask]))
    ch_pk_vel_v49_mean = float(np.nanmean(vel_v49_pk[channel_mask]))
    ch_pk_vel_base_max = float(np.nanmax(vel_base_pk[channel_mask]))
    ch_pk_vel_v49_max = float(np.nanmax(vel_v49_pk[channel_mask]))
    ch_pk_h_base_mean = float(np.nanmean(h_base_pk[channel_mask]))
    ch_pk_h_v49_mean = float(np.nanmean(h_v49_pk[channel_mask]))
    ch_pk_zs_base_mean = float(np.nanmean(zs_base_pk[channel_mask]))
    ch_pk_zs_v49_mean = float(np.nanmean(zs_v49_pk[channel_mask]))

    # Floodplain metrics (outside channel, low elevation)
    fp_mask = ~channel_mask & eval_mask & (dem < 30.0) & (hand < 10.0)
    fp_h_base_mean = float(np.nanmean(h_base[fp_mask]))
    fp_h_v49_mean = float(np.nanmean(h_v49[fp_mask]))
    fp_vel_base_mean = float(np.nanmean(vel_base[fp_mask]))
    fp_vel_v49_mean = float(np.nanmean(vel_v49[fp_mask]))

    # Da Dien sea mouth bottleneck (eastern outlet)
    col_min = max(0, int((261000 - x_min) / dx))
    col_max = min(shape[1], int((267000 - x_min) / dx))
    row_min = max(0, int((y_max - 1447000) / dy))
    row_max = min(shape[0], int((y_max - 1441000) / dy))
    dd_slice = (slice(row_min, row_max), slice(col_min, col_max))

    dd_vel_base = float(np.nanmean(vel_base[dd_slice]))
    dd_vel_v49 = float(np.nanmean(vel_v49[dd_slice]))
    dd_vel_base_max = float(np.nanmax(vel_base[dd_slice]))
    dd_vel_v49_max = float(np.nanmax(vel_v49[dd_slice]))
    dd_h_base = float(np.nanmean(h_base[dd_slice]))
    dd_h_v49 = float(np.nanmean(h_v49[dd_slice]))

    # Discharge / conveyance estimation across Da Rang lower bridge transect (x ~ 261,500m, y from 1443000 to 1445000)
    transect_col = int((261500 - x_min) / dx)
    transect_r1 = int((y_max - 1445500) / dy)
    transect_r2 = int((y_max - 1442500) / dy)
    # Flux Q = sum(u * h * dy) across N-S cross-section
    q_base_sar = float(np.sum(u_base[transect_r1:transect_r2, transect_col] * h_base[transect_r1:transect_r2, transect_col] * dy))
    q_v49_sar = float(np.sum(u_v49[transect_r1:transect_r2, transect_col] * h_v49[transect_r1:transect_r2, transect_col] * dy))
    q_base_pk = float(np.sum(u_base_pk[transect_r1:transect_r2, transect_col] * h_base_pk[transect_r1:transect_r2, transect_col] * dy))
    q_v49_pk = float(np.sum(u_v49_pk[transect_r1:transect_r2, transect_col] * h_v49_pk[transect_r1:transect_r2, transect_col] * dy))

    # -------------------------------------------------------------
    # 2. REMOTE SENSING & GIS CONTINGENCY ANALYSIS
    # -------------------------------------------------------------
    def get_contingency(obs_bin, sim_bin, mask):
        tp = int((mask & obs_bin & sim_bin).sum())
        fp = int((mask & ~obs_bin & sim_bin).sum())
        fn = int((mask & obs_bin & ~sim_bin).sum())
        tn = int((mask & ~obs_bin & ~sim_bin).sum())
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        csi = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0.0
        f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0
        return {
            "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": prec, "recall": rec, "csi_iou": csi, "f1": f1,
            "tp_km2": tp * pixel_area_km2,
            "fp_km2": fp * pixel_area_km2,
            "fn_km2": fn * pixel_area_km2,
            "sim_area_km2": (tp + fp) * pixel_area_km2,
            "obs_area_km2": (tp + fn) * pixel_area_km2,
            "area_bias": (fp - fn) / (tp + fn) if (tp + fn) > 0 else 0.0
        }

    # Full domain contingency (threshold h > 0.3m)
    ctg_base_03 = get_contingency(obs_wet, h_base > 0.3, eval_mask)
    ctg_v49_03 = get_contingency(obs_wet, h_v49 > 0.3, eval_mask)

    # Sensitivity with threshold h > 0.1m
    ctg_base_01 = get_contingency(obs_wet, h_base > 0.1, eval_mask)
    ctg_v49_01 = get_contingency(obs_wet, h_v49 > 0.1, eval_mask)

    # Tuy Hoa Plain sub-domain (HAND < 5m)
    tuyhoa_mask = eval_mask & (hand < 5.0) & (dem < 25.0)
    ctg_base_th = get_contingency(obs_wet, h_base > 0.3, tuyhoa_mask)
    ctg_v49_th = get_contingency(obs_wet, h_v49 > 0.3, tuyhoa_mask)

    # FP and FN spatial breakdown across HAND elevation tiers
    hand_bins = [0.0, 1.0, 2.0, 5.0, 10.0, 50.0]
    hand_analysis = []
    for i in range(len(hand_bins)-1):
        low, high = hand_bins[i], hand_bins[i+1]
        zmask = eval_mask & (hand >= low) & (hand < high)
        n_obs = int((zmask & obs_wet).sum())
        fp_b = int((zmask & ~obs_wet & (h_base > 0.3)).sum())
        fp_v = int((zmask & ~obs_wet & (h_v49 > 0.3)).sum())
        fn_b = int((zmask & obs_wet & ~(h_base > 0.3)).sum())
        fn_v = int((zmask & obs_wet & ~(h_v49 > 0.3)).sum())
        tp_b = int((zmask & obs_wet & (h_base > 0.3)).sum())
        tp_v = int((zmask & obs_wet & (h_v49 > 0.3)).sum())
        hand_analysis.append({
            "hand_range": f"{low}-{high}m",
            "cells": int(zmask.sum()),
            "area_km2": float(zmask.sum() * pixel_area_km2),
            "obs_wet_km2": float(n_obs * pixel_area_km2),
            "tp_base_km2": float(tp_b * pixel_area_km2),
            "tp_v49_km2": float(tp_v * pixel_area_km2),
            "fp_base_km2": float(fp_b * pixel_area_km2),
            "fp_v49_km2": float(fp_v * pixel_area_km2),
            "delta_fp_km2": float((fp_v - fp_b) * pixel_area_km2),
            "fn_base_km2": float(fn_b * pixel_area_km2),
            "fn_v49_km2": float(fn_v * pixel_area_km2),
        })

    # -------------------------------------------------------------
    # 3. DISASTER RISK & ENGINEERING IMPACT ANALYSIS
    # -------------------------------------------------------------
    hazard_levels = [
        ("Level 1 (0.1 - 0.3m, Warning)", 0.1, 0.3),
        ("Level 2 (0.3 - 1.0m, Moderate Danger)", 0.3, 1.0),
        ("Level 3 (1.0 - 2.0m, High Danger)", 1.0, 2.0),
        ("Level 4 (>= 2.0m, Extreme Danger)", 2.0, 999.0),
    ]

    hazard_sar_time = []
    hazard_peak_time = []

    for name, h_min, h_max in hazard_levels:
        # At SAR time (t = 102h)
        mask_b_sar = (h_base >= h_min) & (h_base < h_max) & eval_mask
        mask_v_sar = (h_v49 >= h_min) & (h_v49 < h_max) & eval_mask
        area_b_sar = float(mask_b_sar.sum() * pixel_area_km2)
        area_v_sar = float(mask_v_sar.sum() * pixel_area_km2)

        # At Peak time
        mask_b_pk = (h_base_pk >= h_min) & (h_base_pk < h_max) & eval_mask
        mask_v_pk = (h_v49_pk >= h_min) & (h_v49_pk < h_max) & eval_mask
        area_b_pk = float(mask_b_pk.sum() * pixel_area_km2)
        area_v_pk = float(mask_v_pk.sum() * pixel_area_km2)

        hazard_sar_time.append({
            "level": name,
            "v48_base_km2": round(area_b_sar, 3),
            "v49_method1_km2": round(area_v_sar, 3),
            "delta_km2": round(area_v_sar - area_b_sar, 3),
            "pct_change": round(((area_v_sar - area_b_sar) / area_b_sar * 100), 2) if area_b_sar > 0 else 0.0
        })
        hazard_peak_time.append({
            "level": name,
            "v48_base_km2": round(area_b_pk, 3),
            "v49_method1_km2": round(area_v_pk, 3),
            "delta_km2": round(area_v_pk - area_b_pk, 3),
            "pct_change": round(((area_v_pk - area_b_pk) / area_b_pk * 100), 2) if area_b_pk > 0 else 0.0
        })

    # Inhabited floodplain (Tuy Hoa lowlands: dem < 15m, hand < 3m)
    inhabited_mask = eval_mask & (dem < 15.0) & (hand < 3.0)
    inh_base_severe = float(((h_base >= 1.0) & inhabited_mask).sum() * pixel_area_km2)
    inh_v49_severe = float(((h_v49 >= 1.0) & inhabited_mask).sum() * pixel_area_km2)
    inh_base_total = float(((h_base >= 0.3) & inhabited_mask).sum() * pixel_area_km2)
    inh_v49_total = float(((h_v49 >= 0.3) & inhabited_mask).sum() * pixel_area_km2)

    report_data = {
        "metadata": {
            "target_sar_time_h": 101.614,
            "matched_frame_h": float(times_h[idx_sar]),
            "peak_frame_h": float(times_h[idx_peak]),
            "total_frames": len(times_s),
            "domain_pixel_area_km2": pixel_area_km2,
            "eval_domain_km2": float(eval_mask.sum() * pixel_area_km2),
            "sar_flood_area_km2": float(obs_wet.sum() * pixel_area_km2),
        },
        "hydraulic_expert": {
            "dredged_volume_m3": mod_vol_m3,
            "dredged_volume_million_m3": round(mod_vol_m3 / 1e6, 3),
            "modified_channel_cells": n_mod,
            "modified_channel_area_km2": round(n_mod * pixel_area_km2, 3),
            "in_channel_sar_time": {
                "v48_base_depth_m": round(ch_h_base_mean, 3),
                "v49_method1_depth_m": round(ch_h_v49_mean, 3),
                "v48_base_vel_mean_ms": round(ch_vel_base_mean, 3),
                "v49_method1_vel_mean_ms": round(ch_vel_v49_mean, 3),
                "v48_base_vel_max_ms": round(ch_vel_base_max, 3),
                "v49_method1_vel_max_ms": round(ch_vel_v49_max, 3),
                "v48_base_wse_m": round(ch_zs_base_mean, 3),
                "v49_method1_wse_m": round(ch_zs_v49_mean, 3),
                "wse_lowering_cm": round((ch_zs_base_mean - ch_zs_v49_mean) * 100, 2),
            },
            "in_channel_peak_time": {
                "v48_base_depth_m": round(ch_pk_h_base_mean, 3),
                "v49_method1_depth_m": round(ch_pk_h_v49_mean, 3),
                "v48_base_vel_mean_ms": round(ch_pk_vel_base_mean, 3),
                "v49_method1_vel_mean_ms": round(ch_pk_vel_v49_mean, 3),
                "v48_base_vel_max_ms": round(ch_pk_vel_base_max, 3),
                "v49_method1_vel_max_ms": round(ch_pk_vel_v49_max, 3),
                "v48_base_wse_m": round(ch_pk_zs_base_mean, 3),
                "v49_method1_wse_m": round(ch_pk_zs_v49_mean, 3),
                "peak_wse_lowering_cm": round((ch_pk_zs_base_mean - ch_pk_zs_v49_mean) * 100, 2),
            },
            "floodplain_sar_time": {
                "v48_base_depth_m": round(fp_h_base_mean, 3),
                "v49_method1_depth_m": round(fp_h_v49_mean, 3),
                "v48_base_vel_mean_ms": round(fp_vel_base_mean, 3),
                "v49_method1_vel_mean_ms": round(fp_vel_v49_mean, 3),
            },
            "da_dien_sea_outlet": {
                "v48_base_vel_mean_ms": round(dd_vel_base, 3),
                "v49_method1_vel_mean_ms": round(dd_vel_v49, 3),
                "v48_base_vel_max_ms": round(dd_vel_base_max, 3),
                "v49_method1_vel_max_ms": round(dd_vel_v49_max, 3),
                "v48_base_depth_m": round(dd_h_base, 3),
                "v49_method1_depth_m": round(dd_h_v49, 3),
            },
            "da_rang_transect_discharge_cms": {
                "sar_time_v48_cms": round(q_base_sar, 1),
                "sar_time_v49_cms": round(q_v49_sar, 1),
                "sar_time_delta_pct": round(((q_v49_sar - q_base_sar) / max(1.0, abs(q_base_sar)) * 100), 2),
                "peak_time_v48_cms": round(q_base_pk, 1),
                "peak_time_v49_cms": round(q_v49_pk, 1),
                "peak_time_delta_pct": round(((q_v49_pk - q_base_pk) / max(1.0, abs(q_base_pk)) * 100), 2),
            }
        },
        "remote_sensing_expert": {
            "contingency_h03": {
                "v48_base": ctg_base_03,
                "v49_method1": ctg_v49_03,
                "difference": {k: ctg_v49_03[k] - ctg_base_03[k] for k in ["csi_iou", "f1", "precision", "recall", "tp_km2", "fp_km2", "fn_km2", "sim_area_km2"]}
            },
            "contingency_h01": {
                "v48_base": ctg_base_01,
                "v49_method1": ctg_v49_01,
            },
            "tuy_hoa_plain_contingency": {
                "v48_base": ctg_base_th,
                "v49_method1": ctg_v49_th,
            },
            "hand_elevation_tiers": hand_analysis,
        },
        "disaster_risk_expert": {
            "hazard_levels_sar_time": hazard_sar_time,
            "hazard_levels_peak_time": hazard_peak_time,
            "inhabited_lowlands_sar_time": {
                "total_inundated_v48_base_km2": round(inh_base_total, 3),
                "total_inundated_v49_method1_km2": round(inh_v49_total, 3),
                "total_reduction_km2": round(inh_base_total - inh_v49_total, 3),
                "severe_danger_v48_base_km2": round(inh_base_severe, 3),
                "severe_danger_v49_method1_km2": round(inh_v49_severe, 3),
                "severe_reduction_km2": round(inh_base_severe - inh_v49_severe, 3),
            }
        }
    }

    out_file = RUN_DIR / "visual_reports" / "v49_multi_expert_metrics.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2)

    print(f"Results successfully saved to {out_file}", flush=True)

if __name__ == "__main__":
    main()
