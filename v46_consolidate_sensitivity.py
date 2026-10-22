"""Consolidate V46 sensitivity dry-runs into an auditable stable core.

This script never modifies the DEM. It intersects Tier-A consensus candidates
from strict/base/wide corridor settings, labels connected components, and writes
component-level evidence plus hashes of every source artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import label


ROOT = Path(r"D:/VTP")
DEFAULT_STRICT = ROOT / "V46_dryrun_sensitivity/strict_1_2"
DEFAULT_BASE = ROOT / "V46_dryrun_20260930"
DEFAULT_WIDE = ROOT / "V46_dryrun_sensitivity/wide_3_5"
DEFAULT_OUT = ROOT / "V46_stable_core_20260930"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_tier(run_dir: Path):
    p = run_dir / "V46_obstruction_candidate_tier.tif"
    with rasterio.open(p) as src:
        return src.read(1), src.profile.copy(), src.transform, src.crs, p


def write_raster(path: Path, arr: np.ndarray, profile: dict, dtype: str, nodata: int = 0) -> None:
    p = profile.copy()
    p.update(driver="GTiff", dtype=dtype, count=1, compress="deflate", nodata=nodata)
    with rasterio.open(path, "w", **p) as dst:
        dst.write(arr.astype(dtype), 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", type=Path, default=DEFAULT_STRICT)
    ap.add_argument("--base", type=Path, default=DEFAULT_BASE)
    ap.add_argument("--wide", type=Path, default=DEFAULT_WIDE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    s, profile, transform, crs, ps = read_tier(args.strict)
    b, profile_b, transform_b, crs_b, pb = read_tier(args.base)
    w, profile_w, transform_w, crs_w, pw = read_tier(args.wide)
    if s.shape != b.shape or s.shape != w.shape:
        raise ValueError("Sensitivity rasters have different shapes")
    if transform != transform_b or transform != transform_w or crs != crs_b or crs != crs_w:
        raise ValueError("Sensitivity rasters are not on the same grid")

    tier_a_s = s == 2
    tier_a_b = b == 2
    tier_a_w = w == 2
    stable_tier_a = tier_a_s & tier_a_b & tier_a_w
    stable_any = (s > 0) & (b > 0) & (w > 0)

    component_raster, n_components = label(stable_tier_a, np.ones((3, 3), dtype=np.uint8))
    stable_path = args.out_dir / "V46_stable_tierA_core.tif"
    component_path = args.out_dir / "V46_stable_tierA_components.tif"
    write_raster(stable_path, stable_tier_a.astype(np.uint8), profile, "uint8")
    write_raster(component_path, component_raster.astype(np.int32), profile, "int32")

    csv_in = args.strict / "V46_obstruction_candidates.csv"
    df = pd.read_csv(csv_in)
    df = df[df["review_status"] == "TIER_A_CONSENSUS_CANDIDATE"].copy()
    df["component_id"] = [int(component_raster[int(r), int(c)]) for r, c in zip(df.row, df.col)]
    df = df[df.component_id > 0]

    component_rows = []
    for cid, g in df.groupby("component_id", sort=True):
        component_rows.append({
            "component_id": int(cid),
            "cells": int(len(g)),
            "area_km2": float(len(g) * 0.0009),
            "x_min": float(g.x.min()),
            "x_max": float(g.x.max()),
            "y_min": float(g.y.min()),
            "y_max": float(g.y.max()),
            "relief_min_m": float(g.local_relief_m.min()),
            "relief_median_m": float(g.local_relief_m.median()),
            "relief_max_m": float(g.local_relief_m.max()),
            "cells_relief_le_2m": int((g.local_relief_m <= 2.0).sum()),
            "cells_relief_le_3m": int((g.local_relief_m <= 3.0).sum()),
            "v44_legacy_overlap_cells": int((g.v44_minus_v41_m.abs() > 0.001).sum()),
            "v45_added_overlap_cells": int((g.v45_minus_v44_m.abs() > 0.001).sum()),
            "osm_way_ids": ";".join(map(str, sorted(set(g.nearest_osm_way_id.astype(int))))),
            "hydrorivers_ids": ";".join(map(str, sorted(set(g.nearest_hyriv_id.astype(int))))),
        })

    components_csv = args.out_dir / "V46_stable_tierA_components.csv"
    pd.DataFrame(component_rows).to_csv(components_csv, index=False, encoding="utf-8-sig")

    sizes = np.bincount(component_raster.ravel())[1:]
    stable_count = int(stable_tier_a.sum())
    summary = {
        "status": "STABLE_CORE_DRY_RUN_NO_DEM_MODIFICATION",
        "grid": {
            "shape": list(stable_tier_a.shape),
            "crs": str(crs),
            "transform": list(transform)[:6],
            "cell_area_km2": 0.0009,
        },
        "sensitivity": {
            "strict_tier_a_cells": int(tier_a_s.sum()),
            "base_tier_a_cells": int(tier_a_b.sum()),
            "wide_tier_a_cells": int(tier_a_w.sum()),
            "stable_tier_a_intersection_cells": stable_count,
            "stable_tier_a_area_km2": stable_count * 0.0009,
            "strict_not_in_base": int((tier_a_s & ~tier_a_b).sum()),
            "base_not_in_wide": int((tier_a_b & ~tier_a_w).sum()),
            "stable_any_candidate_cells": int(stable_any.sum()),
        },
        "components": {
            "count": int(n_components),
            "singletons": int((sizes == 1).sum()),
            "multi_cell": int((sizes > 1).sum()),
            "largest_cells": int(sizes.max()) if len(sizes) else 0,
            "sizes_desc": sorted(map(int, sizes.tolist()), reverse=True),
        },
        "stable_core_evidence": {
            "relief_min_m": float(df.local_relief_m.min()),
            "relief_median_m": float(df.local_relief_m.median()),
            "relief_max_m": float(df.local_relief_m.max()),
            "cells_relief_le_2m": int((df.local_relief_m <= 2.0).sum()),
            "cells_relief_le_3m": int((df.local_relief_m <= 3.0).sum()),
            "cells_relief_gt_3m": int((df.local_relief_m > 3.0).sum()),
            "v44_legacy_overlap_cells": int((df.v44_minus_v41_m.abs() > 0.001).sum()),
            "v45_added_overlap_cells": int((df.v45_minus_v44_m.abs() > 0.001).sum()),
        },
        "invariants": {
            "sentinel1_2021_used": False,
            "osm_temporal_cutoff": "2021-11-25T00:00:00Z",
            "dem_modified": False,
        },
        "outputs": {
            "stable_core_raster": str(stable_path),
            "component_raster": str(component_path),
            "component_csv": str(components_csv),
        },
    }
    summary_path = args.out_dir / "V46_stable_core_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    input_paths = [
        ps, pb, pw,
        args.strict / "V46_dryrun_summary.json",
        args.base / "V46_dryrun_summary.json",
        args.wide / "V46_dryrun_summary.json",
        csv_in,
    ]
    output_paths = [stable_path, component_path, components_csv, summary_path]
    manifest = {
        "algorithm": str(Path(__file__)),
        "algorithm_sha256": sha256(Path(__file__)),
        "inputs": {str(p): sha256(p) for p in input_paths},
        "outputs": {str(p): sha256(p) for p in output_paths},
    }
    manifest_path = args.out_dir / "V46_stable_core_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "stable_tier_a_cells": stable_count,
        "components": int(n_components),
        "cells_relief_le_3m": summary["stable_core_evidence"]["cells_relief_le_3m"],
        "cells_relief_gt_3m": summary["stable_core_evidence"]["cells_relief_gt_3m"],
        "summary": str(summary_path),
        "manifest": str(manifest_path),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
