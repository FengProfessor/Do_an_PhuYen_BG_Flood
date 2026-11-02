# -*- coding: utf-8 -*-
"""Generate high-resolution scientific visualization maps and time series from V49 Method 1 (Scope B1) NetCDF output at t = 60h."""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LightSource
import netCDF4 as nc
from pathlib import Path
import shutil

# Paths
ROOT = Path("D:/VTP")
RUN_DIR = ROOT / "River_Bathymetry_Project" / "V49_Method1_Runs"
NC_PATH = RUN_DIR / "results" / "V49_Method1_ScopeB1_CENTRAL.nc"
OUT_DIR = RUN_DIR / "visual_reports"
ARTIFACT_DIR = Path(r"C:\Users\CuongHM\.gemini\antigravity\brain\4141814d-0340-4201-ac1d-dd87a0691d73")

OUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# Font configuration
plt.rcParams["font.sans-serif"] = ["Segoe UI", "Arial", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

print(f"[VISUAL] Opening NetCDF file: {NC_PATH}")
ds = nc.Dataset(str(NC_PATH), 'r')

x = ds.variables['x'][:]
y = ds.variables['y'][:]
time_s = ds.variables['time'][:]
time_h = time_s / 3600.0
n_frames = len(time_s)

zb = np.asarray(ds.variables['zb'][:, :], dtype=np.float32)
if zb.ndim == 3:
    zb = zb[0, :, :]
elif zb.ndim > 3:
    zb = zb.squeeze()

dx = float(x[1] - x[0]) if len(x) > 1 else 30.0
dy = float(abs(y[1] - y[0])) if len(y) > 1 else 30.0
cell_area_km2 = (dx * dy) / 1e6
extent = [float(x.min()) / 1000.0, float(x.max()) / 1000.0, float(y.min()) / 1000.0, float(y.max()) / 1000.0]

print(f"[VISUAL] Grid: {len(x)} x {len(y)}, dx={dx}m, dy={dy}m | Frames: {n_frames} | t_max={time_h[-1]:.1f}h")

# Hillshade calculation
try:
    ls = LightSource(azdeg=315, altdeg=45)
    hillshade = ls.hillshade(zb, vert_exag=1.5, dx=dx, dy=dy)
except Exception:
    hillshade = (zb - zb.min()) / max(1e-5, (zb.max() - zb.min()))

# Colormaps
colors_flood = [(0.75, 0.90, 1.0), (0.25, 0.65, 0.95), (0.05, 0.35, 0.85), (0.0, 0.12, 0.55), (0.45, 0.0, 0.50)]
flood_cmap = LinearSegmentedColormap.from_list('flood_depth', colors_flood, N=256)

# -------------------------------------------------------------
# 1. Figure 1: Inundation Area Time Series (t = 0 -> 60h)
# -------------------------------------------------------------
print("[VISUAL] Computing inundation time series...")
area_01 = []
area_03 = []
area_10 = []

for i in range(n_frames):
    h_arr = np.asarray(ds.variables['h'][i, :, :], dtype=np.float32)
    area_01.append(float((h_arr >= 0.1).sum()) * cell_area_km2)
    area_03.append(float((h_arr >= 0.3).sum()) * cell_area_km2)
    area_10.append(float((h_arr >= 1.0).sum()) * cell_area_km2)

fig, ax = plt.subplots(figsize=(10, 5.5), dpi=250)
ax.plot(time_h, area_01, color='#0288d1', linewidth=2.0, marker='o', markersize=4, label='Ngập nông (h ≥ 0.1 m)')
ax.plot(time_h, area_03, color='#1565c0', linewidth=2.5, marker='s', markersize=5, label='Ngập đáng kể (h ≥ 0.3 m — Chuẩn Sentinel-1 SAR)')
ax.plot(time_h, area_10, color='#0d47a1', linewidth=2.0, marker='^', markersize=4, label='Ngập sâu (h ≥ 1.0 m)')

# Highlight t = 60h point
t_last = float(time_h[-1])
a_last = area_03[-1]
ax.scatter([t_last], [a_last], color='#2e7d32', s=130, zorder=6, label=f'Mốc t = {t_last:.1f}h ({a_last:.1f} km²)')

ax.set_title('Diễn biến Diện tích Ngập lụt V49 Cách 1 (SCOPE B1 — 41 Reaches CENTRAL)\nt = 0h → 60h', fontsize=13, fontweight='bold', pad=12)
ax.set_xlabel('Thời gian mô phỏng (Giờ)', fontsize=11, fontweight='bold')
ax.set_ylabel('Diện tích ngập (km²)', fontsize=11, fontweight='bold')
ax.grid(True, linestyle=':', alpha=0.6)
ax.legend(loc='upper left', framealpha=0.95, fontsize=9.5)
ax.set_xlim(0, max(63.0, t_last + 3.0))
fig.tight_layout()

f1_path = OUT_DIR / 'inundation_area_time_series_t60h.png'
fig.savefig(f1_path)
plt.close(fig)
print(f"[VISUAL] Saved: {f1_path}")

# -------------------------------------------------------------
# 2. Figure 2: High-Resolution Flood Depth Map at t = 60h
# -------------------------------------------------------------
latest_idx = n_frames - 1
print(f"[VISUAL] Rendering Flood Depth Map at t = {time_h[latest_idx]:.1f}h...")
h_latest = np.asarray(ds.variables['h'][latest_idx, :, :], dtype=np.float32)
h_masked = np.ma.masked_where(h_latest < 0.2, h_latest)

fig, ax = plt.subplots(figsize=(10, 9), dpi=250)
ax.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.55)
im = ax.imshow(h_masked, cmap=flood_cmap, vmin=0.2, vmax=8.0, extent=extent, origin='lower', alpha=0.92)
cbar = fig.colorbar(im, ax=ax, fraction=0.038, pad=0.04)
cbar.set_label('Độ sâu ngập h (m)', fontsize=11, fontweight='bold')

ax.set_title(f'Bản đồ Độ sâu Ngập lũ V49 Cách 1 (SCOPE B1 — CENTRAL) tại t = {time_h[latest_idx]:.1f}h\n'
             f'[Diện tích ngập (h ≥ 0.3m): {area_03[latest_idx]:.1f} km² | Độ sâu tâm dòng cực đại: {float(h_latest.max()):.2f} m]',
             fontsize=12, fontweight='bold', pad=12)
ax.set_xlabel('Tọa độ UTM X (km)', fontsize=10, fontweight='bold')
ax.set_ylabel('Tọa độ UTM Y (km)', fontsize=10, fontweight='bold')
ax.grid(True, linestyle=':', alpha=0.5, color='white')

f2_path = OUT_DIR / 'flood_depth_map_t60h.png'
fig.savefig(f2_path, bbox_inches='tight')
plt.close(fig)
print(f"[VISUAL] Saved: {f2_path}")

# -------------------------------------------------------------
# 3. Figure 3: 4-Panel Evolution Progression (t=6h, 24h, 42h, 60h)
# -------------------------------------------------------------
print("[VISUAL] Rendering 4-panel Flood Evolution Map...")
prog_indices = [1, 7, 13, latest_idx]  # ~6h, 24h, 42h, 60h
fig, axes = plt.subplots(2, 2, figsize=(14, 12), dpi=200)
axes = axes.flatten()

for idx, f_idx in enumerate(prog_indices):
    ax = axes[idx]
    h_f = np.asarray(ds.variables['h'][f_idx, :, :], dtype=np.float32)
    h_f_masked = np.ma.masked_where(h_f < 0.2, h_f)
    t_val = time_h[f_idx]
    area_val = float((h_f >= 0.3).sum()) * cell_area_km2

    ax.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.5)
    im_sub = ax.imshow(h_f_masked, cmap=flood_cmap, vmin=0.2, vmax=7.0, extent=extent, origin='lower', alpha=0.9)

    ax.set_title(f't = {t_val:.1f}h (Khung {f_idx + 1}/41)\nDiện tích ngập (h ≥ 0.3m): {area_val:.1f} km²',
                 fontsize=11, fontweight='bold')
    ax.set_xlabel('UTM X (km)', fontsize=9)
    ax.set_ylabel('UTM Y (km)', fontsize=9)
    ax.grid(True, linestyle=':', alpha=0.4, color='white')

fig.suptitle('Diễn biến Lan truyền Lũ V49 Cách 1 (SCOPE B1 CENTRAL) qua các mốc thời gian', fontsize=14, fontweight='bold', y=0.98)
fig.subplots_adjust(right=0.88, hspace=0.22, wspace=0.18)
cbar_ax = fig.add_axes([0.90, 0.15, 0.025, 0.7])
cbar_prog = fig.colorbar(im_sub, cax=cbar_ax)
cbar_prog.set_label('Độ sâu ngập h (m)', fontsize=11, fontweight='bold')

f3_path = OUT_DIR / 'flood_evolution_progression_t60h.png'
fig.savefig(f3_path, bbox_inches='tight')
plt.close(fig)
print(f"[VISUAL] Saved: {f3_path}")

# -------------------------------------------------------------
# 4. Figure 4: Flow Velocity Field Map at t = 60h
# -------------------------------------------------------------
print(f"[VISUAL] Rendering Flow Velocity Map at t = {time_h[latest_idx]:.1f}h...")
u = np.asarray(ds.variables['u'][latest_idx, :, :], dtype=np.float32)
v = np.asarray(ds.variables['v'][latest_idx, :, :], dtype=np.float32)
vel_mag = np.sqrt(u**2 + v**2)
vel_masked = np.ma.masked_where(h_latest < 0.2, vel_mag)

fig, ax = plt.subplots(figsize=(10, 9), dpi=250)
ax.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.55)
im_vel = ax.imshow(vel_masked, cmap='plasma', vmin=0.0, vmax=3.5, extent=extent, origin='lower', alpha=0.92)
cbar_v = fig.colorbar(im_vel, ax=ax, fraction=0.038, pad=0.04)
cbar_v.set_label('Vận tốc dòng chảy V (m/s)', fontsize=11, fontweight='bold')

ax.set_title(f'Bản đồ Trường Vận tốc Dòng lũ V49 Cách 1 (SCOPE B1) tại t = {time_h[latest_idx]:.1f}h\n'
             f'[Vận tốc cực đại tâm dòng thoát lũ: {float(vel_mag.max()):.2f} m/s]',
             fontsize=12, fontweight='bold', pad=12)
ax.set_xlabel('Tọa độ UTM X (km)', fontsize=10, fontweight='bold')
ax.set_ylabel('Tọa độ UTM Y (km)', fontsize=10, fontweight='bold')
ax.grid(True, linestyle=':', alpha=0.5, color='white')

f4_path = OUT_DIR / 'flow_velocity_map_t60h.png'
fig.savefig(f4_path, bbox_inches='tight')
plt.close(fig)
print(f"[VISUAL] Saved: {f4_path}")

# -------------------------------------------------------------
# 5. Figure 5: Zoom into Lower Song Ba & Tuy Hoa Plain
# -------------------------------------------------------------
print("[VISUAL] Rendering Zoom into Lower Song Ba & Tuy Hoa Plain...")
# Tuy Hoa plain coordinates: X in [310, 332] km, Y in [1435, 1455] km
fig, ax = plt.subplots(figsize=(11, 7.5), dpi=250)
ax.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.55)
im_zoom = ax.imshow(h_masked, cmap=flood_cmap, vmin=0.2, vmax=6.0, extent=extent, origin='lower', alpha=0.92)
cbar_z = fig.colorbar(im_zoom, ax=ax, fraction=0.035, pad=0.03)
cbar_z.set_label('Độ sâu ngập h (m)', fontsize=11, fontweight='bold')

ax.set_xlim(310.0, 332.0)
ax.set_ylim(1435.0, 1455.0)
ax.set_title(f'Chi tiết Hạ lưu Sông Ba & Đồng bằng Tuy Hòa (V49 Cách 1 Scope B1) tại t = {time_h[latest_idx]:.1f}h\n'
             'Khơi thông 41 đoạn sông lớn: Dòng chính Đà Rằng thoát lũ mạnh ra cửa biển Đà Diễn',
             fontsize=11.5, fontweight='bold', pad=12)
ax.set_xlabel('Tọa độ UTM X (km)', fontsize=10, fontweight='bold')
ax.set_ylabel('Tọa độ UTM Y (km)', fontsize=10, fontweight='bold')
ax.grid(True, linestyle=':', alpha=0.5, color='white')

f5_path = OUT_DIR / 'lower_song_ba_tuy_hoa_zoom_t60h.png'
fig.savefig(f5_path, bbox_inches='tight')
plt.close(fig)
print(f"[VISUAL] Saved: {f5_path}")

ds.close()

# Copy to artifact directory
generated_files = [f1_path, f2_path, f3_path, f4_path, f5_path]
for f in generated_files:
    dst = ARTIFACT_DIR / f.name
    shutil.copy2(f, dst)
    print(f"[ARTIFACT] Copied {f.name} -> {dst}")

print("[VISUAL] All 5 high-resolution maps successfully generated and synchronized to artifact directory!")
