import xarray as xr
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata

sim_nc = r"D:\VTP\BG_Flood_Project\BG_Flood\results\PhuYen_30m_V37_1.nc"
sar_tif = r"D:\VTP\05-Du-lieu-GIS\DakLak_PhuYen_FloodExtent_Otsu_20211130_05h36.tif"

target_bounds = (310000, 1438000, 326000, 1453000)

ds = xr.open_dataset(sim_nc)
h_sim = ds.h.isel(time=8) 

sim_x = ds.x.values
sim_y = ds.y.values
sim_x_mask = (sim_x >= target_bounds[0]) & (sim_x <= target_bounds[2])
sim_y_mask = (sim_y >= target_bounds[1]) & (sim_y <= target_bounds[3])

sim_h_crop = h_sim.values[np.ix_(sim_y_mask, sim_x_mask)]
sim_x_crop = sim_x[sim_x_mask]
sim_y_crop = sim_y[sim_y_mask]

with rasterio.open(sar_tif) as src:
    window = rasterio.windows.from_bounds(
        target_bounds[0], target_bounds[1], target_bounds[2], target_bounds[3], transform=src.transform
    )
    sar_crop = src.read(1, window=window)
    sar_transform = src.window_transform(window)
    sar_bounds = rasterio.windows.bounds(window, src.transform)
    sar_extent = [sar_bounds[0], sar_bounds[2], sar_bounds[1], sar_bounds[3]]
    
    # Resample SAR to Sim grid for comparison
    sar_x = np.linspace(sar_bounds[0], sar_bounds[2], sar_crop.shape[1])
    sar_y = np.linspace(sar_bounds[3], sar_bounds[1], sar_crop.shape[0])
    sar_xx, sar_yy = np.meshgrid(sar_x, sar_y)
    
    sim_xx, sim_yy = np.meshgrid(sim_x_crop, sim_y_crop)
    sar_resampled = griddata((sar_xx.flatten(), sar_yy.flatten()), sar_crop.flatten(), (sim_xx, sim_yy), method='nearest')

fig, axes = plt.subplots(1, 3, figsize=(24, 8))

ax = axes[0]
ax.imshow(sar_crop, extent=sar_extent, origin='upper', cmap='gray')
ax.set_title("SAR Flood Extent")

ax = axes[1]
sim_extent = [sim_x_crop[0], sim_x_crop[-1], sim_y_crop[0], sim_y_crop[-1]]
if sim_y_crop[0] > sim_y_crop[-1]:
    sim_extent = [sim_x_crop[0], sim_x_crop[-1], sim_y_crop[-1], sim_y_crop[0]]
    sim_h_crop_disp = np.flipud(sim_h_crop)
else:
    sim_h_crop_disp = sim_h_crop

im = ax.imshow(sim_h_crop_disp, extent=sim_extent, origin='lower', cmap='Blues', vmin=0.1, vmax=5)
plt.colorbar(im, ax=ax, label='Water depth (m)')
ax.set_title("V37 Simulation (Frame 8)")

ax = axes[2]
# False Negative: SAR = 1, Sim < 0.1
fn_mask = (sar_resampled == 1) & (sim_h_crop < 0.1)
if sim_y_crop[0] > sim_y_crop[-1]:
    fn_mask_disp = np.flipud(fn_mask)
else:
    fn_mask_disp = fn_mask

# Plot FN as yellow
from matplotlib.colors import ListedColormap
cmap_fn = ListedColormap(['none', 'yellow'])
ax.imshow(sim_h_crop_disp, extent=sim_extent, origin='lower', cmap='Blues', vmin=0.1, vmax=5)
ax.imshow(fn_mask_disp, extent=sim_extent, origin='lower', cmap=cmap_fn, alpha=0.6)
ax.set_title("Yellow: False Negative (SAR flooded, Sim not flooded)")

plt.savefig(r"D:\VTP\BG_Flood_Project\BG_Flood\results\v37_sar_comparison_fn.png", dpi=300)
print("Plot saved.")
