"""
========================================================================================
ADVERSARIAL EMPIRICAL AUDIT HARNESS: MILESTONE 1 ITERATION 2 REMEDIATION
Author: challenger_m1_3 (teamwork_preview_challenger)
Role: Empirical Challenger (Critic / Specialist)
Target Deliverable: D:\\VTP\\River_Bathymetry_Project\\river_network_data.npz
========================================================================================
"""

import sys
import io
import os
import json
import hashlib
import numpy as np
import rasterio
from scipy.ndimage import label

# Force UTF-8 stdout
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DEM_PATH = r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
JRC_PATH = r"D:\VTP\V48_research_20261002\hydro_evidence_raw\V46_JRC_GSW1_3_occurrence_1984_2020.tif"
OSM_DIST_PATH = r"D:\VTP\V46_dryrun_20260930\V46_distance_to_osm_waterway_m.tif"
NPZ_PATH = r"D:\VTP\River_Bathymetry_Project\river_network_data.npz"
BASE_DEM_EXPECTED_SHA256 = "0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508"

EXPECTED_BRANCHES = [
    "song_ba",
    "song_ban_thach",
    "song_ky_lo",
    "kenh_chinh_bac",
    "kenh_chinh_nam"
]


def run_comprehensive_challenge():
    print("=" * 80)
    print("EMPIRICAL CHALLENGER: MILESTONE 1 ITERATION 2 DEEP STRESS TEST")
    print("=" * 80)

    results = {
        "status": "PASS",
        "failures": [],
        "checks": {}
    }

    # 1. BASE DEM SHA-256 INTEGRITY
    print("\n[CHALLENGE 1] Base DEM Cryptographic Integrity Audit...")
    hasher = hashlib.sha256()
    with open(BASE_DEM_PATH, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    actual_sha = hasher.hexdigest()
    sha_pass = (actual_sha == BASE_DEM_EXPECTED_SHA256)
    print(f"  Actual SHA-256  : {actual_sha}")
    print(f"  Expected SHA-256: {BASE_DEM_EXPECTED_SHA256}")
    print(f"  Verdict: {'PASS' if sha_pass else 'FAIL'}")
    results["checks"]["base_dem_sha256"] = {
        "pass": sha_pass,
        "actual": actual_sha,
        "expected": BASE_DEM_EXPECTED_SHA256
    }
    if not sha_pass:
        results["failures"].append("Base DEM SHA-256 mismatch! File was tampered.")

    # Load Base DEM raster
    with rasterio.open(BASE_DEM_PATH) as src:
        dem = src.read(1)
        transform = src.transform
        bounds = src.bounds
        crs = str(src.crs)

    with rasterio.open(JRC_PATH) as src:
        jrc = src.read(1)

    with rasterio.open(OSM_DIST_PATH) as src:
        osm = src.read(1)

    # 2. NPZ ARCHIVE INTEGRITY & KEY COMPLETENESS
    print("\n[CHALLENGE 2] NPZ Archive Completeness & Structure...")
    npz_data = np.load(NPZ_PATH, allow_pickle=True)
    all_keys = set(npz_data.keys())
    print(f"  Total keys in NPZ: {len(all_keys)}")
    print(f"  Keys: {sorted(list(all_keys))}")

    required_keys = ["dong_cam_mask", "union_channel_mask", "metadata_json"]
    for b in EXPECTED_BRANCHES:
        required_keys.append(f"mask_{b}")
        required_keys.append(f"thalweg_{b}")

    missing_keys = [k for k in required_keys if k not in all_keys]
    if missing_keys:
        results["failures"].append(f"Missing keys in NPZ: {missing_keys}")
    print(f"  Required keys check: {'PASS' if not missing_keys else 'FAIL'}")

    meta = json.loads(str(npz_data["metadata_json"]))
    branches_meta = list(meta.get("branches", {}).keys())
    print(f"  Branches declared in metadata: {branches_meta}")
    has_pseudo = "kenh_dong_cam" in branches_meta
    print(f"  Pseudo-branch 'kenh_dong_cam' eliminated: {not has_pseudo}")
    if has_pseudo:
        results["failures"].append("Pseudo-branch 'kenh_dong_cam' is still present in metadata branches!")

    # 3. ĐẬP ĐỒNG CAM WEIR MASK GEOMETRY & PHYSICAL HYDROLOGY
    print("\n[CHALLENGE 3] Đập Đồng Cam Weir Mask Relocation & Channel Crossing...")
    dong_cam_mask = npz_data["dong_cam_mask"]
    weir_coords = np.argwhere(dong_cam_mask)
    n_weir_cells = len(weir_coords)
    r_min, r_max = int(np.min(weir_coords[:, 0])), int(np.max(weir_coords[:, 0]))
    c_min, c_max = int(np.min(weir_coords[:, 1])), int(np.max(weir_coords[:, 1]))
    n_rows = r_max - r_min + 1
    n_cols = c_max - c_min + 1
    is_solid = (n_weir_cells == n_rows * n_cols) and np.all(dong_cam_mask[r_min:r_max+1, c_min:c_max+1])

    geom_pass = (n_weir_cells == 187) and (r_min == 1272) and (r_max == 1288) and (c_min == 1212) and (c_max == 1222)
    print(f"  Total cells: {n_weir_cells} (Expected: 187) -> {'PASS' if n_weir_cells == 187 else 'FAIL'}")
    print(f"  Rows span  : [{r_min}, {r_max}] (Expected: [1272, 1288]) -> {'PASS' if (r_min==1272 and r_max==1288) else 'FAIL'}")
    print(f"  Cols span  : [{c_min}, {c_max}] (Expected: [1212, 1222]) -> {'PASS' if (c_min==1212 and c_max==1222) else 'FAIL'}")
    print(f"  Solid block: {is_solid} ({n_rows} x {n_cols} = {n_rows*n_cols} cells)")

    if not geom_pass:
        results["failures"].append(f"Đập Đồng Cam geometry mismatch: cells={n_weir_cells}, rows=[{r_min}, {r_max}], cols=[{c_min}, {c_max}]")

    # Overlap with Sông Ba corridor
    mask_ba = npz_data["mask_song_ba"]
    overlap_corridor = int(np.sum(dong_cam_mask & mask_ba))
    corridor_overlap_pct = overlap_corridor / n_weir_cells * 100.0
    print(f"  Overlap with Sông Ba corridor (mask_song_ba): {overlap_corridor} / {n_weir_cells} ({corridor_overlap_pct:.1f}%)")
    if overlap_corridor == 0:
        results["failures"].append("dong_cam_mask has 0 overlap with mask_song_ba!")

    # Overlap with Sông Ba thalweg
    thalweg_ba = npz_data["thalweg_song_ba"]
    thalweg_set = set((int(r), int(c)) for r, c in thalweg_ba)
    weir_set = set((int(r), int(c)) for r, c in weir_coords)
    overlap_thalweg = len(thalweg_set.intersection(weir_set))
    print(f"  Overlap with Sông Ba thalweg (thalweg_song_ba): {overlap_thalweg} cells")
    if overlap_thalweg == 0:
        results["failures"].append("dong_cam_mask does NOT cross Sông Ba thalweg!")

    # Check crossing cell (1278, 1217)
    crossing_rc = (1278, 1217)
    in_mask = dong_cam_mask[crossing_rc]
    in_thalweg = crossing_rc in thalweg_set
    crossing_z = float(dem[crossing_rc])
    crossing_jrc = int(jrc[crossing_rc])
    crossing_osm = float(osm[crossing_rc])
    print(f"  Crossing node {crossing_rc}:")
    print(f"    In dong_cam_mask: {in_mask}")
    print(f"    In thalweg_song_ba: {in_thalweg}")
    print(f"    Base DEM elevation: {crossing_z:.2f}m MSL (Expected: +5.50m MSL)")
    print(f"    JRC Water Occurrence: {crossing_jrc}%")
    print(f"    OSM Waterway Distance: {crossing_osm:.1f}m")

    crossing_pass = in_mask and in_thalweg and (abs(crossing_z - 5.50) < 0.05)
    if not crossing_pass:
        results["failures"].append(f"Crossing node (1278, 1217) validation failed: in_mask={in_mask}, in_thalweg={in_thalweg}, z={crossing_z:.2f}m")

    # Elevation stats of weir mask
    weir_z = dem[dong_cam_mask]
    z_min, z_max = float(np.min(weir_z)), float(np.max(weir_z))
    z_mean, z_median = float(np.mean(weir_z)), float(np.median(weir_z))
    print(f"  Weir crest Base DEM elevations: min={z_min:.2f}m, max={z_max:.2f}m, mean={z_mean:.2f}m, median={z_median:.2f}m")

    # JRC & OSM stats
    weir_jrc = jrc[dong_cam_mask]
    weir_osm = osm[dong_cam_mask]
    print(f"  Weir crest JRC Water Occurrence: min={np.min(weir_jrc)}%, max={np.max(weir_jrc)}%, mean={np.mean(weir_jrc):.1f}%")
    print(f"  Weir crest OSM Distance: min={np.min(weir_osm):.1f}m, max={np.max(weir_osm):.1f}m, mean={np.mean(weir_osm):.1f}m")

    results["checks"]["dong_cam_weir"] = {
        "cell_count": n_weir_cells,
        "rows": [r_min, r_max],
        "cols": [c_min, c_max],
        "overlap_corridor_cells": overlap_corridor,
        "overlap_thalweg_cells": overlap_thalweg,
        "crossing_node": crossing_rc,
        "crossing_z": crossing_z,
        "crossing_jrc": crossing_jrc,
        "crossing_osm": crossing_osm,
        "z_min": z_min, "z_max": z_max, "z_mean": z_mean, "z_median": z_median,
        "pass": geom_pass and crossing_pass
    }

    # 4. 8-CONNECTIVITY STRESS TEST ACROSS ALL 5 THALWEGS
    print("\n[CHALLENGE 4] Strict 8-Connectivity Stress Test on All 5 Thalwegs...")
    conn_results = {}
    union_mask = npz_data["union_channel_mask"]

    for b_id in EXPECTED_BRANCHES:
        thalweg = npz_data[f"thalweg_{b_id}"]
        mask = npz_data[f"mask_{b_id}"]
        N = len(thalweg)

        dr = np.abs(np.diff(thalweg[:, 0]))
        dc = np.abs(np.diff(thalweg[:, 1]))
        chebyshev = np.maximum(dr, dc)

        gaps = np.where(chebyshev > 1)[0]
        zero_steps = np.where(chebyshev == 0)[0]
        max_step = int(np.max(chebyshev)) if N > 1 else 0
        min_step = int(np.min(chebyshev)) if N > 1 else 0

        # Simple path: cycle check
        tuples_list = [tuple(rc) for rc in thalweg]
        unique_nodes = set(tuples_list)
        duplicates = N - len(unique_nodes)

        # Containment check
        uncontained_branch = int(np.sum(~mask[thalweg[:, 0], thalweg[:, 1]]))
        uncontained_union = int(np.sum(~union_mask[thalweg[:, 0], thalweg[:, 1]]))

        branch_pass = (len(gaps) == 0) and (len(zero_steps) == 0) and (max_step == 1) and (min_step == 1) and (duplicates == 0) and (uncontained_branch == 0)

        print(f"  Branch '{b_id:16s}': {N:5d} nodes, {N-1:5d} steps, min/max=[{min_step}, {max_step}], gaps={len(gaps)}, zero_steps={len(zero_steps)}, duplicates={duplicates}, uncontained={uncontained_branch} -> {'PASS' if branch_pass else 'FAIL'}")

        if not branch_pass:
            results["failures"].append(f"Branch {b_id} 8-connectivity failure! Gaps={len(gaps)}, zero_steps={len(zero_steps)}, max_step={max_step}")

        conn_results[b_id] = {
            "node_count": N,
            "step_count": N - 1,
            "min_step": min_step,
            "max_step": max_step,
            "gaps": len(gaps),
            "zero_steps": len(zero_steps),
            "duplicates": duplicates,
            "uncontained_branch": uncontained_branch,
            "pass": branch_pass
        }

    results["checks"]["8_connectivity"] = conn_results

    # 5. SÔNG BÀN THẠCH CORRIDOR CONTINUITY & FRACTURE RECOVERY AUDIT
    print("\n[CHALLENGE 5] Sông Bàn Thạch Corridor Mask Continuity & Area Audit...")
    mask_bt = npz_data["mask_song_ban_thach"]
    thalweg_bt = npz_data["thalweg_song_ban_thach"]
    bt_cells = int(np.sum(mask_bt))
    bt_area_km2 = bt_cells * 900.0 / 1e6

    print(f"  Sông Bàn Thạch corridor mask area: {bt_cells:,} cells ({bt_area_km2:.2f} km²)")
    # Check target ~34,372 cells
    diff_from_target = abs(bt_cells - 34372)
    print(f"  Difference from expected target (34,372 cells): {diff_from_target} cells")
    bt_area_pass = (bt_cells >= 34000)
    print(f"  Area check (>= 34,000 cells): {'PASS' if bt_area_pass else 'FAIL'}")
    if not bt_area_pass:
        results["failures"].append(f"Sông Bàn Thạch corridor mask area is under-recovered: {bt_cells} cells (expected ~34,372)")

    # Connected component analysis using 8-connectivity
    s8 = np.ones((3, 3), dtype=bool)
    labeled_bt, num_features = label(mask_bt, structure=s8)
    thalweg_labels = set(labeled_bt[thalweg_bt[:, 0], thalweg_bt[:, 1]])
    print(f"  Total connected components in Bàn Thạch mask (8-conn): {num_features}")
    print(f"  Labels traversed by thalweg: {thalweg_labels}")
    # The thalweg should be in a single connected component (excluding background 0)
    thalweg_components = thalweg_labels - {0}
    single_component_thalweg = (len(thalweg_components) == 1)
    print(f"  Thalweg traverses exactly 1 single connected component: {single_component_thalweg}")
    if not single_component_thalweg:
        results["failures"].append(f"Sông Bàn Thạch thalweg traverses multiple disconnected components: {thalweg_components}")

    # Check upstream reach: row < 1500 or col < 600
    # In Iteration 1, the upstream section from discharge (1783, 200) was fractured
    upstream_mask_cells = int(np.sum(mask_bt[:, :600]))
    print(f"  Upstream corridor cells (cols 0..600): {upstream_mask_cells:,} cells")
    if upstream_mask_cells < 5000:
        results["failures"].append(f"Upstream reach still fractured! Found only {upstream_mask_cells} cells in cols 0..600.")

    results["checks"]["ban_thach_corridor"] = {
        "mask_cells": bt_cells,
        "mask_area_km2": bt_area_km2,
        "diff_from_34372": diff_from_target,
        "num_connected_components": int(num_features),
        "thalweg_components": list(thalweg_components),
        "upstream_cells_col_lt_600": upstream_mask_cells,
        "pass": bt_area_pass and single_component_thalweg
    }

    # 6. KÊNH CHÍNH BẮC INTAKE ALIGNMENT & DRY LAND BRIDGE ELIMINATION
    print("\n[CHALLENGE 6] Kênh chính Bắc Intake Alignment & Terrain Audit...")
    thalweg_kn = npz_data["thalweg_kenh_chinh_bac"]
    kn_inflow = tuple(thalweg_kn[0])
    kn_outlet = tuple(thalweg_kn[-1])
    print(f"  Inflow: {kn_inflow}, Outlet: {kn_outlet}")
    kn_inflow_pass = (kn_inflow == (1270, 1217))
    print(f"  Anchored at true North abutment (1270, 1217): {kn_inflow_pass}")

    # Check dry cells (>300m from OSM waterway)
    kn_dry_cells = [tuple(pt) for pt in thalweg_kn if osm[pt[0], pt[1]] > 300.0]
    kn_osm_dists = [float(osm[pt[0], pt[1]]) for pt in thalweg_kn]
    print(f"  OSM waterway distance along Kênh Bắc: min={np.min(kn_osm_dists):.1f}m, max={np.max(kn_osm_dists):.1f}m, mean={np.mean(kn_osm_dists):.1f}m")
    print(f"  Cells forced across dry terrain (>300m): {len(kn_dry_cells)} / {len(thalweg_kn)}")
    if len(kn_dry_cells) > 0:
        results["failures"].append(f"Kênh chính Bắc still has {len(kn_dry_cells)} cells forced through dry terrain!")

    results["checks"]["kenh_chinh_bac"] = {
        "inflow": kn_inflow,
        "outlet": kn_outlet,
        "dry_cells_count": len(kn_dry_cells),
        "mean_osm_dist": float(np.mean(kn_osm_dists)),
        "max_osm_dist": float(np.max(kn_osm_dists)),
        "pass": kn_inflow_pass and (len(kn_dry_cells) == 0)
    }

    # 7. OVERALL VERDICT
    print("\n" + "=" * 80)
    if len(results["failures"]) == 0:
        results["status"] = "PASS"
        results["verdict"] = "APPROVE"
        print("OVERALL VERDICT: APPROVE (ALL EMPIRICAL ADVERSARIAL CHALLENGES PASSED 100%)")
    else:
        results["status"] = "FAIL"
        results["verdict"] = "REQUEST_CHANGES"
        print(f"OVERALL VERDICT: REQUEST_CHANGES ({len(results['failures'])} FAILURES DETECTED)")
        for fail in results["failures"]:
            print(f"  [X] {fail}")
    print("=" * 80)

    def default_serializer(obj):
        if isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)

    # Save to json
    out_json = r"D:\VTP\River_Bathymetry_Project\empirical_audit_results_iter2.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=default_serializer)
    print(f"\nEmpirical audit results written to {out_json}")

    return results


if __name__ == "__main__":
    res = run_comprehensive_challenge()
    if res["verdict"] != "APPROVE":
        sys.exit(1)
