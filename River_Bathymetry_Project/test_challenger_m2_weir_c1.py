"""
Empirical Stress-Test: Milestone 2 Weir Lock & C1 Smoothness Verification
Author: challenger_m2_2 (teamwork_preview_challenger)

Checks:
1. Base DEM SHA-256 cryptographic hash preservation.
2. Đập Đồng Cam Weir Crest Invariance (AC-03):
   - dong_cam_mask (187 cells from river_network_data.npz): delta z == 0.000000m on all cells.
   - Thalweg crossing node (1278, 1217): Base DEM = +5.50m MSL, Carved DEM = +5.50m MSL, delta z == 0.0m.
3. Floodplain Invariance (AC-04 & AC-05):
   - delta z == 0.000000m outside channels (union_channel_mask).
   - Domain-wide raising check: 0 cells with delta z < 0.0 or Carved DEM > Base DEM.
   - Exact consistency check: Carved DEM == Base DEM - delta_z.
4. Bank Tangency & Perimeter Cliff Drops (AC-06):
   - 8-connected perimeter of carved area: carved & dilation(uncarved, 3x3).
   - Max perimeter cliff drop < 0.05m (C1 smoothness).
   - Detailed distribution: max, 99th percentile, mean, count >= 0.05m, count >= 0.01m.
   - Perimeter cliffs per branch (Sông Ba, Sông Bàn Thạch, Sông Kỳ Lộ, Canals).
"""

import os
import sys
import json
import hashlib
import numpy as np
import rasterio
from scipy.ndimage import binary_dilation

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DEM_PATH = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
NPZ_PATH = r"D:\VTP\River_Bathymetry_Project\river_network_data.npz"
DELTA_Z_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\delta_z_bathymetry.tif"
DELTA_Z_FULL_PATH = r"D:\VTP\River_Bathymetry_Project\delta_z_full_bathymetry.tif"
TRIAL_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Bathymetry_trial.tif"
FULL_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Full_River_Bathymetry.tif"

EXPECTED_BASE_SHA256 = "0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508"

def main():
    print("=" * 80)
    print("EMPIRICAL STRESS TEST: WEIR LOCK & C1 SMOOTHNESS (M2)")
    print("=" * 80)

    results = {}

    # 1. Base DEM SHA-256
    print("\n[CHECK 1] Base DEM Cryptographic Integrity Check")
    hasher = hashlib.sha256()
    with open(BASE_DEM_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    base_sha256 = hasher.hexdigest()
    base_hash_match = (base_sha256 == EXPECTED_BASE_SHA256)
    print(f"  Base DEM SHA-256: {base_sha256}")
    print(f"  Expected:        {EXPECTED_BASE_SHA256}")
    print(f"  Match: {base_hash_match}")
    results["base_dem_sha256"] = {
        "observed": base_sha256,
        "expected": EXPECTED_BASE_SHA256,
        "match": base_hash_match
    }

    # Load Rasters and NPZ
    print("\n[CHECK 2] Loading Rasters & Network Data")
    with rasterio.open(BASE_DEM_PATH) as src:
        base_dem = src.read(1)
        base_meta = src.meta.copy()

    with rasterio.open(DELTA_Z_TIF_PATH) as src:
        dz_dem = src.read(1)
        dz_meta = src.meta.copy()

    with rasterio.open(FULL_TIF_PATH) as src:
        carved_full_dem = src.read(1)
        full_meta = src.meta.copy()

    with rasterio.open(TRIAL_TIF_PATH) as src:
        carved_trial_dem = src.read(1)

    npz_data = np.load(NPZ_PATH, allow_pickle=True)
    dong_cam_mask = npz_data["dong_cam_mask"].astype(bool)
    union_channel_mask = npz_data["union_channel_mask"].astype(bool)
    mask_song_ba = npz_data["mask_song_ba"].astype(bool)
    mask_song_ban_thach = npz_data["mask_song_ban_thach"].astype(bool)
    mask_song_ky_lo = npz_data["mask_song_ky_lo"].astype(bool)
    mask_kenh_chinh_bac = npz_data["mask_kenh_chinh_bac"].astype(bool)
    mask_kenh_chinh_nam = npz_data["mask_kenh_chinh_nam"].astype(bool)

    # 2. Đập Đồng Cam Weir Crest Invariance
    print("\n[CHECK 3] Đập Đồng Cam Weir Crest Invariance (AC-03)")
    weir_cell_count = int(np.sum(dong_cam_mask))
    print(f"  dong_cam_mask total cells: {weir_cell_count} (Expected: 187)")
    
    weir_dz = dz_dem[dong_cam_mask]
    weir_max_dz = float(np.max(np.abs(weir_dz)))
    weir_sum_dz = float(np.sum(np.abs(weir_dz)))
    weir_nonzero_count = int(np.sum(weir_dz != 0.0))
    print(f"  Max |delta z| on 187 weir cells: {weir_max_dz:.10f} m")
    print(f"  Sum |delta z| on 187 weir cells: {weir_sum_dz:.10f} m")
    print(f"  Non-zero cells in weir mask:     {weir_nonzero_count} / {weir_cell_count}")

    # Crossing node (1278, 1217)
    node_r, node_c = 1278, 1217
    node_base_z = float(base_dem[node_r, node_c])
    node_full_z = float(carved_full_dem[node_r, node_c])
    node_trial_z = float(carved_trial_dem[node_r, node_c])
    node_dz = float(dz_dem[node_r, node_c])

    print(f"  Thalweg Crossing Node ({node_r}, {node_c}):")
    print(f"    Base DEM elevation:   {node_base_z:.6f} m MSL (Expected: +5.50m)")
    print(f"    Carved Full DEM:      {node_full_z:.6f} m MSL (Expected: +5.50m)")
    print(f"    Carved Trial DEM:     {node_trial_z:.6f} m MSL (Expected: +5.50m)")
    print(f"    Delta z:              {node_dz:.10f} m (Expected: 0.000000m)")

    weir_pass = (weir_cell_count == 187 and weir_max_dz == 0.0 and weir_nonzero_count == 0 and
                 abs(node_base_z - 5.50) < 1e-4 and abs(node_full_z - 5.50) < 1e-4 and node_dz == 0.0)

    results["weir_crest_invariance"] = {
        "pass": bool(weir_pass),
        "weir_cell_count": weir_cell_count,
        "weir_max_abs_dz": weir_max_dz,
        "weir_sum_abs_dz": weir_sum_dz,
        "weir_nonzero_cells": weir_nonzero_count,
        "crossing_node": {
            "row": node_r,
            "col": node_c,
            "base_z": node_base_z,
            "carved_full_z": node_full_z,
            "carved_trial_z": node_trial_z,
            "delta_z": node_dz
        }
    }

    # 3. Floodplain Invariance (AC-04 & AC-05)
    print("\n[CHECK 4] Floodplain Invariance (AC-04 & AC-05)")
    # delta_z outside channels
    outside_channel_mask = ~union_channel_mask
    outside_channel_cells = int(np.sum(outside_channel_mask))
    outside_channel_dz = dz_dem[outside_channel_mask]
    outside_max_abs_dz = float(np.max(np.abs(outside_channel_dz)))
    outside_nonzero_cells = int(np.sum(outside_channel_dz != 0.0))

    print(f"  Outside channel cells: {outside_channel_cells:,} ({outside_channel_cells/dz_dem.size*100:.2f}%)")
    print(f"  Max |delta z| outside channel mask: {outside_max_abs_dz:.10f} m")
    print(f"  Non-zero cells outside channels:    {outside_nonzero_cells}")

    # Domain-wide raising check: delta z < 0 or carved > base
    raising_cells_dz = int(np.sum(dz_dem < 0.0))
    min_dz = float(np.min(dz_dem))
    raising_cells_full = int(np.sum(carved_full_dem > base_dem + 1e-5))
    raising_cells_trial = int(np.sum(carved_trial_dem > base_dem + 1e-5))

    print(f"  Domain-wide min delta z: {min_dz:.10f} m")
    print(f"  Cells with delta z < 0.0: {raising_cells_dz}")
    print(f"  Cells where Carved Full DEM > Base DEM: {raising_cells_full}")
    print(f"  Cells where Carved Trial DEM > Base DEM: {raising_cells_trial}")

    # Consistency check: base_dem - carved_dem == dz_dem
    diff_full_consistency = np.abs((base_dem - carved_full_dem) - dz_dem)
    max_diff_full_consistency = float(np.max(diff_full_consistency))
    print(f"  Max discrepancy |(Base - Carved) - delta_z|: {max_diff_full_consistency:.10f} m")

    floodplain_pass = (outside_max_abs_dz == 0.0 and outside_nonzero_cells == 0 and
                       raising_cells_dz == 0 and raising_cells_full == 0 and max_diff_full_consistency < 1e-4)

    results["floodplain_invariance"] = {
        "pass": bool(floodplain_pass),
        "outside_channel_cells": outside_channel_cells,
        "outside_max_abs_dz": outside_max_abs_dz,
        "outside_nonzero_cells": outside_nonzero_cells,
        "min_delta_z": min_dz,
        "raising_cells_dz_lt_0": raising_cells_dz,
        "raising_cells_full": raising_cells_full,
        "max_diff_full_consistency": max_diff_full_consistency
    }

    # 4. Bank Tangency & 8-Connected Perimeter Cliff Drops (AC-06)
    print("\n[CHECK 5] Bank Tangency & 8-Connected Perimeter Cliff Drops (AC-06)")
    # Carved area is delta_z > 0
    carved_mask = (dz_dem > 0.0)
    uncarved_mask = ~carved_mask
    carved_cell_count = int(np.sum(carved_mask))
    print(f"  Total carved cells: {carved_cell_count:,}")

    # 8-connected dilation of uncarved
    structure_8 = np.ones((3, 3), dtype=bool)
    dilated_uncarved_8 = binary_dilation(uncarved_mask, structure=structure_8)
    perimeter_mask_8 = carved_mask & dilated_uncarved_8
    perimeter_count_8 = int(np.sum(perimeter_mask_8))
    print(f"  8-connected perimeter cells: {perimeter_count_8:,}")

    # Sample perimeter delta_z
    p_dz = dz_dem[perimeter_mask_8]
    p_max = float(np.max(p_dz)) if len(p_dz) > 0 else 0.0
    p_min = float(np.min(p_dz)) if len(p_dz) > 0 else 0.0
    p_mean = float(np.mean(p_dz)) if len(p_dz) > 0 else 0.0
    p_median = float(np.median(p_dz)) if len(p_dz) > 0 else 0.0
    p_p95 = float(np.percentile(p_dz, 95)) if len(p_dz) > 0 else 0.0
    p_p99 = float(np.percentile(p_dz, 99)) if len(p_dz) > 0 else 0.0

    count_ge_005 = int(np.sum(p_dz >= 0.05))
    count_ge_001 = int(np.sum(p_dz >= 0.01))
    count_ge_0001 = int(np.sum(p_dz >= 0.001))

    print(f"  Perimeter Cliff Distribution:")
    print(f"    Max cliff drop:        {p_max:.6f} m (Requirement: < 0.05m)")
    print(f"    99th percentile cliff: {p_p99:.6f} m")
    print(f"    95th percentile cliff: {p_p95:.6f} m")
    print(f"    Mean cliff drop:       {p_mean:.6f} m")
    print(f"    Median cliff drop:     {p_median:.6f} m")
    print(f"    Min cliff drop:        {p_min:.6f} m")
    print(f"    Count >= 0.05m:        {count_ge_005}")
    print(f"    Count >= 0.01m:        {count_ge_001}")
    print(f"    Count >= 0.001m:       {count_ge_0001}")

    # Per-branch perimeter check
    branches = {
        "song_ba": mask_song_ba,
        "song_ban_thach": mask_song_ban_thach,
        "song_ky_lo": mask_song_ky_lo,
        "kenh_chinh_bac": mask_kenh_chinh_bac,
        "kenh_chinh_nam": mask_kenh_chinh_nam
    }
    per_branch_cliffs = {}
    for b_name, b_mask in branches.items():
        b_carved = (dz_dem > 0.0) & b_mask
        b_p_mask = b_carved & dilated_uncarved_8
        b_p_dz = dz_dem[b_p_mask]
        b_max = float(np.max(b_p_dz)) if len(b_p_dz) > 0 else 0.0
        b_mean = float(np.mean(b_p_dz)) if len(b_p_dz) > 0 else 0.0
        b_ge_005 = int(np.sum(b_p_dz >= 0.05))
        per_branch_cliffs[b_name] = {
            "perimeter_cells": int(np.sum(b_p_mask)),
            "max_cliff_m": b_max,
            "mean_cliff_m": b_mean,
            "count_ge_005m": b_ge_005
        }
        print(f"    Branch '{b_name}': perimeter={int(np.sum(b_p_mask)):,}, max={b_max:.6f}m, mean={b_mean:.6f}m, >=0.05m: {b_ge_005}")

    bank_tangency_pass = (p_max < 0.05 and count_ge_005 == 0)

    results["bank_tangency_cliff"] = {
        "pass": bool(bank_tangency_pass),
        "total_carved_cells": carved_cell_count,
        "perimeter_cells_8conn": perimeter_count_8,
        "max_cliff_m": p_max,
        "min_cliff_m": p_min,
        "mean_cliff_m": p_mean,
        "median_cliff_m": p_median,
        "p95_cliff_m": p_p95,
        "p99_cliff_m": p_p99,
        "count_ge_005m": count_ge_005,
        "count_ge_001m": count_ge_001,
        "per_branch": per_branch_cliffs
    }

    # 5. Overall Verdict
    all_pass = (base_hash_match and weir_pass and floodplain_pass and bank_tangency_pass)
    verdict = "APPROVE" if all_pass else "REQUEST_CHANGES"
    print("\n" + "=" * 80)
    print(f"FINAL AUDIT VERDICT: {verdict}")
    print("=" * 80)
    results["overall_verdict"] = verdict
    results["all_pass"] = bool(all_pass)

    out_json = r"D:\VTP\River_Bathymetry_Project\empirical_m2_weir_c1_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Detailed results saved to: {out_json}")

    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
