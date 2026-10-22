"""Reconcile contradictory V49-C types, then rebuild C/D/C.1/E/F in an isolated revision.

Current OSM and JRC evidence determines supported feature type. It does not
establish surveyed bathymetry, the 2021 shoreline, or permanent water by itself.
The frozen Gate-G experiment remains unchanged.
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import geopandas as gpd
import pandas as pd

from v49_classify_waterbodies import (CHANNEL_ELIGIBLE_CLASSES, DEFAULT_GRAPH,
    DEFAULT_OUTPUT_DIR as OLD_C, _plot_map, sha256_file, treatment_for_class)

PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT / "V49_R2_20261013"
OLD_C1 = PROJECT / "V49_C1_20261012"


def number(row, key):
    try:
        value = float(row.get(key, 0.))
        return value if math.isfinite(value) else 0.
    except (ValueError, TypeError):
        return 0.


def reconciled_class(row):
    original = str(row["final_class"])
    if original == "OCEAN":
        return original, "Marine boundary retained."
    kind = str(row.get("current_osm_polygon_dominant_type", "")).lower()
    fraction = number(row, "current_osm_polygon_overlap_fraction")
    water_support = (number(row, "jrc_occurrence_p50") >= 5.
                     or number(row, "jrc_recurrence_p50") >= 50.
                     or number(row, "jrc_2024_permanent_fraction") + number(row, "jrc_2024_seasonal_fraction") >= .1)
    if kind in {"lake", "reservoir", "pond"} and fraction >= .75 and water_support:
        return "LAKE_RESERVOIR", f"Current mapped {kind} overlaps {fraction:.2%}; independent JRC water supports standing-water type. Persistence and historical shoreline are assessed separately."
    linear_support = number(row, "current_osm_channel_m") >= 200. or number(row, "graph_length_m") >= 300.
    if original == "UNKNOWN_REVIEW_REQUIRED" and kind == "river" and fraction >= .60 and water_support and linear_support:
        if ("distance_to_ocean_m" in row and number(row, "distance_to_ocean_m") <= 5000.
                and number(row, "dem_mean_m") <= 5.):
            return "ESTUARY_TIDAL_RIVER", f"Mapped coastal channel overlaps {fraction:.2%}; low elevation and coastal proximity require explicit tidal/backwater assessment. Tidal influence is not assumed verified."
        return "RIVER_STREAM", f"Current mapped river overlaps {fraction:.2%}, with linear OSM/HydroRIVERS support and JRC water. Geometry authorization remains subject to D and C.1."
    return original, "Available evidence does not justify changing the existing type."


def build_reconciled_classification(refresh=False, root=ROOT, parent_support_dir=None):
    output = root / "C"
    output.mkdir(parents=True, exist_ok=True)
    source_c = OLD_C
    parent_proof = None
    if parent_support_dir is not None:
        from v49_audit_parent_channel_support import validated_table, R2
        if root.resolve() == R2.resolve():
            raise ValueError("Parent reconciliation must use a new revision; R2 is preserved")
        parent_proof = validated_table(parent_support_dir).set_index("object_id")
        source_c = R2 / "C"
        evidence_path = R2 / "C1" / "V49_C1_fixed_water_evidence.gpkg"
    else:
        evidence_path = OLD_C1 / "V49_C1_fixed_water_evidence.gpkg"
    original = gpd.read_file(source_c / "V49_waterbody_classification.gpkg", layer="classified_objects")
    evidence = gpd.read_file(evidence_path, layer="audited_water_objects").set_index("object_id")
    changes = []
    for idx, row in original.iterrows():
        obj = evidence.loc[row.object_id].to_dict()
        if parent_proof is None:
            cls, reason = reconciled_class(obj)
        else:
            decision = parent_proof.loc[row.object_id]
            if decision.before != row.final_class:
                raise ValueError("Parent decision does not match source classification")
            cls, reason = str(decision.after), str(decision.reason)
        original.loc[idx, "prior_final_class"] = row.final_class
        original.loc[idx, "reconciliation_reason"] = reason
        original.loc[idx, "type_evidence_epoch"] = "OSM 2026-10-11; JRC 1984-2024/2024; not a verified 2021 shoreline"
        if cls == row.final_class:
            continue
        changes.append(dict(object_id=row.object_id, before=row.final_class, after=cls, reason=reason))
        original.loc[idx, "final_class"] = cls
        original.loc[idx, "subtype"] = ("CURRENT_STANDING_WATER_EVIDENCE" if cls == "LAKE_RESERVOIR"
                                       else "COASTAL_CHANNEL_REGIME_UNVERIFIED" if cls == "ESTUARY_TIDAL_RIVER"
                                       else "CORROBORATED_MAPPED_CHANNEL")
        original.loc[idx, "final_confidence"] = "MEDIUM"
        # Accepted type is not accepted depth, storage geometry, or historic persistence.
        original.loc[idx, "review_required_final"] = True
        original.loc[idx, "evidence_summary"] = str(row.evidence_summary) + " | " + root.name + ": " + reason
        treatment, rule = treatment_for_class(cls)
        original.loc[idx, "treatment_code"] = treatment
        original.loc[idx, "treatment_rule"] = rule
        original.loc[idx, "future_channel_geometry_eligible"] = cls in CHANNEL_ELIGIBLE_CLASSES
    gpkg = output / "V49_waterbody_classification.gpkg"
    if gpkg.exists():
        if not refresh:
            raise FileExistsError(f"Revision already exists: {gpkg}; review rather than overwrite.")
        archive = root / "superseded_coastal_candidate"
        archive.mkdir(exist_ok=True)
        for name in (gpkg.name, "V49_C_classification_audit.json", "V49_C_reconciliation_changes.csv"):
            shutil.copy2(output / name, archive / name)
        gpkg.unlink()
    original.to_file(gpkg, layer="classified_objects", driver="GPKG")
    historical = gpd.read_file(source_c / gpkg.name, layer="osm_historical_waterways")
    historical.to_file(gpkg, layer="osm_historical_waterways", driver="GPKG")
    original.drop(columns="geometry").to_csv(output / "V49_waterbody_classification.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(changes).to_csv(output / "V49_C_reconciliation_changes.csv", index=False, encoding="utf-8-sig")
    graph = gpd.read_file(DEFAULT_GRAPH, layer="reaches")
    _plot_map(original, graph, output / "V49_C_classification_map.png")
    shutil.copyfile(source_c / "historical_osm_manifest_source.json", output / "historical_osm_manifest_source.json")
    audit = json.loads((source_c / "V49_C_classification_audit.json").read_text(encoding="utf-8"))
    if parent_proof is not None:
        parent_manifest = parent_support_dir / "V49_parent_channel_support.json"
        audit["prior_reconciliation_changes"] = audit.get("reconciliation_changes", [])
        audit["parent_channel_support"] = {"path": str(parent_manifest.resolve()), "sha256": sha256_file(parent_manifest)}
    unknown = original[original.final_class == "UNKNOWN_REVIEW_REQUIRED"]
    audit.update(schema_version="V49-C-audit-2", revision=root.name,
                 class_counts={str(k): int(v) for k, v in original.final_class.value_counts().items()},
                 class_area_km2={str(k): float(v) for k, v in original.groupby("final_class").area_km2.sum().items()},
                 unknown_review_count=len(unknown), unknown_review_area_km2=float(unknown.area_km2.sum()),
                 review_required_total=int(original.review_required_final.astype(bool).sum()),
                 reconciliation_count=len(changes), reconciliation_changes=changes,
                 key_object_summary={},
                 independent_evidence={"path": str(evidence_path), "sha256": sha256_file(evidence_path)},
                 temporal_limit="Current evidence supports revised type; no 2021 shoreline or field bathymetry is inferred.")
    (output / "V49_C_classification_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return changes


def rebuild_phases(resume=False, refresh=False, root=ROOT, parent_support_dir=None):
    from v49_estimate_reach_geometry import build_v49_d
    from v49_fixed_water_evidence_audit import build_audit
    from v49_synthesize_hydraulic_bed import build_v49_e
    from v49_science_qaqc import build_v49_f
    from v49_validate_waterbody_classes import validate_classification
    from v49_validate_reach_geometry import validate_v49_d
    from v49_validate_fixed_water_evidence import validate_v49_c1
    from v49_validate_hydraulic_bed import validate_v49_e
    from v49_validate_science_qaqc import validate_v49_f
    c, d, c1, e, f = (root / phase for phase in ("C", "D", "C1", "E", "F"))
    if resume and not refresh:
        audit = json.loads((c / "V49_C_classification_audit.json").read_text(encoding="utf-8"))
        pin = audit["independent_evidence"]
        if sha256_file(Path(pin["path"])) != pin["sha256"]:
            raise RuntimeError("Cannot resume after independent evidence changed")
        changes = audit["reconciliation_changes"]
    else:
        changes = build_reconciled_classification(refresh=refresh, root=root, parent_support_dir=parent_support_dir)
    validations = {"C": validate_classification(c)}
    build_v49_d(classification_path=c / "V49_waterbody_classification.gpkg", output_dir=d)
    geometry = d / "V49_reach_geometry.gpkg"
    validations["D"] = validate_v49_d(d)
    build_audit(classified_path=c / "V49_waterbody_classification.gpkg", geometry_path=geometry, output_dir=c1)
    validations["C1"] = validate_v49_c1(c1, geometry)
    gate, evidence = c1 / "V49_C1_v49e_reach_gate.csv", c1 / "V49_C1_fixed_water_evidence.gpkg"
    build_v49_e(geometry_path=geometry, c1_gate_path=gate, c1_evidence_path=evidence, output_dir=e)
    validations["E"] = validate_v49_e(e, geometry, gate, evidence)
    build_v49_f(c_table_path=c / "V49_waterbody_classification.csv", c1_table_path=c1 / "V49_C1_fixed_water_audit.csv",
                c1_evidence_path=evidence, d_geometry_path=geometry, d_audit_path=d / "V49_D_geometry_audit.json",
                e_output_dir=e, output_dir=f)
    validations["F"] = validate_v49_f(f)
    checks = {phase: bool(report.get(f"gate_{phase.lower()}_pass")) for phase, report in validations.items()}
    summary = {"revision": root.name, "class_changes": changes, "phase_checks": checks,
               "hydraulic_promotion_ready": False, "frozen_G_inputs_modified": False}
    (root / ("V49_R3_REBUILD_REPORT.json" if parent_support_dir is not None else "V49_R2_REBUILD_REPORT.json")).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        raise RuntimeError(f"{root.name} phase validation failed: {checks}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true", help="Keep already reconciled C and rebuild dependent R2 products")
    parser.add_argument("--refresh-classification", action="store_true", help="Archive the intermediate C candidate and regenerate C through F")
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    parser.add_argument("--parent-support-dir", type=Path, help="Use validated connected-parent evidence in a new revision")
    args = parser.parse_args()
    rebuild_phases(args.resume, args.refresh_classification, args.output_dir, args.parent_support_dir)
