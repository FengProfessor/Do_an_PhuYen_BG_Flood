"""Build a geospatial, evidence-specific handoff for unresolved V49 acceptance.

Coverage counts actual edited pixels. Candidate OSM edges retain unknown
direction and never enter the accepted hydrograph without verification.
"""
from __future__ import annotations
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds, Window
from shapely.geometry import LineString, Point

from v49_estimate_reach_geometry import DEFAULT_DEM, DEFAULT_GRAPH
from v49_synthesize_hydraulic_bed import sha256_file
from v49_graph_support_audit import audit_object_graph_support
from v49_audit_published_locations import validate_location_context

PROJECT = Path(__file__).resolve().parent
R2 = PROJECT / "V49_R2_20261013"
OUTPUT = R2 / "REMAINING_EVIDENCE"


def build(revision_dir=R2):
    output = revision_dir / "REMAINING_EVIDENCE"
    output.mkdir(parents=True, exist_ok=True)
    evidence_path = revision_dir / "C1" / "V49_C1_fixed_water_evidence.gpkg"
    objects = gpd.read_file(evidence_path, layer="audited_water_objects")
    graph = gpd.read_file(DEFAULT_GRAPH, layer="reaches")
    support = audit_object_graph_support(objects, graph)
    support.to_csv(output / "V49_graph_support_30m_90m.csv", index=False, encoding="utf-8-sig")
    support_index = support.set_index("object_id")
    geometry = gpd.read_file(revision_dir / "D" / "V49_reach_geometry.gpkg", layer="reach_geometry")
    e_audit = json.loads((revision_dir / "E" / "V49_E_hydraulic_bed_audit.json").read_text(encoding="utf-8"))
    authorized = set(e_audit["authorized_reach_ids"])
    register_path = PROJECT / "V49_PUBLIC_EVIDENCE_20261013" / "V49_PUBLIC_EVIDENCE_REGISTER.json"
    register = json.loads(register_path.read_text(encoding="utf-8")) if register_path.exists() else {}
    curve_by_object = {r["inventory_object_id"]: name for name, r in register.get("reservoir_curves", {}).items()}
    capacity_by_object = {r["inventory_object_id_candidate"]: r for r in register.get("minor_reservoir_capacity_references", [])}
    location_context = validate_location_context()
    if not location_context["readback_pass"]:
        raise ValueError("Published relative-location context must be rebuilt from intact evidence")
    locations = pd.read_csv(OUTPUT / "V49_published_location_and_footprint_context.csv")
    history_path = revision_dir / "WATER_HISTORY_2021" / "V49_2021_WATER_HISTORY_REGISTER.json"
    history = None
    if history_path.is_file():
        from v49_audit_2021_water_history import validate as validate_history
        history = validate_history(history_path.parent)
        if not history["pass_"]:
            raise ValueError("2021 water history failed source readback")
        november = pd.read_csv(history_path.parent / "V49_2021_November_water_observations.csv").set_index("object_id")
        annual = pd.read_csv(history_path.parent / "V49_2021_annual_observation_coverage.csv").set_index("object_id")
    rows = []
    with rasterio.open(DEFAULT_DEM) as source, rasterio.open(revision_dir / "E" / "V49_E_hydraulic_bed.tif") as bed:
        for _, obj in objects.iterrows():
            if obj.final_class == "OCEAN":
                continue
            window = from_bounds(*obj.geometry.bounds, transform=source.transform).round_offsets().round_lengths()
            window = window.intersection(Window(0, 0, source.width, source.height))
            before = source.read(1, window=window)
            after = bed.read(1, window=window)
            mask = geometry_mask([obj.geometry], out_shape=before.shape, transform=source.window_transform(window), invert=True)
            valid = mask & (source.read_masks(1, window=window) > 0)
            changed = valid & (before - after > 1e-6)
            ids = [x.strip() for x in str(obj.graph_reach_ids).split("|") if x.strip()]
            associated = geometry[geometry.reach_id.isin(ids)]
            holds = sorted(set(associated.loc[~associated.geometry_authorized_for_v49e.astype(bool), "authorization_reason"].astype(str)))
            cls = str(obj.final_class)
            requirements = []
            if cls == "UNKNOWN_REVIEW_REQUIRED":
                requirements.append("Identify type/connectivity using field map, imagery or authoritative hydrography; preserve the object meanwhile")
            if cls == "LAKE_RESERVOIR":
                if obj.object_id in curve_by_object:
                    requirements.append("Published ZFW reference retrieved; verify complete reservoir footprint, vertical datum transformation, survey date/sedimentation, spatial bathymetry and operating controls")
                elif obj.object_id in capacity_by_object:
                    requirements.append("Published single-volume engineering reference retrieved; verify footprint identity and obtain full ZFW curve or surveyed bathymetry, datum, date and operating controls")
                else:
                    requirements.append("Reservoir identity, stage-area-volume curve or surveyed bathymetry, vertical datum, observation date and operating controls")
            if cls == "ESTUARY_TIDAL_RIVER":
                requirements.append("Spatial limit of tidal/backwater influence, dated tide/WSE boundary and vertical datum; controlled reach geometry")
            if cls in {"RIVER_STREAM", "CANAL"}:
                requirements.append("Independent cross-sections/depth or defensible hydraulic inversion; bank elevations, discharge and datum")
                if support_index.loc[obj.object_id, "support_state"] == "NO_GRAPH_WITHIN_90M_REVIEW":
                    requirements.append("Verify direction and connection of the supplied OSM edge candidates before adding graph reaches")
                elif support_index.loc[obj.object_id, "support_state"] == "COARSE_GRAPH_ALIGNMENT_REVIEW":
                    requirements.append("An existing graph reach is nearby within 90 m; verify coarse centerline alignment rather than duplicating a branch")
                if str(obj.fixed_water_status) != "CONFIRMED_PERSISTENT":
                    requirements.append("Dated water observations corroborating persistence; non-detection alone does not establish absence")
            if cls == "WETLAND_FLOODPLAIN_WATER":
                requirements.append("Seasonal storage extent and micro-topography; preserve hydraulic storage")
            accepted_ids = sorted(set(ids) & authorized)
            relative_locations = locations[locations.object_id_candidate.eq(obj.object_id)]
            rows.append({"object_id": obj.object_id, "final_class": cls, "fixed_water_status": obj.fixed_water_status,
                         "current_osm_names": obj.current_osm_names, "area_km2": float(obj.area_km2),
                         "inventory_water_cells": int(valid.sum()), "actually_edited_cells": int(changed.sum()),
                         "edited_area_km2": float(changed.sum()) * abs(source.transform.a * source.transform.e) / 1e6,
                         "edited_water_pixel_pct": 100. * changed.sum() / max(1, valid.sum()),
                         "accepted_reach_ids": " | ".join(accepted_ids),
                         "geometry_hold_reasons": " | ".join(holds),
                         "graph_support_state": support_index.loc[obj.object_id, "support_state"],
                         "graph_90m_reach_ids": support_index.loc[obj.object_id, "graph_90m_reach_ids"],
                         "published_zfw_reference": curve_by_object.get(obj.object_id, ""),
                         "published_single_capacity_reference": obj.object_id in capacity_by_object,
                         "published_relative_map_location_count": len(relative_locations),
                         "relative_location_min_polygon_distance_m": float(relative_locations.relative_point_to_candidate_polygon_distance_m.min()) if len(relative_locations) else None,
                         "full_reservoir_footprint_verified": False,
                         "required_evidence": " | ".join(requirements),
                         "hydraulic_geometry_complete": False, "geometry": obj.geometry})
            if history is not None:
                month = november.loc[obj.object_id]
                year = annual.loc[obj.object_id]
                rows[-1].update(november_2021_observed_native_cells=int(month.observed_cells),
                                november_2021_no_observation_native_cells=int(month.no_observation_cells),
                                november_2021_water_fraction_of_observed=float(month.water_fraction_of_observed) if pd.notna(month.water_fraction_of_observed) else None,
                                median_2021_observed_months=float(year.median_observed_months),
                                median_2021_water_observed_months=float(year.median_water_observed_months),
                                monthly_water_is_not_daily_event_shoreline=True)
    coverage = gpd.GeoDataFrame(rows, geometry="geometry", crs=objects.crs)
    coverage.drop(columns="geometry").to_csv(output / "V49_object_evidence_and_pixel_coverage.csv", index=False, encoding="utf-8-sig")
    gpkg = output / "V49_remaining_evidence.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    coverage.to_file(gpkg, layer="object_evidence_requirements", driver="GPKG")
    lines = gpd.read_file(evidence_path, layer="geofabrik_current_waterways")
    candidate_rows = []
    candidate_ids = set(support.loc[support.support_state.isin(["NO_GRAPH_WITHIN_90M_REVIEW", "COARSE_GRAPH_ALIGNMENT_REVIEW"]), "object_id"])
    for _, obj in objects[objects.object_id.isin(candidate_ids)].iterrows():
        nearby = lines[lines.geometry.intersects(obj.geometry.buffer(90.)) & lines.waterway.isin(["river", "stream", "canal"])]
        for _, line in nearby.iterrows():
            clipped = line.geometry.intersection(obj.geometry.buffer(90.))
            parts = list(clipped.geoms) if hasattr(clipped, "geoms") else [clipped]
            for part in parts:
                if not isinstance(part, LineString) or part.length < 30.:
                    continue
                candidate_rows.append({"object_id": obj.object_id, "osm_id": str(line.osm_id), "name": line.get("name", ""),
                                       "waterway": line.waterway, "length_m": float(part.length),
                                       "minimum_distance_to_accepted_graph_m": float(graph.distance(part).min()),
                                       "direction_status": "UNVERIFIED", "connectivity_status": "UNVERIFIED",
                                       "candidate_purpose": support_index.loc[obj.object_id, "support_state"],
                                       "accepted_into_graph": False, "source_sha256": sha256_file(evidence_path), "geometry": part})
    candidates = gpd.GeoDataFrame(candidate_rows, geometry="geometry", crs=objects.crs)
    if len(candidates):
        candidates.to_file(gpkg, layer="missing_graph_osm_candidates", driver="GPKG")
        candidates.drop(columns="geometry").to_csv(output / "V49_missing_graph_osm_candidates.csv", index=False, encoding="utf-8-sig")
    nodes = gpd.read_file(DEFAULT_GRAPH, layer="nodes")
    junction_rows = []
    with rasterio.open(revision_dir / "E" / "V49_E_hydraulic_bed.tif") as bed:
        def sample(point):
            value = float(next(bed.sample([(point.x, point.y)]))[0])
            return value if np.isfinite(value) and value != bed.nodata else None
        for _, node in nodes[nodes.node_type.eq("CONFLUENCE")].iterrows():
            incoming = graph[graph.to_node.eq(node.node_id)]
            outgoing = graph[graph.from_node.eq(node.node_id)]
            for _, inc in incoming.iterrows():
                for _, out in outgoing.iterrows():
                    up = sample(Point(inc.geometry.coords[-1]))
                    down = sample(Point(out.geometry.coords[0]))
                    both = inc.reach_id in authorized and out.reach_id in authorized
                    junction_rows.append({"node_id": node.node_id, "incoming_reach_id": inc.reach_id,
                                          "outgoing_reach_id": out.reach_id, "sampled_incoming_endpoint_bed_m": up,
                                          "sampled_outgoing_endpoint_bed_m": down,
                                          "actual_raster_endpoint_rise_m": down - up if up is not None and down is not None else None,
                                          "both_incident_reaches_evidence_authorized": both,
                                          "physical_ordering_certified": False,
                                          "reason": "Raster samples are real; remaining channel/control/survey evidence is needed for physical bed-order acceptance"})
    pd.DataFrame(junction_rows).to_csv(output / "V49_actual_raster_confluence_samples.csv", index=False, encoding="utf-8-sig")
    summary = {"schema_version": "V49-evidence-dossier-1", "inland_objects_documented": len(coverage),
               "objects_with_any_edited_cells": int((coverage.actually_edited_cells > 0).sum()),
               "actual_edited_water_cells": int(coverage.actually_edited_cells.sum()),
               "actual_edited_water_area_km2": float(coverage.edited_area_km2.sum()),
               "unknown_types": int(coverage.final_class.eq("UNKNOWN_REVIEW_REQUIRED").sum()),
               "objects_with_published_zfw_reference": int(coverage.published_zfw_reference.ne("").sum()),
               "objects_with_single_capacity_reference": int(coverage.published_single_capacity_reference.sum()),
               "published_relative_location_context": location_context,
               "missing_graph_candidate_edges": len(candidates),
               "channel_objects_without_graph_within_90m": support.loc[support.support_state.eq("NO_GRAPH_WITHIN_90M_REVIEW"), "object_id"].tolist(),
               "coarse_graph_alignment_review_objects": support.loc[support.support_state.eq("COARSE_GRAPH_ALIGNMENT_REVIEW"), "object_id"].tolist(),
               "actual_raster_confluence_pairs": len(junction_rows),
               "hydraulic_geometry_complete": False,
               "pixel_coverage_is_not_depth_validation": True,
               "revision_dir": str(revision_dir.resolve()),
               "water_history_2021_readback": history,
               "water_history_2021_manifest_sha256": sha256_file(history_path) if history is not None else None,
               "source_evidence_sha256": sha256_file(evidence_path),
               "source_e_bed_sha256": sha256_file(revision_dir / "E" / "V49_E_hydraulic_bed.tif")}
    (output / "V49_remaining_evidence_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision-dir", type=Path, default=R2)
    args = parser.parse_args()
    build(args.revision_dir)
