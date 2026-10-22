"""V49-D reach-scale hydraulic-geometry estimation.

This phase does not edit the source DEM.  It converts the V49-B directed
hydrograph and the V49-C conservative water-body classification into a
traceable reach-geometry table for later V49-E hydraulic-bed synthesis.

Scientific safeguards:

* Copernicus DEM samples are water-surface / terrain proxies, never surveyed
  river-bed elevations.
* HydroRIVERS ``DIS_AV_CMS`` is explicitly retained as a mean-discharge proxy,
  not silently relabelled as bankfull discharge.
* Persistent-water polygons are used to estimate observed surface-water width
  with repeated perpendicular cross-sections.  Width is not taken from a
  branch name or from the legacy fixed-width benchmarks.
* Manning inversion is used only when width, a positive longitudinal slope,
  discharge proxy and roughness prior are all available.  Otherwise the
  documented HydroMT power-law form is a low-information fallback.
* Estuary/tidal reaches and unverified legacy canals remain review-only and
  are never authorized automatically for V49-E carving.
* Fixed legacy depths (3.50 / 2.25 / 1.20 m) are not used by this estimator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import LineString, Point
from shapely.ops import unary_union


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


PROJECT_DIR = Path(r"D:\VTP\River_Bathymetry_Project")
DEFAULT_GRAPH = PROJECT_DIR / "V49_B_20261012" / "V49_hydrograph.gpkg"
DEFAULT_CLASSIFICATION = PROJECT_DIR / "V49_C_20261012" / "V49_waterbody_classification.gpkg"
DEFAULT_DEM = Path(r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif")
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "V49_D_20261012"

EXPECTED_DEM_SHA256 = "0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508"

ELIGIBLE_CLASSES = {"RIVER_STREAM", "ESTUARY_TIDAL_RIVER"}
TIDAL_CLASS = "ESTUARY_TIDAL_RIVER"
NATURAL_N_CENTRAL = 0.035
NATURAL_N_LOW = 0.025
NATURAL_N_HIGH = 0.050


@dataclass(frozen=True)
class GeometryConfig:
    width_sample_count: int = 9
    profile_sample_count: int = 21
    tangent_half_window_m: float = 45.0
    cross_section_half_length_m: float = 2500.0
    max_cross_section_distance_m: float = 75.0
    bank_outward_offset_m: float = 30.0
    min_width_m: float = 5.0
    max_width_m: float = 4000.0
    min_slope: float = 1.0e-5
    max_slope: float = 2.0e-2
    confluence_bed_tolerance_m: float = 0.75
    structure_context_distance_m: float = 300.0
    manning_uncertainty_low_factor: float = 0.50
    manning_uncertainty_high_factor: float = 1.70
    powerlaw_uncertainty_low_factor: float = 0.40
    powerlaw_uncertainty_high_factor: float = 1.80
    tidal_uncertainty_low_factor: float = 0.35
    tidal_uncertainty_high_factor: float = 2.00


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def split_pipe(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    return [item.strip() for item in str(value).split("|") if item.strip()]


def _finite(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def hydromt_powerlaw_depth(q_cms: float, hc: float = 0.27, hp: float = 0.30) -> float:
    """HydroMT-documented fallback form h = hc * Qbf**hp.

    V49-D may feed HydroRIVERS mean discharge into this function only as a
    clearly labelled proxy; the caller owns that provenance and uncertainty.
    """

    q = _finite(q_cms)
    if not math.isfinite(q) or q <= 0.0:
        return float("nan")
    return float(hc * q**hp)


def manning_rectangular_discharge(width_m: float, depth_m: float, slope: float, n: float) -> float:
    width = _finite(width_m)
    depth = _finite(depth_m)
    slope_value = _finite(slope)
    roughness = _finite(n)
    if min(width, depth, slope_value, roughness) <= 0.0:
        return float("nan")
    area = width * depth
    wetted_perimeter = width + 2.0 * depth
    radius = area / wetted_perimeter
    return float((1.0 / roughness) * area * radius ** (2.0 / 3.0) * math.sqrt(slope_value))


def manning_rectangular_depth(
    q_cms: float,
    width_m: float,
    slope: float,
    n: float = NATURAL_N_CENTRAL,
) -> float:
    """Invert Manning's equation for a rectangular reach by bisection."""

    q = _finite(q_cms)
    width = _finite(width_m)
    slope_value = _finite(slope)
    roughness = _finite(n)
    if q <= 0.0 or width <= 0.0 or slope_value <= 0.0 or roughness <= 0.0:
        return float("nan")

    lo = 0.01
    hi = max(2.0, hydromt_powerlaw_depth(q) * 4.0)
    while hi < 100.0 and manning_rectangular_discharge(width, hi, slope_value, roughness) < q:
        hi *= 2.0
    if manning_rectangular_discharge(width, hi, slope_value, roughness) < q:
        return float("nan")
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if manning_rectangular_discharge(width, mid, slope_value, roughness) < q:
            lo = mid
        else:
            hi = mid
    return float(0.5 * (lo + hi))


def _line_parts(geometry) -> list[LineString]:
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    if geometry.geom_type == "MultiLineString":
        return [part for part in geometry.geoms if not part.is_empty]
    if geometry.geom_type == "GeometryCollection":
        parts: list[LineString] = []
        for item in geometry.geoms:
            parts.extend(_line_parts(item))
        return parts
    return []


def local_cross_section(line: LineString, fraction: float, cfg: GeometryConfig) -> tuple[Point, LineString]:
    length = float(line.length)
    chainage = max(0.0, min(length, float(fraction) * length))
    delta = min(cfg.tangent_half_window_m, max(5.0, 0.20 * length))
    p0 = line.interpolate(max(0.0, chainage - delta))
    p1 = line.interpolate(min(length, chainage + delta))
    center = line.interpolate(chainage)
    vx = float(p1.x - p0.x)
    vy = float(p1.y - p0.y)
    norm = math.hypot(vx, vy)
    if norm <= 1.0e-9:
        coords = list(line.coords)
        vx = float(coords[-1][0] - coords[0][0])
        vy = float(coords[-1][1] - coords[0][1])
        norm = math.hypot(vx, vy)
    if norm <= 1.0e-9:
        raise ValueError("Cannot derive local tangent for zero-length reach")
    px = -vy / norm
    py = vx / norm
    half = cfg.cross_section_half_length_m
    section = LineString(
        [
            (center.x - px * half, center.y - py * half),
            (center.x + px * half, center.y + py * half),
        ]
    )
    return center, section


def width_from_cross_section(
    line: LineString,
    water_geometry,
    fraction: float,
    cfg: GeometryConfig,
) -> tuple[float, tuple[Point, Point] | None]:
    center, section = local_cross_section(line, fraction, cfg)
    intersection = water_geometry.intersection(section)
    parts = _line_parts(intersection)
    if not parts:
        return float("nan"), None
    part = min(parts, key=lambda item: float(item.distance(center)))
    if float(part.distance(center)) > cfg.max_cross_section_distance_m:
        return float("nan"), None
    width = float(part.length)
    if width < cfg.min_width_m or width > cfg.max_width_m:
        return float("nan"), None
    coords = list(part.coords)
    return width, (Point(coords[0]), Point(coords[-1]))


def _valid_raster_value(dataset: rasterio.io.DatasetReader, value: float) -> bool:
    if not math.isfinite(value):
        return False
    if dataset.nodata is not None and math.isclose(value, float(dataset.nodata), rel_tol=0.0, abs_tol=1e-6):
        return False
    return True


def sample_raster_point(dataset: rasterio.io.DatasetReader, point: Point) -> float:
    value = float(next(dataset.sample([(point.x, point.y)]))[0])
    return value if _valid_raster_value(dataset, value) else float("nan")


def sample_bank_outside(
    dataset: rasterio.io.DatasetReader,
    center: Point,
    endpoints: tuple[Point, Point] | None,
    cfg: GeometryConfig,
) -> list[float]:
    if endpoints is None:
        return []
    values: list[float] = []
    for endpoint in endpoints:
        vx = float(endpoint.x - center.x)
        vy = float(endpoint.y - center.y)
        norm = math.hypot(vx, vy)
        if norm <= 1.0e-9:
            continue
        scale = cfg.bank_outward_offset_m / norm
        outside = Point(endpoint.x + vx * scale, endpoint.y + vy * scale)
        value = sample_raster_point(dataset, outside)
        if math.isfinite(value):
            values.append(value)
    return values


def sample_width_and_bank(
    line: LineString,
    water_geometry,
    dataset: rasterio.io.DatasetReader,
    cfg: GeometryConfig,
) -> dict:
    fractions = np.linspace(0.10, 0.90, cfg.width_sample_count)
    widths: list[float] = []
    bank_elevations: list[float] = []
    for fraction in fractions:
        center, _ = local_cross_section(line, float(fraction), cfg)
        width, endpoints = width_from_cross_section(line, water_geometry, float(fraction), cfg)
        if not math.isfinite(width):
            continue
        widths.append(width)
        bank_elevations.extend(sample_bank_outside(dataset, center, endpoints, cfg))
    if not widths:
        return {
            "width_m": float("nan"),
            "width_p25_m": float("nan"),
            "width_p75_m": float("nan"),
            "width_sample_count": 0,
            "bank_elevation_proxy_m": float("nan"),
            "bank_sample_count": 0,
        }
    arr = np.asarray(widths, dtype=float)
    bank_arr = np.asarray(bank_elevations, dtype=float)
    return {
        "width_m": float(np.median(arr)),
        "width_p25_m": float(np.quantile(arr, 0.25)),
        "width_p75_m": float(np.quantile(arr, 0.75)),
        "width_sample_count": int(arr.size),
        "bank_elevation_proxy_m": float(np.median(bank_arr)) if bank_arr.size else float("nan"),
        "bank_sample_count": int(bank_arr.size),
    }


def robust_profile_slope(
    line: LineString,
    dataset: rasterio.io.DatasetReader,
    cfg: GeometryConfig,
) -> dict:
    """Estimate signed downstream water-surface/terrain slope robustly.

    The reach direction is V49-B upstream -> downstream.  Positive returned
    slope therefore means the sampled surface falls in the downstream direction.
    Pairwise slopes use only points separated by at least 20% of reach length
    to suppress 30 m pixel-scale DEM noise.
    """

    fractions = np.linspace(0.03, 0.97, cfg.profile_sample_count)
    distances: list[float] = []
    elevations: list[float] = []
    length = float(line.length)
    for fraction in fractions:
        point = line.interpolate(float(fraction) * length)
        value = sample_raster_point(dataset, point)
        if math.isfinite(value):
            distances.append(float(fraction) * length)
            elevations.append(value)
    pair_slopes: list[float] = []
    min_sep = max(30.0, 0.20 * length)
    for i in range(len(distances)):
        for j in range(i + 1, len(distances)):
            ds = distances[j] - distances[i]
            if ds >= min_sep:
                pair_slopes.append((elevations[i] - elevations[j]) / ds)
    slope = float(np.median(pair_slopes)) if pair_slopes else float("nan")
    upstream_values = [z for f, z in zip(fractions, elevations) if f <= 0.15]
    downstream_values = [z for f, z in zip(fractions, elevations) if f >= 0.85]
    # When invalid raster samples reduced the arrays, use direct endpoint windows.
    if len(elevations) >= 3:
        upstream_proxy = float(np.median(elevations[: min(3, len(elevations))]))
        downstream_proxy = float(np.median(elevations[-min(3, len(elevations)) :]))
    else:
        upstream_proxy = float("nan")
        downstream_proxy = float("nan")
    usable = bool(math.isfinite(slope) and cfg.min_slope <= slope <= cfg.max_slope)
    return {
        "slope_proxy": slope,
        "slope_usable_for_manning": usable,
        "profile_sample_count": int(len(elevations)),
        "wse_proxy_upstream_m": upstream_proxy,
        "wse_proxy_downstream_m": downstream_proxy,
    }


def object_width_fallback(objects: gpd.GeoDataFrame) -> float:
    estimates: list[float] = []
    weights: list[float] = []
    for _, row in objects.iterrows():
        area_m2 = max(0.0, _finite(row.get("area_km2"))) * 1.0e6
        graph_length = _finite(row.get("graph_length_m"))
        if area_m2 > 0.0 and graph_length > 0.0:
            estimates.append(area_m2 / graph_length)
            weights.append(graph_length)
    if not estimates:
        return float("nan")
    order = np.argsort(estimates)
    values = np.asarray(estimates, dtype=float)[order]
    w = np.asarray(weights, dtype=float)[order]
    cumulative = np.cumsum(w) / np.sum(w)
    return float(values[int(np.searchsorted(cumulative, 0.5, side="left"))])


def depth_uncertainty(depth_m: float, method: str, cfg: GeometryConfig) -> tuple[float, float, str]:
    depth = _finite(depth_m)
    if not math.isfinite(depth) or depth <= 0.0:
        return float("nan"), float("nan"), "UNRESOLVED"
    if "TIDAL" in method:
        return depth * cfg.tidal_uncertainty_low_factor, depth * cfg.tidal_uncertainty_high_factor, "EXTREME"
    if method.startswith("MANNING"):
        return depth * cfg.manning_uncertainty_low_factor, depth * cfg.manning_uncertainty_high_factor, "HIGH"
    return depth * cfg.powerlaw_uncertainty_low_factor, depth * cfg.powerlaw_uncertainty_high_factor, "VERY_HIGH"


def authorization_decision(
    source_type: str,
    object_classes: Iterable[str],
    width_m: float,
    depth_m: float,
    depth_method: str,
    topology_review_required: bool,
    width_evidence_quality: str = "DIRECT_MEDIUM",
    preliminary_bed_upstream_m: float | None = None,
    preliminary_bed_downstream_m: float | None = None,
    bed_tolerance_m: float = 0.75,
) -> tuple[bool, str]:
    classes = set(object_classes)
    if source_type == "LEGACY_CANAL_CANDIDATE":
        return False, "V49C_NO_ACCEPTED_CANAL; legacy canal candidate remains review-only"
    if TIDAL_CLASS in classes:
        return False, "TIDAL_BACKWATER_REQUIRES_GVF_OR_MARINE_CONTROL"
    if "RIVER_STREAM" not in classes:
        return False, "NO_V49C_AUTHORIZED_RIVER_OBJECT"
    if topology_review_required:
        return False, "V49B_TOPOLOGY_REVIEW_REQUIRED"
    if str(width_evidence_quality) not in {"DIRECT_MEDIUM", "DIRECT_LOW"}:
        return False, "WIDTH_EVIDENCE_NOT_DIRECT_ENOUGH_FOR_AUTOMATIC_V49E_INPUT"
    if not math.isfinite(_finite(width_m)) or _finite(width_m) <= 0.0:
        return False, "WIDTH_UNRESOLVED"
    if not math.isfinite(_finite(depth_m)) or _finite(depth_m) <= 0.0:
        return False, "DEPTH_UNRESOLVED"
    if not depth_method:
        return False, "DEPTH_METHOD_UNRESOLVED"
    if preliminary_bed_upstream_m is not None or preliminary_bed_downstream_m is not None:
        up, down = _finite(preliminary_bed_upstream_m), _finite(preliminary_bed_downstream_m)
        if not math.isfinite(up) or not math.isfinite(down):
            return False, "PRELIMINARY_BED_PROFILE_UNRESOLVED"
        if down > up + bed_tolerance_m:
            return False, "PRELIMINARY_DOWNSTREAM_BED_RISE_REQUIRES_CONTROL_OR_DIRECTION_REVIEW"
    return True, "V49C_RIVER + traceable width/depth evidence; candidate input for V49-E"


def confluence_state(
    inversion_m: float,
    fully_authorized: bool,
    tidal_context: bool,
    structure_context: bool,
    tolerance_m: float,
) -> tuple[str, str]:
    if not fully_authorized:
        if tidal_context:
            return "CONTROL_CONTEXT_TIDAL_REVIEW", "Tidal/backwater geometry is intentionally excluded from automatic V49-E carving."
        return "OUTSIDE_FULL_V49D_CARVING_SCOPE", "At least one incident reach is not V49-D-authorized; no bed-ordering assertion is forced."
    if not math.isfinite(_finite(inversion_m)):
        return "REVIEW_REQUIRED_NO_BED_STATE", "Authorized incident reach is missing a preliminary bed proxy."
    if inversion_m <= tolerance_m:
        return "OK", "Outgoing preliminary bed does not rise above incoming bed beyond the DEM/proxy tolerance."
    if structure_context:
        return "CONTROL_EXCEPTION_STRUCTURE", "Apparent inversion lies within a documented hydraulic-structure context."
    if tidal_context:
        return "CONTROL_EXCEPTION_TIDAL", "Apparent inversion lies in documented tidal/backwater context."
    return "REVIEW_REQUIRED_BED_INVERSION", "Unexplained preliminary downstream bed rise exceeds tolerance; exclude affected reaches from V49-E until resolved."


def _percentiles(values: pd.Series) -> dict[str, float | None]:
    data = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    if data.empty:
        return {key: None for key in ("p01", "p05", "p25", "p50", "p75", "p95", "p99")}
    return {
        "p01": float(data.quantile(0.01)),
        "p05": float(data.quantile(0.05)),
        "p25": float(data.quantile(0.25)),
        "p50": float(data.quantile(0.50)),
        "p75": float(data.quantile(0.75)),
        "p95": float(data.quantile(0.95)),
        "p99": float(data.quantile(0.99)),
    }


def mark_distribution_outliers(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    frame = frame.copy()
    frame["distribution_outlier"] = False
    frame["outlier_reason"] = ""
    frame["outlier_review_status"] = "NOT_OUTLIER"
    authorized = frame[frame.geometry_authorized_for_v49e.astype(bool)].copy()
    if authorized.empty:
        return frame

    flags: dict[str, list[str]] = defaultdict(list)
    for field, lower_physical, upper_physical in (
        ("width_m", 5.0, 2500.0),
        ("depth_est_m", 0.10, 20.0),
    ):
        values = pd.to_numeric(authorized[field], errors="coerce")
        positive = values[(values > 0.0) & np.isfinite(values)]
        log_values = np.log(positive)
        if len(log_values) >= 8:
            q1 = float(log_values.quantile(0.25))
            q3 = float(log_values.quantile(0.75))
            iqr = q3 - q1
            lower_stat = math.exp(q1 - 3.0 * iqr)
            upper_stat = math.exp(q3 + 3.0 * iqr)
        else:
            lower_stat, upper_stat = 0.0, float("inf")
        for idx, value in values.items():
            if not math.isfinite(_finite(value)):
                flags[str(frame.at[idx, "reach_id"])].append(f"{field}:NONFINITE")
            elif value < lower_physical or value > upper_physical:
                flags[str(frame.at[idx, "reach_id"])].append(f"{field}:PHYSICAL_RANGE")
            elif value < lower_stat or value > upper_stat:
                flags[str(frame.at[idx, "reach_id"])].append(f"{field}:ROBUST_LOG_OUTLIER")

    for idx, row in frame.iterrows():
        reach_id = str(row.reach_id)
        depth = _finite(row.depth_est_m)
        width = _finite(row.width_m)
        if bool(row.geometry_authorized_for_v49e) and width > 0.0 and depth / width > 0.35:
            flags[reach_id].append("depth_width_ratio:GT_0.35")
        if reach_id in flags:
            frame.at[idx, "distribution_outlier"] = True
            frame.at[idx, "outlier_reason"] = " | ".join(flags[reach_id])
            frame.at[idx, "outlier_review_status"] = "REVIEW_REQUIRED_EXCLUDED"
            frame.at[idx, "geometry_authorized_for_v49e"] = False
            frame.at[idx, "authorization_reason"] = (
                str(frame.at[idx, "authorization_reason"]) + "; distribution outlier excluded pending review"
            )
    return frame


def _build_object_maps(classified: gpd.GeoDataFrame) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    eligible_map: dict[str, list[int]] = defaultdict(list)
    all_map: dict[str, list[int]] = defaultdict(list)
    for idx, row in classified.iterrows():
        for reach_id in split_pipe(row.get("graph_reach_ids", "")):
            all_map[reach_id].append(idx)
            if bool(row.get("future_channel_geometry_eligible", False)) and str(row.get("final_class", "")) in ELIGIBLE_CLASSES:
                eligible_map[reach_id].append(idx)
    return eligible_map, all_map


def estimate_reaches(
    reaches: gpd.GeoDataFrame,
    classified: gpd.GeoDataFrame,
    dem: rasterio.io.DatasetReader,
    cfg: GeometryConfig,
) -> gpd.GeoDataFrame:
    eligible_map, all_map = _build_object_maps(classified)
    records: list[dict] = []

    for _, reach in reaches.iterrows():
        reach_id = str(reach.reach_id)
        source_type = str(reach.source_type)
        eligible_objects = classified.loc[eligible_map.get(reach_id, [])].copy()
        all_objects = classified.loc[all_map.get(reach_id, [])].copy()
        classes = sorted(set(eligible_objects.final_class.astype(str))) if not eligible_objects.empty else []
        object_ids = sorted(set(eligible_objects.object_id.astype(str))) if not eligible_objects.empty else []
        all_classes = sorted(set(all_objects.final_class.astype(str))) if not all_objects.empty else []

        width_stats = {
            "width_m": float("nan"),
            "width_p25_m": float("nan"),
            "width_p75_m": float("nan"),
            "width_sample_count": 0,
            "bank_elevation_proxy_m": float("nan"),
            "bank_sample_count": 0,
        }
        width_source = "NOT_ESTIMATED_OUTSIDE_V49C_ELIGIBLE_OBJECT"
        width_evidence_quality = "OUT_OF_SCOPE"
        width_object_morphology_status = "NO_ELIGIBLE_OBJECT"
        if not eligible_objects.empty:
            # For fluvial width, prefer only elongated river-like objects.  Broad
            # water polygons can be reservoirs, floodplain pools or merged JRC
            # water complexes even when graph evidence made their V49-C class
            # RIVER_STREAM.  They remain useful evidence, but are too ambiguous
            # to authorize automatic carving width by themselves.
            river_objects = eligible_objects[eligible_objects.final_class.astype(str) == "RIVER_STREAM"]
            riverlike_objects = river_objects[
                pd.to_numeric(river_objects.shape_elongation, errors="coerce") >= 1.8
            ] if not river_objects.empty else river_objects
            if TIDAL_CLASS in classes:
                width_objects = eligible_objects
                width_object_morphology_status = "TIDAL_OBJECT_REVIEW"
            elif not riverlike_objects.empty:
                width_objects = riverlike_objects
                width_object_morphology_status = "ELONGATED_RIVER_OBJECT_SELECTED"
            else:
                width_objects = eligible_objects
                width_object_morphology_status = "BROAD_OR_AMBIGUOUS_WATER_OBJECT"

            water_geometry = unary_union(list(width_objects.geometry))
            width_stats = sample_width_and_bank(reach.geometry, water_geometry, dem, cfg)
            if width_stats["width_sample_count"] >= 3:
                width_source = "JRC_PERSISTENT_WATER_POLYGON_PERPENDICULAR_CROSS_SECTIONS"
                if width_object_morphology_status == "ELONGATED_RIVER_OBJECT_SELECTED":
                    width_evidence_quality = (
                        "DIRECT_MEDIUM" if width_stats["width_sample_count"] >= 5 else "DIRECT_LOW"
                    )
                else:
                    width_evidence_quality = "DIRECT_BUT_MORPHOLOGY_AMBIGUOUS"
            else:
                fallback_width = object_width_fallback(width_objects)
                if math.isfinite(fallback_width) and cfg.min_width_m <= fallback_width <= cfg.max_width_m:
                    width_stats["width_m"] = fallback_width
                    width_stats["width_p25_m"] = 0.50 * fallback_width
                    width_stats["width_p75_m"] = 1.50 * fallback_width
                    width_source = "V49C_OBJECT_AREA_OVER_SUPPORTED_GRAPH_LENGTH_FALLBACK"
                    width_evidence_quality = "INDIRECT_VERY_LOW"
                else:
                    width_source = "WIDTH_UNRESOLVED"
                    width_evidence_quality = "UNRESOLVED"

        width = _finite(width_stats["width_m"])
        if math.isfinite(width) and width > 0.0:
            width_low = min(_finite(width_stats["width_p25_m"]), 0.70 * width)
            width_high = max(_finite(width_stats["width_p75_m"]), 1.30 * width)
        else:
            width_low = width_high = float("nan")

        profile = robust_profile_slope(reach.geometry, dem, cfg)
        q_proxy = _finite(reach.get("DIS_AV_CMS"))
        powerlaw = hydromt_powerlaw_depth(q_proxy)
        manning_depth = float("nan")
        tidal = TIDAL_CLASS in classes

        if source_type == "LEGACY_CANAL_CANDIDATE":
            depth_est = float("nan")
            depth_method = "UNRESOLVED_LEGACY_CANAL_REQUIRES_INDEPENDENT_GEOMETRY"
            depth_status = "REVIEW_REQUIRED"
        elif tidal:
            depth_est = powerlaw
            depth_method = "POWERLAW_HYDROMT_QMEAN_TIDAL_PRIOR_ONLY" if math.isfinite(powerlaw) else "UNRESOLVED_TIDAL"
            depth_status = "TIDAL_BACKWATER_REVIEW_REQUIRED"
        elif (
            "RIVER_STREAM" in classes
            and math.isfinite(width)
            and width > 0.0
            and bool(profile["slope_usable_for_manning"])
            and q_proxy > 0.0
        ):
            manning_depth = manning_rectangular_depth(q_proxy, width, profile["slope_proxy"], NATURAL_N_CENTRAL)
            if math.isfinite(manning_depth) and 0.10 <= manning_depth <= 20.0 and manning_depth / width <= 0.35:
                depth_est = manning_depth
                depth_method = "MANNING_RECTANGULAR_QMEAN_PROXY"
                depth_status = "INFERRED_HIGH_UNCERTAINTY"
            else:
                depth_est = powerlaw
                depth_method = "POWERLAW_HYDROMT_QMEAN_PROXY_MANNING_REJECTED"
                depth_status = "INFERRED_VERY_HIGH_UNCERTAINTY"
        elif "RIVER_STREAM" in classes:
            depth_est = powerlaw
            depth_method = "POWERLAW_HYDROMT_QMEAN_PROXY"
            depth_status = "INFERRED_VERY_HIGH_UNCERTAINTY"
        else:
            depth_est = powerlaw
            depth_method = "POWERLAW_HYDROMT_QMEAN_QA_PRIOR_ONLY" if math.isfinite(powerlaw) else "UNRESOLVED_OUT_OF_SCOPE"
            depth_status = "QA_PRIOR_OUTSIDE_V49C_CARVING_SCOPE"

        depth_low, depth_high, uncertainty_class = depth_uncertainty(depth_est, depth_method, cfg)
        topology_review_value = _finite(reach.get("topology_review_required"))
        topology_review = bool(int(topology_review_value)) if math.isfinite(topology_review_value) else False
        wse_up = _finite(profile["wse_proxy_upstream_m"])
        wse_down = _finite(profile["wse_proxy_downstream_m"])
        bed_up = wse_up - depth_est if math.isfinite(wse_up) and math.isfinite(_finite(depth_est)) else float("nan")
        bed_down = wse_down - depth_est if math.isfinite(wse_down) and math.isfinite(_finite(depth_est)) else float("nan")
        authorized, authorization_reason = authorization_decision(
            source_type=source_type,
            object_classes=classes,
            width_m=width,
            depth_m=depth_est,
            depth_method=depth_method,
            topology_review_required=topology_review,
            width_evidence_quality=width_evidence_quality,
            preliminary_bed_upstream_m=bed_up,
            preliminary_bed_downstream_m=bed_down,
            bed_tolerance_m=cfg.confluence_bed_tolerance_m,
        )

        wse_up = _finite(profile["wse_proxy_upstream_m"])
        wse_down = _finite(profile["wse_proxy_downstream_m"])
        bed_up = wse_up - depth_est if math.isfinite(wse_up) and math.isfinite(_finite(depth_est)) else float("nan")
        bed_down = wse_down - depth_est if math.isfinite(wse_down) and math.isfinite(_finite(depth_est)) else float("nan")

        bank_elev = _finite(width_stats["bank_elevation_proxy_m"])
        bank_source = (
            "COPERNICUS_DEM_30M_OUTSIDE_JRC_WATER_EDGE_MEDIAN"
            if math.isfinite(bank_elev)
            else "UNRESOLVED_NO_VALID_OUTSIDE_WATER_EDGE_SAMPLES"
        )

        geometry_role = "AUTHORIZED_V49E_INPUT_CANDIDATE" if authorized else "REVIEW_OR_QA_ONLY"
        record = reach.to_dict()
        record.update(
            {
                "v49c_object_ids": " | ".join(object_ids),
                "v49c_eligible_classes": " | ".join(classes),
                "v49c_all_associated_classes": " | ".join(all_classes),
                "v49d_scope": "V49C_ELIGIBLE_CHANNEL" if classes else "OUTSIDE_V49C_ELIGIBLE_CHANNEL",
                "hydraulic_regime": "TIDAL_BACKWATER_REVIEW" if tidal else ("FLUVIAL" if "RIVER_STREAM" in classes else "OUT_OF_SCOPE"),
                "width_m": width,
                "width_low_m": width_low,
                "width_high_m": width_high,
                "width_sample_count": int(width_stats["width_sample_count"]),
                "width_source": width_source,
                "width_evidence_quality": width_evidence_quality,
                "width_object_morphology_status": width_object_morphology_status,
                "bank_elevation_proxy_m": bank_elev,
                "bank_sample_count": int(width_stats["bank_sample_count"]),
                "bank_elevation_source": bank_source,
                "slope_proxy": _finite(profile["slope_proxy"]),
                "slope_usable_for_manning": bool(profile["slope_usable_for_manning"]),
                "slope_source": "COPERNICUS_DEM_30M_ROBUST_LONGITUDINAL_SURFACE_SLOPE_PROXY",
                "profile_sample_count": int(profile["profile_sample_count"]),
                "wse_proxy_upstream_m": wse_up,
                "wse_proxy_downstream_m": wse_down,
                "wse_proxy_source": "COPERNICUS_DEM_30M_SURFACE_PROXY_NOT_BED",
                "q_proxy_cms": q_proxy,
                "q_source": "HYDRORIVERS_DIS_AV_CMS_MEAN_DISCHARGE_PROXY_NOT_BANKFULL",
                "manning_n_low": NATURAL_N_LOW if source_type == "HYDRORIVERS" else float("nan"),
                "manning_n_central": NATURAL_N_CENTRAL if source_type == "HYDRORIVERS" else float("nan"),
                "manning_n_high": NATURAL_N_HIGH if source_type == "HYDRORIVERS" else float("nan"),
                "roughness_source": "GENERIC_NATURAL_CHANNEL_PRIOR_NOT_SITE_CALIBRATED" if source_type == "HYDRORIVERS" else "UNRESOLVED",
                "depth_manning_qmean_m": manning_depth,
                "depth_powerlaw_qmean_m": powerlaw,
                "depth_est_m": depth_est,
                "depth_low_m": depth_low,
                "depth_high_m": depth_high,
                "depth_method": depth_method,
                "depth_status": depth_status,
                "uncertainty_class": uncertainty_class,
                "depth_provenance": (
                    "V49-D inference; no surveyed bathymetry located. HydroRIVERS mean discharge proxy + JRC width/DEM slope where available; "
                    "HydroMT h=0.27*Q^0.30 fallback otherwise. Legacy branch-name depths are not used."
                ),
                "preliminary_bed_upstream_m": bed_up,
                "preliminary_bed_downstream_m": bed_down,
                "preliminary_bed_state": "WSE_PROXY_MINUS_INFERRED_DEPTH_FOR_QA_ONLY" if math.isfinite(_finite(depth_est)) else "UNRESOLVED",
                "geometry_authorized_for_v49e": bool(authorized),
                "authorization_reason": authorization_reason,
                "geometry_role": geometry_role,
            }
        )
        records.append(record)

    frame = gpd.GeoDataFrame(records, geometry="geometry", crs=reaches.crs)
    return mark_distribution_outliers(frame)


def build_confluence_checks(
    nodes: gpd.GeoDataFrame,
    reach_geometry: gpd.GeoDataFrame,
    structures: gpd.GeoDataFrame,
    cfg: GeometryConfig,
) -> gpd.GeoDataFrame:
    confluences = nodes[nodes.node_type.astype(str) == "CONFLUENCE"].copy()
    rows: list[dict] = []
    reach_lookup = {str(row.reach_id): row for _, row in reach_geometry.iterrows()}
    incoming_map: dict[str, list[str]] = defaultdict(list)
    outgoing_map: dict[str, list[str]] = defaultdict(list)
    for _, reach in reach_geometry.iterrows():
        incoming_map[str(reach.to_node)].append(str(reach.reach_id))
        outgoing_map[str(reach.from_node)].append(str(reach.reach_id))

    structure_union = unary_union(list(structures.geometry)) if not structures.empty else None
    for _, node in confluences.iterrows():
        node_id = str(node.node_id)
        incoming_ids = incoming_map.get(node_id, [])
        outgoing_ids = outgoing_map.get(node_id, [])
        incident_ids = incoming_ids + outgoing_ids
        incident = [reach_lookup[rid] for rid in incident_ids if rid in reach_lookup]
        all_authorized = bool(incident) and all(bool(item.geometry_authorized_for_v49e) for item in incident)
        tidal_context = any("ESTUARY_TIDAL_RIVER" in str(item.v49c_eligible_classes) for item in incident)
        structure_context = bool(
            structure_union is not None
            and not structure_union.is_empty
            and float(node.geometry.distance(structure_union)) <= cfg.structure_context_distance_m
        )

        incoming_beds = [
            _finite(reach_lookup[rid].preliminary_bed_downstream_m)
            for rid in incoming_ids
            if rid in reach_lookup and math.isfinite(_finite(reach_lookup[rid].preliminary_bed_downstream_m))
        ]
        outgoing_beds = [
            _finite(reach_lookup[rid].preliminary_bed_upstream_m)
            for rid in outgoing_ids
            if rid in reach_lookup and math.isfinite(_finite(reach_lookup[rid].preliminary_bed_upstream_m))
        ]
        if incoming_beds and outgoing_beds:
            # Worst apparent downstream rise among incident reach pairs.
            inversion = float(max(outgoing_beds) - min(incoming_beds))
        else:
            inversion = float("nan")
        state, explanation = confluence_state(
            inversion_m=inversion,
            fully_authorized=all_authorized,
            tidal_context=tidal_context,
            structure_context=structure_context,
            tolerance_m=cfg.confluence_bed_tolerance_m,
        )
        rows.append(
            {
                "node_id": node_id,
                "incoming_reach_ids": " | ".join(incoming_ids),
                "outgoing_reach_ids": " | ".join(outgoing_ids),
                "incident_reach_count": len(incident_ids),
                "all_incident_authorized": all_authorized,
                "tidal_context": tidal_context,
                "structure_context": structure_context,
                "incoming_bed_min_m": min(incoming_beds) if incoming_beds else float("nan"),
                "incoming_bed_max_m": max(incoming_beds) if incoming_beds else float("nan"),
                "outgoing_bed_min_m": min(outgoing_beds) if outgoing_beds else float("nan"),
                "outgoing_bed_max_m": max(outgoing_beds) if outgoing_beds else float("nan"),
                "max_apparent_downstream_bed_rise_m": inversion,
                "preliminary_bed_state": state,
                "control_explanation": explanation,
                "geometry": node.geometry,
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=nodes.crs)


def build_structure_controls(
    structures: gpd.GeoDataFrame,
    reach_geometry: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    rows: list[dict] = []
    for _, structure in structures.iterrows():
        sid = str(structure.structure_id)
        incoming = reach_geometry[reach_geometry.to_node.astype(str) == sid]
        outgoing = reach_geometry[reach_geometry.from_node.astype(str) == sid]
        in_bed = pd.to_numeric(incoming.preliminary_bed_downstream_m, errors="coerce").dropna()
        out_bed = pd.to_numeric(outgoing.preliminary_bed_upstream_m, errors="coerce").dropna()
        rows.append(
            {
                "structure_id": sid,
                "name": str(structure.get("name", "")),
                "structure_type": str(structure.get("structure_type", "")),
                "incoming_reach_ids": " | ".join(incoming.reach_id.astype(str).tolist()),
                "outgoing_reach_ids": " | ".join(outgoing.reach_id.astype(str).tolist()),
                "incoming_bed_proxy_m": float(in_bed.median()) if not in_bed.empty else float("nan"),
                "outgoing_bed_proxy_m": float(out_bed.median()) if not out_bed.empty else float("nan"),
                "control_state": "EXPLICIT_HYDRAULIC_CONTROL_NO_MONOTONIC_ENFORCEMENT",
                "control_explanation": (
                    "Dong Cam is a verified weir/structure from V48/V49-B. Any later bed synthesis must preserve the control and must not "
                    "erase it with a global monotonic filter."
                ),
                "geometry": structure.geometry,
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=structures.crs)


def _write_maps(
    reaches: gpd.GeoDataFrame,
    classified: gpd.GeoDataFrame,
    confluences: gpd.GeoDataFrame,
    output_dir: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 10))
    classified.boundary.plot(ax=ax, linewidth=0.35, alpha=0.35)
    reaches[~reaches.geometry_authorized_for_v49e.astype(bool)].plot(ax=ax, linewidth=0.6, alpha=0.35)
    authorized = reaches[reaches.geometry_authorized_for_v49e.astype(bool)]
    if not authorized.empty:
        authorized.plot(ax=ax, column="depth_method", linewidth=1.8, legend=True, categorical=True)
    flagged = confluences[confluences.preliminary_bed_state.astype(str).str.startswith("REVIEW_REQUIRED")]
    if not flagged.empty:
        flagged.plot(ax=ax, marker="x", markersize=35)
    ax.set_title("V49-D reach geometry: authorized candidates and review context")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(output_dir / "V49_D_geometry_map.png", dpi=180)
    plt.close(fig)

    auth = reaches[reaches.geometry_authorized_for_v49e.astype(bool)].copy()
    for field, title, filename in (
        ("width_m", "V49-D authorized reach width distribution", "V49_D_width_distribution.png"),
        ("depth_est_m", "V49-D authorized reach depth distribution", "V49_D_depth_distribution.png"),
    ):
        data = pd.to_numeric(auth[field], errors="coerce").dropna()
        fig, ax = plt.subplots(figsize=(8, 5))
        if not data.empty:
            bins = min(30, max(6, int(math.sqrt(len(data))) + 2))
            ax.hist(data, bins=bins)
        ax.set_title(title)
        ax.set_xlabel(field)
        ax.set_ylabel("reach count")
        fig.tight_layout()
        fig.savefig(output_dir / filename, dpi=180)
        plt.close(fig)


def build_v49_d(
    graph_path: Path = DEFAULT_GRAPH,
    classification_path: Path = DEFAULT_CLASSIFICATION,
    dem_path: Path = DEFAULT_DEM,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    cfg: GeometryConfig = GeometryConfig(),
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    dem_before = sha256_file(dem_path)
    if dem_before != EXPECTED_DEM_SHA256:
        raise RuntimeError(f"Source DEM hash mismatch before V49-D: {dem_before}")

    reaches = gpd.read_file(graph_path, layer="reaches")
    nodes = gpd.read_file(graph_path, layer="nodes")
    structures = gpd.read_file(graph_path, layer="structures")
    classified = gpd.read_file(classification_path, layer="classified_objects")
    if reaches.crs != classified.crs:
        classified = classified.to_crs(reaches.crs)

    with rasterio.open(dem_path) as dem:
        reach_geometry = estimate_reaches(reaches, classified, dem, cfg)

    confluence_checks = build_confluence_checks(nodes, reach_geometry, structures, cfg)
    structure_controls = build_structure_controls(structures, reach_geometry)

    gpkg_path = output_dir / "V49_reach_geometry.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()
    reach_geometry.to_file(gpkg_path, layer="reach_geometry", driver="GPKG")
    confluence_checks.to_file(gpkg_path, layer="confluence_checks", driver="GPKG")
    structure_controls.to_file(gpkg_path, layer="structure_controls", driver="GPKG")

    csv_frame = pd.DataFrame(reach_geometry.drop(columns="geometry"))
    csv_frame.to_csv(output_dir / "V49_reach_geometry.csv", index=False, encoding="utf-8-sig")
    review_queue = reach_geometry[
        (~reach_geometry.geometry_authorized_for_v49e.astype(bool))
        & (
            reach_geometry.v49d_scope.astype(str).eq("V49C_ELIGIBLE_CHANNEL")
            | reach_geometry.source_type.astype(str).eq("LEGACY_CANAL_CANDIDATE")
        )
    ].copy()
    pd.DataFrame(review_queue.drop(columns="geometry")).to_csv(
        output_dir / "V49_D_review_queue.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(confluence_checks.drop(columns="geometry")).to_csv(
        output_dir / "V49_D_confluence_checks.csv", index=False, encoding="utf-8-sig"
    )

    _write_maps(reach_geometry, classified, confluence_checks, output_dir)

    authorized = reach_geometry[reach_geometry.geometry_authorized_for_v49e.astype(bool)].copy()
    tidal = reach_geometry[reach_geometry.hydraulic_regime.astype(str) == "TIDAL_BACKWATER_REVIEW"]
    legacy_canals = reach_geometry[reach_geometry.source_type.astype(str) == "LEGACY_CANAL_CANDIDATE"]
    unresolved_inversions = confluence_checks[
        confluence_checks.preliminary_bed_state.astype(str) == "REVIEW_REQUIRED_BED_INVERSION"
    ]
    dem_after = sha256_file(dem_path)

    audit = {
        "schema_version": "V49-D-geometry-1",
        "config": asdict(cfg),
        "inputs": {
            "hydrograph": str(graph_path),
            "classification": str(classification_path),
            "dem": str(dem_path),
        },
        "source_hashes": {
            "dem_expected_sha256": EXPECTED_DEM_SHA256,
            "dem_sha256_before": dem_before,
            "dem_sha256_after": dem_after,
        },
        "dem_unchanged": dem_before == dem_after == EXPECTED_DEM_SHA256,
        "dem_modified_pixel_count_in_v49_d": 0,
        "reach_count": int(len(reach_geometry)),
        "hydrorivers_reach_count": int((reach_geometry.source_type.astype(str) == "HYDRORIVERS").sum()),
        "v49c_eligible_reach_count": int((reach_geometry.v49d_scope.astype(str) == "V49C_ELIGIBLE_CHANNEL").sum()),
        "geometry_authorized_for_v49e_count": int(len(authorized)),
        "review_queue_count": int(len(review_queue)),
        "tidal_review_only_reach_count": int(len(tidal)),
        "legacy_canal_review_only_count": int(len(legacy_canals)),
        "width_evidence_quality_counts_eligible": dict(
            Counter(
                reach_geometry.loc[
                    reach_geometry.v49d_scope.astype(str).eq("V49C_ELIGIBLE_CHANNEL"),
                    "width_evidence_quality",
                ].astype(str)
            )
        ),
        "authorization_reason_counts_eligible": dict(
            Counter(
                reach_geometry.loc[
                    reach_geometry.v49d_scope.astype(str).eq("V49C_ELIGIBLE_CHANNEL"),
                    "authorization_reason",
                ].astype(str)
            )
        ),
        "depth_method_counts_all": dict(Counter(reach_geometry.depth_method.astype(str))),
        "depth_method_counts_authorized": dict(Counter(authorized.depth_method.astype(str))),
        "uncertainty_class_counts_authorized": dict(Counter(authorized.uncertainty_class.astype(str))),
        "authorized_width_percentiles_m": _percentiles(authorized.width_m),
        "authorized_depth_percentiles_m": _percentiles(authorized.depth_est_m),
        "authorized_q_proxy_percentiles_cms": _percentiles(authorized.q_proxy_cms),
        "distribution_outlier_reach_ids": reach_geometry.loc[
            reach_geometry.distribution_outlier.astype(bool), "reach_id"
        ].astype(str).tolist(),
        "confluence_count": int(len(confluence_checks)),
        "confluence_state_counts": dict(Counter(confluence_checks.preliminary_bed_state.astype(str))),
        "unresolved_authorized_confluence_inversion_count": int(len(unresolved_inversions)),
        "unresolved_authorized_confluence_node_ids": unresolved_inversions.node_id.astype(str).tolist(),
        "scientific_limits": [
            "No surveyed cross-section or bathymetric dataset was available in the V49 input bundle.",
            "HydroRIVERS DIS_AV_CMS is mean discharge and is not bankfull discharge.",
            "Copernicus DEM provides surface/terrain elevation proxy over water and is not river-bed elevation.",
            "Generic Manning n is a prior and is not site-calibrated.",
            "Tidal/backwater reaches require GVF/marine boundary evidence before V49-E carving.",
        ],
        "legacy_fixed_depths_used": False,
        "gate_d_preliminary_status": "PASS" if len(unresolved_inversions) == 0 else "PARTIAL",
    }
    (output_dir / "V49_D_geometry_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = f"""# V49-D implementation report — reach-scale geometry estimation

Date: 2026-10-12

## Outcome

V49-D estimated traceable reach-scale hydraulic geometry without modifying the V48 Copernicus DEM.  The estimator uses V49-C final channel eligibility, repeated cross-sections through persistent-water polygons, robust longitudinal DEM surface-slope proxies, HydroRIVERS mean-discharge proxy, Manning inversion where its inputs are usable, and the HydroMT documented power-law fallback otherwise.

Legacy fixed depths 3.50 m / 2.25 m / 1.20 m are not used by the estimator.

## Scope and authorization

- Graph reaches: **{len(reach_geometry)}**
- Reaches associated with a V49-C eligible river/tidal object: **{int((reach_geometry.v49d_scope.astype(str) == 'V49C_ELIGIBLE_CHANNEL').sum())}**
- Reaches authorized as candidate V49-E fluvial geometry: **{len(authorized)}**
- Reaches held in the explicit V49-D review queue: **{len(review_queue)}**
- Tidal/backwater reaches held for review: **{len(tidal)}**
- Legacy canal candidates held for review: **{len(legacy_canals)}**
- Distribution outliers excluded pending review: **{int(reach_geometry.distribution_outlier.astype(bool).sum())}**

Authorization is conservative: an authorized reach must be a V49-C `RIVER_STREAM`, have traceable positive width and depth, have no unresolved V49-B topology review, and not be tidal or an unverified legacy canal.

After physical review of the first-pass width distribution, indirect `object area / graph length` widths and widths derived only from broad/ambiguous water-object morphology were downgraded to review-only.  This prevents large lake/floodplain-like polygons from being silently converted into channel width.

## Depth evidence hierarchy actually available

No surveyed bathymetry/local cross-sections were present in the V49 bundle.  Therefore V49-D uses:

1. Manning rectangular inversion when JRC-derived width, positive DEM longitudinal slope proxy, HydroRIVERS discharge proxy and roughness prior are all usable.
2. HydroMT-style power law `h = 0.27 * Q^0.30` as the fallback.

`DIS_AV_CMS` remains explicitly labelled a **mean-discharge proxy, not bankfull discharge**.  The generic natural-channel Manning range 0.025–0.050 (central 0.035) is stored as a prior, not a calibration.  Inferred depth uncertainty is wider than the minimum ±30% envelope because the key discharge and roughness quantities are not locally calibrated.

## Preliminary bed QA

The preliminary bed fields are `Copernicus surface/WSE proxy - inferred depth` and are QA quantities only.  They are not surveyed bed elevations.  All **{len(confluence_checks)}** V49-B confluences have an explicit state.  Unexplained inversions among fully authorized incident reaches: **{len(unresolved_inversions)}**.

Dong Cam remains an explicit hydraulic control.  Its structure record states that later V49-E synthesis must preserve the control and must not erase it with a global monotonic filter.

## DEM invariance

- Expected SHA-256: `{EXPECTED_DEM_SHA256}`
- Before V49-D: `{dem_before}`
- After V49-D: `{dem_after}`
- Modified DEM pixels in V49-D: **0**

## Preliminary Gate D status

**{audit['gate_d_preliminary_status']}**.  Final Gate D is decided independently by `v49_validate_reach_geometry.py`.

Outputs are in `{output_dir}`.  V49-E must consume only rows where `geometry_authorized_for_v49e = True`; tidal/review/excluded rows must remain unchanged until their missing hydraulic evidence is resolved.
"""
    (PROJECT_DIR / "V49_D_IMPLEMENTATION_REPORT_20261012.md").write_text(report, encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--classification", type=Path, default=DEFAULT_CLASSIFICATION)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    audit = build_v49_d(args.graph, args.classification, args.dem, args.output_dir)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
