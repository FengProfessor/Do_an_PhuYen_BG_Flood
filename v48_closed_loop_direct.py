from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


ROOT = Path(r"D:\VTP")
GIS = ROOT / "05-Du-lieu-GIS"
DESIGN = ROOT / "V48_closed_loop_topology_design_20261002.json"
START_DEM = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.tif"
BASE_DEM = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
INITIAL_CUTS = ROOT / "V48_research_20261002/final_selection/V48_final_cut_cells.csv"
OUT_ROOT = ROOT / "V48_closed_loop_direct_20261002"
FINAL_TIF = OUT_ROOT / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_DIRECT_CANDIDATE.tif"
FINAL_ASC = OUT_ROOT / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_DIRECT_CANDIDATE.asc"
MAX_ITERATIONS = 32
EPS = 1e-5


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_python(script: Path, dependency_path: Path, *args: object) -> None:
    env = os.environ.copy()
    previous = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(dependency_path) + (os.pathsep + previous if previous else "")
    subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        cwd=ROOT,
        env=env,
        check=True,
    )


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_tif(path: Path, array: np.ndarray, profile: dict, tags: dict[str, str]) -> None:
    out_profile = profile.copy()
    out_profile.update(driver="GTiff", dtype="float32", count=1, compress="deflate")
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(array.astype(np.float32), 1)
        dst.update_tags(**tags)


def parse_resume_flag() -> bool:
    args = sys.argv[1:]
    if not args:
        return False
    if args == ["--resume"]:
        return True
    raise SystemExit("Usage: python v48_closed_loop_direct.py [--resume]")


def read_topology_result(topology_dir: Path, current_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    components_path = topology_dir / "V46_topology_components.csv"
    cuts_path = topology_dir / "V46_proposed_cut_cells.csv"
    components = pd.read_csv(components_path)
    cuts = pd.read_csv(cuts_path)
    strict_components = components[components.decision.eq("AUTO_APPROVE_STRICT")].copy()
    strict_ids = strict_components.component_id.astype(int).tolist()
    strict_cuts = cuts[
        cuts.component_id.astype(int).isin(strict_ids)
        & cuts.decision.eq("AUTO_APPROVE_STRICT")
    ].copy()
    counts = components.decision.value_counts().to_dict()
    no_cut_count = int(
        components.reason_codes.fillna("").str.contains("NO_POSITIVE_CUT_NEEDED").sum()
    )
    record = {
        "input_dem": str(current_path),
        "input_dem_sha256": sha256(current_path),
        "decision_counts": counts,
        "components_with_no_positive_cut_needed": no_cut_count,
        "strict_components": len(strict_ids),
        "strict_component_ids": strict_ids,
        "strict_cut_cells": int(len(strict_cuts)),
        "strict_cut_max_residual_m": (
            0.0 if strict_cuts.empty else float(strict_cuts.cut_depth_m.max())
        ),
        "topology_components": str(components_path),
        "topology_components_sha256": sha256(components_path),
    }
    return strict_components, strict_cuts, components, record


def prepare_next_array(
    current: np.ndarray,
    base: np.ndarray,
    valid: np.ndarray,
    component_cells: dict[int, set[tuple[int, int]]],
    cell_owner: dict[tuple[int, int], int],
    strict_cuts: pd.DataFrame,
    strict_max_modified_cells: int,
) -> tuple[np.ndarray, dict[int, set[tuple[int, int]]], dict[tuple[int, int], int]]:
    if strict_cuts.duplicated(["row", "col"]).any():
        raise RuntimeError("Duplicate STRICT cut cell in an iteration")

    next_array = current.copy()
    pending_component_cells = {cid: set(cells) for cid, cells in component_cells.items()}
    pending_owner = dict(cell_owner)
    for rec in strict_cuts.itertuples(index=False):
        cid = int(rec.component_id)
        key = (int(rec.row), int(rec.col))
        original = float(rec.original_z_m)
        proposed = float(rec.proposed_z_m)
        if abs(current[key] - original) > 2e-4:
            raise RuntimeError(f"Topology/current DEM mismatch at {key}")
        if proposed >= current[key] - 1e-9:
            raise RuntimeError(f"Non-lowering residual cut at {key}")
        cumulative_cut = float(base[key] - proposed)
        if cumulative_cut > 1.000001:
            raise RuntimeError(
                f"Cumulative strict cut exceeds 1 m at {key}: {cumulative_cut}"
            )
        owner = pending_owner.get(key)
        if owner is not None and owner != cid:
            raise RuntimeError(
                f"Cut cell component ownership changed at {key}: {owner} -> {cid}"
            )
        pending_owner[key] = cid
        pending_component_cells.setdefault(cid, set()).add(key)
        if len(pending_component_cells[cid]) > strict_max_modified_cells:
            raise RuntimeError(
                f"Cumulative modified cells exceed strict cap for component {cid}"
            )
        next_array[key] = proposed

    diff = base - next_array
    if np.any(diff[valid] < -EPS):
        raise RuntimeError("Closed-loop iteration introduced raising")
    if float(np.max(diff[valid])) > 1.000001:
        raise RuntimeError("Closed-loop iteration exceeded cumulative 1 m cut")
    return next_array, pending_component_cells, pending_owner


def read_and_validate_iteration_tif(
    path: Path,
    expected: np.ndarray,
    valid: np.ndarray,
    base_shape: tuple[int, int],
    base_transform: object,
    base_crs: object,
    base_nodata: object,
) -> np.ndarray:
    with rasterio.open(path) as chk:
        reread = chk.read(1).astype(np.float64)
        if (
            chk.shape != base_shape
            or chk.transform != base_transform
            or chk.crs != base_crs
            or chk.nodata != base_nodata
        ):
            raise RuntimeError("Closed-loop iteration grid metadata mismatch")
    if float(np.max(np.abs(reread[valid] - expected[valid]))) > 1e-4:
        raise RuntimeError("Closed-loop iteration roundtrip mismatch")
    return reread


def main() -> None:
    resume = parse_resume_flag()
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    if design["sentinel1_2021_used"] or design["bg_flood_run"]:
        raise RuntimeError("Closed-loop convergence must remain pre-SAR and pre-BG_Flood")
    if Path(design["base_dem"]) != START_DEM:
        raise RuntimeError("Design no longer points at the expected frozen V48 terrain")
    if sha256(START_DEM) != design["base_dem_sha256"]:
        raise RuntimeError("Starting frozen V48 hash changed")

    dependency_path = Path(design["python_dependency_path"])
    hydro_builder = Path(design["hydro_builder"])
    topology_algorithm = Path(design["topology_algorithm"])
    core = Path(design["core"])
    core_manifest = Path(design["core_manifest"])
    strict_csv = Path(design["strict_csv"])
    jrc = Path(design["jrc"])
    osm_dir = Path(design["osm_dir"])
    fixed = design["fixed_outer_constraints"]
    strict_max_cut_m = float(design["selection_policy"]["baseline_strict_max_cut_m"])
    strict_max_modified_cells = int(
        design["selection_policy"]["baseline_strict_max_modified_cells"]
    )

    if resume:
        OUT_ROOT.mkdir(parents=True, exist_ok=True)
    else:
        clean_dir(OUT_ROOT)

    with rasterio.open(BASE_DEM) as src:
        base = src.read(1).astype(np.float64)
        base_profile = src.profile.copy()
        base_transform = src.transform
        base_crs = src.crs
        base_nodata = src.nodata
        base_shape = src.shape
    with rasterio.open(START_DEM) as src:
        current = src.read(1).astype(np.float64)
        if (
            src.shape != base_shape
            or src.transform != base_transform
            or src.crs != base_crs
            or src.nodata != base_nodata
        ):
            raise RuntimeError("Base/frozen grid metadata mismatch")

    valid = np.isfinite(base)
    if base_nodata is not None:
        valid &= base != base_nodata
    initial_diff = base - current
    if np.any(initial_diff[valid] < -EPS):
        raise RuntimeError("Starting frozen terrain contains a raising modification")
    if float(np.max(initial_diff[valid])) > 1.000001:
        raise RuntimeError("Starting frozen terrain already exceeds 1 m cumulative cut")

    component_cells: dict[int, set[tuple[int, int]]] = {}
    cell_owner: dict[tuple[int, int], int] = {}
    initial = pd.read_csv(INITIAL_CUTS)
    for rec in initial.itertuples(index=False):
        cid = int(rec.component_id)
        key = (int(rec.row), int(rec.col))
        owner = cell_owner.get(key)
        if owner is not None and owner != cid:
            raise RuntimeError(f"Initial cut cell has multiple component owners: {key}")
        cell_owner[key] = cid
        component_cells.setdefault(cid, set()).add(key)
        if abs(current[key] - float(rec.proposed_z_m)) > 2e-4:
            raise RuntimeError(f"Frozen terrain no longer matches initial cut at {key}")

    current_path = START_DEM
    iteration_records: list[dict] = []
    converged = False
    start_iteration = 0

    if resume:
        for iteration in range(MAX_ITERATIONS + 1):
            iter_dir = OUT_ROOT / f"iteration_{iteration:02d}"
            topology_dir = iter_dir / "topology"
            components_path = topology_dir / "V46_topology_components.csv"
            cuts_path = topology_dir / "V46_proposed_cut_cells.csv"
            if not components_path.exists() or not cuts_path.exists():
                start_iteration = iteration
                break

            strict_components, strict_cuts, _, record = read_topology_result(
                topology_dir, current_path
            )
            record["iteration"] = iteration

            if strict_components.empty:
                iteration_records.append(record)
                converged = True
                start_iteration = iteration + 1
                break
            if strict_cuts.empty:
                raise RuntimeError("STRICT components exist but no STRICT cut cells were emitted")
            if iteration >= MAX_ITERATIONS:
                iteration_records.append(record)
                start_iteration = MAX_ITERATIONS + 1
                break

            next_path = iter_dir / f"V48_closed_loop_direct_iteration_{iteration + 1:02d}.tif"
            if not next_path.exists():
                start_iteration = iteration
                break

            next_array, pending_component_cells, pending_owner = prepare_next_array(
                current,
                base,
                valid,
                component_cells,
                cell_owner,
                strict_cuts,
                strict_max_modified_cells,
            )
            reread = read_and_validate_iteration_tif(
                next_path,
                next_array,
                valid,
                base_shape,
                base_transform,
                base_crs,
                base_nodata,
            )
            iteration_records.append(record)
            component_cells = pending_component_cells
            cell_owner = pending_owner
            current = reread
            current_path = next_path
            start_iteration = iteration + 1
        else:
            start_iteration = MAX_ITERATIONS + 1

        for iteration in range(start_iteration, MAX_ITERATIONS + 1):
            iter_dir = OUT_ROOT / f"iteration_{iteration:02d}"
            if iter_dir.exists():
                shutil.rmtree(iter_dir)
        for stale in (
            FINAL_TIF,
            FINAL_ASC,
            FINAL_ASC.with_suffix(".prj"),
            OUT_ROOT / "V48_closed_loop_direct_applied_cells.csv",
            OUT_ROOT / "V48_closed_loop_direct_summary.json",
        ):
            if stale.exists():
                stale.unlink()

    run_start_iteration = MAX_ITERATIONS + 1 if converged else start_iteration
    for iteration in range(run_start_iteration, MAX_ITERATIONS + 1):
        iter_dir = OUT_ROOT / f"iteration_{iteration:02d}"
        if iter_dir.exists():
            shutil.rmtree(iter_dir)
        hydro_dir = iter_dir / "hydro"
        topology_dir = iter_dir / "topology"
        hydro_dir.mkdir(parents=True, exist_ok=True)
        topology_dir.mkdir(parents=True, exist_ok=True)

        run_python(
            hydro_builder,
            dependency_path,
            "--dem",
            current_path,
            "--jrc",
            jrc,
            "--out-dir",
            hydro_dir,
        )
        run_python(
            topology_algorithm,
            dependency_path,
            "--dem",
            current_path,
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
            topology_dir,
            "--max-cut-m",
            fixed["max_cut_m"],
            "--max-modified-cells",
            fixed["max_modified_cells"],
            "--max-path-span-cells",
            fixed["max_path_span_cells"],
            "--strict-max-cut-m",
            strict_max_cut_m,
            "--strict-max-modified-cells",
            strict_max_modified_cells,
        )

        strict_components, strict_cuts, _, record = read_topology_result(
            topology_dir, current_path
        )
        record["iteration"] = iteration
        iteration_records.append(record)

        if strict_components.empty:
            converged = True
            break
        if strict_cuts.empty:
            raise RuntimeError("STRICT components exist but no STRICT cut cells were emitted")
        if iteration >= MAX_ITERATIONS:
            break
        next_array, pending_component_cells, pending_owner = prepare_next_array(
            current,
            base,
            valid,
            component_cells,
            cell_owner,
            strict_cuts,
            strict_max_modified_cells,
        )

        next_path = iter_dir / f"V48_closed_loop_direct_iteration_{iteration + 1:02d}.tif"
        write_tif(
            next_path,
            next_array,
            base_profile,
            {
                "V48_STATUS": "CLOSED_LOOP_DIRECT_ITERATION_PRE_SAR",
                "CLOSED_LOOP_ITERATION": str(iteration + 1),
                "BASE_SHA256": sha256(BASE_DEM),
                "PARENT_DEM_SHA256": sha256(current_path),
                "SENTINEL1_2021_USED_FOR_CONDITIONING": "false",
            },
        )
        reread = read_and_validate_iteration_tif(
            next_path,
            next_array,
            valid,
            base_shape,
            base_transform,
            base_crs,
            base_nodata,
        )

        component_cells = pending_component_cells
        cell_owner = pending_owner
        current = reread
        current_path = next_path

    if not converged:
        summary = {
            "status": "STOP_CLOSED_LOOP_DIRECT_MAX_ITERATIONS",
            "formal_bg_flood_run_allowed": False,
            "method": "pure_direct_exact_topology_proposed_z_only",
            "max_iterations": MAX_ITERATIONS,
            "sentinel1_2021_used": False,
            "starting_frozen": {"path": str(START_DEM), "sha256": sha256(START_DEM)},
            "base": {"path": str(BASE_DEM), "sha256": sha256(BASE_DEM)},
            "iterations": iteration_records,
            "residual_strict_component_sequence": [row["strict_components"] for row in iteration_records],
            "residual_strict_max_cut_sequence_m": [row["strict_cut_max_residual_m"] for row in iteration_records],
            "candidate": None,
            "invariants": {
                "original_frozen_artifacts_overwritten": False,
                "heuristic_candidate_overwritten": False,
                "extrapolation_used": False,
                "bg_flood_run": False,
                "sar_evaluation_run": False,
            },
        }
        summary_path = OUT_ROOT / "V48_closed_loop_direct_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    final_array = current.copy()
    final_diff = base - final_array
    changed = valid & (final_diff > 1e-6)
    final_tags = {
        "V48_STATUS": "CONDITIONED_CLOSED_LOOP_DIRECT_CANDIDATE_PRE_SAR",
        "BASE_SHA256": sha256(BASE_DEM),
        "STARTING_FROZEN_SHA256": sha256(START_DEM),
        "CONVERGENCE_ITERATIONS_WITH_CUTS": str(
            sum(1 for row in iteration_records if row["strict_components"] > 0)
        ),
        "FINAL_STRICT_COMPONENTS": "0",
        "SENTINEL1_2021_USED_FOR_CONDITIONING": "false",
    }
    write_tif(FINAL_TIF, final_array, base_profile, final_tags)

    asc_profile = base_profile.copy()
    asc_profile.update(driver="AAIGrid", dtype="float32", count=1, nodata=base_nodata)
    with rasterio.open(FINAL_ASC, "w", **asc_profile) as dst:
        dst.write(final_array.astype(np.float32), 1)
    final_prj = FINAL_ASC.with_suffix(".prj")
    if base_crs is not None:
        final_prj.write_text(base_crs.to_wkt("WKT1_ESRI"), encoding="utf-8")

    with rasterio.open(FINAL_TIF) as chk:
        final_reread = chk.read(1).astype(np.float64)
    if float(np.max(np.abs(final_reread[valid] - final_array[valid]))) > 1e-4:
        raise RuntimeError("Final closed-loop candidate roundtrip mismatch")

    ledger_rows = []
    for key, cid in sorted(cell_owner.items()):
        r, c = key
        ledger_rows.append(
            {
                "component_id": cid,
                "row": r,
                "col": c,
                "base_z_m": float(base[key]),
                "final_z_m": float(final_reread[key]),
                "cumulative_cut_m": float(base[key] - final_reread[key]),
            }
        )
    ledger_path = OUT_ROOT / "V48_closed_loop_direct_applied_cells.csv"
    pd.DataFrame(ledger_rows).to_csv(ledger_path, index=False, encoding="utf-8-sig")

    summary = {
        "status": "PASS_CLOSED_LOOP_DIRECT_CONVERGED_CANDIDATE_PRE_SAR",
        "formal_bg_flood_run_allowed": False,
        "method": "pure_direct_exact_topology_proposed_z_only",
        "max_iterations": MAX_ITERATIONS,
        "sentinel1_2021_used": False,
        "starting_frozen": {"path": str(START_DEM), "sha256": sha256(START_DEM)},
        "base": {"path": str(BASE_DEM), "sha256": sha256(BASE_DEM)},
        "iterations": iteration_records,
        "convergence": {
            "final_strict_components": 0,
            "iterations_with_new_cuts": sum(
                1 for row in iteration_records if row["strict_components"] > 0
            ),
            "final_changed_cells_vs_base": int(changed.sum()),
            "final_max_cumulative_cut_m": float(final_diff[changed].max()) if changed.any() else 0.0,
            "final_modified_components": len(component_cells),
            "cumulative_strict_max_cut_m": strict_max_cut_m,
            "cumulative_strict_max_modified_cells_per_component": strict_max_modified_cells,
        },
        "candidate": {
            "tif": str(FINAL_TIF),
            "tif_sha256": sha256(FINAL_TIF),
            "asc": str(FINAL_ASC),
            "asc_sha256": sha256(FINAL_ASC),
            "prj": str(final_prj),
            "prj_sha256": sha256(final_prj),
            "applied_cells": str(ledger_path),
            "applied_cells_sha256": sha256(ledger_path),
        },
        "invariants": {
            "original_frozen_artifacts_overwritten": False,
            "heuristic_candidate_overwritten": False,
            "extrapolation_used": False,
            "only_lowering_vs_base": True,
            "max_cumulative_cut_le_1m": True,
            "max_cumulative_modified_cells_per_component_le_4": True,
            "final_baseline_auto_approve_strict_zero": True,
            "bg_flood_run": False,
            "sar_evaluation_run": False,
        },
    }
    summary_path = OUT_ROOT / "V48_closed_loop_direct_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
