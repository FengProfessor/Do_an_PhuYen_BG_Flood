"""V49-C.1 fixed-water evidence audit.

Cross-check every V49-C water object against JRC GSW v1.5 (1984-2024
aggregates plus 2024 seasonality), current Geofabrik/OSM, and the V49-B
hydrographic graph.  This phase is evidence-only and must never modify DEM.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds


PROJECT_DIR = Path(r"D:\VTP\River_Bathymetry_Project")
SOURCE_DIR = Path(r"D:\VTP\V49_C1_sources_20261012")
DEFAULT_CLASSIFIED = PROJECT_DIR / "V49_C_20261012" / "V49_waterbody_classification.gpkg"
DEFAULT_GRAPH = PROJECT_DIR / "V49_B_20261012" / "V49_hydrograph.gpkg"
DEFAULT_GEOMETRY = PROJECT_DIR / "V49_D_20261012" / "V49_reach_geometry.gpkg"
DEFAULT_DEM = Path(r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif")
DEFAULT_PBF = SOURCE_DIR / "geofabrik_vietnam_20261011.osm.pbf"
DEFAULT_PBF_MD5 = SOURCE_DIR / "geofabrik_vietnam_20261011.osm.pbf.md5"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "V49_C1_20261012"
EXPECTED_DEM_SHA256 = "0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508"

JRC_PATHS = {
    key: SOURCE_DIR / f"JRC_{key}_100E_20N_v1_5_2024.tif"
    for key in ("occurrence", "recurrence", "seasonality", "transitions")
}

VALID_STATUSES = {
    "CONFIRMED_PERSISTENT",
    "SEASONAL_DYNAMIC",
    "CONFLICT_REVIEW_REQUIRED",
    "INSUFFICIENT_EVIDENCE",
}


@dataclass(frozen=True)
class AuditConfig:
    line_buffer_m: float = 30.0
    min_current_osm_channel_m: float = 150.0
    min_graph_support_m: float = 300.0
    strong_occurrence_p50: float = 50.0
    strong_recurrence_p50: float = 80.0
    moderate_occurrence_p50: float = 30.0
    permanent_2024_fraction: float = 0.20
    dominant_osm_polygon_overlap_fraction: float = 0.25


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def md5_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def parse_other_tags(value: object) -> dict[str, str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return {}
    text = str(value)
    return {k: v for k, v in re.findall(r'"([^"]+)"=>"([^"]*)"', text)}


def _raster_values(dataset: rasterio.io.DatasetReader, geometry_4326) -> np.ndarray:
    raw = from_bounds(*geometry_4326.bounds, transform=dataset.transform)
    col0 = max(0, int(math.floor(raw.col_off)))
    row0 = max(0, int(math.floor(raw.row_off)))
    col1 = min(dataset.width, int(math.ceil(raw.col_off + raw.width)))
    row1 = min(dataset.height, int(math.ceil(raw.row_off + raw.height)))
    if col1 <= col0 or row1 <= row0:
        return np.array([], dtype=float)
    window = rasterio.windows.Window(col0, row0, col1 - col0, row1 - row0)
    data = dataset.read(1, window=window)
    transform = dataset.window_transform(window)
    inside = geometry_mask(
        [geometry_4326.__geo_interface__],
        out_shape=data.shape,
        transform=transform,
        invert=True,
        all_touched=False,
    )
    values = data[inside]
    if dataset.nodata is not None:
        values = values[values != dataset.nodata]
    if np.issubdtype(values.dtype, np.floating):
        values = values[np.isfinite(values)]
    return values.astype(float, copy=False)


def jrc_metrics(datasets: dict[str, rasterio.io.DatasetReader], geometry_4326) -> dict[str, float | int | str]:
    out: dict[str, float | int | str] = {}
    arrays: dict[str, np.ndarray] = {}
    for key, ds in datasets.items():
        values = _raster_values(ds, geometry_4326)
        arrays[key] = values
        out[f"jrc_{key}_valid_cells"] = int(values.size)
        out[f"jrc_{key}_mean"] = float(np.mean(values)) if values.size else math.nan
        out[f"jrc_{key}_p50"] = float(np.median(values)) if values.size else math.nan

    seasonality = arrays["seasonality"]
    if seasonality.size:
        out["jrc_2024_permanent_fraction"] = float(np.mean(seasonality == 12))
        out["jrc_2024_seasonal_fraction"] = float(np.mean((seasonality >= 1) & (seasonality <= 11)))
        out["jrc_2024_dry_fraction"] = float(np.mean(seasonality == 0))
    else:
        out["jrc_2024_permanent_fraction"] = math.nan
        out["jrc_2024_seasonal_fraction"] = math.nan
        out["jrc_2024_dry_fraction"] = math.nan

    transitions = arrays["transitions"]
    if transitions.size:
        counts = Counter(int(v) for v in transitions)
        out["jrc_transition_mode"] = int(counts.most_common(1)[0][0])
        out["jrc_transition_histogram"] = json.dumps(dict(sorted(counts.items())), ensure_ascii=False)
    else:
        out["jrc_transition_mode"] = -1
        out["jrc_transition_histogram"] = "{}"
    return out


def read_current_osm(pbf_path: Path, bbox_4326: tuple[float, float, float, float], target_crs):
    lines = pyogrio.read_dataframe(pbf_path, layer="lines", bbox=bbox_4326)
    lines = lines[lines.waterway.notna() | lines.barrier.notna()].copy()
    line_tags = lines.other_tags.apply(parse_other_tags)
    lines["intermittent"] = line_tags.apply(lambda d: d.get("intermittent", ""))
    lines["tidal"] = line_tags.apply(lambda d: d.get("tidal", ""))
    lines = lines.to_crs(target_crs)

    polygons = pyogrio.read_dataframe(pbf_path, layer="multipolygons", bbox=bbox_4326)
    poly_tags = polygons.other_tags.apply(parse_other_tags)
    polygons["water"] = poly_tags.apply(lambda d: d.get("water", ""))
    polygons["intermittent"] = poly_tags.apply(lambda d: d.get("intermittent", ""))
    polygons["tidal"] = poly_tags.apply(lambda d: d.get("tidal", ""))
    mask = (
        polygons.natural.fillna("").eq("water")
        | polygons.landuse.fillna("").isin(["reservoir", "basin"])
        | polygons.water.ne("")
    )
    polygons = polygons[mask].copy().to_crs(target_crs)
    return lines, polygons


def osm_metrics(lines: gpd.GeoDataFrame, polygons: gpd.GeoDataFrame, geometry, cfg: AuditConfig) -> dict:
    target = geometry.buffer(cfg.line_buffer_m)
    hits = lines[lines.geometry.intersects(target)]
    lengths: Counter[str] = Counter()
    names: set[str] = set()
    intermittent = False
    tidal = False
    for _, row in hits.iterrows():
        overlap = row.geometry.intersection(target)
        length = float(overlap.length)
        if length <= 0:
            continue
        kind = str(row.waterway or row.barrier or "unknown")
        lengths[kind] += length
        if pd.notna(row.get("name")) and str(row.get("name")).strip():
            names.add(str(row.get("name")).strip())
        intermittent = intermittent or str(row.get("intermittent", "")).lower() in {"yes", "true", "1"}
        tidal = tidal or str(row.get("tidal", "")).lower() in {"yes", "true", "1"}

    phits = polygons[polygons.geometry.intersects(geometry)]
    area_by_type: Counter[str] = Counter()
    pnames: set[str] = set()
    pintermittent = False
    ptidal = False
    for _, row in phits.iterrows():
        overlap = row.geometry.intersection(geometry)
        area = float(overlap.area)
        if area <= 0:
            continue
        semantic = str(row.get("water", "") or row.get("landuse", "") or row.get("natural", "") or "water")
        area_by_type[semantic] += area
        if pd.notna(row.get("name")) and str(row.get("name")).strip():
            pnames.add(str(row.get("name")).strip())
        pintermittent = pintermittent or str(row.get("intermittent", "")).lower() in {"yes", "true", "1"}
        ptidal = ptidal or str(row.get("tidal", "")).lower() in {"yes", "true", "1"}

    geom_area = max(float(geometry.area), 1.0)
    dominant_type, dominant_area = ("", 0.0)
    if area_by_type:
        dominant_type, dominant_area = area_by_type.most_common(1)[0]
    channel_m = sum(lengths.get(k, 0.0) for k in ("river", "stream", "canal", "drain", "ditch", "tidal_channel"))
    return {
        "current_osm_channel_m": float(channel_m),
        "current_osm_river_m": float(lengths.get("river", 0.0)),
        "current_osm_stream_m": float(lengths.get("stream", 0.0)),
        "current_osm_canal_m": float(lengths.get("canal", 0.0)),
        "current_osm_dam_weir_m": float(lengths.get("dam", 0.0) + lengths.get("weir", 0.0)),
        "current_osm_names": " | ".join(sorted(names | pnames)),
        "current_osm_intermittent": bool(intermittent or pintermittent),
        "current_osm_tidal": bool(tidal or ptidal),
        "current_osm_polygon_dominant_type": dominant_type,
        "current_osm_polygon_overlap_fraction": float(dominant_area / geom_area),
        "current_osm_polygon_types": json.dumps({k: round(v / geom_area, 6) for k, v in area_by_type.items()}, ensure_ascii=False),
    }


def decide_fixed_water_status(e: dict, cfg: AuditConfig | None = None) -> tuple[str, str]:
    cfg = cfg or AuditConfig()
    occ = float(e.get("jrc_occurrence_p50", math.nan))
    rec = float(e.get("jrc_recurrence_p50", math.nan))
    perm = float(e.get("jrc_2024_permanent_fraction", math.nan))
    seasonal = float(e.get("jrc_2024_seasonal_fraction", math.nan))
    graph_m = float(e.get("graph_length_m", 0.0) or 0.0)
    osm_channel_m = float(e.get("current_osm_channel_m", 0.0) or 0.0)
    final_class = str(e.get("final_class", ""))
    poly_type = str(e.get("current_osm_polygon_dominant_type", ""))
    poly_frac = float(e.get("current_osm_polygon_overlap_fraction", 0.0) or 0.0)
    intermittent = bool(e.get("current_osm_intermittent", False))

    # Treat persistence as a feature-level conclusion, not a claim that every
    # pixel is wet in every observation.  A channel can have moderate long-term
    # occurrence because its wetted width migrates within a 30 m pixel while
    # recurrence remains high.  Strong recent permanent-water coverage plus
    # high recurrence therefore also counts as strong JRC support.
    strong_jrc = bool(
        math.isfinite(occ)
        and math.isfinite(rec)
        and rec >= cfg.strong_recurrence_p50
        and (
            (occ >= cfg.strong_occurrence_p50 and (not math.isfinite(perm) or perm >= cfg.permanent_2024_fraction))
            or (occ >= cfg.moderate_occurrence_p50 and math.isfinite(perm) and perm >= 0.50)
        )
    )
    recurring_jrc = (
        math.isfinite(occ) and math.isfinite(rec)
        and occ >= cfg.moderate_occurrence_p50 and rec >= cfg.strong_recurrence_p50
    )
    topology = graph_m >= cfg.min_graph_support_m
    current_channel = osm_channel_m >= cfg.min_current_osm_channel_m
    reservoir_semantic = poly_type in {"reservoir", "lake", "pond"} and poly_frac >= cfg.dominant_osm_polygon_overlap_fraction

    if final_class == "OCEAN":
        return "CONFIRMED_PERSISTENT", "Marine object retained as persistent boundary water; never eligible for river carving."
    if final_class == "LAKE_RESERVOIR":
        if strong_jrc:
            return "CONFIRMED_PERSISTENT", "Standing-water type and independent JRC persistence support a persistent feature; no channel carving is authorized."
        if math.isfinite(rec) and rec >= cfg.strong_recurrence_p50 and math.isfinite(seasonal) and seasonal > perm:
            return "SEASONAL_DYNAMIC", "Standing-water type is supported but recent JRC seasonal coverage exceeds permanent coverage."
        return "INSUFFICIENT_EVIDENCE", "Standing-water semantics establish type, not persistence; independent temporal water evidence remains insufficient."
    if final_class == "WETLAND_FLOODPLAIN_WATER":
        return "SEASONAL_DYNAMIC", "Wetland/floodplain water remains dynamic storage and is excluded from channel carving."
    if final_class == "UNKNOWN_REVIEW_REQUIRED":
        if strong_jrc and (current_channel or topology or reservoir_semantic):
            return "CONFLICT_REVIEW_REQUIRED", "Strong water evidence exists but V49-C type remains unresolved; manual type review is required."
        return "INSUFFICIENT_EVIDENCE", "V49-C is unresolved and independent evidence is insufficient for destructive treatment."
    if final_class == "ESTUARY_TIDAL_RIVER":
        return "CONFLICT_REVIEW_REQUIRED", "Tidal/estuarine water is real but requires tidal boundary treatment, not fixed inland carving."
    if final_class in {"RIVER_STREAM", "CANAL"}:
        if reservoir_semantic:
            return "CONFLICT_REVIEW_REQUIRED", "Current OSM standing-water polygon substantially overlaps a channel-class object."
        if intermittent and not strong_jrc:
            return "SEASONAL_DYNAMIC", "Current OSM marks intermittent water and JRC does not independently establish strong persistence."
        if strong_jrc and (current_channel or topology):
            return "CONFIRMED_PERSISTENT", "Long-term JRC persistence plus independent current OSM/topology support confirms a persistent channel feature."
        if recurring_jrc and current_channel and topology:
            return "CONFIRMED_PERSISTENT", "Recurring JRC water plus both current OSM and directed topology confirms a persistent channel feature despite variable wetted width."
        if recurring_jrc and (current_channel or topology):
            if math.isfinite(perm) and math.isfinite(seasonal) and seasonal > perm:
                return "SEASONAL_DYNAMIC", "Water recurs across years but recent seasonality is stronger than permanent-water coverage."
            return "INSUFFICIENT_EVIDENCE", "Only one independent channel evidence family supports the recurring JRC signal."
        return "INSUFFICIENT_EVIDENCE", "Persistent channel evidence is not independently corroborated."
    return "INSUFFICIENT_EVIDENCE", "No fixed-water decision rule applies."


def _safe_bool(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes"}


def build_audit(
    classified_path: Path = DEFAULT_CLASSIFIED,
    graph_path: Path = DEFAULT_GRAPH,
    geometry_path: Path = DEFAULT_GEOMETRY,
    pbf_path: Path = DEFAULT_PBF,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict:
    cfg = AuditConfig()
    output_dir.mkdir(parents=True, exist_ok=True)
    dem_hash_before = sha256_file(DEFAULT_DEM)
    objects = gpd.read_file(classified_path, layer="classified_objects")
    reaches = gpd.read_file(graph_path, layer="reaches")
    geom_reaches = gpd.read_file(geometry_path, layer="reach_geometry")
    bbox_4326 = tuple(objects.to_crs(4326).total_bounds)
    current_lines, current_polygons = read_current_osm(pbf_path, bbox_4326, objects.crs)

    datasets = {key: rasterio.open(path) for key, path in JRC_PATHS.items()}
    try:
        objects4326 = objects.to_crs(4326)
        records: list[dict] = []
        for idx, row in objects.iterrows():
            evidence = row.drop(labels=["geometry"]).to_dict()
            evidence.update(jrc_metrics(datasets, objects4326.loc[idx].geometry))
            evidence.update(osm_metrics(current_lines, current_polygons, row.geometry, cfg))
            status, reason = decide_fixed_water_status(evidence, cfg)
            evidence["fixed_water_status"] = status
            evidence["fixed_water_reason"] = reason
            evidence["automatic_carving_allowed_by_c1"] = bool(
                status == "CONFIRMED_PERSISTENT"
                and str(row.final_class) in {"RIVER_STREAM", "CANAL"}
            )
            records.append(evidence)
    finally:
        for ds in datasets.values():
            ds.close()

    audited = gpd.GeoDataFrame(records, geometry=objects.geometry.values, crs=objects.crs)

    # V49-C.1 can only narrow V49-D authorization. It can never promote a new reach.
    reach_rows: list[dict] = []
    obj_status = audited.set_index("object_id")["fixed_water_status"].to_dict()
    for _, row in geom_reaches.iterrows():
        d_authorized = _safe_bool(row.get("geometry_authorized_for_v49e", False))
        ids = [x.strip() for x in str(row.get("v49c_object_ids", "")).split("|") if x.strip()]
        statuses = [obj_status.get(x, "INSUFFICIENT_EVIDENCE") for x in ids]
        all_confirmed = bool(ids) and all(s == "CONFIRMED_PERSISTENT" for s in statuses)
        c1_authorized = bool(d_authorized and all_confirmed)
        reason = (
            "V49-D authorized and every associated V49-C object is CONFIRMED_PERSISTENT in C.1."
            if c1_authorized
            else "Held: C.1 never promotes V49-D review rows and requires all associated objects to be CONFIRMED_PERSISTENT."
        )
        reach_rows.append(
            {
                "reach_id": str(row.reach_id),
                "v49d_authorized": d_authorized,
                "v49c_object_ids": " | ".join(ids),
                "c1_object_statuses": " | ".join(statuses),
                "c1_authorized_for_v49e": c1_authorized,
                "c1_authorization_reason": reason,
                "geometry": row.geometry,
            }
        )
    reach_gate = gpd.GeoDataFrame(reach_rows, geometry="geometry", crs=geom_reaches.crs)

    # Explicit manual-review queue.  Every conflict/insufficient object blocks
    # V49-E until it is reviewed, and prior V49-D authorization is surfaced so
    # a downgrade cannot be missed during handoff.
    review_queue = audited.loc[
        audited.fixed_water_status.isin({"CONFLICT_REVIEW_REQUIRED", "INSUFFICIENT_EVIDENCE"})
    ].drop(columns="geometry").copy()
    v49d_authorized_reaches = set(
        reach_gate.loc[reach_gate.v49d_authorized, "reach_id"].astype(str)
    )

    def _row_reach_ids(value: object) -> list[str]:
        if pd.isna(value) or not str(value).strip():
            return []
        return [x.strip() for x in str(value).split("|") if x.strip()]

    def _row_overlap(row: pd.Series) -> float:
        value = row.get("current_osm_polygon_overlap_fraction", 0.0)
        return 0.0 if pd.isna(value) else float(value)

    def _row_polygon_type(row: pd.Series) -> str:
        value = row.get("current_osm_polygon_dominant_type", "")
        return "" if pd.isna(value) else str(value).lower()

    def _review_priority(row: pd.Series) -> int:
        standing_water_conflict = (
            str(row.get("final_class", "")) == "RIVER_STREAM"
            and _row_polygon_type(row) in {"lake", "reservoir", "lagoon"}
            and _row_overlap(row) >= 0.5
        )
        if standing_water_conflict:
            return 1
        if str(row.get("fixed_water_status", "")) == "CONFLICT_REVIEW_REQUIRED":
            return 2
        if str(row.get("final_class", "")) == "RIVER_STREAM" or _row_reach_ids(row.get("graph_reach_ids")):
            return 3
        return 4

    def _review_issue(row: pd.Series) -> str:
        standing_water_conflict = (
            str(row.get("final_class", "")) == "RIVER_STREAM"
            and _row_polygon_type(row) in {"lake", "reservoir", "lagoon"}
            and _row_overlap(row) >= 0.5
        )
        if standing_water_conflict:
            return "V49C_CHANNEL_VS_OSM_STANDING_WATER"
        if str(row.get("final_class", "")) == "ESTUARY_TIDAL_RIVER":
            return "TIDAL_BOUNDARY_TREATMENT_REQUIRED"
        if str(row.get("fixed_water_status", "")) == "CONFLICT_REVIEW_REQUIRED":
            return "EVIDENCE_CONFLICT_REQUIRES_MANUAL_CLASS_REVIEW"
        if str(row.get("final_class", "")) == "RIVER_STREAM":
            return "CHANNEL_EVIDENCE_INSUFFICIENT"
        return "CLASS_OR_PERSISTENCE_EVIDENCE_INSUFFICIENT"

    review_queue["review_priority"] = review_queue.apply(_review_priority, axis=1)
    review_queue["review_issue"] = review_queue.apply(_review_issue, axis=1)
    review_queue["affected_v49d_authorized_reaches"] = review_queue["graph_reach_ids"].apply(
        lambda value: " | ".join(
            reach_id for reach_id in _row_reach_ids(value)
            if reach_id in v49d_authorized_reaches
        )
    )
    review_queue["blocks_prior_v49d_authorization"] = review_queue[
        "affected_v49d_authorized_reaches"
    ].str.len().gt(0)
    review_queue["blocks_v49e"] = True
    review_queue = review_queue[
        [
            "review_priority", "object_id", "final_class", "subtype",
            "fixed_water_status", "review_issue", "current_osm_names",
            "current_osm_polygon_dominant_type", "current_osm_polygon_overlap_fraction",
            "current_osm_dam_weir_m", "current_osm_intermittent", "current_osm_tidal",
            "jrc_occurrence_p50", "jrc_recurrence_p50", "jrc_2024_permanent_fraction",
            "jrc_2024_seasonal_fraction", "graph_reach_ids",
            "affected_v49d_authorized_reaches", "blocks_prior_v49d_authorization",
            "blocks_v49e", "fixed_water_reason",
        ]
    ].sort_values(
        ["review_priority", "current_osm_polygon_overlap_fraction", "object_id"],
        ascending=[True, False, True],
    )

    gpkg = output_dir / "V49_C1_fixed_water_evidence.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    audited.to_file(gpkg, layer="audited_water_objects", driver="GPKG")
    reach_gate.to_file(gpkg, layer="v49e_reach_gate", driver="GPKG")
    current_lines.to_file(gpkg, layer="geofabrik_current_waterways", driver="GPKG")
    current_polygons.to_file(gpkg, layer="geofabrik_current_water_polygons", driver="GPKG")
    audited.drop(columns="geometry").to_csv(output_dir / "V49_C1_fixed_water_audit.csv", index=False, encoding="utf-8-sig")
    reach_gate.drop(columns="geometry").to_csv(output_dir / "V49_C1_v49e_reach_gate.csv", index=False, encoding="utf-8-sig")
    review_queue.to_csv(output_dir / "V49_C1_review_queue.csv", index=False, encoding="utf-8-sig")

    pbf_md5_expected = DEFAULT_PBF_MD5.read_text(encoding="utf-8").split()[0].lower()
    pbf_md5_actual = md5_file(pbf_path)
    dem_hash_after = sha256_file(DEFAULT_DEM)
    counts = audited.fixed_water_status.value_counts().to_dict()
    authorized_d = reach_gate[reach_gate.v49d_authorized]
    authorized_c1 = reach_gate[reach_gate.c1_authorized_for_v49e]
    review_priority_counts = review_queue.review_priority.value_counts().sort_index().to_dict()
    source_hashes = {key: sha256_file(path) for key, path in JRC_PATHS.items()}
    source_hashes["geofabrik_pbf_sha256"] = sha256_file(pbf_path)
    source_hashes["dem_sha256_before"] = dem_hash_before
    source_hashes["dem_sha256_after"] = dem_hash_after
    audit = {
        "phase": "V49-C.1",
        "object_count": int(len(audited)),
        "status_counts": {str(k): int(v) for k, v in counts.items()},
        "current_geofabrik_waterway_features": int(len(current_lines)),
        "current_geofabrik_water_polygons": int(len(current_polygons)),
        "geofabrik_snapshot": "2026-10-11",
        "geofabrik_md5_expected": pbf_md5_expected,
        "geofabrik_md5_actual": pbf_md5_actual,
        "geofabrik_md5_match": pbf_md5_expected == pbf_md5_actual,
        "jrc_version": "GSW v1.5 / 2024 release",
        "jrc_long_term_period": "1984-2024 for aggregated occurrence/recurrence/transitions",
        "jrc_seasonality_scope_note": "Downloaded seasonality_..._2024 layer is recent-year context and is not treated as a 1984-2024 aggregate.",
        "jrc_absence_rule": "Lack of JRC detection alone never proves absence of a river; narrow/obscured channels require OSM/topology corroboration.",
        "v49d_authorized_count": int(len(authorized_d)),
        "c1_authorized_for_v49e_count": int(len(authorized_c1)),
        "c1_authorized_reach_ids": sorted(authorized_c1.reach_id.astype(str).tolist()),
        "c1_never_promotes_v49d_review_rows": True,
        "review_queue_count": int(len(review_queue)),
        "review_priority_counts": {str(k): int(v) for k, v in review_priority_counts.items()},
        "dem_modified_pixels_in_c1": 0,
        "dem_unchanged": dem_hash_before == dem_hash_after == EXPECTED_DEM_SHA256,
        "source_hashes": source_hashes,
    }
    (output_dir / "V49_C1_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    result = build_audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
