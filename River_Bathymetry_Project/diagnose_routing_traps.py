import json
import numpy as np
import rasterio

BASE_DEM_PATH = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
PROD_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Full_River_Bathymetry.tif"
DELTA_Z_PATH  = r"D:\VTP\River_Bathymetry_Project\delta_z_full_bathymetry.tif"
THALWEG_JSON_PATH = r"D:\VTP\River_Bathymetry_Project\thalweg_paths.json"

with rasterio.open(BASE_DEM_PATH) as src:
    base_dem = src.read(1).astype(np.float32)
with rasterio.open(PROD_TIF_PATH) as src:
    carved_dem = src.read(1).astype(np.float32)
with rasterio.open(DELTA_Z_PATH) as src:
    delta_z = src.read(1).astype(np.float32)
with open(THALWEG_JSON_PATH, "r", encoding="utf-8") as f:
    thalwegs = json.load(f)

# Analyze the 916 sinks:
# What are their depths, and where are they located?
carved_mask = (delta_z > 0.0)
carved_rcs = np.argwhere(carved_mask)
rows, cols = base_dem.shape
d_neighbors = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]
d_dists = [np.hypot(dr, dc) * 30.0 for dr, dc in d_neighbors]

terminal_outfalls = {
    (1065, 2075), # Đà Diễn
    (1803, 2073), # Đà Nông
    (200, 1950),  # Tiên Châu
    (975, 1402)   # Kênh Bắc terminus
}

sinks = []
thalweg_sinks = 0
off_thalweg_sinks = 0

thal_all_set = set()
for b in thalwegs.values():
    for r, c in b:
        thal_all_set.add((r, c))

for r, c in carved_rcs:
    if c >= 2090 or r <= 5 or r >= 2095 or (r, c) in terminal_outfalls:
        continue
    z_curr = carved_dem[r, c]
    if z_curr <= 0.0:
        continue
    neighbor_zs = [carved_dem[r + dr, c + dc] for dr, dc in d_neighbors if 0 <= r + dr < rows and 0 <= c + dc < cols]
    min_neighbor_z = min(neighbor_zs)
    if z_curr < min_neighbor_z - 1e-5:
        depth = min_neighbor_z - z_curr
        on_thal = (r, c) in thal_all_set
        if on_thal:
            thalweg_sinks += 1
        else:
            off_thalweg_sinks += 1
        sinks.append({
            "rc": (int(r), int(c)),
            "z": float(z_curr),
            "base_z": float(base_dem[r, c]),
            "dz": float(delta_z[r, c]),
            "min_neighbor_z": float(min_neighbor_z),
            "depth": float(depth),
            "on_thalweg": on_thal
        })

print(f"Total sinks in carved corridor: {len(sinks)}")
print(f"  On thalweg: {thalweg_sinks}")
print(f"  Off thalweg (in channel corridor): {off_thalweg_sinks}")

depths = [s["depth"] for s in sinks]
print(f"Sink depth stats: min={min(depths):.4f}m, median={np.median(depths):.4f}m, mean={np.mean(depths):.4f}m, max={max(depths):.4f}m")
print(f"Depth < 0.05m: {sum(d < 0.05 for d in depths)}")
print(f"Depth < 0.10m: {sum(d < 0.10 for d in depths)}")
print(f"Depth >= 0.50m: {sum(d >= 0.50 for d in depths)}")

# Now examine what happens to thalweg nodes during D8:
# Trace a trapped thalweg node on Sông Ba
def trace_d8(start_r, start_c):
    curr_r, curr_c = start_r, start_c
    path = [(curr_r, curr_c, float(carved_dem[curr_r, curr_c]))]
    visited = set([(curr_r, curr_c)])
    for step in range(500):
        if carved_dem[curr_r, curr_c] <= 0.0 or curr_c >= 2075 or (curr_r, curr_c) in terminal_outfalls:
            return "ESCAPED", path
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
            return "TRAPPED", path
        if best_next in visited:
            return "LOOP", path
        visited.add(best_next)
        curr_r, curr_c = best_next
        path.append((curr_r, curr_c, float(carved_dem[curr_r, curr_c])))
    return "MAX_STEPS", path

print("\nTracing first 5 trapped thalweg nodes on Sông Ba:")
trapped_shown = 0
for i, (r, c) in enumerate(thalwegs["song_ba"]):
    res, path = trace_d8(r, c)
    if res == "TRAPPED":
        print(f"Node {i} at ({r},{c}) [z={carved_dem[r,c]:.3f}m]: Trapped after {len(path)-1} steps at {path[-1][0:2]} [z={path[-1][2]:.3f}m]")
        # Show why it left thalweg or why trapped
        # print path
        for p_idx, (pr, pc, pz) in enumerate(path[:6]):
            in_thal = (pr, pc) in thal_all_set
            print(f"   step {p_idx}: ({pr}, {pc}) z={pz:.3f}m, in_thalweg={in_thal}")
        trapped_shown += 1
        if trapped_shown >= 3:
            break
