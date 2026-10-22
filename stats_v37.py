import xarray as xr
import rasterio
import numpy as np
from scipy.interpolate import griddata

sim_nc = r"D:\VTP\BG_Flood_Project\BG_Flood\results\PhuYen_30m_V37_1.nc"
sar_tif = r"D:\VTP\05-Du-lieu-GIS\DakLak_PhuYen_FloodExtent_Otsu_20211130_05h36.tif"

target_bounds = (310000, 1438000, 326000, 1453000)

ds = xr.open_dataset(sim_nc)
h_sim = ds.h.isel(time=8) 
zb = ds.zb.isel(time=0) # elevation

sim_x = ds.x.values
sim_y = ds.y.values
sim_x_mask = (sim_x >= target_bounds[0]) & (sim_x <= target_bounds[2])
sim_y_mask = (sim_y >= target_bounds[1]) & (sim_y <= target_bounds[3])

sim_h_crop = h_sim.values[np.ix_(sim_y_mask, sim_x_mask)]
sim_zb_crop = zb.values[np.ix_(sim_y_mask, sim_x_mask)]
sim_x_crop = sim_x[sim_x_mask]
sim_y_crop = sim_y[sim_y_mask]

with rasterio.open(sar_tif) as src:
    window = rasterio.windows.from_bounds(
        target_bounds[0], target_bounds[1], target_bounds[2], target_bounds[3], transform=src.transform
    )
    sar_crop = src.read(1, window=window)
    sar_bounds = rasterio.windows.bounds(window, src.transform)
    
    sar_x = np.linspace(sar_bounds[0], sar_bounds[2], sar_crop.shape[1])
    sar_y = np.linspace(sar_bounds[3], sar_bounds[1], sar_crop.shape[0])
    sar_xx, sar_yy = np.meshgrid(sar_x, sar_y)
    
    sim_xx, sim_yy = np.meshgrid(sim_x_crop, sim_y_crop)
    sar_resampled = griddata((sar_xx.flatten(), sar_yy.flatten()), sar_crop.flatten(), (sim_xx, sim_yy), method='nearest')

fn_mask = (sar_resampled == 1) & (sim_h_crop < 0.1)

# Divide into North and South
# roughly y = 1446000 is the river Ba.
mid_y = 1445000

north_mask = sim_yy > mid_y
south_mask = sim_yy <= mid_y

def print_stats(name, region_mask):
    total_sar = np.sum((sar_resampled == 1) & region_mask)
    total_sim = np.sum((sim_h_crop >= 0.1) & region_mask)
    total_fn = np.sum(fn_mask & region_mask)
    print(f"--- {name} ---")
    print(f"SAR flooded pixels: {total_sar}")
    print(f"Sim flooded pixels: {total_sim}")
    print(f"False Negatives: {total_fn} ({total_fn/total_sar*100:.1f}% of SAR if total_sar>0 else 0%)")
    
    if total_fn > 0:
        # Check DEM in the FN area vs surrounding area
        fn_zb = sim_zb_crop[fn_mask & region_mask]
        print(f"DEM in FN: min={np.min(fn_zb):.2f}, mean={np.mean(fn_zb):.2f}, max={np.max(fn_zb):.2f}")

print_stats("North Bank (Tuy Hoa)", north_mask)
print_stats("South Bank (Ban Thach)", south_mask)

# Check why water didn't reach. Look at DEM cross sections
# Or just look at the max elevation between the river and the FN area
