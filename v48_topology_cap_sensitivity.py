from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\VTP")
DESIGN = ROOT / "V48_topology_cap_sensitivity_design_20261002.json"
SCRIPT = ROOT / "v47_topology_paths.py"
OUT = ROOT / "V48_research_20261002/topology_cap_sensitivity"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    run_tables: dict[str, pd.DataFrame] = {}
    run_rows = []

    for i, run in enumerate(design["runs"], start=1):
        out_dir = OUT / run["run_id"]
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--dem", design["base_dem"],
            "--core", design["core"],
            "--core-manifest", design["core_manifest"],
            "--strict-csv", design["strict_csv"],
            "--osm-dir", design["osm_dir"],
            "--hydro-dir", design["hydro_dir"],
            "--out-dir", str(out_dir),
            "--max-cut-m", str(run["max_cut_m"]),
            "--max-modified-cells", str(run["max_modified_cells"]),
            "--max-path-span-cells", str(run["max_path_span_cells"]),
        ]
        print(f"[{i}/{len(design['runs'])}] {run['run_id']}", flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)
        comp_path = out_dir / "V46_topology_components.csv"
        table = pd.read_csv(comp_path)
        run_tables[run["run_id"]] = table
        counts = table.decision.value_counts().to_dict()
        run_rows.append({"run_id": run["run_id"], "parameters": run, "decision_counts": counts})

    baseline = run_tables["baseline"].set_index("component_id")
    run_ids = [r["run_id"] for r in design["runs"]]
    component_rows = []
    transition_counts: Counter[str] = Counter()
    stable_strict = []
    stable_approved = []

    for cid in baseline.index.astype(int):
        decisions = {rid: str(run_tables[rid].set_index("component_id").loc[cid, "decision"]) for rid in run_ids}
        base_decision = decisions["baseline"]
        for rid, decision in decisions.items():
            transition_counts[f"{base_decision}->{decision}@{rid}"] += 1
        strict_all = all(d == "AUTO_APPROVE_STRICT" for d in decisions.values())
        approved_all = all(d in {"AUTO_APPROVE_STRICT", "REVIEW_APPROVE_BOUNDED"} for d in decisions.values())
        if strict_all:
            stable_strict.append(cid)
        if approved_all:
            stable_approved.append(cid)
        component_rows.append({"component_id": cid, "baseline_decision": base_decision, "stable_strict_all_runs": int(strict_all), "stable_approved_all_runs": int(approved_all), **{f"decision_{rid}": d for rid, d in decisions.items()}})

    component_csv = OUT / "V48_topology_cap_component_transitions.csv"
    pd.DataFrame(component_rows).to_csv(component_csv, index=False)
    summary = {
        "status": "PASS",
        "design": str(DESIGN),
        "design_sha256": sha256(DESIGN),
        "algorithm": str(SCRIPT),
        "algorithm_sha256": sha256(SCRIPT),
        "sentinel1_2021_used": False,
        "runs": run_rows,
        "cross_run": {
            "configurations": len(run_ids),
            "stable_strict_components_all_runs": len(stable_strict),
            "stable_strict_component_ids": stable_strict,
            "stable_approved_components_all_runs": len(stable_approved),
            "stable_approved_component_ids": stable_approved,
            "transition_counts": dict(sorted(transition_counts.items())),
        },
        "outputs": {"component_transitions": str(component_csv)},
        "interpretation": [
            "Topology-cap stability is a robustness diagnostic, not physical truth.",
            "No Sentinel-1 2021 information is used in any configuration.",
        ],
    }
    out_path = OUT / "V48_topology_cap_sensitivity_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
