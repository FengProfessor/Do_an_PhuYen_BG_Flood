from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(r"D:\VTP")
DESIGN = ROOT / "V48_closed_loop_topology_design_20261002.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_hash(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual.lower() != expected.lower():
        raise RuntimeError(f"Pinned input hash mismatch: {path}: {actual} != {expected}")


def run_python(script: Path, dependency_path: Path, *args: object) -> None:
    cmd = [sys.executable, str(script), *map(str, args)]
    env = os.environ.copy()
    previous = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(dependency_path) + (os.pathsep + previous if previous else "")
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if design["sentinel1_2021_used"] or design["bg_flood_run"]:
        raise RuntimeError("Closed-loop topology design must not use SAR or BG_Flood")

    dem = Path(design["base_dem"])
    core = Path(design["core"])
    core_manifest = Path(design["core_manifest"])
    strict_csv = Path(design["strict_csv"])
    jrc = Path(design["jrc"])
    osm_dir = Path(design["osm_dir"])
    osm_manifest = Path(design["osm_manifest"])
    hydro_builder = Path(design["hydro_builder"])
    topology_algorithm = Path(design["topology_algorithm"])
    dependency_path = Path(design["python_dependency_path"])
    out_root = Path(design["output_root"])
    out_root.mkdir(parents=True, exist_ok=True)
    if not dependency_path.is_dir():
        raise RuntimeError(f"Missing pinned local dependency path: {dependency_path}")

    pinned = [
        (dem, design["base_dem_sha256"]),
        (core, design["core_sha256"]),
        (core_manifest, design["core_manifest_sha256"]),
        (strict_csv, design["strict_csv_sha256"]),
        (jrc, design["jrc_sha256"]),
        (osm_manifest, design["osm_manifest_sha256"]),
    ]
    for path, expected in pinned:
        require_hash(path, expected)

    hydro_dir = out_root / "hydro_recomputed_from_frozen"
    clean_dir(hydro_dir)
    run_python(
        hydro_builder,
        dependency_path,
        "--dem",
        dem,
        "--jrc",
        jrc,
        "--out-dir",
        hydro_dir,
    )
    hydro_summary_path = hydro_dir / "V46_hydro_evidence_summary.json"
    hydro_summary = json.loads(hydro_summary_path.read_text(encoding="utf-8"))
    if hydro_summary["base_dem"]["sha256"].lower() != design["base_dem_sha256"].lower():
        raise RuntimeError("Hydro recomputation did not use the pinned frozen V48 DEM")

    fixed = design["fixed_outer_constraints"]
    run_tables: dict[str, pd.DataFrame] = {}
    run_cuts: dict[str, pd.DataFrame] = {}
    run_summaries: dict[str, dict] = {}
    for run in design["sensitivity_runs"]:
        run_id = run["run_id"]
        run_dir = out_root / "topology_runs" / run_id
        clean_dir(run_dir)
        run_python(
            topology_algorithm,
            dependency_path,
            "--dem",
            dem,
            "--core",
            core,
            "--core-manifest",
            core_manifest,
            "--strict-csv",
            strict_csv,
            "--osm-dir",
            osm_dir,
            "--hydro-dir",
            hydro_dir,
            "--out-dir",
            run_dir,
            "--max-cut-m",
            fixed["max_cut_m"],
            "--max-modified-cells",
            fixed["max_modified_cells"],
            "--max-path-span-cells",
            fixed["max_path_span_cells"],
            "--strict-max-cut-m",
            run["strict_max_cut_m"],
            "--strict-max-modified-cells",
            run["strict_max_modified_cells"],
        )
        run_tables[run_id] = pd.read_csv(run_dir / "V46_topology_components.csv")
        run_cuts[run_id] = pd.read_csv(run_dir / "V46_proposed_cut_cells.csv")
        run_summaries[run_id] = json.loads(
            (run_dir / "V46_topology_summary.json").read_text(encoding="utf-8")
        )

    baseline = run_tables["baseline"].copy()
    component_ids = baseline.component_id.astype(int).tolist()
    for run_id, table in run_tables.items():
        if table.component_id.astype(int).tolist() != component_ids:
            raise RuntimeError(f"Component identity drift across sensitivity run: {run_id}")

    selected_mask = baseline.decision.eq("AUTO_APPROVE_STRICT")
    selected = baseline.loc[selected_mask].copy()
    selected_ids = selected.component_id.astype(int).tolist()
    baseline_cuts = run_cuts["baseline"]
    selected_cuts = baseline_cuts[
        baseline_cuts.component_id.astype(int).isin(selected_ids)
        & baseline_cuts.decision.eq("AUTO_APPROVE_STRICT")
    ].copy()
    if selected.empty or selected_cuts.empty:
        raise RuntimeError("Closed-loop baseline produced an empty strict selection")

    indexed = {run_id: table.set_index("component_id") for run_id, table in run_tables.items()}
    transition_rows = []
    robust_strict_ids = []
    for cid in component_ids:
        decisions = {
            run_id: str(table.loc[cid, "decision"]) for run_id, table in indexed.items()
        }
        strict_all = all(value == "AUTO_APPROVE_STRICT" for value in decisions.values())
        if strict_all:
            robust_strict_ids.append(cid)
        transition_rows.append(
            {
                "component_id": cid,
                "baseline_decision": decisions["baseline"],
                "strict_all_sensitivity_runs": int(strict_all),
                **{f"decision_{run_id}": decision for run_id, decision in decisions.items()},
            }
        )

    transitions_path = out_root / "V48_closed_loop_sensitivity_transitions.csv"
    pd.DataFrame(transition_rows).to_csv(transitions_path, index=False, encoding="utf-8-sig")
    selected_components_path = out_root / "V48_closed_loop_selected_components.csv"
    selected_cuts_path = out_root / "V48_closed_loop_selected_cut_cells.csv"
    selected.to_csv(selected_components_path, index=False, encoding="utf-8-sig")
    selected_cuts.to_csv(selected_cuts_path, index=False, encoding="utf-8-sig")

    previous_selection_path = Path(design["previous_final_selection"])
    previous = json.loads(previous_selection_path.read_text(encoding="utf-8"))
    previous_ids = set(map(int, previous["final_component_ids"]))
    selected_set = set(selected_ids)
    retained_previous = sorted(previous_ids & selected_set)
    dropped_previous = sorted(previous_ids - selected_set)
    newly_strict = sorted(selected_set - previous_ids)

    reference_path = Path(design["reference_post_condition_topology"])
    reference = pd.read_csv(reference_path)
    ref_counts = reference.decision.value_counts().to_dict()
    baseline_counts = baseline.decision.value_counts().to_dict()

    run_rows = []
    for run in design["sensitivity_runs"]:
        run_id = run["run_id"]
        summary = run_summaries[run_id]
        run_rows.append(
            {
                **run,
                "decision_counts": summary["decision_counts"],
                "auto_approved_cut_cells": summary["auto_approved_cut_cells"],
            }
        )

    summary = {
        "status": "PASS_CLOSED_LOOP_TOPOLOGY_SELECTION_DRY_RUN",
        "design": str(DESIGN),
        "design_sha256": sha256(DESIGN),
        "invariants": {
            "selection_source_dem": str(dem),
            "selection_source_dem_sha256": sha256(dem),
            "hydro_recomputed_from_selection_source_dem": True,
            "pre_condition_topology_controls_selection": False,
            "frozen_dem_modified": False,
            "sentinel1_2021_used": False,
            "bg_flood_run": False,
        },
        "baseline": {
            "strict_gate": {
                "max_cut_m": design["selection_policy"]["baseline_strict_max_cut_m"],
                "max_modified_cells": design["selection_policy"]["baseline_strict_max_modified_cells"],
            },
            "decision_counts": baseline_counts,
            "selected_components": len(selected_ids),
            "selected_component_ids": selected_ids,
            "selected_cut_cells": int(len(selected_cuts)),
            "selected_cut_depth_max_m": float(selected_cuts.cut_depth_m.max()),
        },
        "strict_gate_sensitivity": {
            "fixed_outer_constraints": fixed,
            "runs": run_rows,
            "robust_strict_components_all_runs": len(robust_strict_ids),
            "robust_strict_component_ids": robust_strict_ids,
        },
        "comparison_to_previous_frozen_selection": {
            "previous_final_components": len(previous_ids),
            "retained_as_closed_loop_strict": len(retained_previous),
            "retained_component_ids": retained_previous,
            "previous_components_no_longer_strict": len(dropped_previous),
            "previous_components_no_longer_strict_ids": dropped_previous,
            "newly_strict_component_ids": newly_strict,
        },
        "reference_reproduction": {
            "reference_post_condition_components": str(reference_path),
            "reference_decision_counts": ref_counts,
            "closed_loop_baseline_matches_reference_counts": baseline_counts == ref_counts,
        },
        "inputs": {
            str(dem): sha256(dem),
            str(core): sha256(core),
            str(core_manifest): sha256(core_manifest),
            str(strict_csv): sha256(strict_csv),
            str(jrc): sha256(jrc),
            str(osm_manifest): sha256(osm_manifest),
            str(hydro_builder): sha256(hydro_builder),
            str(topology_algorithm): sha256(topology_algorithm),
            str(previous_selection_path): sha256(previous_selection_path),
        },
        "runtime": {
            "python_executable": sys.executable,
            "python_dependency_path": str(dependency_path),
        },
        "outputs": {
            str(hydro_summary_path): sha256(hydro_summary_path),
            str(selected_components_path): sha256(selected_components_path),
            str(selected_cuts_path): sha256(selected_cuts_path),
            str(transitions_path): sha256(transitions_path),
        },
    }
    summary_path = out_root / "V48_closed_loop_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
