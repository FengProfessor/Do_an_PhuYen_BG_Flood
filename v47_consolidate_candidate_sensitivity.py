from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import label


ROOT = Path(r"D:\VTP")
DESIGN = ROOT / "V47_candidate_sensitivity_design_20261001.json"
BASE_DIR = ROOT / "V46_dryrun_sensitivity/strict_1_2"
RUN_ROOT = ROOT / "V47_candidate_sensitivity_20261001"
OUT = RUN_ROOT / "V47_candidate_sensitivity_summary.json"
CELL_CSV = RUN_ROOT / "V47_baseline407_survival.csv"
ROBUST80_TIF = RUN_ROOT / "V47_robust_core_ge9of11.tif"
ALL_TIF = RUN_ROOT / "V47_robust_core_11of11.tif"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tier_a_set(csv_path: Path) -> tuple[set[tuple[int, int]], pd.DataFrame]:
    df = pd.read_csv(csv_path)
    a = df[df.review_status == "TIER_A_CONSENSUS_CANDIDATE"].copy()
    s = set(zip(a.row.astype(int), a.col.astype(int)))
    return s, a


def ncomp(cells: set[tuple[int, int]], shape: tuple[int, int]) -> int:
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
    base_csv = BASE_DIR / "V46_obstruction_candidates.csv"
    baseline, base_df = tier_a_set(base_csv)
    if len(baseline) != 407:
        raise RuntimeError(f"expected 407 baseline Tier-A cells, found {len(baseline)}")

    with rasterio.open(BASE_DIR / "V46_obstruction_candidate_tier.tif") as src:
        profile = src.profile.copy()
        shape = src.shape

    run_sets: dict[str, set[tuple[int, int]]] = {"baseline_strict_1_2": baseline}
    run_rows = []
    base_summary = json.loads((BASE_DIR / "V46_dryrun_summary.json").read_text(encoding="utf-8"))
    run_rows.append(
        {
            "run_id": "baseline_strict_1_2",
            "tier_a_cells": len(baseline),
            "tier_a_components": ncomp(baseline, shape),
            "baseline_retained_cells": len(baseline),
            "baseline_retained_pct": 100.0,
            "new_vs_baseline_cells": 0,
            "jaccard_vs_baseline": 1.0,
            "parameters": base_summary["parameters"],
        }
    )

    for run in design["runs"]:
        run_id = run["run_id"]
        d = RUN_ROOT / run_id
        s, _ = tier_a_set(d / "V46_obstruction_candidates.csv")
        run_sets[run_id] = s
        inter = baseline & s
        union = baseline | s
        run_rows.append(
            {
                "run_id": run_id,
                "tier_a_cells": len(s),
                "tier_a_components": ncomp(s, shape),
                "baseline_retained_cells": len(inter),
                "baseline_retained_pct": 100.0 * len(inter) / len(baseline),
                "new_vs_baseline_cells": len(s - baseline),
                "jaccard_vs_baseline": len(inter) / len(union) if union else 1.0,
                "parameters": run,
            }
        )

    run_ids = list(run_sets)
    all_intersection = set.intersection(*(run_sets[r] for r in run_ids))
    union_all = set.union(*(run_sets[r] for r in run_ids))

    counts = {cell: sum(cell in run_sets[r] for r in run_ids) for cell in baseline}
    robust80 = {cell for cell, c in counts.items() if c >= 9}
    robust10 = {cell for cell, c in counts.items() if c >= 10}
    robust11 = {cell for cell, c in counts.items() if c == 11}

    attrs = base_df.set_index([base_df.row.astype(int), base_df.col.astype(int)])
    rows = []
    for r, c in sorted(baseline):
        rec = {
            "row": r,
            "col": c,
            "survival_count_of_11": counts[(r, c)],
            "survival_fraction": counts[(r, c)] / 11.0,
        }
        hit = attrs.loc[(r, c)]
        rec["x"] = float(hit.x)
        rec["y"] = float(hit.y)
        rec["original_z_m"] = float(hit.original_z_m)
        rec["local_relief_m_baseline"] = float(hit.local_relief_m)
        rec["slope_deg_baseline"] = float(hit.slope_deg)
        for rid in run_ids:
            rec[f"in_{rid}"] = int((r, c) in run_sets[rid])
        rows.append(rec)
    pd.DataFrame(rows).to_csv(CELL_CSV, index=False)

    write_mask(ROBUST80_TIF, robust80, profile)
    write_mask(ALL_TIF, robust11, profile)

    freq = pd.Series(list(counts.values())).value_counts().sort_index().to_dict()
    summary = {
        "status": "PASS",
        "scientific_holdout": {
            "sentinel1_2021_used_for_selection": False,
            "selection_sources": "V41 terrain + historical OSM 2021-11-25 + HydroRIVERS",
        },
        "design": str(DESIGN),
        "design_sha256": sha256(DESIGN),
        "baseline": {
            "tier_a_cells": len(baseline),
            "components_8_neighbor": ncomp(baseline, shape),
        },
        "runs": run_rows,
        "cross_run": {
            "number_of_configurations": len(run_ids),
            "all_run_intersection_cells": len(all_intersection),
            "all_run_intersection_baseline_pct": 100.0 * len(all_intersection) / len(baseline),
            "all_run_intersection_components": ncomp(all_intersection, shape),
            "ge9of11_cells": len(robust80),
            "ge9of11_baseline_pct": 100.0 * len(robust80) / len(baseline),
            "ge9of11_components": ncomp(robust80, shape),
            "ge10of11_cells": len(robust10),
            "ge10of11_baseline_pct": 100.0 * len(robust10) / len(baseline),
            "union_all_tier_a_cells": len(union_all),
            "baseline_survival_frequency": {str(k): int(v) for k, v in freq.items()},
        },
        "outputs": {
            "baseline_survival_csv": str(CELL_CSV),
            "robust_ge9of11_mask": str(ROBUST80_TIF),
            "robust_11of11_mask": str(ALL_TIF),
        },
        "interpretation": [
            "The >=9/11 threshold is a preregistered-style robustness diagnostic, not a physical truth threshold.",
            "All configurations exclude Sentinel-1 2021 from candidate selection.",
            "Results quantify parameter sensitivity of the historical Tier-A candidate stage only; they do not approve DEM cuts.",
        ],
    }
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
