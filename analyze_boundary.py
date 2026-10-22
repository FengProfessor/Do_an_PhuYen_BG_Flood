import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
from rasterio.crs import CRS
import numpy as np
import xarray as xr
from scipy.ndimage import binary_dilation
import time
import os

start_time = time.time()

# 1. Paths
dem_path = r'D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V38_Breached.asc'
sar_path = r'D:\VTP\05-Du-lieu-GIS\DakLak_PhuYen_FloodExtent_Otsu_20211130_05h36.asc'
nc_path = r'D:\VTP\BG_Flood_Project\BG_Flood\results\PhuYen_30m_V38.nc'

print("Loading DEM...")
# Load DEM to get master shape and transform
with rasterio.open(dem_path) as src_dem:
    dem = src_dem.read(1)
    dem_meta = src_dem.meta
    dem_transform = src_dem.transform
    dem_crs = src_dem.crs or CRS.from_epsg(32649) # Fallback to 32649 if None
    dem_shape = dem.shape

print("Loading and reprojecting SAR...")
# Load SAR and reproject to DEM
sar_reproj = np.zeros(dem_shape, dtype=np.float32)
with rasterio.open(sar_path) as src_sar:
    sar_crs = src_sar.crs or dem_crs
    reproject(
        source=rasterio.band(src_sar, 1),
        destination=sar_reproj,
        src_transform=src_sar.transform,
        src_crs=sar_crs,
        dst_transform=dem_transform,
        dst_crs=dem_crs,
        resampling=Resampling.nearest
    )

print("Loading and processing V38 NC...")
# Load NC and reproject
ds = xr.open_dataset(nc_path)
# Get latest frame of h
h_latest = ds.h.isel(time=-1).values

# In BG_Flood NC, y is usually bottom to top. Let's flip it if needed.
# Let's create a source transform for NC based on its attributes
xmin, xmax = ds.attrs['xmin'], ds.attrs['xmax']
ymin, ymax = ds.attrs['ymin'], ds.attrs['ymax']
# h shape is 2099x2099
ny, nx = h_latest.shape
dx = (xmax - xmin) / nx
dy = (ymax - ymin) / ny

# Check if y is ascending or descending
y_coords = ds.y.values
if y_coords[1] > y_coords[0]: # Ascending (bottom to top)
    h_latest = np.flipud(h_latest)
    
nc_transform = rasterio.transform.from_bounds(xmin, ymin, xmax, ymax, nx, ny)

h_reproj = np.zeros(dem_shape, dtype=np.float32)
reproject(
    source=h_latest,
    destination=h_reproj,
    src_transform=nc_transform,
    src_crs=dem_crs,
    dst_transform=dem_transform,
    dst_crs=dem_crs,
    resampling=Resampling.nearest
)

# 2. Identify False Negative and True Positive
# Sim = 1 if h_reproj > 0.1
# SAR = 1 if sar_reproj > 0
print("Classifying pixels...")
sim_water = h_reproj > 0.1
sar_water = sar_reproj > 0

false_negative = (sar_water) & (~sim_water)

# 3. Find boundary between sim_water and false_negative
print("Finding boundary using binary_dilation...")
# Dilate sim_water to see where it intersects false_negative
# We want the boundary in false_negative that is adjacent to sim_water
# Or boundary in dem between them.
dilated_sim = binary_dilation(sim_water, iterations=2)
# Boundary = dilated sim intersects false_negative
boundary_mask = dilated_sim & false_negative

# Get DEM values at boundary
boundary_dem = dem[boundary_mask]

# Also get water levels in adjacent sim_water
dilated_fn = binary_dilation(false_negative, iterations=2)
adjacent_sim = dilated_fn & sim_water
adjacent_h = h_reproj[adjacent_sim]
adjacent_dem = dem[adjacent_sim]
adjacent_wl = adjacent_dem + adjacent_h

print(f"Total false negative pixels: {np.sum(false_negative)}")
print(f"Total boundary pixels: {np.sum(boundary_mask)}")

if len(boundary_dem) > 0:
    print(f"Boundary DEM - Mean: {np.mean(boundary_dem):.2f}, Max: {np.max(boundary_dem):.2f}, Min: {np.min(boundary_dem):.2f}")
if len(adjacent_wl) > 0:
    print(f"Adjacent Water Level - Mean: {np.mean(adjacent_wl):.2f}, Max: {np.max(adjacent_wl):.2f}")
    
# Let's find specific "walls" where boundary DEM is significantly higher than adjacent water level
# We can estimate average adjacent water level
avg_wl = np.mean(adjacent_wl) if len(adjacent_wl) > 0 else 0
walls = boundary_dem[boundary_dem > avg_wl]

print(f"Found {len(walls)} boundary pixels acting as walls (DEM > avg adjacent WL)")
if len(walls) > 0:
    print(f"Walls DEM - Mean: {np.mean(walls):.2f}, Max: {np.max(walls):.2f}")
    
print("Saving output rasters for inspection...")
# Save boundary to raster
profile = dem_meta.copy()
profile.update(dtype=rasterio.float32, count=1, nodata=-9999)

with rasterio.open('boundary_mask.tif', 'w', **profile) as dst:
    dst.write(boundary_mask.astype(np.float32), 1)

with rasterio.open('false_negative.tif', 'w', **profile) as dst:
    dst.write(false_negative.astype(np.float32), 1)

end_time = time.time()
print(f"Processing time: {end_time - start_time:.2f} seconds")

# Write report logic
report = f"""
# Phân tích ranh giới False Negative V38

## 1. Phương pháp
- Đọc file DEM, SAR, và kết quả mô phỏng V38 (nc).
- Đồng bộ hệ tọa độ và lưới (resampling) về cùng shape của DEM.
- Phân loại: Sim Water (h > 0.1m) và SAR Water (SAR > 0).
- Xác định False Negative (FN): Vùng có SAR nhưng không có Sim Water.
- Dùng `scipy.ndimage.binary_dilation` để tìm ranh giới tiếp giáp giữa Sim Water và FN.

## 2. Kết quả rà quét
- Thời gian xử lý: {end_time - start_time:.2f} giây
- Tổng số pixel False Negative: {np.sum(false_negative)}
- Số pixel ranh giới tiếp giáp: {np.sum(boundary_mask)}

### Phân tích cao độ
- Cao độ DEM trung bình tại ranh giới: {np.mean(boundary_dem) if len(boundary_dem) > 0 else 'N/A':.2f} m
- Mực nước trung bình tại vùng lân cận: {avg_wl:.2f} m
- Số điểm ranh giới là vật cản (DEM cao hơn mực nước lân cận): {len(walls)}

## 3. Đề xuất kịch bản V39
Dựa trên các vị trí vật cản (boundary_mask có DEM > mực nước), đề xuất "khoét" (breach) DEM tại các vị trí này xuống thấp hơn mực nước trung bình khoảng 0.5m để tạo kênh dẫn nước vào vùng False Negative, vì trên thực tế nước từ SAR đã vào được vùng này.
"""
with open('Boundary_Analysis_Report.md', 'w', encoding='utf-8') as f:
    f.write(report)
print("Saved report to Boundary_Analysis_Report.md")
