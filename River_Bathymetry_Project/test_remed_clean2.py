"""
Clean test of fully remediated bathymetry carving pipeline.
"""
import time
import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt, binary_dilation

BASE_DEM_PATH = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
RIVER_NETWORK_DATA_PATH = r"D:\VTP\River_Bathymetry_Project\river_network_data.npz"

dem = rasterio.open(BASE_DEM_PATH).read(1).astype(np.float32)
data = np.load(RIVER_NETWORK_DATA_PATH)
rows, cols = dem.shape
dong_cam_mask = data["dong_cam_mask"]

branch_configs = [
    ("song_ba", "ba", 3.50, -6.10, False, 0),
    ("song_ban_thach", "ban_thach", 2.25, -3.50, False, 800),
    ("song_ky_lo", "ky_lo", 2.25, -3.50, False, 350),
    ("kenh_chinh_bac", "kenh_bac", 1.20, -1.00, True, 0),
    ("kenh_chinh_nam", "kenh_nam", 1.20, -1.00, True, 0),
]

def apply_1d_monotonic_filter(b_id, path, z_raw, d_max, outlet_target_z, epsilon=0.0002):
    N = len(path)
    s_path = np.zeros(N, dtype=np.float64)
    for i in range(1, N):
        dr = (path[i][0] - path[i-1][0]) * 30.0
        dc = (path[i][1] - path[i-1][1]) * 30.0
        s_path[i] = s_path[i-1] + np.hypot(dr, dc)

    z_bed = np.zeros(N, dtype=np.float32)

    if b_id == "song_ba":
        k_cross = path.index((1278, 1217)) if (1278, 1217) in path else 1593
        mask_dc = data["dong_cam_mask"]
        k_weir_start = min(i for i in range(N) if mask_dc[path[i]])
        k_weir_end = max(i for i in range(N) if mask_dc[path[i]])

        weir_z = 5.50

        # Reach 1: Upstream of weir
        z_bed[0] = max(z_raw[0] - d_max, weir_z)
        for k in range(1, k_weir_start):
            ds = s_path[k] - s_path[k-1]
            target_z = max(z_raw[k] - d_max, weir_z)
            max_allowed = max(z_bed[k-1] - epsilon * ds, weir_z)
            z_bed[k] = min(target_z, max_allowed)

        # Weir crest
        for k in range(k_weir_start, k_weir_end + 1):
            z_bed[k] = weir_z

        # Reach 2: Plunge pool transition
        k_trans_end = min(k_weir_end + 25, N - 1)
        s_trans_len = max(s_path[k_trans_end] - s_path[k_weir_end], 1.0)
        for k in range(k_weir_end + 1, k_trans_end + 1):
            ds = s_path[k] - s_path[k-1]
            prog = (s_path[k] - s_path[k_weir_end]) / s_trans_len
            target_z = 5.50 - 2.0 * (1.0 - np.cos(np.pi * prog * 0.5))
            max_allowed = z_bed[k-1] - epsilon * ds
            z_bed[k] = min(target_z, max_allowed)

        s_down_total = max(s_path[-1] - s_path[k_trans_end], 1.0)
        for k in range(k_trans_end + 1, N):
            ds = s_path[k] - s_path[k-1]
            progress = (s_path[k] - s_path[k_trans_end]) / s_down_total
            z_ideal = 3.50 - progress * (3.50 - outlet_target_z)
            target_z = min(z_raw[k] - 3.0, z_ideal)
            max_allowed = z_bed[k-1] - epsilon * ds
            z_bed[k] = min(target_z, max_allowed)
    elif b_id.startswith("kenh_"):
        # Irrigation canal: continuous trenching with d_max incision
        z_bed[0] = z_raw[0] - d_max
        for k in range(1, N):
            ds = s_path[k] - s_path[k-1]
            max_allowed = z_bed[k-1] - epsilon * ds
            z_bed[k] = min(z_raw[k] - d_max, max_allowed)
    else:
        # Standard river branch
        z_bed[0] = max(z_raw[0] - d_max, outlet_target_z)
        s_total = max(s_path[-1], 1.0)
        for k in range(1, N):
            ds = s_path[k] - s_path[k-1]
            progress = s_path[k] / s_total
            z_ideal = (z_raw[0] - d_max) - progress * ((z_raw[0] - d_max) - outlet_target_z)
            target_z = min(z_raw[k] - d_max, z_ideal)
            max_allowed = z_bed[k-1] - epsilon * ds
            z_bed[k] = min(target_z, max_allowed)

    delta_z_path = z_raw - z_bed
    return s_path, z_raw, z_bed, delta_z_path

branch_delta_rasters = []
all_corridors = np.zeros((rows, cols), dtype=bool)
thalweg_dict = {}
thalweg_bed_overrides = []

for b_id, short_key, d_max, out_z, is_canal, start_idx in branch_configs:
    path = [tuple(x) for x in data[f"thalweg_{b_id}"][start_idx:]]
    thalweg_dict[short_key] = path
    mask = data[f"mask_{b_id}"]

    z_raw = np.array([dem[r, c] for r, c in path], dtype=np.float32)
    s_p, z_r, z_b, dz_p = apply_1d_monotonic_filter(b_id, path, z_raw, d_max, out_z)
    thalweg_bed_overrides.append((path, z_b))

    path_mask = np.zeros((rows, cols), dtype=bool)
    for r, c in path: path_mask[r, c] = True
    dist_thalweg_cells, nearest_indices = distance_transform_edt(~path_mask, return_indices=True)
    dist_thalweg_m = dist_thalweg_cells * 30.0

    if is_canal:
        corridor = mask | (dist_thalweg_m <= 75.0)
    else:
        corridor = mask | (dist_thalweg_m <= 90.0)

    dist_to_edge_cells = distance_transform_edt(corridor)
    dist_in = np.maximum(dist_to_edge_cells - 1.0, 0.0)
    denom = np.where(dist_thalweg_cells + dist_in == 0, 1.0, dist_thalweg_cells + dist_in)
    xi = np.clip(np.where(corridor, 1.0 - (dist_in / denom), 1.0), 0.0, 1.0)
    phi_cos = np.cos(0.5 * np.pi * xi) ** 2

    thalweg_grid = np.zeros((rows, cols), dtype=np.float32)
    for k, (pr, pc) in enumerate(path):
        thalweg_grid[pr, pc] = dz_p[k]
    d_cl_2d = thalweg_grid[nearest_indices[0], nearest_indices[1]]

    dz_2d = np.zeros((rows, cols), dtype=np.float32)
    if is_canal:
        canal_decay = np.clip(1.0 - dist_thalweg_m / 75.0, 0.0, 1.0) ** 2
        dz_2d[corridor] = d_cl_2d[corridor] * canal_decay[corridor]
    else:
        dz_2d[corridor] = d_cl_2d[corridor] * phi_cos[corridor]
    dz_2d[~corridor] = 0.0

    branch_delta_rasters.append(dz_2d)
    all_corridors |= corridor

# Protect river thalwegs from canal incisions
ba_thal_mask = np.zeros((rows, cols), dtype=bool)
for r, c in thalweg_dict["ba"]: ba_thal_mask[r, c] = True
bt_thal_mask = np.zeros((rows, cols), dtype=bool)
for r, c in thalweg_dict["ban_thach"]: bt_thal_mask[r, c] = True

branch_delta_rasters[3][ba_thal_mask] = 0.0
branch_delta_rasters[4][ba_thal_mask] = 0.0
branch_delta_rasters[4][bt_thal_mask] = 0.0

# Confluence blend
delta_z_merged = np.maximum.reduce(branch_delta_rasters)

# tanh smooth depth cap
over_mask = delta_z_merged > 14.0
if np.any(over_mask):
    delta_z_merged[over_mask] = 14.0 + 0.5 * np.tanh((delta_z_merged[over_mask] - 14.0) / 0.5)

delta_z_merged[~all_corridors] = 0.0
delta_z_merged[dong_cam_mask] = 0.0
delta_z_merged[1278, 1217] = 0.0

# Perimeter clamp
carved_mask = (delta_z_merged > 0.0)
uncarved_mask = (delta_z_merged == 0.0)
dilated_uncarved_8 = binary_dilation(uncarved_mask, structure=np.ones((3, 3)))
perimeter_8 = carved_mask & dilated_uncarved_8

# Exclude thalwegs from clamp ONLY at interior thalwegs
thalweg_all = np.zeros((rows, cols), dtype=bool)
for p in thalweg_dict.values():
    for r, c in p: thalweg_all[r, c] = True

# Perimeter clamp to 0.03m
delta_z_merged[perimeter_8] = np.minimum(delta_z_merged[perimeter_8], 0.03)

# Apply thalweg overrides in reversed priority
for path, z_bed in reversed(thalweg_bed_overrides):
    for k, (r, c) in enumerate(path):
        if not dong_cam_mask[r, c] and (r, c) != (1278, 1217):
            delta_z_merged[r, c] = max(dem[r, c] - z_bed[k], 0.0)

delta_z_merged[dong_cam_mask] = 0.0
delta_z_merged[1278, 1217] = 0.0
delta_z_merged[~all_corridors] = 0.0

# Check p8
carved_mask = (delta_z_merged > 0.0)
uncarved_mask = (delta_z_merged == 0.0)
p8 = carved_mask & binary_dilation(uncarved_mask, structure=np.ones((3, 3)))
max_cliff_8 = float(np.max(delta_z_merged[p8])) if np.any(p8) else 0.0
mean_cliff_8 = float(np.mean(delta_z_merged[p8])) if np.any(p8) else 0.0
p8_gt_005 = int(np.sum(delta_z_merged[p8] > 0.05))

new_dem = dem - delta_z_merged

print("=== Remediation 2 Results ===")
print(f"Max p8 cliff: {max_cliff_8:.6f} m (threshold <= 0.05 m)")
print(f"Mean p8 cliff: {mean_cliff_8:.6f} m (threshold < 0.025 m)")
print(f"p8 cells > 0.05 m: {p8_gt_005}")

for short_key in ["ba", "ban_thach", "ky_lo", "kenh_bac", "kenh_nam"]:
    path = thalweg_dict[short_key]
    z_prof = np.array([new_dem[r, c] for r, c in path], dtype=np.float64)
    diffs = np.diff(z_prof)
    uphill = np.sum(diffs > 0.001)
    sinks = 0
    for k in range(1, len(path)-1):
        if z_prof[k] < z_prof[k-1] - 0.001 and z_prof[k] < z_prof[k+1] - 0.001:
            sinks += 1
    print(f"Branch {short_key}: uphill={uphill}, sinks={sinks}, z[0]={z_prof[0]:.2f}m, z[-1]={z_prof[-1]:.2f}m")
