import rasterio
import numpy as np
import os

dem_in = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V35_fixed.asc"
dem_out = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V39_Targeted.asc"
mask_file = r"D:\VTP\boundary_mask.tif"

print("Loading DEM...")
with rasterio.open(dem_in) as src:
    dem = src.read(1)
    meta = src.meta

print("Loading Mask...")
with rasterio.open(mask_file) as src_mask:
    mask = src_mask.read(1)

target_wl = 20.93
target_z = target_wl - 0.5

obstacle_mask = (mask == 1) & (dem > target_wl)

print(f"Number of obstacle pixels to lower: {np.sum(obstacle_mask)}")

dem_new = dem.copy()
dem_new[obstacle_mask] = target_z

print(f"Saving to {dem_out}...")
with rasterio.open(dem_out, "w", **meta) as dst:
    dst.write(dem_new, 1)

print("Done!")
