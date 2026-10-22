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
OUT_ROOT = ROOT / "V48_closed_loop_convergence_20261002"
FINAL_TIF = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_CANDIDATE.tif"
FINAL_ASC = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_CANDIDATE.asc"
MAX_ITERATIONS = 8
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


def main() -> None:
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
    strict_cell_history: list[set[tuple[int, int, int]]] = []
    cut_history: dict[tuple[int, int, int], list[dict]] = {}
    converged = False

    for iteration in range(MAX_ITERATIONS + 1):
        iter_dir = OUT_ROOT / f"iteration_{iteration:02d}"
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

        components = pd.read_csv(topology_dir / "V46_topology_components.csv")
        cuts = pd.read_csv(topology_dir / "V46_proposed_cut_cells.csv")
        strict_components = components[components.decision.eq("AUTO_APPROVE_STRICT")].copy()
        strict_ids = strict_components.component_id.astype(int).tolist()
        strict_cuts = cuts[
            cuts.component_id.astype(int).isin(strict_ids)
            & cuts.decision.eq("AUTO_APPROVE_STRICT")
        ].copy()
        strict_keys = {
            (int(rec.component_id), int(rec.row), int(rec.col))
            for rec in strict_cuts.itertuples(index=False)
        }
        strict_cell_history.append(strict_keys)
        component_index = components.set_index(components.component_id.astype(int))
        for rec in strict_cuts.itertuples(index=False):
            key = (int(rec.component_id), int(rec.row), int(rec.col))
            comp = component_index.loc[int(rec.component_id)]
            anchor = (
                int(float(comp.upstream_anchor_row)),
                int(float(comp.upstream_anchor_col)),
                int(float(comp.downstream_anchor_row)),
                int(float(comp.downstream_anchor_col)),
            )
            cut_history.setdefault(key, []).append(
                {
                    "iteration": iteration,
                    "original_z_m": float(rec.original_z_m),
                    "cut_depth_m": float(rec.cut_depth_m),
                    "anchor": anchor,
                }
            )
        counts = components.decision.value_counts().to_dict()
        no_cut_count = int(components.reason_codes.fillna("").str.contains("NO_POSITIVE_CUT_NEEDED").sum())

        record = {
            "iteration": iteration,
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
            "topology_components": str(topology_dir / "V46_topology_components.csv"),
            "topology_components_sha256": sha256(topology_dir / "V46_topology_components.csv"),
        }
        iteration_records.append(record)

        if strict_components.empty:
            converged = True
            break
        if strict_cuts.empty:
            raise RuntimeError("STRICT components exist but no STRICT cut cells were emitted")
        if iteration >= MAX_ITERATIONS:
            raise RuntimeError("Closed-loop convergence exceeded maximum iterations")
        if strict_cuts.duplicated(["row", "col"]).any():
            raise RuntimeError("Duplicate STRICT cut cell in an iteration")

        next_array = current.copy()
        pending_component_cells = {cid: set(cells) for cid, cells in component_cells.items()}
        pending_owner = dict(cell_owner)
        fixed_point_targets: dict[tuple[int, int, int], float] = {}
        if len(strict_cell_history) >= 3 and strict_keys:
            stable_cells = strict_cell_history[-1] == strict_cell_history[-2] == strict_cell_history[-3]
            if stable_cells:
                ratios: dict[tuple[int, int, int], float] = {}
                candidate_targets: dict[tuple[int, int, int], float] = {}
                acceleration_ok = True
                for key in sorted(strict_keys):
                    history = cut_history[key]
                    if len(history) < 3:
                        acceleration_ok = False
                        break
                    last3 = history[-3:]
                    if not (last3[0]["anchor"] == last3[1]["anchor"] == last3[2]["anchor"]):
                        acceleration_ok = False
                        break
                    previous_cut = float(last3[-2]["cut_depth_m"])
                    current_cut = float(last3[-1]["cut_depth_m"])
                    if previous_cut <= 0.0:
                        acceleration_ok = False
                        break
                    ratio = current_cut / previous_cut
                    if not (0.0 <= ratio <= 0.75):
                        acceleration_ok = False
                        break
                    original = float(last3[-1]["original_z_m"])
                    limit_z = original - current_cut / (1.0 - ratio)
                    if not np.isfinite(limit_z) or limit_z >= original - 1e-9:
                        acceleration_ok = False
                        break
                    ratios[key] = ratio
                    candidate_targets[key] = limit_z
                if acceleration_ok:
                    fixed_point_targets = candidate_targets
                    record["fixed_point_acceleration"] = {
                        "applied": True,
                        "method": "geometric residual extrapolation after three identical strict-cell sets and stable D8 anchor pairs",
                        "ratios": {
                            f"{cid}:{row}:{col}": ratios[(cid, row, col)]
                            for cid, row, col in sorted(ratios)
                        },
                        "target_z_m": {
                            f"{cid}:{row}:{col}": fixed_point_targets[(cid, row, col)]
                            for cid, row, col in sorted(fixed_point_targets)
                        },
                    }
        if "fixed_point_acceleration" not in record:
            record["fixed_point_acceleration"] = {"applied": False}

        for rec in strict_cuts.itertuples(index=False):
            cid = int(rec.component_id)
            key = (int(rec.row), int(rec.col))
            history_key = (cid, key[0], key[1])
            original = float(rec.original_z_m)
            proposed = fixed_point_targets.get(history_key, float(rec.proposed_z_m))
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

        next_path = iter_dir / f"V48_closed_loop_iteration_{iteration + 1:02d}.tif"
        write_tif(
            next_path,
            next_array,
            base_profile,
            {
                "V48_STATUS": "CLOSED_LOOP_ITERATION_PRE_SAR",
                "CLOSED_LOOP_ITERATION": str(iteration + 1),
                "BASE_SHA256": sha256(BASE_DEM),
                "PARENT_DEM_SHA256": sha256(current_path),
                "SENTINEL1_2021_USED_FOR_CONDITIONING": "false",
            },
        )
        with rasterio.open(next_path) as chk:
            reread = chk.read(1).astype(np.float64)
            if (
                chk.shape != base_shape
                or chk.transform != base_transform
                or chk.crs != base_crs
                or chk.nodata != base_nodata
            ):
                raise RuntimeError("Closed-loop iteration grid metadata mismatch")
        if float(np.max(np.abs(reread[valid] - next_array[valid]))) > 1e-4:
            raise RuntimeError("Closed-loop iteration roundtrip mismatch")

        component_cells = pending_component_cells
        cell_owner = pending_owner
        current = reread
        current_path = next_path

    if not converged:
        raise RuntimeError("Closed-loop convergence did not finish")

    final_array = current.copy()
    final_diff = base - final_array
    changed = valid & (final_diff > 1e-6)
    final_tags = {
        "V48_STATUS": "CONDITIONED_CLOSED_LOOP_CANDIDATE_PRE_SAR",
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
    ledger_path = OUT_ROOT / "V48_closed_loop_applied_cells.csv"
    pd.DataFrame(ledger_rows).to_csv(ledger_path, index=False, encoding="utf-8-sig")

    summary = {
        "status": "PASS_CLOSED_LOOP_CONVERGED_CANDIDATE_PRE_SAR",
        "formal_bg_flood_run_allowed": False,
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
            "only_lowering_vs_base": True,
            "max_cumulative_cut_le_1m": True,
            "max_cumulative_modified_cells_per_component_le_4": True,
            "final_baseline_auto_approve_strict_zero": True,
            "bg_flood_run": False,
            "sar_evaluation_run": False,
        },
    }
    summary_path = OUT_ROOT / "V48_closed_loop_convergence_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
