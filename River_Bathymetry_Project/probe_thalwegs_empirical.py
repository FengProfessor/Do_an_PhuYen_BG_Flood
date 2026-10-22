"""
Adversarial Probe for Monotonicity & Sinks across all 5 branches in thalweg_paths.json
"""
import json
import hashlib
import numpy as np
import rasterio

BASE_DEM_PATH = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
TRIAL_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Bathymetry_trial.tif"
PROD_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Full_River_Bathymetry.tif"
DELTA_Z_TRIAL_PATH = r"D:\VTP\River_Bathymetry_Project\delta_z_bathymetry.tif"
THALWEG_JSON_PATH = r"D:\VTP\River_Bathymetry_Project\thalweg_paths.json"
EXPECTED_BASE_SHA256 = "0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508"

# 1. Base DEM SHA-256
print("=== 1. Base DEM SHA-256 Verification ===")
h = hashlib.sha256()
with open(BASE_DEM_PATH, "rb") as f:
    while chunk := f.read(1024 * 1024):
        h.update(chunk)
base_sha = h.hexdigest()
print(f"Base DEM SHA-256: {base_sha}")
print(f"Match expected: {base_sha == EXPECTED_BASE_SHA256}")

# 2. Load DEMs
with rasterio.open(TRIAL_TIF_PATH) as src:
    trial_dem = src.read(1)
with rasterio.open(BASE_DEM_PATH) as src:
    base_dem = src.read(1)
with rasterio.open(DELTA_Z_TRIAL_PATH) as src:
    dz_trial = src.read(1)

with open(THALWEG_JSON_PATH, "r", encoding="utf-8") as f:
    thalweg_dict = json.load(f)

# 3. Analyze all keys in thalweg_dict
primary_branches = ["ba", "ban_thach", "ky_lo", "kenh_bac", "kenh_nam"]

print("\n=== 2. Probing Thalweg Monotonicity & Sinks on Trial DEM ===")
for b_name in primary_branches:
    if b_name not in thalweg_dict:
        print(f"ERROR: {b_name} not found in thalweg_paths.json!")
        continue
    path = [(int(r), int(c)) for r, c in thalweg_dict[b_name]]
    N = len(path)
    z_trial = np.array([trial_dem[r, c] for r, c in path], dtype=np.float64)
    z_base = np.array([base_dem[r, c] for r, c in path], dtype=np.float64)
    dz = np.array([dz_trial[r, c] for r, c in path], dtype=np.float64)

    # Compute step distances
    ds = np.zeros(N - 1, dtype=np.float64)
    for i in range(N - 1):
        dr = (path[i+1][0] - path[i][0]) * 30.0
        dc = (path[i+1][1] - path[i][1]) * 30.0
        ds[i] = np.hypot(dr, dc)
    
    diffs = np.diff(z_trial) # z[i+1] - z[i]
    slopes = diffs / ds       # dz / ds

    # Uphill steps at tolerances
    uphill_0m = np.where(diffs > 0.0)[0]
    uphill_0001m = np.where(diffs > 0.0001)[0] # 0.1 mm
    uphill_001m = np.where(diffs > 0.001)[0]   # 1 mm
    
    # dz/ds <= -0.0002 violations
    # Adverse slope: slope > 0. Non-downhill or shallow: slope > -0.0002
    slope_violations = np.where(slopes > -0.0002)[0]

    # Sinks at tolerances: z[k] < z[k-1] - tol and z[k] < z[k+1] - tol
    sinks_0m = []
    sinks_0001m = []
    sinks_001m = []
    for k in range(1, N - 1):
        if z_trial[k] < z_trial[k-1] and z_trial[k] < z_trial[k+1]:
            sinks_0m.append(k)
        if z_trial[k] < z_trial[k-1] - 0.0001 and z_trial[k] < z_trial[k+1] - 0.0001:
            sinks_0001m.append(k)
        if z_trial[k] < z_trial[k-1] - 0.001 and z_trial[k] < z_trial[k+1] - 0.001:
            sinks_001m.append(k)

    print(f"\n--- Branch: {b_name} (Length: {N} nodes) ---")
    print(f"  Headwater z: {z_trial[0]:.4f}m (base: {z_base[0]:.4f}m), Outlet z: {z_trial[-1]:.4f}m (base: {z_base[-1]:.4f}m)")
    print(f"  Max uphill step (max diff): {np.max(diffs):.8f}m")
    print(f"  Min downhill step (min diff): {np.min(diffs):.8f}m")
    print(f"  Max slope (dz/ds): {np.max(slopes):.8f}")
    print(f"  Min slope (dz/ds): {np.min(slopes):.8f}")
    print(f"  Uphill steps count (> 0.0m): {len(uphill_0m)}")
    print(f"  Uphill steps count (> 0.0001m / 0.1mm): {len(uphill_001m)}")
    print(f"  Uphill steps count (> 0.001m / 1mm): {len(uphill_001m)}")
    print(f"  Sink count (tol=0.0m): {len(sinks_0m)}")
    print(f"  Sink count (tol=0.0001m): {len(sinks_0001m)}")
    print(f"  Sink count (tol=0.001m): {len(sinks_001m)}")
    print(f"  dz/ds > -0.0002 count: {len(slope_violations)} (out of {N-1})")

    if len(uphill_0m) > 0:
        print(f"  Sample uphill steps (indices): {uphill_0m[:10]}")
        for idx in uphill_0m[:5]:
            print(f"    Node {idx} -> {idx+1}: z[{idx}]={z_trial[idx]:.5f} -> z[{idx+1}]={z_trial[idx+1]:.5f}, diff={diffs[idx]:.8f}m, ds={ds[idx]:.2f}m, slope={slopes[idx]:.6f}")

    if len(sinks_0m) > 0:
        print(f"  Sample sinks (indices): {sinks_0m[:10]}")
        for idx in sinks_0m[:5]:
            print(f"    Sink at {idx}: z[{idx-1}]={z_trial[idx-1]:.5f}, z[{idx}]={z_trial[idx]:.5f}, z[{idx+1}]={z_trial[idx+1]:.5f}")

    if len(slope_violations) > 0:
        # Check where slopes > -0.0002 occur
        print(f"  Sample slope > -0.0002 (indices): {slope_violations[:10]}")
        for idx in slope_violations[:5]:
            print(f"    Slope[{idx}]: diff={diffs[idx]:.8f}m, ds={ds[idx]:.2f}m, slope={slopes[idx]:.6f}")
