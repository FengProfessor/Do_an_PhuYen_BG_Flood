from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import label


ROOT = Path(r"D:\VTP")
V48 = ROOT / "V48_research_20261002"
OUT = V48 / "final_selection"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cap_path = V48 / "topology_cap_sensitivity/V48_topology_cap_sensitivity_summary.json"
    cap = json.loads(cap_path.read_text(encoding="utf-8"))
    cap_stable = set(map(int, cap["cross_run"]["stable_strict_component_ids"]))

    hold_path = V48 / "source_holdout/V48_jrc_holdout_transitions.csv"
    hold = pd.read_csv(hold_path)
    jrc_independent = set(
        hold.loc[
            hold.decision_jrc_heldout == "AUTO_APPROVE_STRICT", "component_id"
        ].astype(int)
    )

    core_path = V48 / "topology_raw815/V48_baseline815_core.tif"
    candidate_csv = V48 / "candidate_baseline_strict_1_2/V46_obstruction_candidates.csv"
    survival_csv = V48 / "candidate_sensitivity/V48_baseline815_survival.csv"
    with rasterio.open(core_path) as src:
        core = src.read(1) > 0
    comps, _ = label(core, np.ones((3, 3), dtype=np.uint8))

    candidates = pd.read_csv(candidate_csv)
    candidates = candidates[candidates.review_status == "TIER_A_CONSENSUS_CANDIDATE"].copy()
    candidates["component_id"] = [
        int(comps[int(r), int(c)]) for r, c in zip(candidates.row, candidates.col)
    ]
    survival = pd.read_csv(survival_csv)[["row", "col", "survival_count_of_11"]]
    candidates = candidates.merge(survival, on=["row", "col"], how="left", validate="one_to_one")
    if candidates.survival_count_of_11.isna().any():
        raise RuntimeError("Missing candidate sensitivity record")
    group_min = candidates.groupby("component_id").survival_count_of_11.min()
    sensitivity_robust = set(group_min[group_min >= 9].index.astype(int))

    final_components = sorted(cap_stable & jrc_independent & sensitivity_robust)

    baseline_comp_path = V48 / "topology_cap_sensitivity/baseline/V46_topology_components.csv"
    baseline_cut_path = V48 / "topology_cap_sensitivity/baseline/V46_proposed_cut_cells.csv"
    comp = pd.read_csv(baseline_comp_path)
    cuts = pd.read_csv(baseline_cut_path)
    final_comp = comp[comp.component_id.astype(int).isin(final_components)].copy()
    final_cuts = cuts[
        cuts.component_id.astype(int).isin(final_components)
        & (cuts.decision == "AUTO_APPROVE_STRICT")
    ].copy()

    if len(final_comp) != len(final_components):
        raise RuntimeError("Final component selection does not match topology table")
    if not (final_comp.decision == "AUTO_APPROVE_STRICT").all():
        raise RuntimeError("Non-strict component entered final selection")
    if final_cuts.empty:
        raise RuntimeError("Final V48 selection is empty")
    if final_cuts.duplicated(["row", "col"]).any():
        raise RuntimeError("Duplicate final cut cell")
    if float(final_cuts.cut_depth_m.max()) > 1.000001:
        raise RuntimeError("Final strict cut exceeds 1 m")

    final_comp_path = OUT / "V48_final_components.csv"
    final_cuts_path = OUT / "V48_final_cut_cells.csv"
    final_comp.to_csv(final_comp_path, index=False, encoding="utf-8-sig")
    final_cuts.to_csv(final_cuts_path, index=False, encoding="utf-8-sig")

    summary = {
        "status": "PASS_FINAL_PRE_SAR_SELECTION_FROZEN",
        "selection_rule": {
            "baseline_class": "AUTO_APPROVE_STRICT",
            "topology_cap_stable_all_7": True,
            "jrc_heldout_class_still_strict": True,
            "all_component_candidate_cells_survive_at_least_9_of_11": True,
            "sentinel1_2021_used": False,
        },
        "counts": {
            "baseline_strict_components": int((comp.decision == "AUTO_APPROVE_STRICT").sum()),
            "cap_stable_strict_components": len(cap_stable),
            "jrc_independent_strict_components": len(jrc_independent),
            "sensitivity_robust_components": len(sensitivity_robust),
            "final_components": len(final_components),
            "final_cut_cells": int(len(final_cuts)),
        },
        "final_component_ids": final_components,
        "cut_statistics": {
            "min_m": float(final_cuts.cut_depth_m.min()),
            "median_m": float(final_cuts.cut_depth_m.median()),
            "max_m": float(final_cuts.cut_depth_m.max()),
            "volume_m3": float((final_cuts.cut_depth_m * 900.0).sum()),
        },
        "inputs": {
            str(cap_path): sha256(cap_path),
            str(hold_path): sha256(hold_path),
            str(survival_csv): sha256(survival_csv),
            str(baseline_comp_path): sha256(baseline_comp_path),
            str(baseline_cut_path): sha256(baseline_cut_path),
        },
        "outputs": {
            str(final_comp_path): sha256(final_comp_path),
            str(final_cuts_path): sha256(final_cuts_path),
        },
    }
    summary_path = OUT / "V48_final_selection_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
