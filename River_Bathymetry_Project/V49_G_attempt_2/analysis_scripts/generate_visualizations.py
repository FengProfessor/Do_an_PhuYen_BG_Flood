import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import netCDF4 as nc

nc_path = r'D:\VTP\River_Bathymetry_Project\V49_G_attempt_2\results\V49_G_CENTRAL.nc'
out_dir_d = r'D:\VTP\River_Bathymetry_Project\V49_G_attempt_2\visual_reports'
out_dir_c = r'C:\Users\CuongHM\.gemini\antigravity\brain\303aa3cb-1e89-49b2-8549-ccb345e3d166'
os.makedirs(out_dir_d, exist_ok=True)
os.makedirs(out_dir_c, exist_ok=True)
out_dir = out_dir_d

print(f"Opening NetCDF file: {nc_path}")
ds = nc.Dataset(nc_path, 'r')

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

print(f"Grid size: {len(x)} x {len(y)}, dx={dx}m, dy={dy}m, zb shape={zb.shape}")
print(f"Total frames available: {n_frames}")
print(f"Time steps (hours): {np.round(time_h, 1).tolist()}")

extent = [float(x.min()) / 1000.0, float(x.max()) / 1000.0, float(y.min()) / 1000.0, float(y.max()) / 1000.0]

# --- Figure 1: Inundation Area Time Series ---
print("Calculating inundation time series...")
area_01 = []
area_03 = []
area_10 = []

for i in range(n_frames):
    h = np.asarray(ds.variables['h'][i, :, :], dtype=np.float32)
    area_01.append(float((h >= 0.1).sum()) * cell_area_km2)
    area_03.append(float((h >= 0.3).sum()) * cell_area_km2)
    area_10.append(float((h >= 1.0).sum()) * cell_area_km2)

plt.figure(figsize=(10, 5.5), dpi=200)
plt.plot(time_h, area_01, color='#0288d1', linewidth=2.0, marker='o', markersize=4, label='Ngập nông (h ≥ 0.1 m)')
plt.plot(time_h, area_03, color='#1565c0', linewidth=2.5, marker='s', markersize=5, label='Ngập đáng kể (h ≥ 0.3 m - Tiêu chuẩn SAR)')
plt.plot(time_h, area_10, color='#0d47a1', linewidth=2.0, marker='^', markersize=4, label='Ngập sâu (h ≥ 1.0 m)')

# Vertical line for old interruption
plt.axvline(x=35.4, color='#d32f2f', linestyle='--', linewidth=2, label='Mốc mất điện cũ (V49-G 20261014: 35.4h)')
plt.scatter([35.4], [np.interp(35.4, time_h, area_03)], color='#d32f2f', s=80, zorder=5)

# Current active point
curr_time = float(time_h[-1])
curr_area = area_03[-1]
plt.scatter([curr_time], [curr_area], color='#2e7d32', s=120, zorder=6, label=f'Mốc hiện tại (t = {curr_time:.1f}h | {curr_area:.1f} km²)')

plt.title('Diễn biến diện tích ngập lụt V49-G (CENTRAL) theo thời gian', fontsize=14, fontweight='bold', pad=12)
plt.xlabel('Thời gian mô phỏng (Giờ)', fontsize=11, fontweight='bold')
plt.ylabel('Diện tích ngập (km²)', fontsize=11, fontweight='bold')
plt.grid(True, linestyle=':', alpha=0.6)
plt.legend(loc='upper left', framealpha=0.95, fontsize=9.5)
plt.xlim(0, max(48.0, curr_time + 3.0))
plt.tight_layout()

f1_path = os.path.join(out_dir, 'inundation_area_time_series.png')
plt.savefig(f1_path)
plt.close()
print(f"Saved: {f1_path}")

# --- Figure 2: Flood Depth Map at latest frame ---
latest_idx = n_frames - 1
print(f"Generating high-resolution flood depth map at t = {time_h[latest_idx]:.1f}h...")
h_latest = np.asarray(ds.variables['h'][latest_idx, :, :], dtype=np.float32)
h_masked = np.ma.masked_where(h_latest < 0.2, h_latest)

# Terrain hillshade or light relief
try:
    from matplotlib.colors import LightSource
    ls = LightSource(azdeg=315, altdeg=45)
    hillshade = ls.hillshade(zb, vert_exag=1.5, dx=dx, dy=dy)
except Exception as e:
    print(f"Hillshade fallback: {e}")
    hillshade = (zb - zb.min()) / max(1e-5, (zb.max() - zb.min()))

fig, ax = plt.subplots(figsize=(10, 9), dpi=250)
# Plot background hillshade
ax.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.55)

# Custom colormap for water depth
colors = [(0.7, 0.88, 1.0), (0.2, 0.6, 0.9), (0.05, 0.3, 0.8), (0.0, 0.1, 0.5), (0.5, 0.0, 0.5)]
flood_cmap = LinearSegmentedColormap.from_list('flood_depth', colors, N=256)

im = ax.imshow(h_masked, cmap=flood_cmap, vmin=0.2, vmax=8.0, extent=extent, origin='lower', alpha=0.92)
cbar = plt.colorbar(im, ax=ax, fraction=0.038, pad=0.04)
cbar.set_label('Độ sâu ngập h (m)', fontsize=11, fontweight='bold')

ax.set_title(f'Bản đồ độ sâu ngập lũ V49-G (CENTRAL) tại t = {time_h[latest_idx]:.1f}h\n'
             f'[Diện tích ngập (h ≥ 0.3m): {area_03[latest_idx]:.1f} km² | Độ sâu cực đại: {float(h_latest.max()):.2f} m]',
             fontsize=13, fontweight='bold', pad=12)
ax.set_xlabel('Tọa độ UTM X (km)', fontsize=10, fontweight='bold')
ax.set_ylabel('Tọa độ UTM Y (km)', fontsize=10, fontweight='bold')
ax.grid(True, linestyle=':', alpha=0.5, color='white')

f2_path = os.path.join(out_dir, 'flood_depth_map_t57h.png')
plt.savefig(f2_path, bbox_inches='tight')
# Also save as flood_depth_map_latest.png
plt.savefig(os.path.join(out_dir, 'flood_depth_map_latest.png'), bbox_inches='tight')
plt.close()
print(f"Saved: {f2_path}")

# --- Figure 3: Flood Evolution Progression (4 Frames) ---
print("Generating 4-panel progression map...")
prog_indices = [1, 6, 11, latest_idx]  # ~6h, 21h, 36h, latest
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
    
    note = ""
    if f_idx == 10:
        note = " [Xấp xỉ mốc mất điện cũ 35.4h]"
    elif f_idx == latest_idx:
        note = " [Mốc mới nhất hiện tại]"
        
    ax.set_title(f't = {t_val:.1f}h (Frame {f_idx + 1}){note}\nDiện tích ngập (h ≥ 0.3m): {area_val:.1f} km²',
                 fontsize=11, fontweight='bold')
    ax.set_xlabel('UTM X (km)', fontsize=9)
    ax.set_ylabel('UTM Y (km)', fontsize=9)
    ax.grid(True, linestyle=':', alpha=0.4, color='white')

fig.suptitle('Diễn biến lan truyền sóng lũ V49-G (CENTRAL) qua các mốc thời gian', fontsize=15, fontweight='bold', y=0.98)
fig.subplots_adjust(right=0.88, hspace=0.22, wspace=0.18)
cbar_ax = fig.add_axes([0.90, 0.15, 0.025, 0.7])
cbar_prog = fig.colorbar(im_sub, cax=cbar_ax)
cbar_prog.set_label('Độ sâu ngập h (m)', fontsize=11, fontweight='bold')

f3_path = os.path.join(out_dir, 'flood_evolution_progression.png')
plt.savefig(f3_path, bbox_inches='tight')
plt.close()
print(f"Saved: {f3_path}")

# --- Figure 4: Flow Velocity Magnitude Field at t = 45h ---
print("Generating flow velocity field map at t = 45h...")
u = np.asarray(ds.variables['u'][latest_idx, :, :], dtype=np.float32)
v = np.asarray(ds.variables['v'][latest_idx, :, :], dtype=np.float32)
vel_mag = np.sqrt(u**2 + v**2)
vel_masked = np.ma.masked_where(h_latest < 0.2, vel_mag)

fig, ax = plt.subplots(figsize=(10, 9), dpi=250)
ax.imshow(hillshade, cmap='gray', extent=extent, origin='lower', alpha=0.55)

im_vel = ax.imshow(vel_masked, cmap='plasma', vmin=0.0, vmax=3.5, extent=extent, origin='lower', alpha=0.92)
cbar_v = plt.colorbar(im_vel, ax=ax, fraction=0.038, pad=0.04)
cbar_v.set_label('Vận tốc dòng chảy V (m/s)', fontsize=11, fontweight='bold')

ax.set_title(f'Bản đồ trường vận tốc dòng lũ V49-G (CENTRAL) tại t = {time_h[latest_idx]:.1f}h\n'
             f'[Vận tốc cực đại trong lòng sông chính: {float(vel_mag.max()):.2f} m/s]',
             fontsize=13, fontweight='bold', pad=12)
ax.set_xlabel('Tọa độ UTM X (km)', fontsize=10, fontweight='bold')
ax.set_ylabel('Tọa độ UTM Y (km)', fontsize=10, fontweight='bold')
ax.grid(True, linestyle=':', alpha=0.5, color='white')

f4_path = os.path.join(out_dir, 'flow_velocity_map_latest.png')
plt.savefig(f4_path, bbox_inches='tight')
plt.close()
print(f"Saved: {f4_path}")

ds.close()
print("All visualizations successfully generated!")
