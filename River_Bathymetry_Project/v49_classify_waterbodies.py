"""Build the V49-C conservative water-body classification.

V49-C is a classification/evidence phase.  It MUST NOT modify the source DEM.
The classifier combines the V49-A persistent-water inventory, the V49-B
directed hydrograph, a historical OSM waterway snapshot, and the raw ESA
WorldCover class raster that is aligned to the modelling grid.

The decision rules are intentionally conservative: uncertain or conflicting
objects become UNKNOWN_REVIEW_REQUIRED with NO_AUTOMATIC_CARVING.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import fiona
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.patches import Patch
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from shapely.geometry import LineString


PROJECT_DIR = Path(r"D:\VTP\River_Bathymetry_Project")
DEFAULT_INVENTORY = PROJECT_DIR / "V49_A_20261012" / "V49_master_water_inventory.gpkg"
DEFAULT_GRAPH = PROJECT_DIR / "V49_B_20261012" / "V49_hydrograph.gpkg"
DEFAULT_OSM_DIR = Path(r"D:\VTP\V46_inputs\osm_historical_20211125")
DEFAULT_WORLDCOVER = Path(r"D:\VTP\05-Du-lieu-GIS\PhuYen_manning_30m.tif")
DEFAULT_DEM = Path(r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif")
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "V49_C_20261012"

EXPECTED_DEM_SHA256 = "0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508"

FINAL_CLASSES = (
    "RIVER_STREAM",
    "CANAL",
    "LAKE_RESERVOIR",
    "WETLAND_FLOODPLAIN_WATER",
    "ESTUARY_TIDAL_RIVER",
    "OCEAN",
    "UNKNOWN_REVIEW_REQUIRED",
)

TREATMENT_BY_CLASS = {
    "RIVER_STREAM": (
        "REACH_SCALE_BATHYMETRY",
        "Estimate channel geometry at reach scale in V49-D/E; do not trench the full water polygon.",
    ),
    "CANAL": (
        "ENGINEERED_CHANNEL_GEOMETRY",
        "Use constrained/engineered channel geometry only after direction, connectivity and function are verified.",
    ),
    "LAKE_RESERVOIR": (
        "STAGE_AREA_VOLUME_OR_BATHYMETRY",
        "Use observed bathymetry or stage-area-volume information; synthetic basin only with explicit uncertainty.",
    ),
    "WETLAND_FLOODPLAIN_WATER": (
        "PRESERVE_STORAGE_NO_RIVER_TRENCH",
        "Preserve storage and micro-topography; never convert the polygon to a river trench.",
    ),
    "ESTUARY_TIDAL_RIVER": (
        "TIDAL_RIVER_WITH_MARINE_BOUNDARY",
        "Combine reach geometry with tidal/marine boundary treatment; do not impose a simple inland monotonic profile.",
    ),
    "OCEAN": (
        "EXTERNAL_BATHYMETRY_OR_BOUNDARY",
        "Use marine boundary/external bathymetry treatment; never apply inland river-depth formula to the ocean polygon.",
    ),
    "UNKNOWN_REVIEW_REQUIRED": (
        "NO_AUTOMATIC_CARVING",
        "Hold unchanged for review until water type, connectivity and hydraulic role are supported by stronger evidence.",
    ),
}

CHANNEL_ELIGIBLE_CLASSES = {"RIVER_STREAM", "CANAL", "ESTUARY_TIDAL_RIVER"}


@dataclass(frozen=True)
class ClassificationConfig:
    evidence_buffer_m: float = 30.0
    estuary_distance_m: float = 750.0
    coastal_ambiguity_distance_m: float = 5000.0
    minimum_line_support_m: float = 200.0
    minimum_graph_support_m: float = 300.0
    lake_min_area_km2: float = 1.0
    lake_min_worldcover_water_fraction: float = 0.40
    lake_max_flow_line_density_km_per_km2: float = 0.85
    wetland_min_fraction: float = 0.20
    wetland_max_flow_support_m: float = 500.0
    canal_min_osm_m: float = 150.0
    canal_dominance_ratio: float = 2.0
    river_min_elongation: float = 1.8
    river_dense_line_km_per_km2: float = 1.20
    broad_water_area_km2: float = 2.0


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def _normalized_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _is_lake_name(names: str) -> bool:
    text = _normalized_text(names)
    return any(token in text for token in ("hồ ", "ho ", "lake", "reservoir"))


def _is_river_name(names: str) -> bool:
    text = _normalized_text(names)
    return any(token in text for token in ("sông ", "song ", "river"))


def _shape_metrics(geometry) -> dict[str, float]:
    area = float(geometry.area)
    perimeter = float(geometry.length)
    compactness = float(4.0 * math.pi * area / (perimeter * perimeter)) if perimeter > 0 else 0.0
    rect = geometry.minimum_rotated_rectangle
    coords = list(rect.exterior.coords)
    sides = [LineString([coords[i], coords[i + 1]]).length for i in range(4)]
    positive = [v for v in sides if v > 1e-9]
    if not positive:
        return {"shape_compactness": compactness, "shape_elongation": 1.0, "shape_major_axis_m": 0.0}
    major = max(positive)
    minor = min(positive)
    return {
        "shape_compactness": compactness,
        "shape_elongation": float(major / minor) if minor > 0 else 999.0,
        "shape_major_axis_m": float(major),
    }


def _way_coords(way: ET.Element, node_lookup: dict[str, tuple[float, float]]) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    for nd in way.findall("nd"):
        if "lon" in nd.attrib and "lat" in nd.attrib:
            coords.append((float(nd.attrib["lon"]), float(nd.attrib["lat"])))
        else:
            ref = nd.attrib.get("ref", "")
            if ref in node_lookup:
                coords.append(node_lookup[ref])
    return coords


def read_historical_osm_waterways(osm_dir: Path, target_crs) -> tuple[gpd.GeoDataFrame, dict]:
    manifest_path = osm_dir / "historical_osm_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing historical OSM manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    records: list[dict] = []
    seen: set[str] = set()
    for path in sorted(osm_dir.glob("*.osm")):
        if path.stat().st_size == 0:
            continue
        root = ET.parse(path).getroot()
        node_lookup = {
            node.attrib["id"]: (float(node.attrib["lon"]), float(node.attrib["lat"]))
            for node in root.findall("node")
            if "id" in node.attrib and "lon" in node.attrib and "lat" in node.attrib
        }
        for way in root.findall("way"):
            way_id = str(way.attrib.get("id", ""))
            if not way_id or way_id in seen:
                continue
            tags = {tag.attrib.get("k", ""): tag.attrib.get("v", "") for tag in way.findall("tag")}
            waterway = tags.get("waterway", "")
            if waterway not in {"river", "stream", "canal", "drain", "tidal_channel"}:
                continue
            coords = _way_coords(way, node_lookup)
            if len(coords) < 2:
                continue
            geometry = LineString(coords)
            if geometry.is_empty or geometry.length == 0:
                continue
            seen.add(way_id)
            records.append(
                {
                    "osm_id": way_id,
                    "waterway": waterway,
                    "name": tags.get("name", ""),
                    "name_en": tags.get("name:en", ""),
                    "tidal": tags.get("tidal", ""),
                    "layer": tags.get("layer", ""),
                    "tunnel": tags.get("tunnel", ""),
                    "source_file": path.name,
                    "geometry": geometry,
                }
            )

    waterways = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    if waterways.empty:
        raise RuntimeError("Historical OSM snapshot yielded zero usable waterways")
    waterways = waterways.to_crs(target_crs)
    return waterways, manifest


def _candidate_rows(lines: gpd.GeoDataFrame, geometry) -> gpd.GeoDataFrame:
    if lines.empty:
        return lines
    try:
        idx = list(lines.sindex.query(geometry, predicate="intersects"))
        return lines.iloc[idx]
    except Exception:
        return lines[lines.geometry.intersects(geometry)]


def _line_metrics(lines: gpd.GeoDataFrame, geometry, buffer_m: float, type_field: str) -> dict:
    target = geometry.buffer(buffer_m)
    hits = _candidate_rows(lines, target)
    lengths: dict[str, float] = {}
    names: set[str] = set()
    ids: set[str] = set()
    count = 0
    for _, row in hits.iterrows():
        overlap = row.geometry.intersection(target)
        length = float(overlap.length)
        if length <= 0:
            continue
        count += 1
        kind = str(row.get(type_field, ""))
        lengths[kind] = lengths.get(kind, 0.0) + length
        value = str(row.get("name", "") or "").strip()
        if value:
            names.add(value)
        feature_id = str(row.get("osm_id", row.get("reach_id", "")) or "").strip()
        if feature_id:
            ids.add(feature_id)
    return {
        "feature_count": int(count),
        "length_by_type_m": lengths,
        "names": " | ".join(sorted(names)),
        "feature_ids": " | ".join(sorted(ids)),
    }


def _window_for_geometry(dataset: rasterio.io.DatasetReader, geometry) -> Window:
    raw = from_bounds(*geometry.bounds, transform=dataset.transform)
    col0 = max(0, int(math.floor(raw.col_off)))
    row0 = max(0, int(math.floor(raw.row_off)))
    col1 = min(dataset.width, int(math.ceil(raw.col_off + raw.width)))
    row1 = min(dataset.height, int(math.ceil(raw.row_off + raw.height)))
    return Window(col0, row0, max(0, col1 - col0), max(0, row1 - row0))


def worldcover_metrics(dataset: rasterio.io.DatasetReader, geometry) -> dict[str, float | int]:
    window = _window_for_geometry(dataset, geometry)
    if window.width <= 0 or window.height <= 0:
        return {"worldcover_valid_cells": 0, "worldcover_water_fraction": 0.0, "worldcover_wetland_fraction": 0.0}
    data = dataset.read(1, window=window)
    transform = dataset.window_transform(window)
    mask = geometry_mask(
        [geometry.__geo_interface__],
        out_shape=data.shape,
        transform=transform,
        invert=True,
        all_touched=False,
    )
    values = data[mask]
    if dataset.nodata is not None:
        values = values[values != dataset.nodata]
    if np.issubdtype(values.dtype, np.floating):
        values = values[np.isfinite(values)]
    if values.size == 0:
        return {"worldcover_valid_cells": 0, "worldcover_water_fraction": 0.0, "worldcover_wetland_fraction": 0.0}
    return {
        "worldcover_valid_cells": int(values.size),
        "worldcover_water_fraction": float(np.mean(values == 80)),
        "worldcover_wetland_fraction": float(np.mean(values == 90)),
    }


def choose_class(e: dict, cfg: ClassificationConfig) -> tuple[str, str, str, bool, str]:
    """Return final_class, subtype, confidence, review_required, decision_reason."""

    if str(e.get("provisional_class", "")) == "OCEAN" or str(e.get("object_id", "")).startswith("OCEAN_"):
        return "OCEAN", "MARINE_OPEN_WATER", "HIGH", False, "V49-A ocean-connected core; marine treatment has priority."

    area = float(e.get("area_km2", 0.0))
    dist_ocean = float(e.get("distance_to_ocean_m", 1.0e12))
    wc80 = float(e.get("worldcover_water_fraction", 0.0))
    wc90 = float(e.get("worldcover_wetland_fraction", 0.0))
    elong = float(e.get("shape_elongation", 1.0))
    graph_m = float(e.get("graph_length_m", 0.0))
    graph_major = int(e.get("graph_major_reach_count", 0))
    osm_river_m = float(e.get("osm_river_m", 0.0))
    osm_stream_m = float(e.get("osm_stream_m", 0.0))
    osm_canal_m = float(e.get("osm_canal_m", 0.0))
    osm_tidal_m = float(e.get("osm_tidal_channel_m", 0.0))
    natural_osm_m = osm_river_m + osm_stream_m + osm_tidal_m
    flow_support_m = graph_m + natural_osm_m
    line_density = (flow_support_m / 1000.0) / max(area, 0.01)
    names = str(e.get("osm_names", ""))

    # Tidal/coastal channel evidence has priority over ordinary river rules.
    if dist_ocean <= cfg.estuary_distance_m and (
        graph_m >= cfg.minimum_graph_support_m or natural_osm_m >= cfg.minimum_line_support_m or osm_tidal_m > 0
    ):
        subtype = "TIDAL_CHANNEL" if osm_tidal_m > 0 else "RIVER_MOUTH_ESTUARY"
        confidence = "HIGH" if graph_m >= 1000 and natural_osm_m >= 500 else "MEDIUM"
        return (
            "ESTUARY_TIDAL_RIVER",
            subtype,
            confidence,
            False,
            "Coastal proximity plus independent river/graph support indicates a river mouth or tidal reach.",
        )

    # Wetland is only assigned when wetland land-cover dominates locally and channel evidence is weak.
    if wc90 >= cfg.wetland_min_fraction and flow_support_m < cfg.wetland_max_flow_support_m:
        return (
            "WETLAND_FLOODPLAIN_WATER",
            "WORLDCOVER_HERBACEOUS_WETLAND",
            "MEDIUM",
            False,
            "WorldCover wetland fraction is strong while mapped channel support is weak; preserve storage/micro-topography.",
        )

    # Standing-water rule: broad persistent water with a lake/reservoir semantic cue, or broad water with sparse
    # through-flow support. A river centerline crossing a broad polygon is not enough to make the polygon a river.
    lake_name = _is_lake_name(names)
    if dist_ocean > cfg.estuary_distance_m and area >= cfg.lake_min_area_km2 and wc80 >= cfg.lake_min_worldcover_water_fraction:
        broad_inland_storage = (
            dist_ocean > cfg.coastal_ambiguity_distance_m
            and line_density <= cfg.lake_max_flow_line_density_km_per_km2
            and elong < 4.0
        )
        if lake_name or broad_inland_storage:
            confidence = "HIGH" if lake_name and wc80 >= 0.55 else "MEDIUM"
            return (
                "LAKE_RESERVOIR",
                "NAMED_OR_BROAD_STANDING_WATER",
                confidence,
                False,
                "Broad inland persistent water is more consistent with standing storage than a channel polygon.",
            )

    # Canal requires direct OSM canal evidence that dominates natural-waterway evidence and a suitably linear/small object.
    if osm_canal_m >= cfg.canal_min_osm_m:
        natural_ref = max(natural_osm_m, 1.0)
        if osm_canal_m >= cfg.canal_dominance_ratio * natural_ref and (area <= 0.5 or elong >= 4.0):
            return (
                "CANAL",
                "OSM_ENGINEERED_WATERWAY",
                "HIGH" if osm_canal_m >= 500 else "MEDIUM",
                False,
                "Historical OSM canal evidence dominates natural-waterway evidence and object geometry is compatible.",
            )

    # A low-confidence OSM-only candidate is not promoted to a river solely because a volunteered centerline crosses it.
    # This keeps V49-A's W20_0011 / W20_0062 type cases reviewable unless independent graph/HydroRIVERS evidence exists.
    if (
        str(e.get("provisional_class", "")) == "OSM_WATERWAY_CANDIDATE"
        and int(e.get("hydrorivers_feature_count", 0)) == 0
        and graph_m < cfg.minimum_graph_support_m
    ):
        return (
            "UNKNOWN_REVIEW_REQUIRED",
            "OSM_ONLY_WATERWAY_AMBIGUOUS",
            "LOW",
            True,
            "OSM-only waterway evidence lacks independent HydroRIVERS/V49-B support; retain for review rather than infer channel type.",
        )

    # Mixed wetland/channel evidence needs a dedicated review rather than forcing either a wetland or river treatment.
    if wc90 >= 0.08 and wc80 < 0.40 and flow_support_m >= cfg.wetland_max_flow_support_m:
        return (
            "UNKNOWN_REVIEW_REQUIRED",
            "MIXED_WETLAND_CHANNEL_AMBIGUOUS",
            "LOW",
            True,
            "Substantial wetland cover and mapped channel support coexist; preserve the object until channel versus floodplain extent is resolved.",
        )

    # Large near-coastal objects outside the explicit estuary band can be river-lagoon complexes. Do not force them.
    if (
        area >= cfg.broad_water_area_km2
        and dist_ocean <= cfg.coastal_ambiguity_distance_m
        and flow_support_m >= cfg.minimum_graph_support_m
    ):
        return (
            "UNKNOWN_REVIEW_REQUIRED",
            "COASTAL_RIVER_LAGOON_AMBIGUOUS",
            "LOW",
            True,
            "Broad near-coastal water has river support but lacks sufficient tidal/standing-water semantics for a safe automatic class.",
        )

    # River/stream requires explicit line/graph support plus linearity, small-object morphology, or dense through-flow evidence.
    has_natural_support = graph_m >= cfg.minimum_graph_support_m or natural_osm_m >= cfg.minimum_line_support_m
    river_geometry_ok = elong >= cfg.river_min_elongation or area <= 0.4 or line_density >= cfg.river_dense_line_km_per_km2
    if has_natural_support and river_geometry_ok:
        if osm_stream_m > osm_river_m and osm_stream_m >= cfg.minimum_line_support_m:
            subtype = "STREAM"
        elif osm_river_m > 0 or graph_major > 0 or _is_river_name(names):
            subtype = "RIVER"
        else:
            subtype = "RIVER_OR_STREAM"
        confidence = "HIGH" if graph_m >= 500 and natural_osm_m >= 200 else "MEDIUM"
        return (
            "RIVER_STREAM",
            subtype,
            confidence,
            False,
            "Mapped hydrography and object morphology support a flowing natural channel representation.",
        )

    return (
        "UNKNOWN_REVIEW_REQUIRED",
        "INSUFFICIENT_OR_CONFLICTING_EVIDENCE",
        "LOW",
        True,
        "Available evidence does not support a safe automatic water-body type; retain unchanged pending review.",
    )


def treatment_for_class(final_class: str) -> tuple[str, str]:
    if final_class not in TREATMENT_BY_CLASS:
        raise KeyError(f"No treatment registered for class {final_class}")
    return TREATMENT_BY_CLASS[final_class]


def _build_evidence_record(
    row: pd.Series,
    graph: gpd.GeoDataFrame,
    osm: gpd.GeoDataFrame,
    worldcover_ds: rasterio.io.DatasetReader,
    cfg: ClassificationConfig,
) -> dict:
    geometry = row.geometry
    shape_metrics = _shape_metrics(geometry)
    graph_metrics = _line_metrics(graph, geometry, cfg.evidence_buffer_m, "source_type")
    osm_metrics = _line_metrics(osm, geometry, cfg.evidence_buffer_m, "waterway")
    wc = worldcover_metrics(worldcover_ds, geometry)

    gtypes = graph_metrics["length_by_type_m"]
    otypes = osm_metrics["length_by_type_m"]
    graph_hits = _candidate_rows(graph, geometry.buffer(cfg.evidence_buffer_m))
    graph_major_count = 0
    terminal_count = 0
    reach_ids: set[str] = set()
    for _, grow in graph_hits.iterrows():
        overlap_m = float(grow.geometry.intersection(geometry.buffer(cfg.evidence_buffer_m)).length)
        if overlap_m <= 0:
            continue
        graph_major_count += int(bool(grow.get("major_reach", 0)))
        terminal_count += int(bool(str(grow.get("terminal_type", "") or "").strip()))
        rid = str(grow.get("reach_id", "") or "").strip()
        if rid:
            reach_ids.add(rid)

    record = row.drop(labels=["geometry"]).to_dict()
    record.update(shape_metrics)
    record.update(wc)
    record.update(
        {
            "graph_reach_count": int(graph_metrics["feature_count"]),
            "graph_major_reach_count": int(graph_major_count),
            "terminal_reach_count": int(terminal_count),
            "graph_length_m": float(sum(gtypes.values())),
            "graph_reach_ids": " | ".join(sorted(reach_ids)),
            "osm_feature_count": int(osm_metrics["feature_count"]),
            "osm_river_m": float(otypes.get("river", 0.0)),
            "osm_stream_m": float(otypes.get("stream", 0.0)),
            "osm_canal_m": float(otypes.get("canal", 0.0)),
            "osm_drain_m": float(otypes.get("drain", 0.0)),
            "osm_tidal_channel_m": float(otypes.get("tidal_channel", 0.0)),
            "osm_names": str(osm_metrics["names"]),
            "osm_way_ids": str(osm_metrics["feature_ids"]),
        }
    )
    flow_support_m = record["graph_length_m"] + record["osm_river_m"] + record["osm_stream_m"] + record["osm_tidal_channel_m"]
    record["flow_support_m"] = float(flow_support_m)
    record["flow_line_density_km_per_km2"] = float((flow_support_m / 1000.0) / max(float(row.area_km2), 0.01))

    final_class, subtype, confidence, review_required, reason = choose_class(record, cfg)
    treatment_code, treatment_rule = treatment_for_class(final_class)
    record.update(
        {
            "final_class": final_class,
            "subtype": subtype,
            "final_confidence": confidence,
            "review_required_final": bool(review_required),
            "treatment_code": treatment_code,
            "treatment_rule": treatment_rule,
            "future_channel_geometry_eligible": bool(final_class in CHANNEL_ELIGIBLE_CLASSES),
            "decision_reason": reason,
        }
    )
    record["evidence_summary"] = (
        f"area={float(row.area_km2):.4f} km2; ocean_dist={float(row.distance_to_ocean_m):.1f} m; "
        f"graph={record['graph_length_m'] / 1000.0:.2f} km ({record['graph_reach_count']} reaches, {record['graph_major_reach_count']} major); "
        f"OSM river/stream/canal={record['osm_river_m'] / 1000.0:.2f}/{record['osm_stream_m'] / 1000.0:.2f}/{record['osm_canal_m'] / 1000.0:.2f} km; "
        f"WC water/wetland={record['worldcover_water_fraction']:.3f}/{record['worldcover_wetland_fraction']:.3f}; "
        f"elongation={record['shape_elongation']:.2f}; names={record['osm_names'] or 'none'}"
    )
    record["geometry"] = geometry
    return record


def _plot_map(classified: gpd.GeoDataFrame, graph: gpd.GeoDataFrame, output_path: Path) -> None:
    colors = {
        "OCEAN": "#9ecae1",
        "ESTUARY_TIDAL_RIVER": "#3182bd",
        "RIVER_STREAM": "#08519c",
        "CANAL": "#756bb1",
        "LAKE_RESERVOIR": "#41b6c4",
        "WETLAND_FLOODPLAIN_WATER": "#74c476",
        "UNKNOWN_REVIEW_REQUIRED": "#fdae6b",
    }
    fig, ax = plt.subplots(figsize=(11, 11))
    for cls in FINAL_CLASSES:
        subset = classified[classified.final_class == cls]
        if not subset.empty:
            subset.plot(ax=ax, color=colors[cls], edgecolor="white", linewidth=0.25, alpha=0.92)
    major = graph[graph.major_reach.astype(bool)] if "major_reach" in graph.columns else graph.iloc[0:0]
    if not major.empty:
        major.plot(ax=ax, color="black", linewidth=0.45, alpha=0.55)
    for object_id in ("W20_0059", "W20_0022", "W20_0009", "W20_0046", "W20_0002", "W20_0080", "W20_0070", "W20_0072"):
        hit = classified[classified.object_id == object_id]
        if not hit.empty:
            p = hit.geometry.iloc[0].representative_point()
            ax.text(p.x, p.y, object_id, fontsize=6.5, ha="center", va="center")
    legend = [Patch(facecolor=colors[c], edgecolor="none", label=c) for c in FINAL_CLASSES if (classified.final_class == c).any()]
    ax.legend(handles=legend, loc="lower left", fontsize=7, frameon=True)
    ax.set_title("V49-C conservative full-domain water-body classification")
    ax.set_aspect("equal")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def build_classification(
    inventory_path: Path = DEFAULT_INVENTORY,
    graph_path: Path = DEFAULT_GRAPH,
    osm_dir: Path = DEFAULT_OSM_DIR,
    worldcover_path: Path = DEFAULT_WORLDCOVER,
    dem_path: Path = DEFAULT_DEM,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config: ClassificationConfig = ClassificationConfig(),
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    dem_hash_before = sha256_file(dem_path)
    if dem_hash_before != EXPECTED_DEM_SHA256:
        raise RuntimeError(
            f"Source DEM hash mismatch before V49-C: {dem_hash_before}; expected {EXPECTED_DEM_SHA256}"
        )

    inventory = gpd.read_file(inventory_path, layer="water_objects")
    graph = gpd.read_file(graph_path, layer="reaches").to_crs(inventory.crs)
    osm, osm_manifest = read_historical_osm_waterways(osm_dir, inventory.crs)

    records: list[dict] = []
    with rasterio.open(worldcover_path) as worldcover_ds:
        if worldcover_ds.crs != inventory.crs:
            raise ValueError(f"WorldCover CRS {worldcover_ds.crs} does not match inventory CRS {inventory.crs}")
        for _, row in inventory.sort_values("object_id").iterrows():
            records.append(_build_evidence_record(row, graph, osm, worldcover_ds, config))

    classified = gpd.GeoDataFrame(records, geometry="geometry", crs=inventory.crs).sort_values("object_id").reset_index(drop=True)
    if len(classified) != len(inventory):
        raise RuntimeError("Classification row count does not match V49-A inventory")
    if classified.object_id.duplicated().any():
        raise RuntimeError("Duplicate object_id generated in V49-C")

    gpkg_path = output_dir / "V49_waterbody_classification.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()
    classified.to_file(gpkg_path, layer="classified_objects", driver="GPKG")
    osm.to_file(gpkg_path, layer="osm_historical_waterways", driver="GPKG")

    csv_path = output_dir / "V49_waterbody_classification.csv"
    classified.drop(columns="geometry").to_csv(csv_path, index=False, encoding="utf-8-sig")

    map_path = output_dir / "V49_C_classification_map.png"
    _plot_map(classified, graph, map_path)

    source_manifest = osm_dir / "historical_osm_manifest.json"
    copied_manifest = output_dir / "historical_osm_manifest_source.json"
    shutil.copyfile(source_manifest, copied_manifest)

    dem_hash_after = sha256_file(dem_path)
    class_counts = {str(k): int(v) for k, v in classified.final_class.value_counts().sort_index().items()}
    class_area = {
        str(k): float(v)
        for k, v in classified.groupby("final_class", sort=True).area_km2.sum().items()
    }
    unknown = classified[classified.final_class == "UNKNOWN_REVIEW_REQUIRED"]
    audit = {
        "schema_version": "V49-C-audit-1",
        "phase": "V49-C",
        "purpose": "Conservative water-body classification and treatment assignment; no DEM modification.",
        "classification_config": asdict(config),
        "source_paths": {
            "inventory": str(inventory_path),
            "hydrograph": str(graph_path),
            "historical_osm_directory": str(osm_dir),
            "worldcover_raw_class_raster": str(worldcover_path),
            "source_dem": str(dem_path),
        },
        "source_hashes": {
            "inventory_gpkg_sha256": sha256_file(inventory_path),
            "hydrograph_gpkg_sha256": sha256_file(graph_path),
            "worldcover_raster_sha256": sha256_file(worldcover_path),
            "historical_osm_manifest_sha256": sha256_file(source_manifest),
            "dem_sha256_before": dem_hash_before,
            "dem_sha256_after": dem_hash_after,
        },
        "historical_osm": {
            "status": osm_manifest.get("status"),
            "snapshot_utc": osm_manifest.get("snapshot_utc"),
            "source": osm_manifest.get("source"),
            "license": osm_manifest.get("license"),
            "unique_waterway_count": int(len(osm)),
            "waterway_counts": {str(k): int(v) for k, v in osm.waterway.value_counts().sort_index().items()},
            "fresh_network_refresh_used": False,
            "note": "V49-C uses the locally preserved 2021-11-25 historical OSM snapshot; no fresh network OSM download is required for this gate.",
        },
        "inventory_object_count": int(len(inventory)),
        "classified_object_count": int(len(classified)),
        "class_counts": class_counts,
        "class_area_km2": class_area,
        "unknown_review_count": int(len(unknown)),
        "unknown_review_area_km2": float(unknown.area_km2.sum()),
        "review_required_total": int(classified.review_required_final.astype(bool).sum()),
        "dem_expected_sha256": EXPECTED_DEM_SHA256,
        "dem_unchanged": bool(dem_hash_before == dem_hash_after == EXPECTED_DEM_SHA256),
        "dem_modified_in_v49_c": False,
        "safety_invariants": {
            "unknown_no_automatic_carving": bool(
                (unknown.treatment_code == "NO_AUTOMATIC_CARVING").all()
            ),
            "ocean_never_river_formula": bool(
                (classified.loc[classified.final_class == "OCEAN", "treatment_code"] == "EXTERNAL_BATHYMETRY_OR_BOUNDARY").all()
            ),
            "wetland_never_river_trench": bool(
                (classified.loc[classified.final_class == "WETLAND_FLOODPLAIN_WATER", "treatment_code"] == "PRESERVE_STORAGE_NO_RIVER_TRENCH").all()
            ),
            "lake_never_reach_scale_river_treatment": bool(
                (classified.loc[classified.final_class == "LAKE_RESERVOIR", "treatment_code"] == "STAGE_AREA_VOLUME_OR_BATHYMETRY").all()
            ),
        },
        "key_object_summary": {
            row.object_id: {
                "final_class": row.final_class,
                "confidence": row.final_confidence,
                "review_required": bool(row.review_required_final),
                "treatment_code": row.treatment_code,
                "evidence_summary": row.evidence_summary,
            }
            for _, row in classified[classified.object_id.isin(
                ["W20_0059", "W20_0022", "W20_0009", "W20_0046", "W20_0002", "W20_0080", "W20_0070", "W20_0072"]
            )].iterrows()
        },
    }
    audit_path = output_dir / "V49_C_classification_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--osm-dir", type=Path, default=DEFAULT_OSM_DIR)
    parser.add_argument("--worldcover", type=Path, default=DEFAULT_WORLDCOVER)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    audit = build_classification(
        inventory_path=args.inventory,
        graph_path=args.graph,
        osm_dir=args.osm_dir,
        worldcover_path=args.worldcover,
        dem_path=args.dem,
        output_dir=args.output_dir,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
