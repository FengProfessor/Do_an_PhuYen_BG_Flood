import rasterio
import numpy as np

base_path = r'D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif'
legacy_path = r'D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Full_River_Bathymetry.tif'

with rasterio.open(base_path) as s1, rasterio.open(legacy_path) as s2:
    d1 = s1.read(1)
    d2 = s2.read(1)

valid = (d1 > -100) & (d2 > -100)
diff = d1 - d2
carved = valid & (diff > 0.1)

print(f"Full River Bathymetry Carved cells: {carved.sum()} cells ({carved.sum() * 0.0009:.2f} km2)")
print(f"Max lowering: {diff[valid].max():.2f} m")
print(f"Mean lowering in carved channel: {diff[carved].mean():.2f} m")
print(f"Min elevation in Full Bathymetry: {d2[valid].min():.2f} m (vs Base: {d1[valid].min():.2f} m)")
