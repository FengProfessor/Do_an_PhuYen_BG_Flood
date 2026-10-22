import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import label


ROOT = Path(r"D:\VTP")
SURVIVAL = ROOT / "V47_candidate_sensitivity_20261001" / "V47_baseline407_survival.csv"
COMPONENTS = ROOT / "V47_topology_historical407_20261001" / "V46_topology_components.csv"
OUT_CSV = ROOT / "V47_topology_sensitivity_components_20261001.csv"
OUT_JSON = ROOT / "V47_topology_sensitivity_cross_20261001.json"


def main():
    cells = pd.read_csv(SURVIVAL)
    comps = pd.read_csv(COMPONENTS)

    shape = (int(cells.row.max()) + 1, int(cells.col.max()) + 1)
    core = np.zeros(shape, dtype=bool)
    core[cells.row.to_numpy(int), cells.col.to_numpy(int)] = True
    labels, ncomp = label(core, np.ones((3, 3), dtype=np.uint8))
    cells["component_id"] = labels[cells.row.to_numpy(int), cells.col.to_numpy(int)]

    if len(cells) != 407 or ncomp != 151:
        raise RuntimeError(f"unexpected baseline geometry: cells={len(cells)} components={ncomp}")
    if set(cells.component_id) != set(comps.component_id):
        raise RuntimeError("component IDs do not match topology output")

    agg = (
        cells.groupby("component_id", as_index=False)
        .agg(
            baseline_cells=("component_id", "size"),
            survival_min=("survival_count_of_11", "min"),
            survival_mean=("survival_count_of_11", "mean"),
            survival_max=("survival_count_of_11", "max"),
            cells_11of11=("survival_count_of_11", lambda s: int((s == 11).sum())),
            cells_ge9of11=("survival_count_of_11", lambda s: int((s >= 9).sum())),
        )
    )
    agg["all_cells_11of11"] = agg.cells_11of11 == agg.baseline_cells
    agg["all_cells_ge9of11"] = agg.cells_ge9of11 == agg.baseline_cells
    agg["any_cell_11of11"] = agg.cells_11of11 > 0
    agg["any_cell_ge9of11"] = agg.cells_ge9of11 > 0

    merged = comps.merge(agg, on="component_id", how="left", validate="one_to_one")
    merged.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    by_decision = {}
    for decision, g in merged.groupby("decision"):
        by_decision[decision] = {
            "components": int(len(g)),
            "baseline_cells": int(g.baseline_cells.sum()),
            "all_cells_11of11_components": int(g.all_cells_11of11.sum()),
            "any_cell_11of11_components": int(g.any_cell_11of11.sum()),
            "all_cells_ge9of11_components": int(g.all_cells_ge9of11.sum()),
            "any_cell_ge9of11_components": int(g.any_cell_ge9of11.sum()),
            "mean_component_survival_count_of_11": float(g.survival_mean.mean()),
            "min_component_cell_survival_count_of_11": int(g.survival_min.min()),
        }

    reject_reasons = (
        merged.loc[merged.decision == "REJECT", "reason_codes"]
        .value_counts()
        .to_dict()
    )
    jrc_support = pd.to_numeric(merged.jrc_occurrence_buffer_max_pct, errors="coerce").fillna(0) >= 25
    uparea_support = pd.to_numeric(merged.upstream_area_buffer_max_km2, errors="coerce").fillna(0) >= 0.5
    approved = merged.decision != "REJECT"

    out = {
        "status": "PASS",
        "purpose": "Cross-analyze preregistered candidate sensitivity with historical-407 topology decisions.",
        "baseline": {"cells": 407, "components": 151},
        "component_decision_robustness": by_decision,
        "approved_support_channels": {
            "approved_components": int(approved.sum()),
            "jrc25_support": int((approved & jrc_support).sum()),
            "upstream_area_0_5km2_support": int((approved & uparea_support).sum()),
            "both": int((approved & jrc_support & uparea_support).sum()),
            "upstream_area_only": int((approved & ~jrc_support & uparea_support).sum()),
            "jrc_only": int((approved & jrc_support & ~uparea_support).sum()),
        },
        "reject_reason_counts": {str(k): int(v) for k, v in reject_reasons.items()},
        "interpretation": [
            "Candidate-stage robustness and topology admissibility are distinct filters.",
            "All-11 or >=9/11 survival is a parameter-sensitivity diagnostic, not physical truth.",
            "Approval counts remain dry-run outputs; this analysis does not modify the DEM.",
        ],
        "outputs": {"component_csv": str(OUT_CSV)},
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
