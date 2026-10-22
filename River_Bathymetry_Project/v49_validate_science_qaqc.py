"""Independent acceptance validator for V49-F science QA/QC outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import numpy as np

from v49_estimate_reach_geometry import DEFAULT_DEM, EXPECTED_DEM_SHA256
from v49_science_qaqc import DEFAULT_OUTPUT_DIR
from v49_synthesize_hydraulic_bed import sha256_file


def validate_graph_support_table(path: Path, topology: dict, object_count: int) -> bool:
    """Check the saved per-object diagnosis; coarse alignment cannot mean a new edge."""
    try:
        table = pd.read_csv(path, keep_default_na=False)
        if sha256_file(path) != topology.get("object_graph_support_table_sha256"):
            return False
        if len(table) != object_count or not table.object_id.is_unique:
            return False
        missing_ids, alignment_ids = [], []
        for row in table.itertuples(index=False):
            counts = [float(row.graph_30m_reach_count), float(row.graph_90m_reach_count)]
            if not all(np.isfinite(n) and n >= 0 and n.is_integer() for n in counts):
                return False
            ids30 = set(filter(None, str(row.graph_30m_reach_ids).split(" | ")))
            ids90 = set(filter(None, str(row.graph_90m_reach_ids).split(" | ")))
            if len(ids30) != counts[0] or len(ids90) != counts[1] or not ids30.issubset(ids90):
                return False
            if str(row.automatic_graph_or_carving_authorization).lower() != "false":
                return False
            relevant = str(row.channel_graph_relevant).lower()
            if relevant not in {"true", "false"}:
                return False
            expected = "NO_CHANNEL_GRAPH_GAP_IDENTIFIED"
            if relevant == "true" and not ids90:
                expected = "NO_GRAPH_WITHIN_90M_REVIEW"
                missing_ids.append(row.object_id)
            elif relevant == "true" and not ids30:
                expected = "COARSE_GRAPH_ALIGNMENT_REVIEW"
                alignment_ids.append(row.object_id)
            if row.support_state != expected:
                return False
        return (len(missing_ids) == topology.get("linear_water_object_without_graph_support_count")
                and sorted(missing_ids) == sorted(topology.get("current_channel_or_candidate_objects_without_graph_90m_ids", []))
                and sorted(alignment_ids) == sorted(topology.get("coarse_graph_alignment_review_object_ids", [])))
    except (OSError, ValueError, AttributeError, KeyError, pd.errors.ParserError):
        return False


def validate_v49_f(output_dir: Path = DEFAULT_OUTPUT_DIR, dem_path: Path = DEFAULT_DEM) -> dict:
    report_path = output_dir / "V49_F_science_qaqc.json"
    required = [
        report_path,
        output_dir / "V49_F_coverage_by_class.csv",
        output_dir / "V49_F_major_persistent_omissions.csv",
        output_dir / "V49_F_geometry_by_strahler.csv",
        output_dir / "V49_F_geometry_source_fractions.csv",
        output_dir / "V49_F_incision_by_reach.csv",
        output_dir / "V49_F_added_storage_by_reach.csv",
        output_dir / "V49_F_coverage_by_class.png",
        output_dir / "V49_F_depth_by_strahler.png",
    ]
    missing = [str(path) for path in required if not path.exists() or path.stat().st_size == 0]
    if missing:
        result = {"schema_version": "V49-F-validation-1", "missing_outputs": missing, "gate_f_pass": False}
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "V49_F_validation_report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result

    report = json.loads(report_path.read_text(encoding="utf-8"))
    coverage = pd.read_csv(output_dir / "V49_F_coverage_by_class.csv")
    geometry = pd.read_csv(output_dir / "V49_F_geometry_by_strahler.csv")
    sources = pd.read_csv(output_dir / "V49_F_geometry_source_fractions.csv")
    incision = pd.read_csv(output_dir / "V49_F_incision_by_reach.csv")
    storage = pd.read_csv(output_dir / "V49_F_added_storage_by_reach.csv")

    guards = report.get("scientific_guardrails", {})
    sensitivity = report.get("hydraulic_sensitivity", {})
    topology = report.get("topology", {})
    confluence = report.get("confluence", {})
    promotion = report.get("promotion", {})
    dem_hash = sha256_file(dem_path)

    checks = {
        "source_dem_unchanged": dem_hash == EXPECTED_DEM_SHA256,
        "coverage_reported_by_class": len(coverage) > 0 and coverage.water_class.is_unique,
        "coverage_has_representation_and_actual_footprint": {
            "v49e_represented_object_area_pct",
            "v49e_actual_modified_area_pct_of_class",
        }.issubset(coverage.columns),
        "topology_orphans_zero": int(topology.get("orphan_major_reach_count", -1)) == 0,
        "topology_directed_cycles_zero": int(topology.get("directed_cycle_count", -1)) == 0,
        "authorized_confluence_inconsistency_zero": int(
            confluence.get("v49e_unresolved_confluence_count", -1)
        ) == 0,
        "geometry_percentiles_reported_by_strahler": len(geometry) > 0
        and {"width_p50_m", "depth_p50_m"}.issubset(geometry.columns),
        "incision_percentiles_reported_by_reach": len(incision) > 0
        and {"incision_p50_m_pre_quantization", "incision_p95_m_pre_quantization"}.issubset(
            incision.columns
        ),
        "storage_reported_by_reach_and_class": len(storage) > 0
        and {"reach_id", "water_class", "lowering_volume_m3"}.issubset(storage.columns),
        "geometry_source_fractions_reported": len(sources) > 0
        and abs(float(sources.fraction_pct.sum()) - 100.0) < 1.0e-6,
        "no_storage_acceptance_target": guards.get("uses_minimum_storage_target") is False
        and report.get("incision_and_storage", {}).get("storage_is_acceptance_target") is False,
        "no_circular_depth_certification": guards.get("certifies_depth_by_raster_self_reproduction_only") is False,
        "uncertainty_reported": guards.get("reports_uncertainty_with_geometry") is True
        and bool(report.get("geometry", {}).get("v49e_uncertainty_class_counts")),
        "sensitivity_status_explicit": sensitivity.get("status") == "PENDING_V49_G_MATCHED_BG_FLOOD_RUNS"
        and sensitivity.get("metrics_available") is False,
        "promotion_not_claimed_before_v49g": promotion.get("hydraulic_promotion_ready") is False,
    }
    if topology.get("object_graph_support_table"):
        checks["current_graph_support_consistent"] = validate_graph_support_table(
            output_dir / topology["object_graph_support_table"], topology,
            int(report.get("coverage", {}).get("qualifying_inland_object_count", -1)))
        refs = report.get("lineage", {}).get("graph_support_inputs", {})
        checks["current_graph_support_source_integrity"] = bool(refs) and all(
            Path(refs.get(key + "_path", "")).is_file()
            and sha256_file(Path(refs[key + "_path"])) == refs.get(key + "_sha256")
            for key in ("objects", "graph"))
    gate_f_pass = bool(all(checks.values()))
    result = {
        "schema_version": "V49-F-validation-1",
        "checks": checks,
        "major_persistent_omission_count": int(
            report.get("major_persistent_omissions", {}).get("count", -1)
        ),
        "v49e_represented_inland_object_count_pct": float(
            report.get("coverage", {}).get("v49e_represented_inland_object_count_pct", 0.0)
        ),
        "v49e_represented_inland_object_area_pct": float(
            report.get("coverage", {}).get("v49e_represented_inland_object_area_pct", 0.0)
        ),
        "hydraulic_promotion_ready": bool(promotion.get("hydraulic_promotion_ready", False)),
        "gate_f_interpretation": (
            "Gate F PASS means the science/coverage QA is complete and honestly reports unresolved coverage and uncertainty. "
            "It does not promote the hydraulic DEM; V49-G matched BG_Flood validation remains mandatory."
        ),
        "gate_f_pass": gate_f_pass,
        "current_graph_support": {
            "no_graph_within_90m_object_ids": topology.get("current_channel_or_candidate_objects_without_graph_90m_ids", []),
            "alignment_review_object_ids": topology.get("coarse_graph_alignment_review_object_ids", []),
            "historical_v49b_missing_object_ids": topology.get("historical_v49b_missing_graph_object_ids", []),
        },
    }
    (output_dir / "V49_F_validation_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    args = parser.parse_args()
    result = validate_v49_f(args.output_dir, args.dem)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["gate_f_pass"] else 1)


if __name__ == "__main__":
    main()
