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
SOURCE_ROOT = ROOT / "V48_closed_loop_topology_20261002"
OUT_ROOT = ROOT / "V48_CLOSED_LOOP_REISSUE_20261002"

BASE_DEM = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
FROZEN_TIF = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.tif"
FROZEN_ASC = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.asc"
FROZEN_PRJ = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.prj"
RELEASE = ROOT / "V48_audit_20261002" / "V48_FINAL_RELEASE_20261002.json"

SOURCE_SUMMARY = SOURCE_ROOT / "V48_closed_loop_summary.json"
SOURCE_COMPONENTS = SOURCE_ROOT / "V48_closed_loop_selected_components.csv"
SOURCE_CUTS = SOURCE_ROOT / "V48_closed_loop_selected_cut_cells.csv"
DESIGN = ROOT / "V48_closed_loop_topology_design_20261002.json"

FINAL_TIF = OUT_ROOT / "V48_CLOSED_LOOP_REISSUE_SET_FIXED_POINT.tif"
FINAL_ASC = OUT_ROOT / "V48_CLOSED_LOOP_REISSUE_SET_FIXED_POINT.asc"
FINAL_PRJ = OUT_ROOT / "V48_CLOSED_LOOP_REISSUE_SET_FIXED_POINT.prj"
LEDGER = OUT_ROOT / "V48_CLOSED_LOOP_REISSUE_APPLIED_CELLS.csv"
SUMMARY = OUT_ROOT / "V48_CLOSED_LOOP_REISSUE_SUMMARY.json"
MANIFEST = OUT_ROOT / "V48_CLOSED_LOOP_REISSUE_MANIFEST.json"
HASHSET = OUT_ROOT / "V48_CLOSED_LOOP_REISSUE_HASHSET.sha256"

MAX_TRANSITIONS = 8
EPS = 1e-6
ROUNDTRIP_TOL = 1e-4


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


def write_tif(path: Path, array: np.ndarray, profile: dict, tags: dict[str, str]) -> None:
    tif_profile = profile.copy()
    tif_profile.update(driver="GTiff", dtype="float32", count=1, compress="deflate")
    with rasterio.open(path, "w", **tif_profile) as dst:
        dst.write(array.astype(np.float32), 1)
        dst.update_tags(**tags)


def validate_grid(path: Path, shape, transform, crs, nodata) -> np.ndarray:
    with rasterio.open(path) as src:
        if (
            src.shape != shape
            or src.transform != transform
            or src.crs != crs
            or src.nodata != nodata
        ):
            raise RuntimeError(f"Grid metadata mismatch: {path}")
        return src.read(1).astype(np.float64)


def export_ascii(array: np.ndarray, profile: dict, crs) -> None:
    asc_profile = profile.copy()
    asc_profile.update(driver="AAIGrid", dtype="float32", count=1)
    with rasterio.open(FINAL_ASC, "w", **asc_profile) as dst:
        dst.write(array.astype(np.float32), 1)
    if crs is None:
        raise RuntimeError("Cannot emit PRJ because base DEM has no CRS")
    FINAL_PRJ.write_text(crs.to_wkt("WKT1_ESRI"), encoding="utf-8")


def apply_cuts(
    current: np.ndarray,
    base: np.ndarray,
    cuts: pd.DataFrame,
    allowed_components: set[int],
    component_cells: dict[int, set[tuple[int, int]]],
    cell_owner: dict[tuple[int, int], int],
    valid: np.ndarray,
    strict_max_cut_m: float,
    strict_max_modified_cells: int,
) -> tuple[np.ndarray, dict[int, set[tuple[int, int]]], dict[tuple[int, int], int]]:
    if cuts.empty:
        return current.copy(), {k: set(v) for k, v in component_cells.items()}, dict(cell_owner)
    if cuts.duplicated(["row", "col"]).any():
        raise RuntimeError("Duplicate STRICT cut cell")
    if not cuts.decision.eq("AUTO_APPROVE_STRICT").all():
        raise RuntimeError("Non-STRICT row entered reissue cut set")

    next_array = current.copy()
    next_component_cells = {cid: set(cells) for cid, cells in component_cells.items()}
    next_owner = dict(cell_owner)

    for rec in cuts.itertuples(index=False):
        cid = int(rec.component_id)
        if cid not in allowed_components:
            raise RuntimeError(f"Component outside the 11-component remediation scope: {cid}")
        r, c = int(rec.row), int(rec.col)
        key = (r, c)
        if not (0 <= r < current.shape[0] and 0 <= c < current.shape[1]):
            raise RuntimeError(f"Cut outside DEM grid: {key}")
        if not valid[key]:
            raise RuntimeError(f"Cut targets invalid/nodata cell: {key}")

        current_z = float(current[key])
        proposed_z = float(rec.proposed_z_m)
        if not np.isfinite(proposed_z):
            raise RuntimeError(f"Non-finite proposed elevation: {key}")
        if proposed_z >= current_z - 1e-9:
            raise RuntimeError(
                f"Iteration proposed a non-lowering cut at {key}: {current_z} -> {proposed_z}"
            )
        cumulative_cut = float(base[key] - proposed_z)
        if cumulative_cut <= 0.0 or cumulative_cut > strict_max_cut_m + 1e-6:
            raise RuntimeError(
                f"Cumulative cut violates STRICT max at {key}: {cumulative_cut}"
            )

        owner = next_owner.get(key)
        if owner is not None and owner != cid:
            raise RuntimeError(f"Cell ownership changed at {key}: {owner} -> {cid}")
        next_owner[key] = cid
        next_component_cells.setdefault(cid, set()).add(key)
        if len(next_component_cells[cid]) > strict_max_modified_cells:
            raise RuntimeError(
                f"Cumulative modified-cell count violates STRICT cap for component {cid}"
            )
        next_array[key] = proposed_z

    diff = base - next_array
    if np.any(diff[valid] < -EPS):
        raise RuntimeError("Reissue iteration introduced raising versus BASE")
    if float(np.max(diff[valid])) > strict_max_cut_m + 1e-6:
        raise RuntimeError("Reissue iteration exceeded cumulative STRICT cut bound")
    return next_array, next_component_cells, next_owner


def main() -> None:
    protected = [FROZEN_TIF, FROZEN_ASC, FROZEN_PRJ, RELEASE]
    protected_before = {str(p): sha256(p) for p in protected}

    source_summary = json.loads(SOURCE_SUMMARY.read_text(encoding="utf-8"))
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    source_components = pd.read_csv(SOURCE_COMPONENTS)
    source_cuts = pd.read_csv(SOURCE_CUTS)

    if design["sentinel1_2021_used"] or design["bg_flood_run"]:
        raise RuntimeError("Pinned closed-loop design is not pre-SAR/pre-BG_Flood")
    if source_summary["invariants"]["sentinel1_2021_used"]:
        raise RuntimeError("Source selection reports Sentinel usage")
    if source_summary["invariants"]["bg_flood_run"]:
        raise RuntimeError("Source selection reports BG_Flood usage")
    if sha256(SOURCE_COMPONENTS) != source_summary["outputs"][str(SOURCE_COMPONENTS)]:
        raise RuntimeError("Selected component CSV hash no longer matches source summary")
    if sha256(SOURCE_CUTS) != source_summary["outputs"][str(SOURCE_CUTS)]:
        raise RuntimeError("Selected cut-cell CSV hash no longer matches source summary")
    if sha256(BASE_DEM) != release["base"]["sha256"]:
        raise RuntimeError("V48_BASE_COPERNICUS hash no longer matches frozen release provenance")

    baseline = source_summary["baseline"]
    source_ids = list(map(int, baseline["selected_component_ids"]))
    source_set = set(source_ids)
    if len(source_ids) != 11 or len(source_set) != 11:
        raise RuntimeError(f"Expected exactly 11 baseline STRICT components, got {source_ids}")
    csv_ids = set(source_components.component_id.astype(int))
    cut_ids = set(source_cuts.component_id.astype(int))
    if csv_ids != source_set or cut_ids != source_set:
        raise RuntimeError("Source CSV component IDs do not match the 11 IDs pinned in summary")
    if not source_components.decision.eq("AUTO_APPROVE_STRICT").all():
        raise RuntimeError("Source selected component CSV contains non-STRICT decisions")
    if not source_cuts.decision.eq("AUTO_APPROVE_STRICT").all():
        raise RuntimeError("Source selected cut-cell CSV contains non-STRICT decisions")
    if len(source_cuts) != int(baseline["selected_cut_cells"]):
        raise RuntimeError("Source cut-cell count does not match summary")

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
    if strict_max_cut_m != 1.0 or strict_max_modified_cells != 4:
        raise RuntimeError("Pinned baseline STRICT gate changed from 1 m / 4 cells")

    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    with rasterio.open(BASE_DEM) as src:
        base = src.read(1).astype(np.float64)
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
        nodata = src.nodata
        shape = src.shape
    valid = np.isfinite(base)
    if nodata is not None:
        valid &= base != nodata

    current = base.copy()
    component_cells: dict[int, set[tuple[int, int]]] = {}
    cell_owner: dict[tuple[int, int], int] = {}

    # Reissue step: reconstruct from V48_BASE_COPERNICUS using exactly the
    # 11 closed-loop baseline STRICT components and their pinned target cells.
    current, component_cells, cell_owner = apply_cuts(
        current,
        base,
        source_cuts,
        source_set,
        component_cells,
        cell_owner,
        valid,
        strict_max_cut_m,
        strict_max_modified_cells,
    )
    applied_set = source_set.copy()
    applied_cuts = source_cuts.copy()
    seen_sets: dict[frozenset[int], int] = {frozenset(applied_set): 0}
    iteration_records: list[dict] = []
    fixed_point = False
    stop_reason = ""
    current_path: Path | None = None

    for iteration in range(MAX_TRANSITIONS + 1):
        iter_dir = OUT_ROOT / f"iteration_{iteration:02d}"
        iter_dir.mkdir(parents=True)
        current_path = iter_dir / f"V48_CLOSED_LOOP_REISSUE_ITERATION_{iteration:02d}.tif"
        write_tif(
            current_path,
            current,
            profile,
            {
                "V48_STATUS": "CLOSED_LOOP_REISSUE_PRE_SAR",
                "REISSUE_ITERATION": str(iteration),
                "BASE_SHA256": sha256(BASE_DEM),
                "SOURCE_STRICT_COMPONENT_IDS": ",".join(map(str, source_ids)),
                "APPLIED_COMPONENT_IDS": ",".join(map(str, sorted(applied_set))),
                "SENTINEL1_2021_USED_FOR_CONDITIONING": "false",
                "BG_FLOOD_RUN": "false",
            },
        )
        reread = validate_grid(current_path, shape, transform, crs, nodata)
        if float(np.max(np.abs(reread[valid] - current[valid]))) > ROUNDTRIP_TOL:
            raise RuntimeError("Iteration GeoTIFF roundtrip mismatch")
        current = reread

        hydro_dir = iter_dir / "hydro"
        topology_dir = iter_dir / "topology"
        hydro_dir.mkdir()
        topology_dir.mkdir()
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

        components_path = topology_dir / "V46_topology_components.csv"
        cuts_path = topology_dir / "V46_proposed_cut_cells.csv"
        components = pd.read_csv(components_path)
        cuts = pd.read_csv(cuts_path)
        selected = components[components.decision.eq("AUTO_APPROVE_STRICT")].copy()
        selected_ids = sorted(selected.component_id.astype(int).tolist())
        selected_set = set(selected_ids)
        selected_cuts = cuts[
            cuts.component_id.astype(int).isin(selected_set)
            & cuts.decision.eq("AUTO_APPROVE_STRICT")
        ].copy()
        counts = {str(k): int(v) for k, v in components.decision.value_counts().to_dict().items()}
        changed = valid & ((base - current) > EPS)
        cumulative = base - current
        record = {
            "iteration": iteration,
            "terrain": str(current_path),
            "terrain_sha256": sha256(current_path),
            "applied_component_ids": sorted(applied_set),
            "applied_component_count": len(applied_set),
            "applied_cut_rows_this_transition": int(len(applied_cuts)),
            "recomputed_strict_component_ids": selected_ids,
            "recomputed_strict_component_count": len(selected_ids),
            "recomputed_strict_cut_cells": int(len(selected_cuts)),
            "recomputed_strict_cut_max_m": (
                0.0 if selected_cuts.empty else float(selected_cuts.cut_depth_m.max())
            ),
            "decision_counts": counts,
            "set_fixed_point": selected_set == applied_set,
            "changed_cells_vs_base": int(changed.sum()),
            "modified_components_vs_base": len(component_cells),
            "max_cumulative_cut_m": float(cumulative[changed].max()) if changed.any() else 0.0,
            "topology_components": str(components_path),
            "topology_components_sha256": sha256(components_path),
            "topology_cut_cells": str(cuts_path),
            "topology_cut_cells_sha256": sha256(cuts_path),
        }
        iteration_records.append(record)

        if selected_set == applied_set:
            fixed_point = True
            stop_reason = "STRICT component set unchanged after applying that set"
            break
        if not selected_set:
            fixed_point = True
            stop_reason = "STRICT component set became empty; empty-set reapplication is identity"
            record["empty_set_identity_fixed_point"] = True
            break
        if not selected_set.issubset(source_set):
            stop_reason = (
                "Recomputed STRICT set introduced component(s) outside the pinned 11-component remediation scope: "
                + ",".join(map(str, sorted(selected_set - source_set)))
            )
            break
        frozen_selected = frozenset(selected_set)
        if frozen_selected in seen_sets:
            stop_reason = (
                f"Component-set cycle detected: set first seen at iteration {seen_sets[frozen_selected]}"
            )
            break
        if iteration >= MAX_TRANSITIONS:
            stop_reason = f"Bounded iteration limit reached ({MAX_TRANSITIONS} transitions)"
            break
        if selected_cuts.empty:
            stop_reason = "STRICT components were selected but no STRICT cut cells were emitted"
            break

        # Only continue when the next transition remains within the same 11
        # pinned components and cumulative STRICT cut/cell caps remain valid.
        try:
            next_array, next_component_cells, next_owner = apply_cuts(
                current,
                base,
                selected_cuts,
                source_set,
                component_cells,
                cell_owner,
                valid,
                strict_max_cut_m,
                strict_max_modified_cells,
            )
        except RuntimeError as exc:
            stop_reason = f"Bounded iteration rejected: {exc}"
            break

        seen_sets[frozen_selected] = iteration + 1
        current = next_array
        component_cells = next_component_cells
        cell_owner = next_owner
        applied_set = selected_set
        applied_cuts = selected_cuts

    if current_path is None:
        raise RuntimeError("No reissue terrain was produced")

    final_array = current.copy()
    final_status = (
        "PASS_CLOSED_LOOP_REISSUE_SET_FIXED_POINT"
        if fixed_point
        else "STOPPED_CLOSED_LOOP_REISSUE_NONCONVERGED"
    )
    write_tif(
        FINAL_TIF,
        final_array,
        profile,
        {
            "V48_STATUS": final_status,
            "BASE_SHA256": sha256(BASE_DEM),
            "SOURCE_STRICT_COMPONENT_IDS": ",".join(map(str, source_ids)),
            "SET_FIXED_POINT": str(fixed_point).lower(),
            "SENTINEL1_2021_USED_FOR_CONDITIONING": "false",
            "BG_FLOOD_RUN": "false",
        },
    )
    final_reread = validate_grid(FINAL_TIF, shape, transform, crs, nodata)
    if float(np.max(np.abs(final_reread[valid] - final_array[valid]))) > ROUNDTRIP_TOL:
        raise RuntimeError("Final GeoTIFF roundtrip mismatch")
    export_ascii(final_reread, profile, crs)

    final_diff = base - final_reread
    final_changed = valid & (final_diff > EPS)
    ledger_rows = []
    for (r, c), cid in sorted(cell_owner.items(), key=lambda item: (item[1], item[0][0], item[0][1])):
        ledger_rows.append(
            {
                "component_id": cid,
                "row": r,
                "col": c,
                "base_z_m": float(base[r, c]),
                "final_z_m": float(final_reread[r, c]),
                "cumulative_cut_m": float(base[r, c] - final_reread[r, c]),
            }
        )
    pd.DataFrame(ledger_rows).to_csv(LEDGER, index=False, encoding="utf-8-sig")

    protected_after = {str(p): sha256(p) for p in protected}
    protected_unchanged = protected_before == protected_after
    if not protected_unchanged:
        raise RuntimeError("A protected frozen/release artifact changed during reissue")

    summary = {
        "status": final_status,
        "fixed_point_definition": (
            "The STRICT component set recomputed on the conditioned terrain equals the component set "
            "whose cuts were applied in the preceding transition; empty STRICT is treated as an identity fixed point."
        ),
        "fixed_point_reached": fixed_point,
        "stop_reason": stop_reason,
        "iteration_count_topology_evaluations": len(iteration_records),
        "iteration_count_conditioning_transitions": max(1, len(iteration_records)),
        "max_transitions": MAX_TRANSITIONS,
        "source_selection": {
            "summary": str(SOURCE_SUMMARY),
            "summary_sha256": sha256(SOURCE_SUMMARY),
            "components": str(SOURCE_COMPONENTS),
            "components_sha256": sha256(SOURCE_COMPONENTS),
            "cuts": str(SOURCE_CUTS),
            "cuts_sha256": sha256(SOURCE_CUTS),
            "baseline_strict_component_ids": source_ids,
            "baseline_strict_component_count": len(source_ids),
            "baseline_strict_cut_cells": int(len(source_cuts)),
        },
        "base": {"path": str(BASE_DEM), "sha256": sha256(BASE_DEM)},
        "strict_gate": {
            "strict_max_cut_m": strict_max_cut_m,
            "strict_max_modified_cells": strict_max_modified_cells,
            "outer_max_cut_m": fixed["max_cut_m"],
            "outer_max_modified_cells": fixed["max_modified_cells"],
            "outer_max_path_span_cells": fixed["max_path_span_cells"],
        },
        "iterations": iteration_records,
        "final": {
            "tif": str(FINAL_TIF),
            "tif_sha256": sha256(FINAL_TIF),
            "asc": str(FINAL_ASC),
            "asc_sha256": sha256(FINAL_ASC),
            "prj": str(FINAL_PRJ),
            "prj_sha256": sha256(FINAL_PRJ),
            "applied_cells": str(LEDGER),
            "applied_cells_sha256": sha256(LEDGER),
            "changed_cells_vs_base": int(final_changed.sum()),
            "modified_component_ids": sorted(component_cells),
            "modified_component_count": len(component_cells),
            "max_cumulative_cut_m": (
                float(final_diff[final_changed].max()) if final_changed.any() else 0.0
            ),
        },
        "protected_artifacts": {
            "before": protected_before,
            "after": protected_after,
            "unchanged": protected_unchanged,
        },
        "invariants": {
            "initial_reissue_started_from_v48_base_copernicus": True,
            "initial_reissue_used_exactly_11_pinned_strict_components": True,
            "all_iterations_restricted_to_original_11_component_universe": True,
            "cumulative_cut_le_1m": bool(
                not final_changed.any() or float(final_diff[final_changed].max()) <= 1.000001
            ),
            "cumulative_modified_cells_per_component_le_4": all(
                len(cells) <= 4 for cells in component_cells.values()
            ),
            "only_lowering_vs_base": bool(np.all(final_diff[valid] >= -EPS)),
            "sentinel1_2021_used": False,
            "bg_flood_run": False,
            "frozen_dem_asc_prj_release_unchanged": protected_unchanged,
        },
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest_inputs = [
        BASE_DEM,
        SOURCE_SUMMARY,
        SOURCE_COMPONENTS,
        SOURCE_CUTS,
        DESIGN,
        RELEASE,
        hydro_builder,
        topology_algorithm,
        core,
        core_manifest,
        strict_csv,
        jrc,
    ]
    manifest = {
        "algorithm": str(Path(__file__)),
        "algorithm_sha256": sha256(Path(__file__)),
        "inputs": {str(p): sha256(p) for p in manifest_inputs},
        "outputs": {
            str(FINAL_TIF): sha256(FINAL_TIF),
            str(FINAL_ASC): sha256(FINAL_ASC),
            str(FINAL_PRJ): sha256(FINAL_PRJ),
            str(LEDGER): sha256(LEDGER),
            str(SUMMARY): sha256(SUMMARY),
        },
        "fixed_point_reached": fixed_point,
        "sentinel1_2021_used": False,
        "bg_flood_run": False,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Hash every generated artifact except the hash set itself, which cannot
    # contain its own digest without becoming self-referential.
    generated = sorted(p for p in OUT_ROOT.rglob("*") if p.is_file() and p != HASHSET)
    hash_lines = [f"{sha256(p)}  {p.relative_to(OUT_ROOT).as_posix()}" for p in generated]
    HASHSET.write_text("\n".join(hash_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"MANIFEST_SHA256={sha256(MANIFEST)}")
    print(f"HASHSET_SHA256={sha256(HASHSET)}")


if __name__ == "__main__":
    main()
