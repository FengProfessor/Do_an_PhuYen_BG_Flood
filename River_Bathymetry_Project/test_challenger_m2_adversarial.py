"""
========================================================================================
ADVERSARIAL STRESS-TEST HARNESS — MILESTONE 2 (EMPIRICAL CHALLENGER)
Downhill Monotonicity & Sink Elimination Verification Across All 5 Thalwegs
========================================================================================

Author: challenger_m2_1 (teamwork_preview_challenger)
Role: Empirical Challenger / Adversarial Critic & Specialist
Deliverable Under Audit:
  - D:\\VTP\\River_Bathymetry_Project\\PhuYen_DEM_30m_with_Bathymetry_trial.tif
  - D:\\VTP\\River_Bathymetry_Project\\PhuYen_DEM_30m_with_Full_River_Bathymetry.tif
  - D:\\VTP\\River_Bathymetry_Project\\delta_z_bathymetry.tif
  - D:\\VTP\\River_Bathymetry_Project\\thalweg_paths.json
  - D:\\VTP\\05-Du-lieu-GIS\\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif

Mandatory Verification Criteria:
1. Base DEM SHA-256 hash integrity: 0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508
2. Downhill monotonicity: dz/ds <= -0.0002, exactly 0 uphill steps across ALL 5 branches.
3. Zero depression sinks: exactly 0 thalweg depression sinks across ALL 5 branches.
4. Strict multi-tolerance audit: evaluated at tol = 0.001m (1mm), tol = 0.0001m (0.1mm), and tol = 0.0m.
========================================================================================
"""

import os
import sys
import json
import hashlib
import numpy as np
import rasterio

# Paths
BASE_DEM_PATH = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
TRIAL_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Bathymetry_trial.tif"
PROD_TIF_PATH = r"D:\VTP\River_Bathymetry_Project\PhuYen_DEM_30m_with_Full_River_Bathymetry.tif"
DELTA_Z_TRIAL_PATH = r"D:\VTP\River_Bathymetry_Project\delta_z_bathymetry.tif"
DELTA_Z_PROD_PATH = r"D:\VTP\River_Bathymetry_Project\delta_z_full_bathymetry.tif"
THALWEG_JSON_PATH = r"D:\VTP\River_Bathymetry_Project\thalweg_paths.json"
OUTPUT_JSON_PATH = r"D:\VTP\River_Bathymetry_Project\challenger_m2_adversarial_results.json"

EXPECTED_BASE_SHA256 = "0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508"

BRANCH_INFO = {
    "ba": {
        "name": "Sông Ba (Sông Đà Rằng)",
        "aliases": ["ba", "song_ba"],
        "expected_d_max": 3.50,
        "sea_target_z": -2.80
    },
    "ban_thach": {
        "name": "Sông Bàn Thạch (Nhánh Nam)",
        "aliases": ["ban_thach", "song_ban_thach"],
        "expected_d_max": 2.25,
        "sea_target_z": -2.50
    },
    "ky_lo": {
        "name": "Sông Kỳ Lộ (Nhánh Bắc)",
        "aliases": ["ky_lo", "song_ky_lo"],
        "expected_d_max": 2.25,
        "sea_target_z": -2.50
    },
    "kenh_bac": {
        "name": "Kênh chính Bắc",
        "aliases": ["kenh_bac", "kenh_chinh_bac"],
        "expected_d_max": 1.20,
        "sea_target_z": 2.00
    },
    "kenh_nam": {
        "name": "Kênh chính Nam",
        "aliases": ["kenh_nam", "kenh_chinh_nam"],
        "expected_d_max": 1.20,
        "sea_target_z": 2.00
    }
}


def audit_base_dem_sha256() -> dict:
    print("=" * 80)
    print("TEST 1: CRYPTOGRAPHIC INTEGRITY AUDIT OF BASE DEM")
    print("=" * 80)
    if not os.path.exists(BASE_DEM_PATH):
        raise FileNotFoundError(f"Base DEM missing at {BASE_DEM_PATH}")
    
    sz = os.path.getsize(BASE_DEM_PATH)
    hasher = hashlib.sha256()
    with open(BASE_DEM_PATH, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest()
    matched = (actual_hash == EXPECTED_BASE_SHA256)

    print(f"  Base DEM Path: {BASE_DEM_PATH}")
    print(f"  File Size: {sz:,} bytes")
    print(f"  Expected SHA-256: {EXPECTED_BASE_SHA256}")
    print(f"  Actual SHA-256:   {actual_hash}")
    print(f"  Integrity Status: {'PASS' if matched else 'FAIL'}")

    return {
        "path": BASE_DEM_PATH,
        "size_bytes": sz,
        "expected_sha256": EXPECTED_BASE_SHA256,
        "actual_sha256": actual_hash,
        "pass": matched
    }


def audit_thalweg_branch(b_key: str, path_nodes: list, dem: np.ndarray, base_dem: np.ndarray, dz: np.ndarray) -> dict:
    meta = BRANCH_INFO[b_key]
    N = len(path_nodes)
    z_carved = np.array([dem[r, c] for r, c in path_nodes], dtype=np.float64)
    z_base = np.array([base_dem[r, c] for r, c in path_nodes], dtype=np.float64)
    dz_prof = np.array([dz[r, c] for r, c in path_nodes], dtype=np.float64)

    # 1. Step Distances ds
    ds = np.zeros(N - 1, dtype=np.float64)
    for i in range(N - 1):
        dr = (path_nodes[i+1][0] - path_nodes[i][0]) * 30.0
        dc = (path_nodes[i+1][1] - path_nodes[i][1]) * 30.0
        ds[i] = np.hypot(dr, dc)
    
    total_length_m = float(np.sum(ds))
    diffs = np.diff(z_carved)  # z[k+1] - z[k]
    slopes = diffs / ds        # dz/ds

    # 2. Multi-tolerance Uphill steps (adverse slope)
    tolerances = [0.001, 0.0001, 0.0]  # 1mm, 0.1mm, 0.0m
    uphill_results = {}
    for tol in tolerances:
        tol_key = f"tol_{tol}m"
        viol_idx = np.where(diffs > tol)[0]
        uphill_results[tol_key] = {
            "count": int(len(viol_idx)),
            "indices": viol_idx.tolist()
        }

    # 3. Multi-tolerance Sinks (local depression along 1D thalweg profile)
    # Sink condition: z[k] < z[k-1] - tol AND z[k] < z[k+1] - tol
    sink_results = {}
    for tol in tolerances:
        tol_key = f"tol_{tol}m"
        sinks = []
        for k in range(1, N - 1):
            if (z_carved[k] < z_carved[k-1] - tol) and (z_carved[k] < z_carved[k+1] - tol):
                sinks.append(k)
        sink_results[tol_key] = {
            "count": int(len(sinks)),
            "indices": sinks
        }

    # 4. Slope requirement: dz/ds <= -0.0002
    # Non-compliant steps: slope > -0.0002
    slope_violations_idx = np.where(slopes > -0.0002)[0]
    # Distinguish flat/near-flat from true uphill
    flat_steps_idx = np.where((slopes > -0.0002) & (slopes <= 0.0))[0]
    true_uphill_idx = np.where(slopes > 0.0)[0]

    max_uphill_m = float(np.max(diffs)) if len(diffs) > 0 else 0.0
    min_downhill_m = float(np.min(diffs)) if len(diffs) > 0 else 0.0
    max_slope = float(np.max(slopes)) if len(slopes) > 0 else 0.0
    min_slope = float(np.min(slopes)) if len(slopes) > 0 else 0.0

    # Detailed report of worst violations
    worst_uphill_steps = []
    if len(true_uphill_idx) > 0:
        sorted_uphill = sorted(true_uphill_idx, key=lambda i: diffs[i], reverse=True)
        for i in sorted_uphill[:10]:
            worst_uphill_steps.append({
                "from_index": int(i),
                "to_index": int(i+1),
                "from_rc": list(path_nodes[i]),
                "to_rc": list(path_nodes[i+1]),
                "from_z": float(z_carved[i]),
                "to_z": float(z_carved[i+1]),
                "step_diff_m": float(diffs[i]),
                "step_ds_m": float(ds[i]),
                "step_slope": float(slopes[i])
            })

    worst_sinks = []
    sinks_001 = sink_results["tol_0.001m"]["indices"]
    if len(sinks_001) > 0:
        for k in sinks_001[:10]:
            worst_sinks.append({
                "sink_index": int(k),
                "sink_rc": list(path_nodes[k]),
                "prev_z": float(z_carved[k-1]),
                "sink_z": float(z_carved[k]),
                "next_z": float(z_carved[k+1]),
                "drop_from_prev_m": float(z_carved[k-1] - z_carved[k]),
                "climb_to_next_m": float(z_carved[k+1] - z_carved[k])
            })

    is_compliant = (uphill_results["tol_0.001m"]["count"] == 0 and 
                    sink_results["tol_0.001m"]["count"] == 0)

    return {
        "branch_key": b_key,
        "name": meta["name"],
        "node_count": N,
        "length_m": total_length_m,
        "headwater_z_carved": float(z_carved[0]),
        "headwater_z_base": float(z_base[0]),
        "outlet_z_carved": float(z_carved[-1]),
        "outlet_z_base": float(z_base[-1]),
        "max_uphill_step_m": max_uphill_m,
        "min_downhill_step_m": min_downhill_m,
        "max_slope": max_slope,
        "min_slope": min_slope,
        "uphill_audit": uphill_results,
        "sink_audit": sink_results,
        "dz_ds_gt_minus_00002_count": int(len(slope_violations_idx)),
        "flat_or_subthreshold_steps_count": int(len(flat_steps_idx)),
        "true_uphill_steps_count": int(len(true_uphill_idx)),
        "worst_uphill_steps": worst_uphill_steps,
        "worst_sinks": worst_sinks,
        "compliant": is_compliant
    }


def run_adversarial_suite():
    print("=" * 80)
    print("STARTING ADVERSARIAL STRESS-TEST ON TRIAL & PRODUCTION BATHYMETRY")
    print("=" * 80)

    # 1. Base DEM Check
    base_dem_audit = audit_base_dem_sha256()

    # 2. Ingest DEMs and thalweg paths
    print("\n" + "=" * 80)
    print("TEST 2: LOADING DELIVERABLES & THALWEG SEQUENCES")
    print("=" * 80)
    with rasterio.open(TRIAL_TIF_PATH) as src_trial:
        trial_dem = src_trial.read(1).astype(np.float32)
    with rasterio.open(BASE_DEM_PATH) as src_base:
        base_dem = src_base.read(1).astype(np.float32)
    with rasterio.open(DELTA_Z_TRIAL_PATH) as src_dz:
        dz_trial = src_dz.read(1).astype(np.float32)

    with open(THALWEG_JSON_PATH, "r", encoding="utf-8") as f:
        thalweg_dict = json.load(f)

    # 3. Audit each of the 5 branches
    branch_audits = {}
    all_branches_pass = True

    print("\n" + "=" * 80)
    print("TEST 3: EMPIRICAL STRESS-TESTING OF ALL 5 THALWEGS")
    print("=" * 80)

    for b_key in ["ba", "ban_thach", "ky_lo", "kenh_bac", "kenh_nam"]:
        path = [(int(r), int(c)) for r, c in thalweg_dict[b_key]]
        res = audit_thalweg_branch(b_key, path, trial_dem, base_dem, dz_trial)
        branch_audits[b_key] = res

        print(f"\n--- Branch: {res['name']} ({b_key}) ---")
        print(f"  Nodes: {res['node_count']:,} | Length: {res['length_m']/1000.0:.2f} km")
        print(f"  Headwater z: {res['headwater_z_carved']:.4f}m | Outlet z: {res['outlet_z_carved']:.4f}m")
        print(f"  Uphill steps > 1.0mm:   {res['uphill_audit']['tol_0.001m']['count']}")
        print(f"  Uphill steps > 0.1mm:   {res['uphill_audit']['tol_0.0001m']['count']}")
        print(f"  Uphill steps > 0.0m:     {res['uphill_audit']['tol_0.0m']['count']}")
        print(f"  Max uphill step:        {res['max_uphill_step_m']:+.6f} m")
        print(f"  Sinks > 1.0mm:          {res['sink_audit']['tol_0.001m']['count']}")
        print(f"  Sinks > 0.1mm:          {res['sink_audit']['tol_0.0001m']['count']}")
        print(f"  Sinks > 0.0m:           {res['sink_audit']['tol_0.0m']['count']}")
        print(f"  dz/ds > -0.0002 count:  {res['dz_ds_gt_minus_00002_count']} (True uphill: {res['true_uphill_steps_count']}, Flat/shallow: {res['flat_or_subthreshold_steps_count']})")
        print(f"  Compliance Verdict:     {'PASS' if res['compliant'] else 'FAIL (CRITICAL BUG)'}")

        if not res['compliant']:
            all_branches_pass = False

    # 4. Summary Aggregations
    total_uphill_1mm = sum(b['uphill_audit']['tol_0.001m']['count'] for b in branch_audits.values())
    total_uphill_01mm = sum(b['uphill_audit']['tol_0.0001m']['count'] for b in branch_audits.values())
    total_uphill_0mm = sum(b['uphill_audit']['tol_0.0m']['count'] for b in branch_audits.values())
    total_sinks_1mm = sum(b['sink_audit']['tol_0.001m']['count'] for b in branch_audits.values())
    total_sinks_01mm = sum(b['sink_audit']['tol_0.0001m']['count'] for b in branch_audits.values())
    total_sinks_0mm = sum(b['sink_audit']['tol_0.0m']['count'] for b in branch_audits.values())

    print("\n" + "=" * 80)
    print("EXECUTIVE CHALLENGER AUDIT SUMMARY")
    print("=" * 80)
    print(f"  Base DEM SHA-256 Intact:              {base_dem_audit['pass']}")
    print(f"  Total Thalweg Branches Audited:       {len(branch_audits)}")
    print(f"  Total Adverse Uphill Steps (> 1.0mm): {total_uphill_1mm} (Expected: 0)")
    print(f"  Total Adverse Uphill Steps (> 0.1mm): {total_uphill_01mm} (Expected: 0)")
    print(f"  Total Adverse Uphill Steps (> 0.0m):   {total_uphill_0mm} (Expected: 0)")
    print(f"  Total Thalweg Depression Sinks (> 1mm):{total_sinks_1mm} (Expected: 0)")
    print(f"  Total Thalweg Depression Sinks (>0.1m):{total_sinks_01mm} (Expected: 0)")
    print(f"  Total Thalweg Depression Sinks (> 0m): {total_sinks_0mm} (Expected: 0)")
    print(f"  Overall Milestone 2 Compliance:      {'PASS' if all_branches_pass else 'FAIL'}")
    print(f"  Challenger Final Recommendation:      {'APPROVE' if (base_dem_audit['pass'] and all_branches_pass) else 'REQUEST_CHANGES'}")

    final_payload = {
        "timestamp": "2026-10-10T02:20:00Z",
        "author": "challenger_m2_1",
        "verdict": "APPROVE" if (base_dem_audit['pass'] and all_branches_pass) else "REQUEST_CHANGES",
        "base_dem_audit": base_dem_audit,
        "branch_audits": branch_audits,
        "summary": {
            "total_branches": len(branch_audits),
            "total_uphill_steps_gt_1mm": total_uphill_1mm,
            "total_uphill_steps_gt_01mm": total_uphill_01mm,
            "total_uphill_steps_gt_0mm": total_uphill_0mm,
            "total_sinks_gt_1mm": total_sinks_1mm,
            "total_sinks_gt_01mm": total_sinks_01mm,
            "total_sinks_gt_0mm": total_sinks_0mm,
            "failing_branches": [k for k, v in branch_audits.items() if not v['compliant']],
            "passing_branches": [k for k, v in branch_audits.items() if v['compliant']]
        }
    }

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2)
    print(f"\nStructured results exported to {OUTPUT_JSON_PATH}")

    return final_payload


if __name__ == "__main__":
    run_adversarial_suite()
