"""Compare primary relative map locations to current water polygons.

This resolves source/footprint context only. It does not certify a survey
location, choose an operating level, or reconstruct any reservoir bed.
"""
from pathlib import Path
import json
import geopandas as gpd
import pandas as pd
import rasterio
from pyproj import CRS
from pyproj.transformer import TransformerGroup
from shapely.geometry import Point, box

from v49_estimate_reach_geometry import DEFAULT_DEM
from v49_ingest_public_evidence import CURVES, storage_at_level
from v49_runtime_observer import atomic_json
from v49_synthesize_hydraulic_bed import sha256_file
from v49_validate_hydraulic_validation import inspect_published_evidence

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "V49_PUBLIC_EVIDENCE_20261013"
OUTPUT = ROOT / "V49_R2_20261013" / "REMAINING_EVIDENCE"


def audit_locations():
    register_path = EVIDENCE / "V49_PUBLIC_EVIDENCE_REGISTER.json"
    if not inspect_published_evidence(register_path)["available"]:
        raise ValueError("Published evidence source or output integrity failed")
    object_path = ROOT / "V49_R2_20261013" / "C1" / "V49_C1_fixed_water_evidence.gpkg"
    objects = gpd.read_file(object_path, layer="audited_water_objects").set_index("object_id")
    locations = pd.read_csv(EVIDENCE / "published_relative_geographic_locations.csv")
    operations = TransformerGroup(CRS.from_epsg(4756), objects.crs, always_xy=True, allow_ballpark=False)
    if not operations.best_available or not operations.transformers:
        raise ValueError("A defined VN-2000 datum transformation is required")
    transform = operations.transformers[0]
    with rasterio.open(DEFAULT_DEM) as ds:
        if ds.crs != objects.crs or not ds.crs.is_projected:
            raise ValueError("Relative-location comparison requires the model projected CRS")
        domain = box(*ds.bounds)
    rows, points = [], []
    for _, location in locations.iterrows():
        oid = location.inventory_object_id_candidate
        if oid not in objects.index:
            raise ValueError(f"Unknown water-object candidate {oid}")
        obj = objects.loc[oid]
        x, y = transform.transform(location.longitude_vn2000_degrees, location.latitude_vn2000_degrees)
        point = Point(x,y)
        curve_key = next((key for key, curve in CURVES.items() if curve["object_id"] == oid), None)
        item = dict(object_id_candidate=oid, name_as_published=location.name_as_published,
                    source_pdf_page_1_based=int(location.source_pdf_page_1_based),
                    source_sha256=location.source_sha256,
                    relative_point_to_candidate_polygon_distance_m=float(point.distance(obj.geometry)),
                    relative_point_inside_candidate=bool(obj.geometry.covers(point)),
                    relative_point_inside_model_domain=bool(domain.covers(point)),
                    object_link_semantics=location.object_link_semantics,
                    inventory_polygon_area_km2=float(obj.geometry.area/1e6),
                    inventory_polygon_distance_to_model_edge_m=float(obj.geometry.distance(domain.boundary)),
                    inventory_polygon_intersects_model_edge=bool(obj.geometry.intersects(domain.boundary)),
                    coordinate_status="RELATIVE_MAP_LOCATION_NOT_SURVEY_VERIFIED",
                    full_reservoir_footprint_verified=False, storage_constraint_authorized=False,
                    hydraulic_bed_geometry_authorized=False)
        if curve_key:
            design_z = 105. if curve_key == "SONG_BA_HA" else 209.
            design = storage_at_level(CURVES[curve_key],design_z)
            item.update(published_reference_level_m=design_z,
                        published_reference_area_km2=design["surface_area_km2"],
                        inventory_to_design_area_ratio=float(obj.geometry.area/1e6/design["surface_area_km2"]),
                        design_level_area_method=design["interpolation"],
                        area_comparison_is_footprint_completeness_test=False)
        rows.append(item);points.append(point)
    OUTPUT.mkdir(exist_ok=True)
    table_path = OUTPUT / "V49_published_location_and_footprint_context.csv"
    pd.DataFrame(rows).to_csv(table_path,index=False,encoding="utf-8-sig")
    spatial_path = OUTPUT / "V49_published_relative_locations.gpkg"
    gpd.GeoDataFrame(rows,geometry=points,crs=objects.crs).to_file(
        spatial_path,layer="relative_map_location_context",driver="GPKG",mode="w")
    report = {"schema_version":"V49-relative-location-context-1", "location_count":len(rows),
              "source_register":str(register_path),"source_register_sha256":sha256_file(register_path),
              "object_source":str(object_path),"object_source_sha256":sha256_file(object_path),
              "table_path":str(table_path),"table_sha256":sha256_file(table_path),
              "spatial_path":str(spatial_path),"spatial_sha256":sha256_file(spatial_path),
              "horizontal_transform":transform.description,"horizontal_transform_pipeline":transform.to_proj4(),
              "epsg_operation_accuracy_m":transform.accuracy,"catalogue_location_accuracy_m":None,
              "limitations":"1:25000 relative feature centres are not gauge or survey positions. Area at a design level is not a completeness test for a polygon from another date/level. Boundary intersection flags domain context; full reservoir footprint, datum, sedimentation and operation remain unverified.",
              "storage_constraint_authorized_count":0,"hydraulic_bed_geometry_authorized_count":0,
              "hydraulic_promotion_ready":False}
    atomic_json(OUTPUT / "V49_published_location_context_audit.json",report)
    print(json.dumps({"locations":len(rows),"model_edge_intersecting_object_ids":sorted({r["object_id_candidate"] for r in rows if r["inventory_polygon_intersects_model_edge"]}),
                      "geometry_authorized":0},indent=2))
    return report


def validate_location_context():
    path = OUTPUT / "V49_published_location_context_audit.json"
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        refs = (("source_register", "source_register_sha256"), ("object_source", "object_source_sha256"),
                ("table_path", "table_sha256"), ("spatial_path", "spatial_sha256"))
        integrity = all(Path(report[p]).is_file() and sha256_file(Path(report[p])) == report[s] for p,s in refs)
        table = pd.read_csv(report["table_path"])
        holds = all(table[col].astype(str).str.lower().eq("false").all()
                    for col in ("full_reservoir_footprint_verified", "storage_constraint_authorized", "hydraulic_bed_geometry_authorized"))
        return {"readback_pass":bool(integrity and holds and len(table)==report["location_count"]),
                "location_count":len(table), "geometry_authorized":0,
                "edge_intersecting_object_ids": sorted(set(table.loc[table.inventory_polygon_intersects_model_edge, "object_id_candidate"]))}
    except (OSError, ValueError, KeyError):
        return {"readback_pass":False, "geometry_authorized":0}


if __name__ == "__main__":
    audit_locations()
