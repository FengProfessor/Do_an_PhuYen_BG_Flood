import json
import numpy as np
import rasterio

PROD_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Full_River_Bathymetry.tif"
THALWEG_JSON_PATH = r"D:\VTP\River_Bathymetry_Project\thalweg_paths.json"

with rasterio.open(PROD_TIF_PATH) as src:
    carved_dem = src.read(1).astype(np.float32)
with open(THALWEG_JSON_PATH, "r", encoding="utf-8") as f:
    thalwegs = json.load(f)

d_neighbors = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]
d_dists = [np.hypot(dr, dc) * 30.0 for dr, dc in d_neighbors]
rows, cols = carved_dem.shape

def route_d8(r, c):
    curr_r, curr_c = r, c
    visited = set([(curr_r, curr_c)])
    for step in range(5000):
        if carved_dem[curr_r, curr_c] <= 0.0 or curr_c >= 2075 or (curr_r, curr_c) == (1065, 2075):
            return "ESCAPED", step
        curr_z = carved_dem[curr_r, curr_c]
        best_slope = 0.0
        best_next = None
        for (dr, dc), dist in zip(d_neighbors, d_dists):
            nr, nc = curr_r + dr, curr_c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                nz = carved_dem[nr, nc]
                slope = (curr_z - nz) / dist
                if slope > best_slope:
                    best_slope = slope
                    best_next = (nr, nc)
        if best_next is None or best_slope <= 0.0:
            return "TRAPPED", step
        if best_next in visited:
            return "LOOP", step
        visited.add(best_next)
        curr_r, curr_c = best_next
    return "MAX_STEPS", step

# Check Sông Ba upstream vs downstream of Đập Đồng Cam (around index 1590)
ba_path = thalwegs["song_ba"]
us_esc, us_trap = 0, 0
ds_esc, ds_trap = 0, 0

for i, (r, c) in enumerate(ba_path):
    status, _ = route_d8(r, c)
    if i < 1590:
        if status == "ESCAPED": us_esc += 1
        else: us_trap += 1
    else:
        if status == "ESCAPED": ds_esc += 1
        else: ds_trap += 1

print(f"Sông Ba Upstream of Đồng Cam (0..1589): Escaped={us_esc}, Trapped={us_trap}")
print(f"Sông Ba Downstream of Đồng Cam (1590..end): Escaped={ds_esc}, Trapped={ds_trap}")
