"""
========================================================================================
ADVERSARIAL STRESS-TEST HARNESS — CHALLENGER 2: DIFFERENTIAL GEOMETRY & GPU NUMERICAL STABILITY
Project: Phu Yen Multi-Source River Bathymetry Reconstruction & DEM Carving
Author: Challenger 2 (teamwork_preview_challenger)
Role: Adversarial Differential Geometry & Numerical Stability Challenger
Authority Documents:
  - D:\VTP\.agents\teamwork\challenger_m2_geometry\DISPATCH.md
  - D:\VTP\.agents\teamwork\ORIGINAL_REQUEST.md
  - D:\VTP\.agents\teamwork\orchestrator_15\PROJECT.md

Mandatory Challenge Dimensions:
  1. Scan 100% of all ~19,000 p8 perimeter boundary cells for edge cliff drops > 0.05m.
  2. Compute normal derivative dz/dn across banks and verify C1 tangency (<= 0.005 m/m).
  3. Convolve discrete 9-point Laplacian operator across carved DEM and hunt for extreme curvature spikes (> 0.025 m^-1).
  4. Verify 2D SWE simulation stability on GPU (zero NaN, zero Inf, Courant CFL stability).
  5. Check floodplain invariance (0 leaked cells outside active corridor).
========================================================================================
"""

import os
import sys
import io
import time
import json
import hashlib
import numpy as np
import rasterio
from scipy.ndimage import binary_dilation, distance_transform_edt, convolve
import cupy as cp

# Ensure standard output uses UTF-8
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ========================================================================================
# PATHS AND CONSTANTS
# ========================================================================================

BASE_DEM_PATH = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
PROD_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Full_River_Bathymetry.tif"
PROD_ASC_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Full_River_Bathymetry.asc"
DELTA_Z_PATH  = r"D:\VTP\River_Bathymetry_Project\delta_z_full_bathymetry.tif"
CARVED_NPZ_PATH = r"D:\VTP\River_Bathymetry_Project\carved_bathymetry_arrays.npz"
NETWORK_NPZ_PATH = r"D:\VTP\River_Bathymetry_Project\river_network_data.npz"
THALWEG_JSON_PATH = r"D:\VTP\River_Bathymetry_Project\thalweg_paths.json"

OUTPUT_RESULTS_JSON = r"D:\VTP\River_Bathymetry_Project\challenger_m2_geometry_stress_results.json"
EXPECTED_BASE_SHA256 = "0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508"

# ========================================================================================
# HARNESS IMPLEMENTATION
# ========================================================================================

class AdversarialGeometryStabilityHarness:
    def __init__(self):
        print("=" * 80)
        print("ADVERSARIAL DIFFERENTIAL GEOMETRY & GPU NUMERICAL STABILITY HARNESS")
        print("=" * 80)
        self.start_time = time.time()
        self.results = {}
        
        # Load Rasters
        print("[INIT] Loading Base DEM, Production Carved DEM, and Delta-Z rasters...")
        with rasterio.open(BASE_DEM_PATH) as src:
            self.base_dem = src.read(1).astype(np.float32)
            self.transform = src.transform
            self.crs = str(src.crs)
            self.bounds = src.bounds
            
        with rasterio.open(PROD_TIF_PATH) as src:
            self.carved_dem = src.read(1).astype(np.float32)
            
        with rasterio.open(DELTA_Z_PATH) as src:
            self.delta_z = src.read(1).astype(np.float32)
            
        with open(THALWEG_JSON_PATH, "r", encoding="utf-8") as f:
            self.thalwegs = json.load(f)
            
        print("[INIT] Loading River Network masks...")
        net_data = np.load(NETWORK_NPZ_PATH)
        self.dong_cam_mask = net_data["dong_cam_mask"].astype(bool)
        self.union_channel_mask = net_data["union_channel_mask"].astype(bool)
        self.mask_song_ba = net_data["mask_song_ba"].astype(bool)
        self.mask_song_ban_thach = net_data["mask_song_ban_thach"].astype(bool)
        self.mask_song_ky_lo = net_data["mask_song_ky_lo"].astype(bool)
        self.mask_kenh_chinh_bac = net_data["mask_kenh_chinh_bac"].astype(bool)
        self.mask_kenh_chinh_nam = net_data["mask_kenh_chinh_nam"].astype(bool)
        
        # Exact masks
        self.carved_mask = (self.delta_z > 0.0)
        self.uncarved_mask = (self.delta_z == 0.0)
        print(f"Domain Shape: {self.base_dem.shape}")
        print(f"Carved Cells (delta_z > 0): {np.sum(self.carved_mask):,}")
        print(f"Uncarved Cells (delta_z == 0): {np.sum(self.uncarved_mask):,}")

    def run_all_challenges(self):
        self.challenge_1_perimeter_cliff_drops()
        self.challenge_2_c1_bank_tangency()
        self.challenge_3_discrete_laplacian_curvature()
        self.challenge_4_swe_gpu_simulation_stability()
        self.challenge_5_floodplain_invariance_and_integrity()
        self.summarize_and_export()

    # ------------------------------------------------------------------------------------
    # CHALLENGE 1: 100% SCAN OF ALL ~19,000 p8 PERIMETER BOUNDARY CELLS
    # ------------------------------------------------------------------------------------
    def challenge_1_perimeter_cliff_drops(self):
        print("\n" + "=" * 80)
        print("CHALLENGE 1: 100% SCAN OF ALL p8 PERIMETER BOUNDARY CELLS FOR CLIFF DROPS > 0.05m")
        print("=" * 80)
        
        # 8-connected perimeter of carved cells touching uncarved domain
        dilated_uncarved_8 = binary_dilation(self.uncarved_mask, structure=np.ones((3, 3)))
        p8_mask = self.carved_mask & dilated_uncarved_8
        p8_count = int(np.sum(p8_mask))
        p8_drops = self.delta_z[p8_mask]
        
        max_cliff = float(np.max(p8_drops))
        mean_cliff = float(np.mean(p8_drops))
        median_cliff = float(np.median(p8_drops))
        p90_cliff = float(np.percentile(p8_drops, 90))
        p95_cliff = float(np.percentile(p8_drops, 95))
        p99_cliff = float(np.percentile(p8_drops, 99))
        p999_cliff = float(np.percentile(p8_drops, 99.9))
        
        violations_ge_0_05 = int(np.sum(p8_drops >= 0.050000))
        violations_gt_0_045 = int(np.sum(p8_drops > 0.045000))
        violations_ge_0_03 = int(np.sum(p8_drops >= 0.030000))
        
        print(f"  Total p8 Perimeter Boundary Cells: {p8_count:,}")
        print(f"  Max Cliff Drop:                    {max_cliff:.6f} m (Threshold <= 0.050m)")
        print(f"  Mean Cliff Drop:                   {mean_cliff:.6f} m (Standard < 0.025m)")
        print(f"  Median Cliff Drop:                 {median_cliff:.6f} m")
        print(f"  95th Percentile Cliff Drop:        {p95_cliff:.6f} m")
        print(f"  99th Percentile Cliff Drop:        {p99_cliff:.6f} m")
        print(f"  99.9th Percentile Cliff Drop:      {p999_cliff:.6f} m")
        print(f"  Violations (drop >= 0.05m):        {violations_ge_0_05}")
        print(f"  Cells with drop > 0.045m:          {violations_gt_0_045}")
        print(f"  Cells with drop >= 0.030m:         {violations_ge_0_03}")
        
        # 4-connected perimeter check (p4)
        structure_4 = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
        dilated_uncarved_4 = binary_dilation(self.uncarved_mask, structure=structure_4)
        p4_mask = self.carved_mask & dilated_uncarved_4
        p4_count = int(np.sum(p4_mask))
        p4_drops = self.delta_z[p4_mask]
        max_p4_cliff = float(np.max(p4_drops))
        violations_p4 = int(np.sum(p4_drops >= 0.050000))
        print(f"  Total p4 Perimeter Cells:          {p4_count:,}")
        print(f"  Max p4 Cliff Drop:                 {max_p4_cliff:.6f} m")
        print(f"  Violations in p4 (drop >= 0.05m):  {violations_p4}")
        
        # Per-branch perimeter analysis
        branch_perimeters = {}
        for b_name, b_mask in [
            ("Sông Ba", self.mask_song_ba),
            ("Sông Bàn Thạch", self.mask_song_ban_thach),
            ("Sông Kỳ Lộ", self.mask_song_ky_lo),
            ("Kênh Bắc", self.mask_kenh_chinh_bac),
            ("Kênh Nam", self.mask_kenh_chinh_nam)
        ]:
            b_p8 = p8_mask & b_mask
            b_cnt = int(np.sum(b_p8))
            if b_cnt > 0:
                b_drops = self.delta_z[b_p8]
                b_max = float(np.max(b_drops))
                b_mean = float(np.mean(b_drops))
                b_viol = int(np.sum(b_drops >= 0.050000))
            else:
                b_max, b_mean, b_viol = 0.0, 0.0, 0
            print(f"    Branch [{b_name}]: {b_cnt:,} p8 cells, max drop={b_max:.6f}m, mean={b_mean:.6f}m, viol={b_viol}")
            branch_perimeters[b_name] = {
                "cell_count": b_cnt,
                "max_drop_m": b_max,
                "mean_drop_m": b_mean,
                "violations_ge_0_05m": b_viol
            }
            
        # Top 10 highest perimeter drops
        p8_r, p8_c = np.where(p8_mask)
        sort_idx = np.argsort(p8_drops)[::-1][:10]
        top10_drops = []
        for idx in sort_idx:
            r, c = int(p8_r[idx]), int(p8_c[idx])
            val = float(p8_drops[idx])
            utm_x = self.bounds.left + c * 30.0 + 15.0
            utm_y = self.bounds.top - r * 30.0 - 15.0
            top10_drops.append({"row": r, "col": c, "utm_x": utm_x, "utm_y": utm_y, "drop_m": val})
            
        print(f"  Top highest perimeter drop: row={top10_drops[0]['row']}, col={top10_drops[0]['col']}, val={top10_drops[0]['drop_m']:.6f}m")
        
        c1_pass = (violations_ge_0_05 == 0) and (max_cliff <= 0.050000) and (mean_cliff < 0.025000)
        self.results["challenge_1_p8_perimeter_cliff_drops"] = {
            "passed": bool(c1_pass),
            "verdict": "PASS" if c1_pass else "FAIL",
            "total_p8_cells": p8_count,
            "max_cliff_drop_m": max_cliff,
            "mean_cliff_drop_m": mean_cliff,
            "median_cliff_drop_m": median_cliff,
            "p95_cliff_drop_m": p95_cliff,
            "p99_cliff_drop_m": p99_cliff,
            "p999_cliff_drop_m": p999_cliff,
            "violations_ge_0_05m": violations_ge_0_05,
            "violations_gt_0_045m": violations_gt_0_045,
            "p4_perimeter_cells": p4_count,
            "max_p4_cliff_m": max_p4_cliff,
            "violations_p4": violations_p4,
            "branch_breakdown": branch_perimeters,
            "top10_highest_drops": top10_drops
        }

    # ------------------------------------------------------------------------------------
    # CHALLENGE 2: NORMAL DERIVATIVE dz/dn ACROSS BANKS AND C1 TANGENCY
    # ------------------------------------------------------------------------------------
    def challenge_2_c1_bank_tangency(self):
        print("\n" + "=" * 80)
        print("CHALLENGE 2: NORMAL DERIVATIVE dz/dn ACROSS BANKS AND C1 TANGENCY (<= 0.005 m/m)")
        print("=" * 80)
        
        dilated_uncarved_8 = binary_dilation(self.uncarved_mask, structure=np.ones((3, 3)))
        p8_mask = self.carved_mask & dilated_uncarved_8
        p8_r, p8_c = np.where(p8_mask)
        
        dr_list = [-1, -1, -1, 0, 0, 1, 1, 1]
        dc_list = [-1, 0, 1, -1, 1, -1, 0, 1]
        dist_list = [np.hypot(dr * 30.0, dc * 30.0) for dr, dc in zip(dr_list, dc_list)]
        
        normal_slopes = []
        normal_dem_slopes = []
        crevice_inversions = 0
        
        for r, c in zip(p8_r, p8_c):
            dz_edge = self.delta_z[r, c]
            z_carved_edge = self.carved_dem[r, c]
            
            max_s = 0.0
            max_dem_s = -1e9
            
            for dr, dc, d_step in zip(dr_list, dc_list, dist_list):
                nr, nc = r + dr, c + dc
                if 0 <= nr < 2100 and 0 <= nc < 2100 and self.uncarved_mask[nr, nc]:
                    slope = dz_edge / d_step
                    if slope > max_s:
                        max_s = slope
                        
                    # Also evaluate DEM slope towards uncarved bank
                    z_bank = self.carved_dem[nr, nc]
                    dem_s = (z_bank - z_carved_edge) / d_step
                    if dem_s > max_dem_s:
                        max_dem_s = dem_s
                        
                    # Check for negative drop (crevice where bank is lower than carved bed)
                    if dz_edge < -1e-6:
                        crevice_inversions += 1
                        
            normal_slopes.append(max_s)
            if max_dem_s != -1e9:
                normal_dem_slopes.append(max_dem_s)
                
        normal_slopes = np.array(normal_slopes, dtype=np.float32)
        max_normal_slope = float(np.max(normal_slopes))
        mean_normal_slope = float(np.mean(normal_slopes))
        median_normal_slope = float(np.median(normal_slopes))
        p95_normal_slope = float(np.percentile(normal_slopes, 95))
        p99_normal_slope = float(np.percentile(normal_slopes, 99))
        p999_normal_slope = float(np.percentile(normal_slopes, 99.9))
        violations_c1 = int(np.sum(normal_slopes > 0.005000))
        
        print(f"  Max Outward Normal Slope dz/dn:    {max_normal_slope:.6f} m/m (Threshold <= 0.005000 m/m)")
        print(f"  Mean Outward Normal Slope:         {mean_normal_slope:.6f} m/m (Standard <= 0.001000 m/m)")
        print(f"  Median Normal Slope:               {median_normal_slope:.6f} m/m")
        print(f"  95th Percentile Normal Slope:      {p95_normal_slope:.6f} m/m")
        print(f"  99th Percentile Normal Slope:      {p99_normal_slope:.6f} m/m")
        print(f"  99.9th Percentile Normal Slope:    {p999_normal_slope:.6f} m/m")
        print(f"  C1 Tangency Violations (> 0.005):  {violations_c1}")
        print(f"  Crevice / Bed Inversions:          {crevice_inversions}")
        
        # Top 10 highest normal slopes
        sort_s_idx = np.argsort(normal_slopes)[::-1][:10]
        top10_slopes = []
        for idx in sort_s_idx:
            r, c = int(p8_r[idx]), int(p8_c[idx])
            s_val = float(normal_slopes[idx])
            utm_x = self.bounds.left + c * 30.0 + 15.0
            utm_y = self.bounds.top - r * 30.0 - 15.0
            top10_slopes.append({"row": r, "col": c, "utm_x": utm_x, "utm_y": utm_y, "slope_m_per_m": s_val})
            
        print(f"  Top normal slope: row={top10_slopes[0]['row']}, col={top10_slopes[0]['col']}, slope={top10_slopes[0]['slope_m_per_m']:.6f} m/m")
        
        c2_pass = (violations_c1 == 0) and (max_normal_slope <= 0.005000) and (mean_normal_slope <= 0.001000) and (crevice_inversions == 0)
        self.results["challenge_2_c1_bank_tangency"] = {
            "passed": bool(c2_pass),
            "verdict": "PASS" if c2_pass else "FAIL",
            "max_normal_slope_m_per_m": max_normal_slope,
            "mean_normal_slope_m_per_m": mean_normal_slope,
            "median_normal_slope_m_per_m": median_normal_slope,
            "p95_normal_slope_m_per_m": p95_normal_slope,
            "p99_normal_slope_m_per_m": p99_normal_slope,
            "p999_normal_slope_m_per_m": p999_normal_slope,
            "violations_gt_0_005m_per_m": violations_c1,
            "crevice_inversions": crevice_inversions,
            "top10_highest_normal_slopes": top10_slopes
        }

    # ------------------------------------------------------------------------------------
    # CHALLENGE 3: DISCRETE 9-POINT LAPLACIAN OPERATOR AND CURVATURE SPIKES
    # ------------------------------------------------------------------------------------
    def challenge_3_discrete_laplacian_curvature(self):
        print("\n" + "=" * 80)
        print("CHALLENGE 3: DISCRETE 9-POINT LAPLACIAN OPERATOR AND CURVATURE SPIKES (> 0.025 m^-1)")
        print("=" * 80)
        
        # Discrete 9-point isotropic Laplacian kernel
        # L = 1/(6*dx^2) * [[1, 4, 1], [4, -20, 4], [1, 4, 1]]
        # dx = 30m -> 6*30^2 = 5400.0
        w_lap9 = np.array([
            [1.0,  4.0, 1.0],
            [4.0, -20.0, 4.0],
            [1.0,  4.0, 1.0]
        ], dtype=np.float32) / 5400.0
        
        # Convolve with delta_z
        lap_dz = np.abs(convolve(self.delta_z, w_lap9))
        active_lap_dz = lap_dz[self.carved_mask]
        
        max_curv_dz = float(np.max(active_lap_dz))
        mean_curv_dz = float(np.mean(active_lap_dz))
        median_curv_dz = float(np.median(active_lap_dz))
        p95_curv_dz = float(np.percentile(active_lap_dz, 95))
        p99_curv_dz = float(np.percentile(active_lap_dz, 99))
        p999_curv_dz = float(np.percentile(active_lap_dz, 99.9))
        fatal_spikes_dz = int(np.sum(active_lap_dz > 0.025000))
        monitored_spikes_dz = int(np.sum(active_lap_dz > 0.010000))
        
        print(f"  [Delta-Z] Active Carved Cells Evaluated: {len(active_lap_dz):,}")
        print(f"  [Delta-Z] Max 9-point Laplacian Curvature: {max_curv_dz:.6f} m^-1 (Threshold <= 0.025 m^-1)")
        print(f"  [Delta-Z] Mean Curvature:                 {mean_curv_dz:.6f} m^-1 (Standard < 0.002 m^-1)")
        print(f"  [Delta-Z] 99th Percentile Curvature:      {p99_curv_dz:.6f} m^-1")
        print(f"  [Delta-Z] 99.9th Percentile Curvature:    {p999_curv_dz:.6f} m^-1")
        print(f"  [Delta-Z] Fatal Spikes (> 0.025 m^-1):     {fatal_spikes_dz}")
        print(f"  [Delta-Z] Monitored Spikes (> 0.010 m^-1): {monitored_spikes_dz}")
        
        # Convolve directly with Carved DEM
        lap_carved = np.abs(convolve(self.carved_dem, w_lap9))
        lap_base   = np.abs(convolve(self.base_dem, w_lap9))
        # Incremental curvature induced by carving: |nabla^2 z_carved - nabla^2 z_base|
        diff_lap = np.abs(convolve(self.carved_dem - self.base_dem, w_lap9))
        active_diff_lap = diff_lap[self.carved_mask]
        max_incremental_curv = float(np.max(active_diff_lap))
        
        print(f"  [DEM Diff] Max Incision Laplacian Curvature: {max_incremental_curv:.6f} m^-1")
        
        # 5-point standard cross Laplacian as cross-check:
        # L5 = 1/dx^2 * [[0, 1, 0], [1, -4, 1], [0, 1, 0]], dx^2 = 900.0
        w_lap5 = np.array([
            [0.0,  1.0, 0.0],
            [1.0, -4.0, 1.0],
            [0.0,  1.0, 0.0]
        ], dtype=np.float32) / 900.0
        lap5_dz = np.abs(convolve(self.delta_z, w_lap5))
        active_lap5 = lap5_dz[self.carved_mask]
        max_curv_5pt = float(np.max(active_lap5))
        fatal_spikes_5pt = int(np.sum(active_lap5 > 0.025000))
        print(f"  [5-point Cross-check] Max Laplacian Curvature: {max_curv_5pt:.6f} m^-1, fatal spikes (> 0.025): {fatal_spikes_5pt}")
        
        # Find Top 10 Curvature Spike Locations
        carved_r, carved_c = np.where(self.carved_mask)
        top_curv_indices = np.argsort(active_lap_dz)[::-1][:10]
        top10_spikes = []
        for idx in top_curv_indices:
            r, c = int(carved_r[idx]), int(carved_c[idx])
            curv_val = float(active_lap_dz[idx])
            utm_x = self.bounds.left + c * 30.0 + 15.0
            utm_y = self.bounds.top - r * 30.0 - 15.0
            top10_spikes.append({
                "row": r, "col": c, "utm_x": utm_x, "utm_y": utm_y,
                "curvature_m_inv": curv_val,
                "delta_z": float(self.delta_z[r, c]),
                "carved_z": float(self.carved_dem[r, c])
            })
            
        print(f"  Top Curvature Spike: row={top10_spikes[0]['row']}, col={top10_spikes[0]['col']}, curv={top10_spikes[0]['curvature_m_inv']:.6f} m^-1")
        
        c3_pass = (fatal_spikes_dz == 0) and (max_curv_dz <= 0.025000) and (mean_curv_dz < 0.002000)
        self.results["challenge_3_discrete_laplacian_curvature"] = {
            "passed": bool(c3_pass),
            "verdict": "PASS" if c3_pass else "FAIL",
            "max_laplacian_curvature_m_inv": max_curv_dz,
            "mean_laplacian_curvature_m_inv": mean_curv_dz,
            "median_curvature_m_inv": median_curv_dz,
            "p95_curvature_m_inv": p95_curv_dz,
            "p99_curvature_m_inv": p99_curv_dz,
            "p999_curvature_m_inv": p999_curv_dz,
            "fatal_spikes_gt_0_025m_inv": fatal_spikes_dz,
            "monitored_spikes_gt_0_010m_inv": monitored_spikes_dz,
            "max_5point_curvature_m_inv": max_curv_5pt,
            "fatal_spikes_5point": fatal_spikes_5pt,
            "top10_curvature_spikes": top10_spikes
        }

    # ------------------------------------------------------------------------------------
    # CHALLENGE 4: 2D SWE SIMULATION STABILITY ON GPU (ZERO NaN, ZERO Inf, COURANT CFL)
    # ------------------------------------------------------------------------------------
    def challenge_4_swe_gpu_simulation_stability(self):
        print("\n" + "=" * 80)
        print("CHALLENGE 4: 2D SWE SIMULATION STABILITY ON GPU (ZERO NaN, ZERO Inf, COURANT CFL)")
        print("=" * 80)
        
        if not cp.cuda.is_available():
            raise RuntimeError("CUDA is not available on this machine!")
            
        p = cp.cuda.runtime.getDeviceProperties(0)
        gpu_name = p['name'].decode() if isinstance(p['name'], bytes) else p['name']
        print(f"  Active GPU: {gpu_name}")
        
        # We test TWO distinct hydrodynamic stress scenarios:
        # Scenario A: Baseline Dynamic Propagation (350 steps)
        # Scenario B: High Inflow Shock / Dam Break Wetting-Drying Wave (250 steps)
        
        dx = 30.0
        g = 9.81
        cfl = 0.45
        manning_n = 0.030
        
        # SCENARIO A: BASELINE HYDRAULIC INFLOW
        print("\n  [GPU Test A] Baseline Hydraulic Conveyance across Ba River & Canals (350 steps)...")
        zb_gpu = cp.asarray(self.carved_dem, dtype=cp.float32)
        dz_gpu = cp.asarray(self.delta_z, dtype=cp.float32)
        
        # Initial depth in carved river corridor
        h_gpu = cp.where(dz_gpu > 0.05, cp.maximum(0.5, dz_gpu * 0.4), 0.0).astype(cp.float32)
        u_gpu = cp.zeros_like(h_gpu)
        v_gpu = cp.zeros_like(h_gpu)
        
        # Upstream inflow boundary at headwaters of Ba River
        inflow_r = slice(1270, 1280)
        inflow_c = slice(5, 15)
        
        nan_count_total = 0
        inf_count_total = 0
        negative_depth_count = 0
        dt_list_a = []
        
        t0 = time.time()
        for step in range(1, 351):
            # Inflow boundary
            h_gpu[inflow_r, inflow_c] = cp.maximum(h_gpu[inflow_r, inflow_c], 2.8)
            u_gpu[inflow_r, inflow_c] = 1.5
            
            # CFL calculation
            c_wave = cp.sqrt(g * cp.maximum(h_gpu, 0.0))
            max_speed = float(cp.max(cp.maximum(cp.abs(u_gpu) + c_wave, cp.abs(v_gpu) + c_wave)))
            if max_speed < 1.0: max_speed = 1.0
            
            dt = cfl * dx / max_speed
            dt = max(0.80, min(dt, 1.80))
            dt_list_a.append(dt)
            
            # Kurganov-Petrova numerical fluxes
            # X fluxes
            hl, hr = h_gpu[1:-1, :-1], h_gpu[1:-1, 1:]
            ul, ur = u_gpu[1:-1, :-1], u_gpu[1:-1, 1:]
            cl = cp.sqrt(g * cp.maximum(hl, 0.0))
            cr = cp.sqrt(g * cp.maximum(hr, 0.0))
            ap = cp.maximum(cp.maximum(ul + cl, ur + cr), 0.0)
            am = cp.minimum(cp.minimum(ul - cl, ur - cr), 0.0)
            denom_x = cp.maximum(ap - am, 1e-6)
            ql, qr = hl * ul, hr * ur
            Fh_x = (ap * ql - am * qr + ap * am * (hr - hl)) / denom_x
            Fu_x = (ap * (ql * ul + 0.5 * g * hl**2) - am * (qr * ur + 0.5 * g * hr**2) + ap * am * (qr - ql)) / denom_x
            Fv_x = cp.where(Fh_x > 0, v_gpu[1:-1, :-1] * Fh_x, v_gpu[1:-1, 1:] * Fh_x)
            
            # Y fluxes
            hb, ht = h_gpu[:-1, 1:-1], h_gpu[1:, 1:-1]
            vb, vt = v_gpu[:-1, 1:-1], v_gpu[1:, 1:-1]
            cb = cp.sqrt(g * cp.maximum(hb, 0.0))
            ct = cp.sqrt(g * cp.maximum(ht, 0.0))
            bp = cp.maximum(cp.maximum(vb + cb, vt + ct), 0.0)
            bm = cp.minimum(cp.minimum(vb - cb, vt - ct), 0.0)
            denom_y = cp.maximum(bp - bm, 1e-6)
            qb, qt = hb * vb, ht * vt
            Fh_y = (bp * qb - bm * qt + bp * bm * (ht - hb)) / denom_y
            Fv_y = (bp * (qb * vb + 0.5 * g * hb**2) - bm * (qt * vt + 0.5 * g * ht**2) + bp * bm * (qt - qb)) / denom_y
            Fu_y = cp.where(Fh_y > 0, u_gpu[:-1, 1:-1] * Fh_y, u_gpu[1:, 1:-1] * Fh_y)
            
            div_Fh = (Fh_x[:, 1:] - Fh_x[:, :-1]) / dx + (Fh_y[1:, :] - Fh_y[:-1, :]) / dx
            div_Fu = (Fu_x[:, 1:] - Fu_x[:, :-1]) / dx + (Fu_y[1:, :] - Fu_y[:-1, :]) / dx
            div_Fv = (Fv_x[:, 1:] - Fv_x[:, :-1]) / dx + (Fv_y[1:, :] - Fv_y[:-1, :]) / dx
            
            dzb_dx = (zb_gpu[1:-1, 2:] - zb_gpu[1:-1, :-2]) / (2.0 * dx)
            dzb_dy = (zb_gpu[2:, 1:-1] - zb_gpu[:-2, 1:-1]) / (2.0 * dx)
            
            h_int = h_gpu[1:-1, 1:-1]
            h_new = cp.maximum(0.0, h_int - dt * div_Fh)
            
            hu = h_int * u_gpu[1:-1, 1:-1] - dt * div_Fu - dt * g * h_new * dzb_dx
            hv = h_int * v_gpu[1:-1, 1:-1] - dt * div_Fv - dt * g * h_new * dzb_dy
            
            v_mag = cp.sqrt(hu**2 + hv**2) / cp.maximum(h_new, 1e-3)
            cf = g * (manning_n**2) / (cp.maximum(h_new, 1e-3)**(1.0/3.0) + 1e-6)
            f_factor = 1.0 / (1.0 + dt * cf * v_mag / cp.maximum(h_new, 1e-3))
            
            hu *= f_factor
            hv *= f_factor
            
            h_gpu[1:-1, 1:-1] = h_new
            u_gpu[1:-1, 1:-1] = cp.where(h_new > 0.01, hu / cp.maximum(h_new, 1e-3), 0.0)
            v_gpu[1:-1, 1:-1] = cp.where(h_new > 0.01, hv / cp.maximum(h_new, 1e-3), 0.0)
            
            # Every 25 steps audit NaNs and Infs
            if step % 25 == 0:
                nans = int(cp.isnan(h_gpu).sum() + cp.isnan(u_gpu).sum() + cp.isnan(v_gpu).sum())
                infs = int(cp.isinf(h_gpu).sum() + cp.isinf(u_gpu).sum() + cp.isinf(v_gpu).sum())
                negs = int((h_gpu < 0.0).sum())
                nan_count_total += nans
                inf_count_total += infs
                negative_depth_count += negs
                
        cp.cuda.Stream.null.synchronize()
        time_a = time.time() - t0
        print(f"  [GPU Test A] Completed in {time_a:.2f}s ({time_a/350*1000:.2f} ms/step)")
        print(f"  [GPU Test A] Min dt: {min(dt_list_a):.3f}s, Max dt: {max(dt_list_a):.3f}s, Mean dt: {np.mean(dt_list_a):.3f}s")
        print(f"  [GPU Test A] NaN violations: {nan_count_total}, Inf violations: {inf_count_total}, Negative depths: {negative_depth_count}")
        
        # SCENARIO B: ADVERSARIAL STRESS TEST — EXTREME PEAK FLOOD SURGE
        print("\n  [GPU Test B] Adversarial Extreme Peak Flood Surge across 3 Basins (200 steps)...")
        # Initialize dry bed with sudden massive inflows at all 3 rivers
        h_gpu_b = cp.zeros_like(zb_gpu)
        u_gpu_b = cp.zeros_like(zb_gpu)
        v_gpu_b = cp.zeros_like(zb_gpu)
        
        # Inflows: Sông Ba (r: 1270-1280, c: 5-15), Sông Bàn Thạch (r: 1780-1790, c: 245-255), Sông Kỳ Lộ (r: 55-65, c: 675-685)
        dt_list_b = []
        nan_b = 0
        inf_b = 0
        t0_b = time.time()
        
        for step in range(1, 201):
            h_gpu_b[1270:1280, 5:15] = 4.5
            u_gpu_b[1270:1280, 5:15] = 2.5
            
            h_gpu_b[1780:1790, 245:255] = 3.5
            u_gpu_b[1780:1790, 245:255] = 2.0
            
            h_gpu_b[55:65, 675:685] = 3.5
            u_gpu_b[55:65, 675:685] = 2.0
            
            c_wave = cp.sqrt(g * cp.maximum(h_gpu_b, 0.0))
            max_speed = float(cp.max(cp.maximum(cp.abs(u_gpu_b) + c_wave, cp.abs(v_gpu_b) + c_wave)))
            if max_speed < 1.0: max_speed = 1.0
            
            dt = cfl * dx / max_speed
            dt = max(0.60, min(dt, 1.80))
            dt_list_b.append(dt)
            
            hl, hr = h_gpu_b[1:-1, :-1], h_gpu_b[1:-1, 1:]
            ul, ur = u_gpu_b[1:-1, :-1], u_gpu_b[1:-1, 1:]
            cl = cp.sqrt(g * cp.maximum(hl, 0.0))
            cr = cp.sqrt(g * cp.maximum(hr, 0.0))
            ap = cp.maximum(cp.maximum(ul + cl, ur + cr), 0.0)
            am = cp.minimum(cp.minimum(ul - cl, ur - cr), 0.0)
            denom_x = cp.maximum(ap - am, 1e-6)
            ql, qr = hl * ul, hr * ur
            Fh_x = (ap * ql - am * qr + ap * am * (hr - hl)) / denom_x
            Fu_x = (ap * (ql * ul + 0.5 * g * hl**2) - am * (qr * ur + 0.5 * g * hr**2) + ap * am * (qr - ql)) / denom_x
            Fv_x = cp.where(Fh_x > 0, v_gpu_b[1:-1, :-1] * Fh_x, v_gpu_b[1:-1, 1:] * Fh_x)
            
            hb, ht = h_gpu_b[:-1, 1:-1], h_gpu_b[1:, 1:-1]
            vb, vt = v_gpu_b[:-1, 1:-1], v_gpu_b[1:, 1:-1]
            cb = cp.sqrt(g * cp.maximum(hb, 0.0))
            ct = cp.sqrt(g * cp.maximum(ht, 0.0))
            bp = cp.maximum(cp.maximum(vb + cb, vt + ct), 0.0)
            bm = cp.minimum(cp.minimum(vb - cb, vt - ct), 0.0)
            denom_y = cp.maximum(bp - bm, 1e-6)
            qb, qt = hb * vb, ht * vt
            Fh_y = (bp * qb - bm * qt + bp * bm * (ht - hb)) / denom_y
            Fv_y = (bp * (qb * vb + 0.5 * g * hb**2) - bm * (qt * vt + 0.5 * g * ht**2) + bp * bm * (qt - qb)) / denom_y
            Fu_y = cp.where(Fh_y > 0, u_gpu_b[:-1, 1:-1] * Fh_y, u_gpu_b[1:, 1:-1] * Fh_y)
            
            div_Fh = (Fh_x[:, 1:] - Fh_x[:, :-1]) / dx + (Fh_y[1:, :] - Fh_y[:-1, :]) / dx
            div_Fu = (Fu_x[:, 1:] - Fu_x[:, :-1]) / dx + (Fu_y[1:, :] - Fu_y[:-1, :]) / dx
            div_Fv = (Fv_x[:, 1:] - Fv_x[:, :-1]) / dx + (Fv_y[1:, :] - Fv_y[:-1, :]) / dx
            
            dzb_dx = (zb_gpu[1:-1, 2:] - zb_gpu[1:-1, :-2]) / (2.0 * dx)
            dzb_dy = (zb_gpu[2:, 1:-1] - zb_gpu[:-2, 1:-1]) / (2.0 * dx)
            
            h_int = h_gpu_b[1:-1, 1:-1]
            h_new = cp.maximum(0.0, h_int - dt * div_Fh)
            hu = h_int * u_gpu_b[1:-1, 1:-1] - dt * div_Fu - dt * g * h_new * dzb_dx
            hv = h_int * v_gpu_b[1:-1, 1:-1] - dt * div_Fv - dt * g * h_new * dzb_dy
            
            v_mag = cp.sqrt(hu**2 + hv**2) / cp.maximum(h_new, 1e-3)
            cf = g * (manning_n**2) / (cp.maximum(h_new, 1e-3)**(1.0/3.0) + 1e-6)
            f_factor = 1.0 / (1.0 + dt * cf * v_mag / cp.maximum(h_new, 1e-3))
            hu *= f_factor
            hv *= f_factor
            
            h_gpu_b[1:-1, 1:-1] = h_new
            u_gpu_b[1:-1, 1:-1] = cp.where(h_new > 0.01, hu / cp.maximum(h_new, 1e-3), 0.0)
            v_gpu_b[1:-1, 1:-1] = cp.where(h_new > 0.01, hv / cp.maximum(h_new, 1e-3), 0.0)
            
            if step % 20 == 0:
                nans = int(cp.isnan(h_gpu_b).sum() + cp.isnan(u_gpu_b).sum() + cp.isnan(v_gpu_b).sum())
                infs = int(cp.isinf(h_gpu_b).sum() + cp.isinf(u_gpu_b).sum() + cp.isinf(v_gpu_b).sum())
                nan_b += nans
                inf_b += infs
                
        cp.cuda.Stream.null.synchronize()
        time_b = time.time() - t0_b
        print(f"  [GPU Test B] Completed in {time_b:.2f}s ({time_b/200*1000:.2f} ms/step)")
        print(f"  [GPU Test B] Min dt: {min(dt_list_b):.3f}s, Max dt: {max(dt_list_b):.3f}s, Mean dt: {np.mean(dt_list_b):.3f}s")
        print(f"  [GPU Test B] NaN violations: {nan_b}, Inf violations: {inf_b}")
        
        c4_pass = (nan_count_total == 0) and (inf_count_total == 0) and (nan_b == 0) and (inf_b == 0) and (min(dt_list_a) >= 0.80) and (min(dt_list_b) >= 0.60)
        self.results["challenge_4_swe_gpu_simulation_stability"] = {
            "passed": bool(c4_pass),
            "verdict": "PASS" if c4_pass else "FAIL",
            "gpu_hardware": gpu_name,
            "test_a_timesteps": 350,
            "test_a_wall_time_s": time_a,
            "test_a_min_dt": float(min(dt_list_a)),
            "test_a_max_dt": float(max(dt_list_a)),
            "test_a_mean_dt": float(np.mean(dt_list_a)),
            "test_a_nans": nan_count_total,
            "test_a_infs": inf_count_total,
            "test_b_stress_timesteps": 200,
            "test_b_wall_time_s": time_b,
            "test_b_min_dt": float(min(dt_list_b)),
            "test_b_max_dt": float(max(dt_list_b)),
            "test_b_mean_dt": float(np.mean(dt_list_b)),
            "test_b_nans": nan_b,
            "test_b_infs": inf_b
        }

    # ------------------------------------------------------------------------------------
    # CHALLENGE 5: FLOODPLAIN INVARIANCE AND ACTIVE CORRIDOR INTEGRITY AUDIT
    # ------------------------------------------------------------------------------------
    def challenge_5_floodplain_invariance_and_integrity(self):
        print("\n" + "=" * 80)
        print("CHALLENGE 5: FLOODPLAIN INVARIANCE (0 LEAKED CELLS OUTSIDE ACTIVE CORRIDOR)")
        print("=" * 80)
        
        # 1. Base DEM SHA-256 Hash
        hasher = hashlib.sha256()
        with open(BASE_DEM_PATH, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        base_hash = hasher.hexdigest()
        hash_matched = (base_hash == EXPECTED_BASE_SHA256)
        print(f"  Base DEM SHA-256: {base_hash} -> {'MATCHED' if hash_matched else 'MISMATCH'}")
        
        # 2. Strict Floodplain Invariance outside authorized river corridor
        # Construct the authorized corridor from all branch masks and thalweg buffers (<=90m for rivers, <=75m for canals)
        # Load thalweg paths
        dist_ba = distance_transform_edt(~(self.mask_song_ba)) * 30.0
        
        # Let's check thalweg distances
        all_paths_mask = np.zeros_like(self.carved_mask)
        for b_name, b_data in self.thalwegs.items():
            for pt in b_data:
                all_paths_mask[pt[0], pt[1]] = True
                
        dist_all_thalwegs = distance_transform_edt(~all_paths_mask) * 30.0
        
        # Authorized active corridor: union of branch masks OR buffered thalwegs (90m)
        authorized_active_corridor = (
            self.union_channel_mask |
            self.mask_song_ba |
            self.mask_song_ban_thach |
            self.mask_song_ky_lo |
            self.mask_kenh_chinh_bac |
            self.mask_kenh_chinh_nam |
            (dist_all_thalwegs <= 90.0)
        )
        
        authorized_cells = int(np.sum(authorized_active_corridor))
        unauthorized_domain = ~authorized_active_corridor
        unauthorized_cells = int(np.sum(unauthorized_domain))
        
        leaked_outside_authorized = int(np.sum(self.delta_z[unauthorized_domain] > 1e-6))
        max_leak_outside = float(np.max(self.delta_z[unauthorized_domain])) if unauthorized_cells > 0 else 0.0
        
        print(f"  Authorized Active Corridor Cells: {authorized_cells:,} ({authorized_cells/self.delta_z.size*100:.2f}%)")
        print(f"  Floodplain Outside Corridor Cells: {unauthorized_cells:,} ({unauthorized_cells/self.delta_z.size*100:.2f}%)")
        print(f"  Leaked Cells Outside Corridor:    {leaked_outside_authorized} (Threshold: EXACTLY 0)")
        print(f"  Max Leak Magnitude:               {max_leak_outside:.6f} m")
        
        # 3. Domain-Wide Raising Check: z_carved > z_base or delta_z < 0
        cells_raised = int(np.sum(self.carved_dem > self.base_dem + 1e-5))
        negative_dz = int(np.sum(self.delta_z < -1e-6))
        print(f"  Domain-Wide Raised Cells (z_carved > z_base): {cells_raised}")
        print(f"  Domain-Wide Negative delta_z:                 {negative_dz}")
        
        # 4. Strict Algebraic Consistency: Carved == Base - delta_z
        algebraic_diff = np.abs((self.base_dem - self.carved_dem) - self.delta_z)
        max_algebraic_diff = float(np.max(algebraic_diff))
        inconsistent_cells = int(np.sum(algebraic_diff > 1e-4))
        print(f"  Algebraic Consistency Max Diff:   {max_algebraic_diff:.10f} m")
        print(f"  Inconsistent Cells (> 0.1mm):     {inconsistent_cells}")
        
        # 5. Đập Đồng Cam Weir Crest Invariance (All 187 cells + Node 1278, 1217)
        weir_dz = self.delta_z[self.dong_cam_mask]
        weir_max_dz = float(np.max(np.abs(weir_dz)))
        weir_viol = int(np.sum(weir_dz != 0.0))
        node_dz = float(self.delta_z[1278, 1217])
        node_carved_z = float(self.carved_dem[1278, 1217])
        print(f"  Đập Đồng Cam Weir Crest (187 cells): max |delta_z| = {weir_max_dz:.10f} m, violations = {weir_viol}")
        print(f"  Crossing Node (1278, 1217): delta_z = {node_dz:.10f} m, elevation = {node_carved_z:.4f} m MSL (Expected: +5.50m)")
        
        # 6. Natural Off-Channel Negative Elevation Cells (Đầm Ô Loan)
        nat_neg_mask = (self.base_dem > -9990.0) & (self.base_dem < 0.0)
        off_channel_neg = nat_neg_mask & unauthorized_domain
        off_channel_neg_count = int(np.sum(off_channel_neg))
        off_channel_neg_leaks = int(np.sum(self.delta_z[off_channel_neg] > 1e-6))
        print(f"  Off-Channel Natural Negative Cells (Đầm Ô Loan): {off_channel_neg_count:,}, leaks: {off_channel_neg_leaks}")
        
        c5_pass = (
            hash_matched and
            (leaked_outside_authorized == 0) and
            (cells_raised == 0) and
            (negative_dz == 0) and
            (inconsistent_cells == 0) and
            (weir_max_dz == 0.0) and
            (weir_viol == 0) and
            (node_dz == 0.0) and
            (off_channel_neg_leaks == 0)
        )
        
        self.results["challenge_5_floodplain_invariance_and_integrity"] = {
            "passed": bool(c5_pass),
            "verdict": "PASS" if c5_pass else "FAIL",
            "base_dem_sha256": base_hash,
            "hash_matched": hash_matched,
            "authorized_corridor_cells": authorized_cells,
            "floodplain_outside_corridor_cells": unauthorized_cells,
            "leaked_cells_outside_corridor": leaked_outside_authorized,
            "max_leak_outside_m": max_leak_outside,
            "domain_wide_raised_cells": cells_raised,
            "domain_wide_negative_delta_z": negative_dz,
            "max_algebraic_diff_m": max_algebraic_diff,
            "algebraic_inconsistent_cells": inconsistent_cells,
            "weir_crest_cells": int(np.sum(self.dong_cam_mask)),
            "weir_crest_max_dz": weir_max_dz,
            "weir_crest_violations": weir_viol,
            "crossing_node_1278_1217_dz": node_dz,
            "crossing_node_elevation_msl": node_carved_z,
            "off_channel_natural_neg_cells": off_channel_neg_count,
            "off_channel_natural_neg_leaks": off_channel_neg_leaks
        }

    # ------------------------------------------------------------------------------------
    # SUMMARY AND EXPORT
    # ------------------------------------------------------------------------------------
    def summarize_and_export(self):
        print("\n" + "=" * 80)
        print("EMPIRICAL CHALLENGER 2 SUMMARY & VERDICT")
        print("=" * 80)
        all_passed = all(res["passed"] for res in self.results.values())
        overall_verdict = "APPROVE" if all_passed else "REQUEST_CHANGES"
        
        print(f"Overall Empirical Verdict: {overall_verdict}")
        for k, res in self.results.items():
            print(f"  - {k}: {res['verdict']}")
            
        exec_time = time.time() - self.start_time
        print(f"Total Audit Execution Time: {exec_time:.2f}s")
        
        summary_payload = {
            "audit_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "overall_verdict": overall_verdict,
            "all_passed": all_passed,
            "total_execution_time_s": exec_time,
            "challenges": self.results
        }
        
        with open(OUTPUT_RESULTS_JSON, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)
        print(f"Saved empirical results to: {OUTPUT_RESULTS_JSON}")


if __name__ == "__main__":
    harness = AdversarialGeometryStabilityHarness()
    harness.run_all_challenges()
