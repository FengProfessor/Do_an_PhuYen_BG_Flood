from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import label


ROOT = Path(r"D:\VTP")
DESIGN = ROOT / "V48_candidate_sensitivity_design_20261002.json"
SCRIPT = ROOT / "v46_conditioning_dryrun.py"
OUT_ROOT = ROOT / "V48_research_20261002" / "candidate_sensitivity"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tier_a_set(csv_path: Path) -> tuple[set[tuple[int, int]], pd.DataFrame]:
    df = pd.read_csv(csv_path)
    tier_a = df[df.review_status == "TIER_A_CONSENSUS_CANDIDATE"].copy()
    cells = set(zip(tier_a.row.astype(int), tier_a.col.astype(int)))
    return cells, tier_a


def component_count(cells: set[tuple[int, int]], shape: tuple[int, int]) -> int:
    arr = np.zeros(shape, dtype=np.uint8)
    if cells:
        rr, cc = zip(*cells)
        arr[np.asarray(rr), np.asarray(cc)] = 1
    _, n = label(arr, np.ones((3, 3), dtype=np.uint8))
    return int(n)


def write_mask(path: Path, cells: set[tuple[int, int]], profile: dict) -> None:
    arr = np.zeros((profile["height"], profile["width"]), dtype=np.uint8)
    if cells:
        rr, cc = zip(*cells)
        arr[np.asarray(rr), np.asarray(cc)] = 1
    p = profile.copy()
    p.update(dtype="uint8", count=1, nodata=0, compress="deflate")
    with rasterio.open(path, "w", **p) as dst:
        dst.write(arr, 1)


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    fixed = design["fixed_inputs"]
    baseline_dir = Path(design["baseline"]["reuse_existing"])
    baseline_csv = baseline_dir / "V46_obstruction_candidates.csv"
    baseline_tier = baseline_dir / "V46_obstruction_candidate_tier.tif"
    if not baseline_csv.exists() or not baseline_tier.exists():
        raise FileNotFoundError("V48 raw-Copernicus baseline dry-run is missing")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    run_manifest_rows = []
    for i, run in enumerate(design["runs"], start=1):
        out = OUT_ROOT / run["run_id"]
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--dem", fixed["dem"],
            "--osm", fixed["osm"],
            "--osm-max-timestamp", fixed["osm_max_timestamp"],
            "--hydrorivers", fixed["hydrorivers"],
            "--out-dir", str(out),
            "--corridor-cells", str(run["corridor_cells"]),
            "--hydro-corridor-cells", str(run["hydro_corridor_cells"]),
            "--relief-threshold-m", str(run["relief_threshold_m"]),
            "--relief-window", str(run["relief_window"]),
            "--max-slope-deg", str(run["max_slope_deg"]),
            "--max-elevation-m", str(run["max_elevation_m"]),
            "--compare-v44", str(ROOT / "_v48_no_legacy_compare_v44.asc"),
            "--compare-v45", str(ROOT / "_v48_no_legacy_compare_v45.asc"),
        ]
        print(f"[{i}/{len(design['runs'])}] {run['run_id']}", flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)
        summary_path = out / "V46_dryrun_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        run_manifest_rows.append(
            {
                "run_id": run["run_id"],
                "out_dir": str(out),
                "summary_sha256": sha256(summary_path),
                "candidate_cells": summary["results"]["candidate_cells"],
                "tier_a_cells": summary["results"]["tier_a_consensus_cells"],
                "parameters": run,
            }
        )

    baseline, base_df = tier_a_set(baseline_csv)
    with rasterio.open(baseline_tier) as src:
        profile = src.profile.copy()
        shape = src.shape

    run_sets: dict[str, set[tuple[int, int]]] = {"baseline_strict_1_2": baseline}
    rows = [
        {
            "run_id": "baseline_strict_1_2",
            "tier_a_cells": len(baseline),
            "tier_a_components": component_count(baseline, shape),
            "baseline_retained_cells": len(baseline),
            "baseline_retained_pct": 100.0,
            "new_vs_baseline_cells": 0,
            "jaccard_vs_baseline": 1.0,
            "parameters": design["baseline"],
        }
    ]
    for run in design["runs"]:
        cells, _ = tier_a_set(OUT_ROOT / run["run_id"] / "V46_obstruction_candidates.csv")
        run_sets[run["run_id"]] = cells
        inter = baseline & cells
        union = baseline | cells
        rows.append(
            {
                "run_id": run["run_id"],
                "tier_a_cells": len(cells),
                "tier_a_components": component_count(cells, shape),
                "baseline_retained_cells": len(inter),
                "baseline_retained_pct": 100.0 * len(inter) / len(baseline),
                "new_vs_baseline_cells": len(cells - baseline),
                "jaccard_vs_baseline": len(inter) / len(union) if union else 1.0,
                "parameters": run,
            }
        )

    run_ids = list(run_sets)
    all_intersection = set.intersection(*(run_sets[r] for r in run_ids))
    union_all = set.union(*(run_sets[r] for r in run_ids))
    counts = {cell: sum(cell in run_sets[r] for r in run_ids) for cell in baseline}
    ge9 = {cell for cell, count in counts.items() if count >= 9}
    ge10 = {cell for cell, count in counts.items() if count >= 10}
    all11 = {cell for cell, count in counts.items() if count == 11}

    attrs = base_df.set_index([base_df.row.astype(int), base_df.col.astype(int)])
    survival_rows = []
    for r, c in sorted(baseline):
        hit = attrs.loc[(r, c)]
        rec = {
            "row": r,
            "col": c,
            "x": float(hit.x),
            "y": float(hit.y),
            "original_z_m": float(hit.original_z_m),
            "local_relief_m_baseline": float(hit.local_relief_m),
            "slope_deg_baseline": float(hit.slope_deg),
            "survival_count_of_11": counts[(r, c)],
            "survival_fraction": counts[(r, c)] / 11.0,
        }
        for run_id in run_ids:
            rec[f"in_{run_id}"] = int((r, c) in run_sets[run_id])
        survival_rows.append(rec)

    survival_csv = OUT_ROOT / "V48_baseline815_survival.csv"
    ge9_tif = OUT_ROOT / "V48_robust_core_ge9of11.tif"
    all11_tif = OUT_ROOT / "V48_robust_core_11of11.tif"
    pd.DataFrame(survival_rows).to_csv(survival_csv, index=False)
    write_mask(ge9_tif, ge9, profile)
    write_mask(all11_tif, all11, profile)

    freq = pd.Series(list(counts.values())).value_counts().sort_index().to_dict()
    summary = {
        "status": "PASS",
        "scientific_holdout": {
            "sentinel1_2021_used_for_selection": False,
            "selection_sources": "raw Copernicus terrain + historical OSM 2021-11-25 + HydroRIVERS",
        },
        "design": str(DESIGN),
        "design_sha256": sha256(DESIGN),
        "baseline": {
            "tier_a_cells": len(baseline),
            "components_8_neighbor": component_count(baseline, shape),
        },
        "runs": rows,
        "cross_run": {
            "number_of_configurations": len(run_ids),
            "all_run_intersection_cells": len(all_intersection),
            "all_run_intersection_baseline_pct": 100.0 * len(all_intersection) / len(baseline),
            "all_run_intersection_components": component_count(all_intersection, shape),
            "ge9of11_cells": len(ge9),
            "ge9of11_baseline_pct": 100.0 * len(ge9) / len(baseline),
            "ge9of11_components": component_count(ge9, shape),
            "ge10of11_cells": len(ge10),
            "ge10of11_baseline_pct": 100.0 * len(ge10) / len(baseline),
            "union_all_tier_a_cells": len(union_all),
            "baseline_survival_frequency": {str(k): int(v) for k, v in freq.items()},
        },
        "outputs": {
            "baseline_survival_csv": str(survival_csv),
            "robust_ge9of11_mask": str(ge9_tif),
            "robust_11of11_mask": str(all11_tif),
        },
        "interpretation": [
            ">=9/11 is a parameter-sensitivity reporting threshold, not a physical truth probability.",
            "All 11 configurations exclude Sentinel-1 2021 from candidate selection.",
            "These outputs identify robust candidate locations only; they do not approve DEM cuts.",
        ],
    }
    summary_path = OUT_ROOT / "V48_candidate_sensitivity_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "status": "PASS",
        "design": str(DESIGN),
        "design_sha256": sha256(DESIGN),
        "driver": str(Path(__file__)),
        "driver_sha256": sha256(Path(__file__)),
        "candidate_algorithm": str(SCRIPT),
        "candidate_algorithm_sha256": sha256(SCRIPT),
        "base_dem": fixed["dem"],
        "sentinel1_2021_used_for_selection": False,
        "runs": run_manifest_rows,
        "summary": str(summary_path),
        "summary_sha256": sha256(summary_path),
    }
    manifest_path = OUT_ROOT / "V48_candidate_sensitivity_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
