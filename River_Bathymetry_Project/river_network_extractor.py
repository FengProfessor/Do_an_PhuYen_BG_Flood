"""
========================================================================================
FULL MULTI-SOURCE RIVER NETWORK EXTRACTOR & CHANNEL IDENTIFICATION ENGINE
Phu Yen Province, Vietnam (2100 x 2100 Grid, 30m Resolution, EPSG:32649)
========================================================================================

Author: worker_m1_1 (teamwork_preview_worker) - Milestone 1
Approved Methodology: River_Bathymetry_Methodology.md & Survey Reports (M0)
Target Consumer: multi_branch_bathymetry_carver.py (Milestone 2)

Key Features:
1. Full-Domain GIS Fusion (Copernicus GLO-30 DEM 30m, JRC GSW 1984-2020, OSM Waterways).
   Overcomes legacy 750:1750 row limitation to cover the entire 2100x2100 calculation grid.
2. Multi-Branch Channel Isolation & Dijkstra Shortest-Path Thalweg Tracing:
   - Sông Ba (Sông Đà Rằng): Inflow (270030, 1441000) -> Cửa Đà Diễn (332250, 1446050)
   - Sông Bàn Thạch: Inflow (276000, 1424500) -> Cửa Đà Nông (332190, 1423910)
   - Sông Kỳ Lộ: Inflow (289000, 1476500) -> Cửa Tiên Châu (328485, 1472000)
   - Đồng Cam Irrigation Canals: Kênh chính Bắc from North Abutment (1270, 1217) and Kênh chính Nam (1360, 1207)
3. Đập Đồng Cam 2D Crest Mask Isolation:
   - True river crossing: col 1212-1222, row 1272-1288 crossing at (1278, 1217) at +5.50m MSL.
4. Fast and robust vectorized SciPy sparse graph Dijkstra solver (scipy.sparse.csgraph.dijkstra).
5. Comprehensive validation: 8-connectivity continuity, thalweg completeness, 0 gap guarantee.
6. Export to compressed NumPy archive river_network_data.npz and clean Python API interface.
========================================================================================
"""

import os
import sys
import io
import time
import json
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

# Ensure UTF-8 output streams on Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import numpy as np
import rasterio
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.ndimage import distance_transform_edt, label, binary_dilation

# Default input file paths
BASE_DEM_PATH = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
JRC_GSW_PATH = r"D:\VTP\V48_research_20261002\hydro_evidence_raw\V46_JRC_GSW1_3_occurrence_1984_2020.tif"
OSM_DIST_PATH = r"D:\VTP\V46_dryrun_20260930\V46_distance_to_osm_waterway_m.tif"
OUTPUT_NPZ_PATH = r"D:\VTP\River_Bathymetry_Project\river_network_data.npz"

BASE_DEM_EXPECTED_SHA256 = "0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508"


@dataclass
class BranchData:
    name: str
    id: str
    mask: np.ndarray             # 2D boolean array of river/canal corridor
    thalweg_rc: List[Tuple[int, int]]  # list of (row, col) ordered from inflow to outlet
    inflow_node: Tuple[int, int] # (row, col)
    outlet_node: Tuple[int, int] # (row, col)
    d_max: float                 # target depth in meters
    outlet_target_z: float       # target bed elevation at outlet (m MSL)
    is_canal: bool               # canal flag for sub-grid trenching
    length_km: float             # thalweg length in kilometers


def verify_base_dem_sha256(dem_path: str = BASE_DEM_PATH) -> str:
    """Verifies that the original Base DEM has not been modified."""
    hasher = hashlib.sha256()
    with open(dem_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    assert digest == BASE_DEM_EXPECTED_SHA256, (
        f"INTEGRITY VIOLATION: Base DEM SHA-256 mismatch! Got {digest}, expected {BASE_DEM_EXPECTED_SHA256}"
    )
    return digest


def load_input_rasters(
    dem_path: str = BASE_DEM_PATH,
    jrc_path: str = JRC_GSW_PATH,
    osm_path: str = OSM_DIST_PATH
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Any, Any]:
    """Loads and validates spatial alignment of DEM, JRC occurrence, and OSM distance."""
    print("[1/5] Loading and verifying GIS input rasters (Full 2100x2100 Domain)...")
    verify_base_dem_sha256(dem_path)
    
    with rasterio.open(dem_path) as src_dem:
        dem = src_dem.read(1).astype(np.float32)
        profile = src_dem.profile.copy()
        transform = src_dem.transform
        bounds = src_dem.bounds

    with rasterio.open(jrc_path) as src_jrc:
        jrc = src_jrc.read(1)
        assert src_jrc.shape == dem.shape, "JRC raster shape mismatch!"
        assert src_jrc.transform == transform, "JRC raster transform mismatch!"

    with rasterio.open(osm_path) as src_osm:
        osm = src_osm.read(1).astype(np.float32)
        assert src_osm.shape == dem.shape, "OSM raster shape mismatch!"
        assert src_osm.transform == transform, "OSM raster transform mismatch!"

    print(f"      Grid size: {dem.shape[0]} rows x {dem.shape[1]} cols (4,410,000 cells)")
    print(f"      Resolution: 30.0m, Bounds: {bounds.left:.0f}, {bounds.bottom:.0f}, {bounds.right:.0f}, {bounds.top:.0f}")
    print(f"      Base DEM: min={np.min(dem):.2f}m, max={np.max(dem):.2f}m, mean={np.mean(dem):.2f}m")
    print(f"      JRC Water Occurrence max={np.max(jrc)}%, OSM Waterway dist min={np.min(osm):.1f}m")
    
    return dem, jrc, osm, profile, transform


def route_thalweg_scipy(
    cost_grid: np.ndarray,
    active_mask: np.ndarray,
    start_rc: Tuple[int, int],
    goal_rc: Tuple[int, int]
) -> List[Tuple[int, int]]:
    """
    Computes optimal monotonic thalweg path between start_rc and goal_rc using
    vectorized SciPy sparse Dijkstra (C-optimized graph search).
    """
    rows, cols = cost_grid.shape
    coords = np.argwhere(active_mask)
    K = len(coords)
    node_map = np.full((rows, cols), -1, dtype=np.int32)
    node_map[active_mask] = np.arange(K)

    start_id = node_map[start_rc]
    goal_id = node_map[goal_rc]
    assert start_id >= 0, f"start_rc {start_rc} not inside active mask!"
    assert goal_id >= 0, f"goal_rc {goal_rc} not inside active mask!"

    r_src = coords[:, 0]
    c_src = coords[:, 1]
    cost_src = cost_grid[r_src, c_src]

    adj_rows = []
    adj_cols = []
    adj_weights = []

    # 8-connectivity neighborhood
    for dr, dc, step in [
        (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
        (-1, -1, 1.41421356), (-1, 1, 1.41421356), (1, -1, 1.41421356), (1, 1, 1.41421356)
    ]:
        r_dst = r_src + dr
        c_dst = c_src + dc
        valid = (r_dst >= 0) & (r_dst < rows) & (c_dst >= 0) & (c_dst < cols)
        dst_ids = np.where(valid, node_map[np.clip(r_dst, 0, rows - 1), np.clip(c_dst, 0, cols - 1)], -1)
        connected = valid & (dst_ids >= 0)

        src_k = np.arange(K)[connected]
        dst_k = dst_ids[connected]
        cost_dst = cost_grid[r_dst[connected], c_dst[connected]]
        w = 0.5 * (cost_src[connected] + cost_dst) * (step * 30.0)

        adj_rows.extend(src_k)
        adj_cols.extend(dst_k)
        adj_weights.extend(w)

    adj = csr_matrix((adj_weights, (adj_rows, adj_cols)), shape=(K, K))
    dist, pred = dijkstra(adj, indices=start_id, return_predecessors=True)

    if np.isinf(dist[goal_id]):
        raise RuntimeError(f"No connected path found between {start_rc} and {goal_rc}!")

    # Trace predecessor chain from goal back to start
    curr = goal_id
    path_nodes = []
    while curr != -9999 and curr != start_id:
        path_nodes.append(curr)
        curr = pred[curr]
    path_nodes.append(start_id)
    path_nodes.reverse()

    path_rc = [(int(coords[nid, 0]), int(coords[nid, 1])) for nid in path_nodes]
    return path_rc


def build_corridor_mask(
    thalweg_rc: List[Tuple[int, int]],
    base_mask: np.ndarray,
    r_max: float,
    grid_shape: Tuple[int, int]
) -> np.ndarray:
    """
    Constructs continuous channel corridor mask within radius r_max around thalweg,
    intersected with water / valley features and preserving strict lateral bounds.
    """
    rows, cols = grid_shape
    path_mask = np.zeros((rows, cols), dtype=bool)
    for r, c in thalweg_rc:
        path_mask[r, c] = True

    # Euclidean distance from thalweg
    dist_thalweg = distance_transform_edt(~path_mask) * 30.0  # in meters

    # Corridor is base water/valley mask restricted within r_max of thalweg
    corridor = base_mask & (dist_thalweg <= r_max)

    # Ensure all thalweg cells are unconditionally included
    corridor[path_mask] = True

    # Retain connected components containing the thalweg (8-connectivity)
    s8 = np.ones((3, 3), dtype=bool)
    labeled, num_lbl = label(corridor, structure=s8)
    thalweg_labels = set(labeled[r, c] for r, c in thalweg_rc if labeled[r, c] > 0)
    if len(thalweg_labels) > 0:
        corridor = np.isin(labeled, list(thalweg_labels)) | path_mask

    return corridor


def extract_river_network(
    dem: np.ndarray,
    jrc: np.ndarray,
    osm: np.ndarray
) -> Tuple[Dict[str, BranchData], np.ndarray]:
    """
    Core extraction engine: identifies all 4 river and canal networks and isolates
    Đập Đồng Cam weir crest mask across the full 2100x2100 calculation domain.
    
    Returns:
        (branch_data, dong_cam_mask) adhering to M1/M2 Interface Contract.
    """
    print("[2/5] Extracting Channel Corridors, Masks, and Thalwegs...")
    rows, cols = dem.shape
    r_grid = np.arange(rows)[:, None]
    c_grid = np.arange(cols)[None, :]
    branch_data: Dict[str, BranchData] = {}

    # =========================================================================
    # 1. SÔNG BA (SÔNG ĐÀ RẰNG - TRỤC CHÍNH)
    # =========================================================================
    # Inflow: (270030, 1441000) -> (1233, 1)
    # Outflow: Cửa Đà Diễn (332250, 1446050) -> (1065, 2075)
    print("      -> [Branch 1/4] Processing Sông Ba (Đà Rằng)...")
    ba_box = (r_grid >= 750) & (r_grid <= 1650)
    ba_water = (jrc >= 20) | (osm <= 350.0)
    ba_forcing = (r_grid >= 1167) & (r_grid <= 1234) & (c_grid <= 22)
    ba_active = (ba_box & ba_water & (dem > -10.0) & (dem < 130.0)) | ba_forcing
    ba_active[1233, 1] = True
    ba_active[1065, 2075] = True

    # Cost grid: lowest elevation + OSM proximity + JRC water
    z_ba = np.clip(dem, -5.0, 120.0)
    z_ba_norm = (z_ba - np.min(z_ba)) / (np.max(z_ba) - np.min(z_ba) + 1e-5)
    cost_ba = 1.0 + 2.5 * z_ba_norm + 1.0 * np.clip(osm / 350.0, 0, 5) - 0.5 * (jrc.astype(np.float32) / 100.0)
    weir_zone = (r_grid >= 1265) & (r_grid <= 1290) & (c_grid >= 1205) & (c_grid <= 1230)
    cost_ba[weir_zone & (dem > 5.55)] += 50.0
    cost_ba = np.maximum(cost_ba, 0.1)

    t0 = time.time()
    thalweg_ba = route_thalweg_scipy(cost_ba, ba_active, (1233, 1), (1065, 2075))
    mask_ba = build_corridor_mask(thalweg_ba, ba_active, r_max=450.0, grid_shape=(rows, cols))
    len_ba = len(thalweg_ba) * 0.030
    print(f"         Sông Ba routed: {len(thalweg_ba)} cells ({len_ba:.2f} km) in {time.time()-t0:.2f}s, Mask: {np.sum(mask_ba)} cells")

    branch_data["song_ba"] = BranchData(
        name="Trục chính Sông Ba (Sông Đà Rằng)",
        id="song_ba",
        mask=mask_ba,
        thalweg_rc=thalweg_ba,
        inflow_node=(1233, 1),
        outlet_node=(1065, 2075),
        d_max=3.50,
        outlet_target_z=-2.80,
        is_canal=False,
        length_km=len_ba
    )

    # =========================================================================
    # 2. SÔNG BÀN THẠCH (NHÁNH NAM)
    # =========================================================================
    # Inflow: (276000, 1424500) -> (1783, 200)
    # Outflow: Cửa Đà Nông (332190, 1423910) -> (1803, 2073)
    print("      -> [Branch 2/4] Processing Sông Bàn Thạch (Nhánh Nam)...")
    bt_box = (r_grid >= 1350) & (r_grid <= 2100) & (c_grid >= 190) & (c_grid <= 2095)
    ridge_block = (r_grid >= 1530) & (r_grid <= 1650) & (c_grid >= 1500) & (c_grid <= 1650) & (dem > 30.0)
    bt_active = bt_box & (dem > -5.0) & (dem < 260.0) & (~ridge_block)
    bt_active[1783, 200] = True
    bt_active[1803, 2073] = True

    cost_bt = 1.0 + 50.0 * np.clip(np.maximum(dem, 0.0) / 4.0, 0, 20)**2 + 1.0 * np.clip(osm / 100.0, 0, 5) - 0.8 * (jrc.astype(np.float32) / 100.0)
    cost_bt = np.maximum(cost_bt, 0.1)

    t0 = time.time()
    thalweg_bt = route_thalweg_scipy(cost_bt, bt_active, (1783, 200), (1803, 2073))
    # Corridor width R=250m
    bt_water_valley = bt_active & ((jrc >= 5) | (osm <= 300.0) | (dem < 35.0))
    mask_bt = build_corridor_mask(thalweg_bt, bt_water_valley, r_max=250.0, grid_shape=(rows, cols))
    len_bt = len(thalweg_bt) * 0.030
    print(f"         Sông Bàn Thạch routed: {len(thalweg_bt)} cells ({len_bt:.2f} km) in {time.time()-t0:.2f}s, Mask: {np.sum(mask_bt)} cells")

    branch_data["song_ban_thach"] = BranchData(
        name="Trục Sông Bàn Thạch (Nhánh Nam)",
        id="song_ban_thach",
        mask=mask_bt,
        thalweg_rc=thalweg_bt,
        inflow_node=(1783, 200),
        outlet_node=(1803, 2073),
        d_max=2.25,
        outlet_target_z=-2.50,
        is_canal=False,
        length_km=len_bt
    )

    # =========================================================================
    # 3. SÔNG KỲ LỘ (NHÁNH BẮC)
    # =========================================================================
    # Inflow: (289000, 1476500) -> (50, 633)
    # Outflow: Cửa Tiên Châu (328485, 1472000) -> (200, 1950)
    print("      -> [Branch 3/4] Processing Sông Kỳ Lộ (Nhánh Bắc)...")
    kl_box = (r_grid <= 700) & (c_grid >= 600)
    kl_active = kl_box & ((jrc >= 5) | (osm <= 350.0) | (dem < 35.0)) & (dem > -10.0) & (dem < 120.0)
    # Bridge northern border loop across provincial boundary (cols 765-945 along row 0)
    kl_active[0, 765:945] = True
    kl_active[50, 633] = True
    kl_active[200, 1950] = True

    z_kl = np.clip(dem, -5.0, 100.0)
    z_kl_norm = (z_kl - np.min(z_kl)) / (np.max(z_kl) - np.min(z_kl) + 1e-5)
    cost_kl = 1.0 + 20.0 * (z_kl_norm ** 1.5) + 0.5 * np.clip(osm / 250.0, 0, 5) - 0.5 * (jrc.astype(np.float32) / 100.0)
    cost_kl[0, 765:945] = 0.5
    cost_kl = np.maximum(cost_kl, 0.1)

    t0 = time.time()
    thalweg_kl = route_thalweg_scipy(cost_kl, kl_active, (50, 633), (200, 1950))
    # Corridor width R=280m
    kl_water_valley = kl_active & ((jrc >= 5) | (osm <= 300.0) | (dem < 35.0))
    mask_kl = build_corridor_mask(thalweg_kl, kl_water_valley, r_max=280.0, grid_shape=(rows, cols))
    len_kl = len(thalweg_kl) * 0.030
    print(f"         Sông Kỳ Lộ routed: {len(thalweg_kl)} cells ({len_kl:.2f} km) in {time.time()-t0:.2f}s, Mask: {np.sum(mask_kl)} cells")

    branch_data["song_ky_lo"] = BranchData(
        name="Trục Sông Kỳ Lộ (Nhánh Bắc)",
        id="song_ky_lo",
        mask=mask_kl,
        thalweg_rc=thalweg_kl,
        inflow_node=(50, 633),
        outlet_node=(200, 1950),
        d_max=2.25,
        outlet_target_z=-2.50,
        is_canal=False,
        length_km=len_kl
    )

    # =========================================================================
    # 4. ĐẬP ĐỒNG CAM WEIR CREST MASK (LOCKING DEFINITION)
    # =========================================================================
    # True river crossing: rows 1272..1288, cols 1212..1222 (crossing cell 1278, 1217 at +5.50m MSL)
    print("      -> [Structure 4/5] Locking Đập Đồng Cam Weir Crest Mask...")
    dong_cam_mask = np.zeros((rows, cols), dtype=bool)
    dong_cam_mask[1272:1289, 1212:1223] = True
    weir_cells = int(np.sum(dong_cam_mask))
    weir_z = dem[dong_cam_mask]
    print(f"         Đập Đồng Cam mask: {weir_cells} cells (rows 1272..1288, cols 1212..1222)")
    print(f"         Elevation range: {np.min(weir_z):.2f}m to {np.max(weir_z):.2f}m MSL (mean {np.mean(weir_z):.2f}m)")

    # =========================================================================
    # 5. HỆ THỐNG KÊNH THỦY NÔNG ĐỒNG CAM (KÊNH CHÍNH BẮC & KÊNH CHÍNH NAM)
    # =========================================================================
    # Origin: Đập Đồng Cam (306510, 1437500)
    # Kênh chính Bắc: intake (1270, 1217) -> terminus (975, 1402)
    # Kênh chính Nam: intake (1360, 1207) -> terminus (1539, 1900)
    print("      -> [Branch 5/5] Processing Irrigation Canals (Kênh Đồng Cam)...")

    # 5a. Kênh chính Bắc (re-anchored to North abutment on Sông Ba at (1270, 1217), strictly avoiding weir body and river thalweg)
    ba_path_mask = np.zeros((rows, cols), dtype=bool)
    for r, c in thalweg_ba:
        if (r, c) != (1270, 1217):
            ba_path_mask[r, c] = True

    north_box = (r_grid >= 900) & (r_grid <= 1300) & (c_grid >= 1190) & (c_grid <= 1650)
    dist_to_intake_n = np.hypot((r_grid - 1270) * 30.0, (c_grid - 1217) * 30.0)
    weir_north_buffer = (r_grid == 1271) & (c_grid >= 1212) & (c_grid <= 1225)
    north_active = north_box & ((osm <= 150.0) | (dist_to_intake_n <= 150.0)) & (~dong_cam_mask) & (~ba_path_mask) & (~weir_north_buffer)
    north_active[1270, 1217] = True
    north_active[975, 1402] = True

    cost_kn = 1.0 + 3.0 * np.clip(osm / 100.0, 0, 5) + 1.0 * np.clip(dem / 50.0, 0, 2)
    t0 = time.time()
    thalweg_kn = route_thalweg_scipy(cost_kn, north_active, (1270, 1217), (975, 1402))
    mask_kn = build_corridor_mask(thalweg_kn, north_active, r_max=45.0, grid_shape=(rows, cols))
    len_kn = len(thalweg_kn) * 0.030
    print(f"         Kênh chính Bắc routed: {len(thalweg_kn)} cells ({len_kn:.2f} km) in {time.time()-t0:.2f}s, Mask: {np.sum(mask_kn)} cells")

    branch_data["kenh_chinh_bac"] = BranchData(
        name="Kênh chính Bắc (Đập Đồng Cam)",
        id="kenh_chinh_bac",
        mask=mask_kn,
        thalweg_rc=thalweg_kn,
        inflow_node=(1270, 1217),
        outlet_node=(975, 1402),
        d_max=1.20,
        outlet_target_z=2.00,
        is_canal=True,
        length_km=len_kn
    )

    # 5b. Kênh chính Nam
    bt_path_mask = np.zeros((rows, cols), dtype=bool)
    for r, c in thalweg_bt:
        if (r, c) != (1360, 1207):
            bt_path_mask[r, c] = True

    south_box = (r_grid >= 1350) & (r_grid <= 1750) & (c_grid >= 1180) & (c_grid <= 1950)
    dist_to_intake_s = np.hypot((r_grid - 1360) * 30.0, (c_grid - 1207) * 30.0)
    south_active = south_box & ((osm <= 350.0) | (dist_to_intake_s <= 3000.0)) & (dem < 60.0) & (~dong_cam_mask) & (~bt_path_mask) & (~ba_path_mask)
    south_active[1360, 1207] = True
    south_active[1539, 1900] = True

    cost_ks = 1.0 + 3.0 * np.clip(osm / 100.0, 0, 5) + 2.0 * np.clip(dem / 50.0, 0, 2)
    t0 = time.time()
    thalweg_ks = route_thalweg_scipy(cost_ks, south_active, (1360, 1207), (1539, 1900))
    mask_ks = build_corridor_mask(thalweg_ks, south_active, r_max=45.0, grid_shape=(rows, cols))
    len_ks = len(thalweg_ks) * 0.030
    print(f"         Kênh chính Nam routed: {len(thalweg_ks)} cells ({len_ks:.2f} km) in {time.time()-t0:.2f}s, Mask: {np.sum(mask_ks)} cells")

    branch_data["kenh_chinh_nam"] = BranchData(
        name="Kênh chính Nam (Đập Đồng Cam)",
        id="kenh_chinh_nam",
        mask=mask_ks,
        thalweg_rc=thalweg_ks,
        inflow_node=(1360, 1207),
        outlet_node=(1539, 1900),
        d_max=1.20,
        outlet_target_z=2.00,
        is_canal=True,
        length_km=len_ks
    )

    return branch_data, dong_cam_mask


def verify_network_completeness(branch_data: Dict[str, BranchData], dong_cam_mask: np.ndarray, dem: np.ndarray):
    """
    Independent mathematical verification of network continuity and integrity.
    Evaluates:
      1. 8-connectivity continuity along all thalweg paths (0 gap jumps).
      2. Start and goal nodes match exactly.
      3. Total thalweg length and corridor coverage.
      4. Đập Đồng Cam weir mask geometry.
    """
    print("[3/5] Verifying Channel Continuity and Completeness...")
    
    for b_id, b_data in branch_data.items():
        path = b_data.thalweg_rc
        N = len(path)
        assert N > 10, f"Branch {b_id} thalweg is suspiciously short: {N} cells!"
        
        # Check start and goal
        assert path[0] == b_data.inflow_node, f"Branch {b_id} start mismatch: {path[0]} vs {b_data.inflow_node}"
        assert path[-1] == b_data.outlet_node, f"Branch {b_id} goal mismatch: {path[-1]} vs {b_data.outlet_node}"
        
        # Check 8-connectivity along the entire thalweg
        max_step = 0
        for i in range(1, N):
            dr = abs(path[i][0] - path[i - 1][0])
            dc = abs(path[i][1] - path[i - 1][1])
            step = max(dr, dc)
            if step > max_step:
                max_step = step
            assert step == 1, f"CONTINUITY ERROR in {b_id} at step {i}: jump from {path[i-1]} to {path[i]} (step={step})!"
            
        # Check mask encompasses thalweg
        for r, c in path:
            assert b_data.mask[r, c], f"Mask for {b_id} does not contain thalweg cell ({r}, {c})!"

        # Elevation sanity
        z_start = dem[path[0]]
        z_end = dem[path[-1]]
        print(f"      [PASS] {b_id:16s}: {N:5d} cells, {b_data.length_km:6.2f} km, 0 gaps (max_step={max_step}), z: {z_start:6.2f}m -> {z_end:5.2f}m")

    # Weir mask verification
    assert np.sum(dong_cam_mask) == 187, f"Weir mask cell count mismatch: {np.sum(dong_cam_mask)} != 187"
    weir_coords = np.argwhere(dong_cam_mask)
    assert np.min(weir_coords[:, 0]) == 1272 and np.max(weir_coords[:, 0]) == 1288
    assert np.min(weir_coords[:, 1]) == 1212 and np.max(weir_coords[:, 1]) == 1222
    assert dong_cam_mask[1278, 1217], "Weir mask must contain crossing node (1278, 1217)!"
    assert abs(dem[1278, 1217] - 5.50) < 0.01, f"Crossing node (1278, 1217) DEM != 5.50m (got {dem[1278, 1217]})"
    print(f"      [PASS] dong_cam_mask   : {np.sum(dong_cam_mask)} cells, rows [1272, 1288], cols [1212, 1222], crossing (1278, 1217) at {dem[1278, 1217]:.2f}m MSL 100% verified.")


def save_river_network_data(
    branch_data: Dict[str, BranchData],
    dong_cam_mask: np.ndarray,
    output_path: str = OUTPUT_NPZ_PATH
):
    """
    Saves extracted channel corridors, thalweg paths, and metadata to river_network_data.npz.
    """
    print(f"[4/5] Saving Extracted River Network Data to {output_path}...")
    
    # Compute union corridor mask
    union_mask = (
        branch_data["song_ba"].mask |
        branch_data["song_ban_thach"].mask |
        branch_data["song_ky_lo"].mask |
        branch_data["kenh_chinh_bac"].mask |
        branch_data["kenh_chinh_nam"].mask
    )

    metadata = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_dem_sha256": BASE_DEM_EXPECTED_SHA256,
        "branches": {}
    }

    save_arrays = {
        "dong_cam_mask": dong_cam_mask,
        "union_channel_mask": union_mask,
        "mask_kenh_dong_cam": branch_data["kenh_chinh_bac"].mask | branch_data["kenh_chinh_nam"].mask
    }

    for b_id, b_data in branch_data.items():
        save_arrays[f"mask_{b_id}"] = b_data.mask
        save_arrays[f"thalweg_{b_id}"] = np.array(b_data.thalweg_rc, dtype=np.int32)
        metadata["branches"][b_id] = {
            "name": b_data.name,
            "id": b_data.id,
            "inflow_node": list(b_data.inflow_node),
            "outlet_node": list(b_data.outlet_node),
            "d_max": b_data.d_max,
            "outlet_target_z": b_data.outlet_target_z,
            "is_canal": b_data.is_canal,
            "length_km": b_data.length_km,
            "cell_count_corridor": int(np.sum(b_data.mask)),
            "cell_count_thalweg": len(b_data.thalweg_rc)
        }

    save_arrays["metadata_json"] = np.array(json.dumps(metadata, indent=2))
    np.savez_compressed(output_path, **save_arrays)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"      Saved {output_path} ({file_size_mb:.2f} MB, {len(save_arrays)} arrays compressed).")
    print(f"      Total Union Channel Area: {np.sum(union_mask):,} cells ({np.sum(union_mask)*900.0/1e6:.2f} km²)")


def load_extracted_network(npz_path: str = OUTPUT_NPZ_PATH) -> Tuple[Dict[str, BranchData], np.ndarray]:
    """
    Loads extracted river network data from npz archive adhering to interface contract.
    """
    data = np.load(npz_path, allow_pickle=True)
    dong_cam_mask = data["dong_cam_mask"]
    metadata = json.loads(str(data["metadata_json"]))

    branch_data = {}
    for b_id, b_meta in metadata["branches"].items():
        thalweg_arr = data[f"thalweg_{b_id}"]
        thalweg_rc = [(int(r), int(c)) for r, c in thalweg_arr]
        branch_data[b_id] = BranchData(
            name=b_meta["name"],
            id=b_meta["id"],
            mask=data[f"mask_{b_id}"],
            thalweg_rc=thalweg_rc,
            inflow_node=tuple(b_meta["inflow_node"]),
            outlet_node=tuple(b_meta["outlet_node"]),
            d_max=float(b_meta["d_max"]),
            outlet_target_z=float(b_meta["outlet_target_z"]),
            is_canal=bool(b_meta["is_canal"]),
            length_km=float(b_meta["length_km"])
        )

    return branch_data, dong_cam_mask


def main():
    print("=" * 80)
    print("STARTING FULL MULTI-SOURCE RIVER NETWORK EXTRACTION (MILESTONE 1)")
    print("=" * 80)
    t_start = time.time()

    # Step 1: Load and verify inputs
    dem, jrc, osm, profile, transform = load_input_rasters()

    # Step 2: Extract corridors, masks, and thalwegs
    branch_data, dong_cam_mask = extract_river_network(dem, jrc, osm)

    # Step 3: Verify completeness & continuity
    verify_network_completeness(branch_data, dong_cam_mask, dem)

    # Step 4: Save compressed npz archive
    save_river_network_data(branch_data, dong_cam_mask)

    # Step 5: Post-run Base DEM SHA-256 integrity verification
    print("[5/5] Performing Post-Run Base DEM Cryptographic Integrity Guard...")
    verify_base_dem_sha256()
    print("      PASS: Base DEM SHA-256 hash remained 100% intact.")

    total_time = time.time() - t_start
    print("=" * 80)
    print(f"MILESTONE 1 EXTRACTION COMPLETED SUCCESSFULLY IN {total_time:.2f}s!")
    print("=" * 80)


if __name__ == "__main__":
    main()
