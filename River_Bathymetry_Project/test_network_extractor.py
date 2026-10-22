"""
Independent test suite for river_network_extractor.py and river_network_data.npz
Verifies channel continuity, thalweg completeness, mask geometry, and cryptographic integrity.
Milestone 1 Remediation (Iteration 2)
"""

import os
import sys
import json
import hashlib
import numpy as np
import rasterio

sys.path.insert(0, r"D:\VTP\River_Bathymetry_Project")
from river_network_extractor import (
    load_extracted_network,
    verify_base_dem_sha256,
    OUTPUT_NPZ_PATH,
    BASE_DEM_PATH,
    BASE_DEM_EXPECTED_SHA256,
    OSM_DIST_PATH
)

def test_npz_deliverable_exists():
    assert os.path.exists(OUTPUT_NPZ_PATH), f"Missing {OUTPUT_NPZ_PATH}!"
    assert os.path.getsize(OUTPUT_NPZ_PATH) > 0, "NPZ file is empty!"
    print("Test 1 PASS: river_network_data.npz exists and is non-empty.")

def test_base_dem_cryptographic_integrity():
    digest = verify_base_dem_sha256()
    assert digest == BASE_DEM_EXPECTED_SHA256
    print(f"Test 2 PASS: Base DEM SHA-256 intact: {digest}")

def test_loaded_network_contract():
    branch_data, dong_cam_mask = load_extracted_network()
    
    # Strictly the 2 independent continuous canal branches; pseudo-branch eliminated
    expected_branches = ["song_ba", "song_ban_thach", "song_ky_lo", "kenh_chinh_bac", "kenh_chinh_nam"]
    assert len(branch_data) == 5, f"branch_data must contain exactly 5 branches! Got {len(branch_data)}"
    for b in expected_branches:
        assert b in branch_data, f"Missing branch {b} in branch_data!"
    assert "kenh_dong_cam" not in branch_data, "Discontinuous pseudo-branch kenh_dong_cam must NOT be in branch_data!"
        
    assert dong_cam_mask.shape == (2100, 2100), f"Wrong shape for weir mask: {dong_cam_mask.shape}"
    assert dong_cam_mask.dtype == bool, f"Wrong dtype for weir mask: {dong_cam_mask.dtype}"
    assert np.sum(dong_cam_mask) == 187, f"Wrong cell count for weir mask: {np.sum(dong_cam_mask)}"
    
    weir_pts = np.argwhere(dong_cam_mask)
    assert np.min(weir_pts[:, 0]) == 1272 and np.max(weir_pts[:, 0]) == 1288, (
        f"Weir rows out of range: [{np.min(weir_pts[:, 0])}, {np.max(weir_pts[:, 0])}]"
    )
    assert np.min(weir_pts[:, 1]) == 1212 and np.max(weir_pts[:, 1]) == 1222, (
        f"Weir cols out of range: [{np.min(weir_pts[:, 1])}, {np.max(weir_pts[:, 1])}]"
    )

    # Check that weir encompasses crossing node (1278, 1217) at +5.50m MSL
    assert dong_cam_mask[1278, 1217], "Weir mask must contain crossing node (1278, 1217)!"
    with rasterio.open(BASE_DEM_PATH) as src:
        dem = src.read(1)
    crossing_z = float(dem[1278, 1217])
    assert abs(crossing_z - 5.50) < 0.05, f"Crossing node elevation mismatch: {crossing_z:.2f}m MSL (expected 5.50m)"

    # Check overlap with Sông Ba channel
    overlap_ba = np.sum(dong_cam_mask & branch_data["song_ba"].mask)
    assert overlap_ba > 0, "Weir mask must intersect Sông Ba channel corridor!"
    print(f"Test 3 PASS: Interface contract and Đập Đồng Cam weir mask geometry verified (rows 1272..1288, cols 1212..1222, crossing node (1278, 1217) at {crossing_z:.2f}m MSL, Sông Ba overlap={overlap_ba} cells).")

def test_thalweg_continuity_and_completeness():
    branch_data, _ = load_extracted_network()
    
    expected_nodes = {
        "song_ba": ((1233, 1), (1065, 2075)),
        "song_ban_thach": ((1783, 200), (1803, 2073)),
        "song_ky_lo": ((50, 633), (200, 1950)),
        "kenh_chinh_bac": ((1270, 1217), (975, 1402)),
        "kenh_chinh_nam": ((1360, 1207), (1539, 1900)),
    }
    
    with rasterio.open(BASE_DEM_PATH) as src:
        dem = src.read(1)
    with rasterio.open(OSM_DIST_PATH) as src:
        osm = src.read(1)
        
    for b_id, (inflow_exp, outlet_exp) in expected_nodes.items():
        b = branch_data[b_id]
        path = b.thalweg_rc
        N = len(path)
        
        # Node endpoints
        assert b.inflow_node == inflow_exp, f"{b_id}: Inflow mismatch {b.inflow_node} vs {inflow_exp}"
        assert b.outlet_node == outlet_exp, f"{b_id}: Outlet mismatch {b.outlet_node} vs {outlet_exp}"
        assert path[0] == inflow_exp, f"{b_id}: Path start mismatch {path[0]} vs {inflow_exp}"
        assert path[-1] == outlet_exp, f"{b_id}: Path end mismatch {path[-1]} vs {outlet_exp}"
        
        # 8-connectivity: strictly 0 gap jumps
        for i in range(1, N):
            dr = abs(path[i][0] - path[i-1][0])
            dc = abs(path[i][1] - path[i-1][1])
            step = max(dr, dc)
            assert step == 1, f"Gap jump at {b_id} step {i}: {path[i-1]} to {path[i]}"
            
        # Mask containment
        assert b.mask.shape == (2100, 2100)
        assert b.mask.dtype == bool
        for r, c in path:
            assert b.mask[r, c], f"{b_id}: thalweg cell ({r}, {c}) not in mask!"
            
        print(f"Test 4 PASS: {b_id:16s} - {N:5d} cells ({b.length_km:5.2f} km), 0 gaps, mask={np.sum(b.mask):6d} cells")

    # Specific check 1: Sông Bàn Thạch corridor mask recovered area (> 34,000 cells)
    bt_mask_cells = np.sum(branch_data["song_ban_thach"].mask)
    assert bt_mask_cells >= 34000, f"Sông Bàn Thạch corridor mask under-recovered! Got {bt_mask_cells} cells (expected >= 34,000)"
    print(f"   -> Sông Bàn Thạch corridor mask verified recovered: {bt_mask_cells:,} cells (8-conn fix confirmed).")

    # Specific check 2: Kênh chính Bắc has 0 cells forced across dry hills (OSM dist > 300m)
    kn_path = branch_data["kenh_chinh_bac"].thalweg_rc
    kn_dry_cells = [pt for pt in kn_path if osm[pt[0], pt[1]] > 300.0]
    assert len(kn_dry_cells) == 0, f"Kênh chính Bắc has {len(kn_dry_cells)} cells across dry hills (>300m OSM dist)!"
    print(f"   -> Kênh chính Bắc thalweg verified on natural waterway: {len(kn_dry_cells)} dry cells (artificial bridge eliminated).")

def test_npz_archive_arrays():
    data = np.load(OUTPUT_NPZ_PATH, allow_pickle=True)
    required_arrays = [
        "dong_cam_mask", "union_channel_mask",
        "mask_song_ba", "mask_song_ban_thach", "mask_song_ky_lo", "mask_kenh_chinh_bac", "mask_kenh_chinh_nam",
        "thalweg_song_ba", "thalweg_song_ban_thach", "thalweg_song_ky_lo", "thalweg_kenh_chinh_bac", "thalweg_kenh_chinh_nam",
        "metadata_json"
    ]
    for arr in required_arrays:
        assert arr in data, f"Missing array {arr} in npz!"
        
    meta = json.loads(str(data["metadata_json"]))
    assert "branches" in meta and len(meta["branches"]) == 5
    assert meta["base_dem_sha256"] == BASE_DEM_EXPECTED_SHA256
    print("Test 5 PASS: All required arrays and metadata present in river_network_data.npz.")

if __name__ == "__main__":
    test_npz_deliverable_exists()
    test_base_dem_cryptographic_integrity()
    test_loaded_network_contract()
    test_thalweg_continuity_and_completeness()
    test_npz_archive_arrays()
    print("\n>>> ALL TESTS PASSED SUCCESSFULLY (100% PASS) <<<")
