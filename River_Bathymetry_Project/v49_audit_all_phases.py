"""Refresh every V49 phase gate and distinguish implementation from acceptance.

Does not launch simulations, modify terrain or read an active NetCDF writer.
Hydrological products are checked again from the saved raster bytes.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import binary_erosion

from v49_build_hydro_conditioned_dem import drainage_graph, D8
from v49_estimate_reach_geometry import DEFAULT_DEM, EXPECTED_DEM_SHA256
from v49_synthesize_hydraulic_bed import sha256_file
from v49_validate_coverage import validate as validate_a
from v49_validate_hydrograph import validate_hydrograph
from v49_validate_waterbody_classes import validate_classification
from v49_validate_reach_geometry import validate_v49_d
from v49_validate_fixed_water_evidence import validate_v49_c1
from v49_validate_hydraulic_bed import validate_v49_e
from v49_validate_science_qaqc import validate_v49_f
from v49_validate_hydraulic_validation import validate_v49_g, inspect_published_evidence
from v49_run_hydraulic_validation import status
from v49_runtime_observer import atomic_json
from v49_audit_published_locations import validate_location_context

ROOT = Path(__file__).resolve().parent
R2 = ROOT / "V49_R2_20261013"
LATEST = ROOT / "V49_R3_20261013"


def validate_hydro_readback():
    folder = ROOT / "V49_HYDRO_20261013"
    recorded = json.loads((folder / "V49_HYDRO_validation_report.json").read_text(encoding="utf-8"))
    hashes = {name: sha256_file(folder / name) == expected
              for name, expected in recorded["outputs_sha256"].items()}
    with rasterio.open(DEFAULT_DEM) as source:
        valid = source.read_masks(1) > 0
        signature = (source.shape, source.transform, source.crs)
        before = source.read(1)
    arrays = {}
    grid_checks = {}
    role_checks = {}
    for name in recorded["outputs_sha256"]:
        with rasterio.open(folder / name) as ds:
            arrays[name] = ds.read(1)
            grid_checks[name] = (ds.shape, ds.transform, ds.crs) == signature
            role_checks[name] = ds.tags().get("purpose") == "DRAINAGE_ANALYSIS_ONLY" and ds.tags().get("hydraulic_bed") == "false"
    direction = arrays["V49_HYDRO_D8.tif"]
    recomputed, cycles, outlets, terminal_sum = drainage_graph(direction, valid)
    boundary = valid & ~binary_erosion(valid, structure=np.ones((3, 3)), border_value=0)
    unresolved = valid & ~np.isin(direction, D8)
    conditioned = arrays["V49_DEM_HYDRO_CONDITIONED.tif"]
    checks = {"output_sha256_match": all(hashes.values()), "same_source_grid": all(grid_checks.values()),
              "drainage_only_role_tags": all(role_checks.values()), "conditioned_float64_preserved": conditioned.dtype == np.float64,
              "zero_directed_cycles": cycles == 0, "zero_internal_unresolved_cells": not (unresolved & ~boundary).any(),
              "all_cells_accounted_for_at_outlets": terminal_sum == int(valid.sum()),
              "saved_accumulation_matches_recomputed_graph": np.array_equal(recomputed[valid], arrays["V49_HYDRO_ACCUMULATION_CELLS.tif"][valid]),
              "no_lowering": bool(np.all(conditioned[valid] >= before[valid])),
              "delta_roundtrip": bool(np.allclose(conditioned[valid] - before[valid], arrays["V49_HYDRO_DELTA_Z.tif"][valid], rtol=0, atol=1e-12)),
              "source_dem_unchanged": sha256_file(DEFAULT_DEM) == EXPECTED_DEM_SHA256}
    report = {"checks": {k: bool(v) for k, v in checks.items()}, "pass": all(checks.values()),
              "valid_cells": int(valid.sum()), "outlet_cells": int(outlets), "usable_as_hydraulic_bed": False}
    atomic_json(folder / "V49_HYDRO_readback_validation.json", report)
    return report


def audit_all_phases(revision_dir=LATEST):
    a = validate_a(ROOT / "V49_A_20261012")
    b = validate_hydrograph()
    c = validate_classification(revision_dir / "C")
    d = validate_v49_d(revision_dir / "D")
    c1 = validate_v49_c1(revision_dir / "C1", revision_dir / "D" / "V49_reach_geometry.gpkg")
    e = validate_v49_e(revision_dir / "E", revision_dir / "D" / "V49_reach_geometry.gpkg",
                       revision_dir / "C1" / "V49_C1_v49e_reach_gate.csv", revision_dir / "C1" / "V49_C1_fixed_water_evidence.gpkg")
    f = validate_v49_f(revision_dir / "F")
    g = validate_v49_g()
    hydro = validate_hydro_readback()
    external = inspect_published_evidence(ROOT / "V49_PUBLIC_EVIDENCE_20261013" / "V49_PUBLIC_EVIDENCE_REGISTER.json")
    location_context = validate_location_context()
    execution = status(ROOT / "V49_G_20261013")
    revision = revision_dir.name.split("_")[1]
    passes = {"A": a["pass"], "B": b["gate_b_pass"], f"C_{revision}": c["gate_c_pass"],
              f"D_{revision}": d["gate_d_pass"], f"C1_{revision}": c1["gate_c1_pass"], f"E_{revision}": e["gate_e_pass"],
              f"F_{revision}": f["gate_f_pass"], "G_preparation": g["preparation_pass"],
              "hydro_readback": hydro["pass"], "published_evidence_integrity": external["available"],
              "published_location_context": location_context["readback_pass"]}
    temporal = None
    if (revision_dir / "WATER_HISTORY_2021" / "V49_2021_WATER_HISTORY_REGISTER.json").is_file():
        from v49_audit_2021_water_history import validate as validate_history
        temporal = validate_history(revision_dir / "WATER_HISTORY_2021")
        passes["water_history_2021_readback"] = temporal["pass_"]
    if "parent_channel_support" in json.loads((revision_dir / "C" / "V49_C_classification_audit.json").read_text(encoding="utf-8")):
        passes["same_connected_parent_channel_support"] = c["parent_channel_support_ok"]
    survey_context = None
    if (revision_dir / "SURVEY_CONTEXT" / "V49_PhuSen_2024_survey_register.json").is_file():
        from v49_ingest_survey_context import validate as validate_survey
        survey_context = validate_survey()
        passes["survey_context_primary_source_readback"] = survey_context["pass_"]
    research_sources = None
    if revision_dir.resolve() == LATEST.resolve():
        from v49_audit_r3_research_sources import audit as audit_research_sources
        research_sources = audit_research_sources()
        passes["new_primary_research_sources_integrity"] = research_sources["pass_"]
    report = {"schema_version": "V49-all-phase-remediation-audit-1", "updated_at_utc": datetime.now(timezone.utc).isoformat(),
              "revision_dir": str(revision_dir.resolve()), "water_history_2021": temporal,
              "survey_context": survey_context,
              "new_primary_research_sources": research_sources,
              "implementation_gate_checks": passes, "all_implementation_checks_pass": all(passes.values()),
              "all_phases_scientifically_complete": False, "gate_g_pass": g["gate_g_pass"], "hydraulic_promotion_ready": False,
              "unknown_object_count": c["unknown_review_count"], "fixed_water_review_count": c1["review_queue_count"],
              "major_persistent_omission_count": f["major_persistent_omission_count"],
              "current_graph_support": f["current_graph_support"],
              "published_location_context": location_context,
              "hydro_readback": hydro, "published_evidence": external,
              "execution": execution,
              "remaining_conditions": [
                  "Complete CENTRAL/LOW/HIGH and the 120 h BASE; evaluate matched SAR, velocity and observed numerical budget",
                  "Resolve object type, persistence, current 30/90 m graph-support gaps and alignment, and evidence-authorized geometry coverage",
                  "Reconcile reservoir footprint, vertical datum, spatial bed and dated operating state with published storage references",
                  "Verify gauge/survey coordinates, vertical datum, observation conflicts and event-window coverage before WSE/timing acceptance",
                  "Record the explicit scientific acceptance decision; implementation PASS cannot substitute for measured accuracy"]}
    atomic_json(ROOT / "V49_ALL_PHASE_AUDIT_20261013.json", report)
    print(json.dumps({k: report[k] for k in ("implementation_gate_checks", "all_implementation_checks_pass", "all_phases_scientifically_complete", "gate_g_pass", "hydraulic_promotion_ready", "unknown_object_count", "major_persistent_omission_count")}, indent=2))
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision-dir", type=Path, default=LATEST)
    args = parser.parse_args()
    result = audit_all_phases(args.revision_dir)
    raise SystemExit(0 if result["all_implementation_checks_pass"] else 1)
