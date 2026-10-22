"""V49-F coverage and science QA/QC aggregation.

This phase is deliberately read-only with respect to terrain.  It combines
the accepted A/B/C/C.1/D/E evidence into auditable coverage, topology,
geometry, incision, storage, provenance, and uncertainty metrics.  Hydraulic
model sensitivity remains a V49-G matched-run activity and is reported here
as an explicit pending item rather than inferred from DEM self-consistency.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import mapping

from v49_estimate_reach_geometry import DEFAULT_DEM, EXPECTED_DEM_SHA256
from v49_graph_support_audit import audit_object_graph_support
from v49_synthesize_hydraulic_bed import (
    DEFAULT_LEGACY_NETWORK,
    MODIFICATION_EPS_M,
    load_protected_mask,
    sha256_file,
    split_pipe,
    synthesize_reach_delta,
)


PROJECT_DIR = Path(r"D:\VTP\River_Bathymetry_Project")
DEFAULT_A_TABLE = PROJECT_DIR / "V49_A_20261012" / "V49_water_object_table.csv"
DEFAULT_B_AUDIT = PROJECT_DIR / "V49_B_20261012" / "V49_graph_audit.json"
DEFAULT_C_TABLE = PROJECT_DIR / "V49_C_20261012" / "V49_waterbody_classification.csv"
DEFAULT_C1_TABLE = PROJECT_DIR / "V49_C1_20261012" / "V49_C1_fixed_water_audit.csv"
DEFAULT_C1_EVIDENCE = PROJECT_DIR / "V49_C1_20261012" / "V49_C1_fixed_water_evidence.gpkg"
DEFAULT_D_GEOMETRY = PROJECT_DIR / "V49_D_20261012" / "V49_reach_geometry.gpkg"
DEFAULT_D_AUDIT = PROJECT_DIR / "V49_D_20261012" / "V49_D_geometry_audit.json"
DEFAULT_E_OUTPUT_DIR = PROJECT_DIR / "V49_E_20261012"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "V49_F_20261013"

MAJOR_OBJECT_AREA_KM2 = 1.0
PERCENTILES = (5, 25, 50, 75, 95)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _percentiles(values: pd.Series | np.ndarray) -> dict[str, float | None]:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {f"p{p:02d}": None for p in PERCENTILES}
    return {f"p{p:02d}": float(np.percentile(array, p)) for p in PERCENTILES}


def _pct(numerator: float, denominator: float) -> float:
    return float(100.0 * numerator / denominator) if denominator else 0.0


def _represented_object_ids(e_volume: pd.DataFrame) -> set[str]:
    represented: set[str] = set()
    for value in e_volume.get("v49c_object_ids", pd.Series(dtype=object)):
        represented.update(split_pipe(value))
    return represented


def build_coverage_by_class(
    classification: pd.DataFrame,
    c1: pd.DataFrame,
    e_volume: pd.DataFrame,
) -> pd.DataFrame:
    represented_ids = _represented_object_ids(e_volume)
    c1_status = c1.set_index(c1.object_id.astype(str))["fixed_water_status"].to_dict()
    rows: list[dict] = []
    for water_class, group in classification.groupby("final_class", dropna=False):
        group = group.copy()
        object_ids = group.object_id.astype(str)
        represented = object_ids.isin(represented_ids)
        confirmed = object_ids.map(c1_status).eq("CONFIRMED_PERSISTENT")
        area = pd.to_numeric(group.area_km2, errors="coerce").fillna(0.0)
        modified_area_m2 = float(
            pd.to_numeric(
                e_volume.loc[e_volume.water_class.astype(str) == str(water_class), "modified_area_m2"],
                errors="coerce",
            ).fillna(0.0).sum()
        )
        total_area_km2 = float(area.sum())
        represented_area_km2 = float(area[represented].sum())
        confirmed_area_km2 = float(area[confirmed].sum())
        rows.append(
            {
                "water_class": str(water_class),
                "object_count": int(len(group)),
                "area_km2": total_area_km2,
                "c1_confirmed_persistent_object_count": int(confirmed.sum()),
                "c1_confirmed_persistent_area_km2": confirmed_area_km2,
                "v49e_represented_object_count": int(represented.sum()),
                "v49e_represented_object_count_pct": _pct(int(represented.sum()), len(group)),
                "v49e_represented_object_area_km2": represented_area_km2,
                "v49e_represented_object_area_pct": _pct(represented_area_km2, total_area_km2),
                "v49e_actual_modified_area_km2": modified_area_m2 / 1_000_000.0,
                "v49e_actual_modified_area_pct_of_class": _pct(
                    modified_area_m2 / 1_000_000.0, total_area_km2
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("water_class").reset_index(drop=True)


def build_major_persistent_omissions(
    c1: pd.DataFrame,
    represented_ids: set[str],
) -> pd.DataFrame:
    rows = c1.copy()
    rows["area_km2"] = pd.to_numeric(rows.area_km2, errors="coerce").fillna(0.0)
    rows["graph_major_reach_count"] = pd.to_numeric(
        rows.get("graph_major_reach_count", 0), errors="coerce"
    ).fillna(0).astype(int)
    rows["major_persistent_rule"] = (
        (rows.area_km2 >= MAJOR_OBJECT_AREA_KM2) | (rows.graph_major_reach_count > 0)
    )
    omissions = rows[
        rows.fixed_water_status.astype(str).eq("CONFIRMED_PERSISTENT")
        & ~rows.final_class.astype(str).eq("OCEAN")
        & rows.major_persistent_rule
        & ~rows.object_id.astype(str).isin(represented_ids)
    ].copy()
    keep = [
        "object_id",
        "final_class",
        "area_km2",
        "graph_major_reach_count",
        "fixed_water_status",
        "treatment_code",
        "future_channel_geometry_eligible",
        "decision_reason",
    ]
    return omissions[[column for column in keep if column in omissions.columns]].sort_values(
        ["area_km2", "object_id"], ascending=[False, True]
    )


def build_geometry_by_order(geometry: pd.DataFrame) -> pd.DataFrame:
    eligible = geometry[
        geometry.v49d_scope.astype(str).ne("OUTSIDE_V49C_ELIGIBLE_CHANNEL")
    ].copy()
    rows: list[dict] = []
    for order, group in eligible.groupby("ORD_STRA", dropna=False):
        widths = pd.to_numeric(group.width_m, errors="coerce")
        depths = pd.to_numeric(group.depth_est_m, errors="coerce")
        width_p = _percentiles(widths)
        depth_p = _percentiles(depths)
        rows.append(
            {
                "strahler_order": int(order) if pd.notna(order) else -1,
                "reach_count": int(len(group)),
                "width_valid_count": int(np.isfinite(widths).sum()),
                "depth_valid_count": int(np.isfinite(depths).sum()),
                **{f"width_{key}_m": value for key, value in width_p.items()},
                **{f"depth_{key}_m": value for key, value in depth_p.items()},
            }
        )
    return pd.DataFrame(rows).sort_values("strahler_order").reset_index(drop=True)


def classify_geometry_source(method: object) -> str:
    text = str(method).upper()
    if "SURVEY" in text or "BATHY" in text:
        return "SURVEY_OR_OBSERVED"
    if "MANNING" in text and "REJECTED" not in text:
        return "HYDRAULIC_INVERSION"
    if "POWERLAW" in text or "EMPIRICAL" in text or "MANNING_REJECTED" in text:
        return "EMPIRICAL_FALLBACK"
    if "UNRESOLVED" in text:
        return "UNRESOLVED"
    return "OTHER"


def build_geometry_source_fractions(geometry: pd.DataFrame) -> pd.DataFrame:
    eligible = geometry[
        geometry.v49d_scope.astype(str).ne("OUTSIDE_V49C_ELIGIBLE_CHANNEL")
    ].copy()
    eligible["source_group"] = eligible.depth_method.map(classify_geometry_source)
    counts = eligible.groupby("source_group").size().rename("reach_count").reset_index()
    counts["fraction_pct"] = counts.reach_count.map(lambda value: _pct(value, len(eligible)))
    counts["scope_reach_count"] = int(len(eligible))
    return counts.sort_values("source_group").reset_index(drop=True)


def build_incision_by_reach(
    geometry_path: Path,
    c1_evidence_path: Path,
    e_volume: pd.DataFrame,
    dem_path: Path,
    legacy_network_path: Path,
) -> pd.DataFrame:
    reaches = gpd.read_file(geometry_path, layer="reach_geometry")
    audited_objects = gpd.read_file(c1_evidence_path, layer="audited_water_objects")
    reach_ids = sorted(e_volume.reach_id.astype(str).tolist())
    authorized = reaches[reaches.reach_id.astype(str).isin(reach_ids)].copy().sort_values("reach_id")

    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        transform = src.transform
        nodata = src.nodata
    valid = np.isfinite(dem)
    if nodata is not None:
        valid &= dem != nodata
    protected = load_protected_mask(legacy_network_path, dem.shape)

    per_reach_delta: list[np.ndarray] = []
    for _, reach in authorized.iterrows():
        object_ids = split_pipe(reach.v49c_object_ids)
        associated = audited_objects[audited_objects.object_id.astype(str).isin(object_ids)]
        class_mask = rasterize(
            [(mapping(geom), 1) for geom in associated.geometry if geom is not None and not geom.is_empty],
            out_shape=dem.shape,
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=False,
        ).astype(bool)
        delta, _, _ = synthesize_reach_delta(dem, valid, transform, reach, class_mask, protected)
        per_reach_delta.append(delta)

    if not per_reach_delta:
        return pd.DataFrame()
    stack = np.stack(per_reach_delta, axis=0)
    winner = np.argmax(stack, axis=0)
    merged = np.max(stack, axis=0)
    rows: list[dict] = []
    for idx, (_, reach) in enumerate(authorized.iterrows()):
        values = merged[(winner == idx) & (merged > MODIFICATION_EPS_M)]
        percentiles = _percentiles(values)
        rows.append(
            {
                "reach_id": str(reach.reach_id),
                "modified_pixel_count_pre_quantization": int(values.size),
                "max_incision_m_pre_quantization": float(values.max()) if values.size else 0.0,
                **{f"incision_{key}_m_pre_quantization": value for key, value in percentiles.items()},
                "depth_est_m": float(reach.depth_est_m),
                "uncertainty_class": str(reach.uncertainty_class),
            }
        )
    return pd.DataFrame(rows)


def _write_coverage_chart(coverage: pd.DataFrame, output_dir: Path) -> None:
    inland = coverage[coverage.water_class != "OCEAN"].copy()
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(inland.water_class, inland.v49e_represented_object_area_pct)
    ax.set_ylabel("represented object area (%)")
    ax.set_title("V49-F hydraulic representation coverage by inland-water class")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(output_dir / "V49_F_coverage_by_class.png", dpi=180)
    plt.close(fig)


def _write_geometry_chart(geometry_by_order: pd.DataFrame, output_dir: Path) -> None:
    valid = geometry_by_order[geometry_by_order.depth_p50_m.notna()].copy()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(valid.strahler_order, valid.depth_p50_m, marker="o")
    ax.set_xlabel("Strahler order")
    ax.set_ylabel("median inferred depth (m)")
    ax.set_title("V49-F inferred depth distribution by Strahler order")
    fig.tight_layout()
    fig.savefig(output_dir / "V49_F_depth_by_strahler.png", dpi=180)
    plt.close(fig)


def build_v49_f(
    a_table_path: Path = DEFAULT_A_TABLE,
    b_audit_path: Path = DEFAULT_B_AUDIT,
    c_table_path: Path = DEFAULT_C_TABLE,
    c1_table_path: Path = DEFAULT_C1_TABLE,
    c1_evidence_path: Path = DEFAULT_C1_EVIDENCE,
    d_geometry_path: Path = DEFAULT_D_GEOMETRY,
    d_audit_path: Path = DEFAULT_D_AUDIT,
    e_output_dir: Path = DEFAULT_E_OUTPUT_DIR,
    dem_path: Path = DEFAULT_DEM,
    legacy_network_path: Path = DEFAULT_LEGACY_NETWORK,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    graph_path: Path | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Read A as an explicit lineage dependency even though C carries the same object IDs.
    inventory = pd.read_csv(a_table_path)
    classification = pd.read_csv(c_table_path)
    c1 = pd.read_csv(c1_table_path)
    geometry = pd.read_csv(d_geometry_path.with_name("V49_reach_geometry.csv"))
    e_volume = pd.read_csv(e_output_dir / "V49_E_modification_volume_by_reach.csv")
    e_adjust = pd.read_csv(e_output_dir / "V49_E_longitudinal_adjustments.csv")
    b_audit = _json(b_audit_path)
    d_audit = _json(d_audit_path)
    e_audit = _json(e_output_dir / "V49_E_hydraulic_bed_audit.json")
    graph_path = graph_path or b_audit_path.with_name("V49_hydrograph.gpkg")
    spatial_objects = gpd.read_file(c1_evidence_path, layer="audited_water_objects")
    graph_reaches = gpd.read_file(graph_path, layer="reaches")
    graph_support = audit_object_graph_support(spatial_objects, graph_reaches)
    graph_support.to_csv(output_dir / "V49_F_object_graph_support.csv", index=False, encoding="utf-8-sig")

    coverage = build_coverage_by_class(classification, c1, e_volume)
    represented_ids = _represented_object_ids(e_volume)
    omissions = build_major_persistent_omissions(c1, represented_ids)
    geometry_by_order = build_geometry_by_order(geometry)
    source_fractions = build_geometry_source_fractions(geometry)
    incision = build_incision_by_reach(
        d_geometry_path, c1_evidence_path, e_volume, dem_path, legacy_network_path
    )

    coverage.to_csv(output_dir / "V49_F_coverage_by_class.csv", index=False, encoding="utf-8-sig")
    omissions.to_csv(output_dir / "V49_F_major_persistent_omissions.csv", index=False, encoding="utf-8-sig")
    geometry_by_order.to_csv(output_dir / "V49_F_geometry_by_strahler.csv", index=False, encoding="utf-8-sig")
    source_fractions.to_csv(output_dir / "V49_F_geometry_source_fractions.csv", index=False, encoding="utf-8-sig")
    incision.to_csv(output_dir / "V49_F_incision_by_reach.csv", index=False, encoding="utf-8-sig")
    e_volume.to_csv(output_dir / "V49_F_added_storage_by_reach.csv", index=False, encoding="utf-8-sig")
    _write_coverage_chart(coverage, output_dir)
    _write_geometry_chart(geometry_by_order, output_dir)

    inland = classification[classification.final_class.astype(str) != "OCEAN"]
    inland_area = float(pd.to_numeric(inland.area_km2, errors="coerce").fillna(0.0).sum())
    represented_inland = inland[inland.object_id.astype(str).isin(represented_ids)]
    represented_inland_area = float(
        pd.to_numeric(represented_inland.area_km2, errors="coerce").fillna(0.0).sum()
    )
    eligible = geometry[
        geometry.v49d_scope.astype(str).ne("OUTSIDE_V49C_ELIGIBLE_CHANNEL")
    ].copy()
    authorized_ids = set(e_volume.reach_id.astype(str))
    authorized_geometry = geometry[geometry.reach_id.astype(str).isin(authorized_ids)].copy()
    geometry_source_counts = {
        row.source_group: int(row.reach_count) for row in source_fractions.itertuples(index=False)
    }
    total_adjustment = float(
        pd.to_numeric(e_adjust.get("adjustment_m", pd.Series(dtype=float)), errors="coerce")
        .fillna(0.0)
        .abs()
        .sum()
    )

    source_hash = sha256_file(dem_path)
    uncertainty_counts = {
        str(key): int(value)
        for key, value in authorized_geometry.uncertainty_class.astype(str).value_counts().to_dict().items()
    }

    report = {
        "schema_version": "V49-F-science-qaqc-1",
        "phase": "V49-F",
        "scope": "coverage/science QA-QC aggregation; no DEM modification and no hydraulic model run",
        "lineage": {
            "v49a_object_count": int(len(inventory)),
            "v49c_object_count": int(len(classification)),
            "v49d_reach_count": int(len(geometry)),
            "v49e_authorized_reach_count": int(len(e_volume)),
            "source_dem_sha256": source_hash,
            "source_dem_matches_expected": source_hash == EXPECTED_DEM_SHA256,
            "graph_support_inputs": {
                "objects_path": str(c1_evidence_path.resolve()), "objects_sha256": sha256_file(c1_evidence_path),
                "graph_path": str(graph_path.resolve()), "graph_sha256": sha256_file(graph_path),
            },
        },
        "coverage": {
            "qualifying_inland_object_count": int(len(inland)),
            "qualifying_inland_area_km2": inland_area,
            "v49e_represented_inland_object_count": int(len(represented_inland)),
            "v49e_represented_inland_object_count_pct": _pct(len(represented_inland), len(inland)),
            "v49e_represented_inland_object_area_km2": represented_inland_area,
            "v49e_represented_inland_object_area_pct": _pct(represented_inland_area, inland_area),
            "v49e_actual_modified_area_km2": float(e_volume.modified_area_m2.sum()) / 1_000_000.0,
            "coverage_table": "V49_F_coverage_by_class.csv",
        },
        "major_persistent_omissions": {
            "definition": (
                "C.1 CONFIRMED_PERSISTENT inland object with area >= 1.0 km2 or at least one associated major graph reach; "
                "omitted means no object association with an accepted V49-E reach."
            ),
            "count": int(len(omissions)),
            "object_ids": omissions.object_id.astype(str).tolist() if not omissions.empty else [],
            "table": "V49_F_major_persistent_omissions.csv",
        },
        "topology": {
            "orphan_major_reach_count": int(b_audit.get("orphan_major_reach_count", -1)),
            "directed_cycle_count": int(b_audit.get("directed_cycle_count", -1)),
            "directed_cycle_explanations": b_audit.get("directed_cycles", []),
            "historical_v49b_linear_water_object_without_graph_support_count": int(
                b_audit.get("linear_water_object_without_graph_support_count", -1)
            ),
            "historical_v49b_missing_graph_object_ids": b_audit.get("linear_water_object_without_graph_support_ids", []),
            "linear_water_object_without_graph_support_count": int(graph_support.support_state.eq("NO_GRAPH_WITHIN_90M_REVIEW").sum()),
            "current_channel_or_candidate_objects_without_graph_90m_ids": graph_support.loc[graph_support.support_state.eq("NO_GRAPH_WITHIN_90M_REVIEW"), "object_id"].tolist(),
            "coarse_graph_alignment_review_object_ids": graph_support.loc[graph_support.support_state.eq("COARSE_GRAPH_ALIGNMENT_REVIEW"), "object_id"].tolist(),
            "object_graph_support_table": "V49_F_object_graph_support.csv",
            "object_graph_support_table_sha256": sha256_file(output_dir / "V49_F_object_graph_support.csv"),
            "graph_support_interpretation": "Current classes or OSM channel candidates are checked at 30/90 m; a 30 m miss with 90 m support is alignment review, not an automatically authorized new graph edge.",
        },
        "confluence": {
            "v49d_confluence_count": int(d_audit.get("confluence_count", -1)),
            "v49d_unresolved_authorized_inversion_count": int(
                d_audit.get("unresolved_authorized_confluence_inversion_count", -1)
            ),
            "v49e_confluence_check_count": int(e_audit.get("confluence_check_count", -1)),
            "v49e_unresolved_confluence_count": int(e_audit.get("unresolved_confluence_count", -1)),
        },
        "geometry": {
            "v49c_eligible_reach_count": int(len(eligible)),
            "v49e_reach_count": int(len(authorized_geometry)),
            "width_depth_by_strahler_table": "V49_F_geometry_by_strahler.csv",
            "source_fraction_table": "V49_F_geometry_source_fractions.csv",
            "source_group_counts_v49c_eligible_scope": geometry_source_counts,
            "v49e_uncertainty_class_counts": uncertainty_counts,
            "survey_geometry_fraction_pct_v49c_eligible_scope": _pct(
                geometry_source_counts.get("SURVEY_OR_OBSERVED", 0), len(eligible)
            ),
            "hydraulic_inversion_fraction_pct_v49c_eligible_scope": _pct(
                geometry_source_counts.get("HYDRAULIC_INVERSION", 0), len(eligible)
            ),
            "empirical_fallback_fraction_pct_v49c_eligible_scope": _pct(
                geometry_source_counts.get("EMPIRICAL_FALLBACK", 0), len(eligible)
            ),
        },
        "incision_and_storage": {
            "incision_table": "V49_F_incision_by_reach.csv",
            "storage_table": "V49_F_added_storage_by_reach.csv",
            "total_added_storage_m3": float(e_volume.lowering_volume_m3.sum()),
            "maximum_effective_incision_m": float(e_volume.max_lowering_m.max()),
            "storage_is_acceptance_target": False,
        },
        "conditioning_adjustment": {
            "forced_longitudinal_adjustment_count": int(len(e_adjust)),
            "sum_absolute_forced_adjustment_m": total_adjustment,
            "global_monotonic_filter_used": bool(e_audit.get("global_monotonic_filter_used", True)),
        },
        "hydraulic_sensitivity": {
            "status": "PENDING_V49_G_MATCHED_BG_FLOOD_RUNS",
            "metrics_available": False,
            "required_scenarios": [
                "V48_BASE",
                "LEGACY_FIVE_BRANCH_DIAGNOSTIC",
                "V49_CENTRAL",
                "V49_LOW",
                "V49_HIGH",
            ],
            "required_metrics": [
                "flood_extent_CSI_F1_precision_recall",
                "WSE_bias_MAE_RMSE",
                "velocity_sanity",
                "arrival_time_error",
                "peak_timing_error",
                "mass_balance_error",
            ],
            "note": (
                "V49-F does not infer flood sensitivity from DEM geometry. Matched BG_Flood runs and independent observations are required in V49-G."
            ),
        },
        "scientific_guardrails": {
            "uses_minimum_storage_target": False,
            "certifies_depth_by_raster_self_reproduction_only": False,
            "reports_uncertainty_with_geometry": True,
            "reports_coverage_with_geometry": True,
            "source_dem_modified_by_v49f": False,
        },
        "promotion": {
            "hydraulic_promotion_ready": False,
            "blockers": [
                "Matched V49 LOW/CENTRAL/HIGH BG_Flood sensitivity runs have not yet been executed and validated against independent observations.",
                f"{len(omissions)} major CONFIRMED_PERSISTENT inland-water objects remain without accepted V49-E hydraulic representation.",
                "V49-E currently represents only the strict evidence-authorized subset; review-only river/tidal/reservoir/wetland objects remain unresolved.",
            ],
            "next_phase": "V49-G — matched BG_Flood hydraulic validation and bathymetry sensitivity",
        },
    }
    (output_dir / "V49_F_science_qaqc.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = build_v49_f(output_dir=args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
