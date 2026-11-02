# -*- coding: utf-8 -*-
"""Diagnostic evaluation comparing V49 Method 1 (Scope B1 CENTRAL) at t = 60h with Sentinel-1 SAR flood extent and V48 BASE."""

import json
from datetime import datetime
from pathlib import Path
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, LinearSegmentedColormap, LightSource
from matplotlib.patches import Patch
import netCDF4 as nc
import rasterio
from rasterio.warp import reproject, Resampling

ROOT = Path("D:/VTP")
RUN_DIR = ROOT / "River_Bathymetry_Project" / "V49_Method1_Runs"
OUT_DIR = RUN_DIR / "visual_reports"
ARTIFACT_DIR = Path(r"C:\Users\CuongHM\.gemini\antigravity\brain\4141814d-0340-4201-ac1d-dd87a0691d73")

BASE_DEM = ROOT / "05-Du-lieu-GIS" / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
SAR_TIF = ROOT / "05-Du-lieu-GIS" / "DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif"
WATER_TIF = ROOT / "05-Du-lieu-GIS" / "water_density_30m.tif"
HAND_TIF = ROOT / "BG_Flood_Project" / "BG_Flood" / "Teamwork_Validation" / "PhuYen_HAND_30m.tif"

V49_NC = RUN_DIR / "results" / "V49_Method1_ScopeB1_CENTRAL.nc"
BASE_NC = ROOT / "V48_runs" / "20261004_runtime_fix_r1" / "results" / "V48_FORMAL_BASE_R1.nc"

OUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Segoe UI", "Arial", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

def aligned(path: Path, shape, transform, crs, dtype, nodata):
    data = np.full(shape, nodata, dtype=dtype)
    with rasterio.open(path) as source:
        reproject(
            source=rasterio.band(source, 1),
            destination=data,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source.nodata,
            dst_transform=transform,
            dst_crs=crs,
            dst_nodata=nodata,
            resampling=Resampling.nearest,
        )
    return data

def contingency(observed, simulated, mask, pixel_area_km2):
    tp = int((mask & observed & simulated).sum())
    fp = int((mask & ~observed & simulated).sum())
    fn = int((mask & observed & ~simulated).sum())
    tn = int((mask & ~observed & ~simulated).sum())
    divide = lambda a, b: float(a / b) if b else 0.0
    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "precision": divide(tp, tp + fp),
        "recall": divide(tp, tp + fn),
        "csi_iou": divide(tp, tp + fp + fn),
        "f1": divide(2 * tp, 2 * tp + fp + fn),
        "observed_area_km2": (tp + fn) * pixel_area_km2,
        "simulated_area_km2": (tp + fp) * pixel_area_km2,
        "area_bias": divide(fp - fn, tp + fn),
    }

print("[SAR_EVAL] Reading grid geometry from BASE DEM...")
with rasterio.open(BASE_DEM) as src:
    shape = src.shape
    transform = src.transform
    crs = src.crs
    dem_data = src.read(1).astype(np.float32)
    dx = float(transform.a)
    dy = float(abs(transform.e))
    pixel_area_km2 = (dx * dy) / 1e6
    extent = [float(transform.c) / 1000.0, float(transform.c + shape[1] * dx) / 1000.0,
              float(transform.f - shape[0] * dy) / 1000.0, float(transform.f) / 1000.0]

print("[SAR_EVAL] Aligning SAR observation and mask rasters...")
sar = aligned(SAR_TIF, shape, transform, crs, "uint8", 255)
water = aligned(WATER_TIF, shape, transform, crs, "float32", -9999.0)
hand = aligned(HAND_TIF, shape, transform, crs, "float32", -9999.0)

eval_mask = np.isin(sar, [0, 1]) & (water <= 0.5) & (hand >= 0.0)
obs_wet = (sar == 1) & eval_mask
observed_flood_area_km2 = float(obs_wet.sum()) * pixel_area_km2

print(f"[SAR_EVAL] Evaluation domain: {int(eval_mask.sum())} valid cells ({int(eval_mask.sum()) * pixel_area_km2:.1f} km²)")
print(f"[SAR_EVAL] Observed Sentinel-1 SAR flood area (excluding permanent water): {observed_flood_area_km2:.2f} km²")

# 1. Read V49 Method 1 at latest frame (t = 60h)
print(f"[SAR_EVAL] Opening V49 Method 1 NetCDF: {V49_NC}")
with nc.Dataset(str(V49_NC), 'r') as ds_v49:
    times_v49 = ds_v49.variables['time'][:]
    idx_v49 = len(times_v49) - 1
    t_v49_h = float(times_v49[idx_v49]) / 3600.0
    h_v49 = np.asarray(ds_v49.variables['h'][idx_v49, :, :], dtype=np.float32)
    y_vals = ds_v49.variables['y'][:]
    if y_vals[0] < y_vals[-1]:
        h_v49 = np.flipud(h_v49)

sim_wet_v49 = (np.nan_to_num(h_v49) > 0.3)
metrics_v49 = contingency(sar == 1, sim_wet_v49, eval_mask, pixel_area_km2)
print(f"[SAR_EVAL] V49 Method 1 (t={t_v49_h:.1f}h): CSI={metrics_v49['csi_iou']:.4f}, F1={metrics_v49['f1']:.4f}, Prec={metrics_v49['precision']:.4f}, Rec={metrics_v49['recall']:.4f}, SimArea={metrics_v49['simulated_area_km2']:.1f} km²")

# 2. Read V48 BASE at t = 60h
print(f"[SAR_EVAL] Opening V48 BASE NetCDF: {BASE_NC}")
with nc.Dataset(str(BASE_NC), 'r') as ds_base:
    times_base = ds_base.variables['time'][:]
    idx_base = int(np.argmin(np.abs(times_base - 60.0 * 3600.0)))
    t_base_h = float(times_base[idx_base]) / 3600.0
    h_base = np.asarray(ds_base.variables['h'][idx_base, :, :], dtype=np.float32)
    y_b = ds_base.variables['y'][:]
    if y_b[0] < y_b[-1]:
        h_base = np.flipud(h_base)

sim_wet_base = (np.nan_to_num(h_base) > 0.3)
metrics_base = contingency(sar == 1, sim_wet_base, eval_mask, pixel_area_km2)
print(f"[SAR_EVAL] V48 BASE (t={t_base_h:.1f}h): CSI={metrics_base['csi_iou']:.4f}, F1={metrics_base['f1']:.4f}, Prec={metrics_base['precision']:.4f}, Rec={metrics_base['recall']:.4f}, SimArea={metrics_base['simulated_area_km2']:.1f} km²")

# 3. Build Spatial Contingency Array for V49
# 0: True Negative (cạn cả hai), 1: True Positive (cả hai ngập), 2: False Positive (mô phỏng ngập thừa), 3: False Negative (SAR ngập thiếu)
ctg_arr = np.zeros(shape, dtype=np.uint8)
ctg_arr[eval_mask & ~obs_wet & ~sim_wet_v49] = 0  # TN
ctg_arr[eval_mask & obs_wet & sim_wet_v49] = 1   # TP (Hit)
ctg_arr[eval_mask & ~obs_wet & sim_wet_v49] = 2  # FP (Overprediction)
ctg_arr[eval_mask & obs_wet & ~sim_wet_v49] = 3  # FN (Underprediction)

# Hillshade
ls = LightSource(azdeg=315, altdeg=45)
hillshade = ls.hillshade(dem_data, vert_exag=1.5, dx=dx, dy=dy)

colors_flood = [(0.75, 0.90, 1.0), (0.25, 0.65, 0.95), (0.05, 0.35, 0.85), (0.0, 0.12, 0.55), (0.45, 0.0, 0.50)]
flood_cmap = LinearSegmentedColormap.from_list('flood_depth', colors_flood, N=256)

# 4-color contingency colormap:
# 0: None (transparent), 1: Green (TP), 2: Amber/Red (FP), 3: Blue (FN)
ctg_colors = ['none', '#2e7d32', '#e65100', '#1565c0']
ctg_cmap = ListedColormap(ctg_colors)

# -------------------------------------------------------------
# Generate 4-Panel Figure
# -------------------------------------------------------------
print("[SAR_EVAL] Rendering 4-Panel Comparison Map...")
fig, axes = plt.subplots(2, 2, figsize=(15, 13), dpi=250)

# (A) Sentinel-1 SAR Observed
ax_a = axes[0, 0]
ax_a.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.55)
sar_plot = np.ma.masked_where(~(eval_mask & obs_wet), obs_wet.astype(np.float32))
ax_a.imshow(sar_plot, cmap=ListedColormap(['#0d47a1']), extent=extent, origin='lower', alpha=0.95)
ax_a.set_title(f"(A) Vệ tinh Sentinel-1 SAR Thực nhận (2021-11-30 05:36 UTC+7)\n"
               f"[Diện tích ngập quan sát: {observed_flood_area_km2:.1f} km² (chuẩn Otsu)]",
               fontsize=11.5, fontweight='bold', pad=10)
ax_a.set_xlabel('Tọa độ UTM X (km)', fontsize=9.5)
ax_a.set_ylabel('Tọa độ UTM Y (km)', fontsize=9.5)
ax_a.grid(True, linestyle=':', alpha=0.4, color='white')

# (B) V48 BASE at t = 60h
ax_b = axes[0, 1]
ax_b.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.55)
h_b_masked = np.ma.masked_where(h_base < 0.3, h_base)
im_b = ax_b.imshow(h_b_masked, cmap=flood_cmap, vmin=0.3, vmax=7.0, extent=extent, origin='lower', alpha=0.92)
ax_b.set_title(f"(B) Mô phỏng V48 BASE (Chưa khơi thông đáy sông) tại t = {t_base_h:.1f}h\n"
               f"[CSI / IoU: {metrics_base['csi_iou']:.4f} | F1: {metrics_base['f1']:.4f} | Diện tích ngập: {metrics_base['simulated_area_km2']:.1f} km²]",
               fontsize=11.5, fontweight='bold', pad=10)
ax_b.set_xlabel('Tọa độ UTM X (km)', fontsize=9.5)
ax_b.set_ylabel('Tọa độ UTM Y (km)', fontsize=9.5)
ax_b.grid(True, linestyle=':', alpha=0.4, color='white')

# (C) V49 Method 1 at t = 60h
ax_c = axes[1, 0]
ax_c.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.55)
h_v_masked = np.ma.masked_where(h_v49 < 0.3, h_v49)
im_c = ax_c.imshow(h_v_masked, cmap=flood_cmap, vmin=0.3, vmax=7.0, extent=extent, origin='lower', alpha=0.92)
ax_c.set_title(f"(C) Mô phỏng V49 Cách 1 (Khơi thông 41 đoạn Scope B1) tại t = {t_v49_h:.1f}h\n"
               f"[CSI / IoU: {metrics_v49['csi_iou']:.4f} | F1: {metrics_v49['f1']:.4f} | Diện tích ngập: {metrics_v49['simulated_area_km2']:.1f} km²]",
               fontsize=11.5, fontweight='bold', pad=10)
ax_c.set_xlabel('Tọa độ UTM X (km)', fontsize=9.5)
ax_c.set_ylabel('Tọa độ UTM Y (km)', fontsize=9.5)
ax_c.grid(True, linestyle=':', alpha=0.4, color='white')

# (D) Spatial Contingency Map V49 vs SAR
ax_d = axes[1, 1]
ax_d.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.55)
ctg_masked = np.ma.masked_where(ctg_arr == 0, ctg_arr)
ax_d.imshow(ctg_masked, cmap=ctg_cmap, vmin=0, vmax=3, extent=extent, origin='lower', alpha=0.92)

tp_km2 = metrics_v49['TP'] * pixel_area_km2
fp_km2 = metrics_v49['FP'] * pixel_area_km2
fn_km2 = metrics_v49['FN'] * pixel_area_km2

ax_d.set_title(f"(D) Bản đồ Ma trận Phù hợp Không gian (V49 Cách 1 vs Sentinel-1 SAR)\n"
               f"[TP (Đồng thuận ngập): {tp_km2:.1f} km² | FP: {fp_km2:.1f} km² | FN: {fn_km2:.1f} km²]",
               fontsize=11.5, fontweight='bold', pad=10)
ax_d.set_xlabel('Tọa độ UTM X (km)', fontsize=9.5)
ax_d.set_ylabel('Tọa độ UTM Y (km)', fontsize=9.5)
ax_d.grid(True, linestyle=':', alpha=0.4, color='white')

legend_elements = [
    Patch(facecolor='#2e7d32', edgecolor='black', label=f'Đồng thuận ngập (TP / Hit): {tp_km2:.1f} km²'),
    Patch(facecolor='#e65100', edgecolor='black', label=f'Mô phỏng ngập thêm (FP): {fp_km2:.1f} km²'),
    Patch(facecolor='#1565c0', edgecolor='black', label=f'SAR ngập, mô phỏng chưa tới (FN): {fn_km2:.1f} km²'),
]
ax_d.legend(handles=legend_elements, loc='upper left', framealpha=0.95, fontsize=8.5)

fig.suptitle(f"Chẩn đoán Kiểm chứng Không gian: V49 Cách 1 (SCOPE B1 CENTRAL) vs Vệ tinh Sentinel-1 SAR\n(Đánh giá sơ bộ tại mốc t = {t_v49_h:.1f}h so với ảnh SAR t = 101.61h)",
             fontsize=14, fontweight='bold', y=0.99)
fig.subplots_adjust(hspace=0.22, wspace=0.18)

out_fig = OUT_DIR / "sar_vs_v49_method1_contingency_t60h.png"
fig.savefig(out_fig, bbox_inches='tight')
plt.close(fig)
print(f"[SAR_EVAL] Saved figure: {out_fig}")

# Copy to artifact dir
dst_artifact = ARTIFACT_DIR / out_fig.name
shutil.copy2(out_fig, dst_artifact)
print(f"[SAR_EVAL] Synchronized to artifact directory: {dst_artifact}")

# Save JSON metrics
eval_result = {
    "timestamp_utc": datetime.utcnow().isoformat(),
    "evaluation_time_h": t_v49_h,
    "target_sar_time_h": 101.61,
    "status": "PRELIMINARY_DIAGNOSTIC_AT_T60H",
    "note": "So sanh so bo tai t=60h giup chan doan huong lan truyen song lu truoc khi mo phong dat moc chinh thuc t=101.61h",
    "metrics_v49_method1": metrics_v49,
    "metrics_v48_base": metrics_base,
    "difference_method1_minus_base": {
        "delta_csi_iou": metrics_v49["csi_iou"] - metrics_base["csi_iou"],
        "delta_f1": metrics_v49["f1"] - metrics_base["f1"],
        "delta_precision": metrics_v49["precision"] - metrics_base["precision"],
        "delta_recall": metrics_v49["recall"] - metrics_base["recall"],
        "delta_simulated_area_km2": metrics_v49["simulated_area_km2"] - metrics_base["simulated_area_km2"],
    }
}

json_path = OUT_DIR / "sar_vs_v49_method1_metrics_t60h.json"
json_path.write_text(json.dumps(eval_result, ensure_ascii=False, indent=2), encoding="utf-8")
shutil.copy2(json_path, ARTIFACT_DIR / json_path.name)
print(json.dumps(eval_result, ensure_ascii=False, indent=2))
