"""Build the V49-A full-domain surface-water inventory without editing DEM elevations.

The pipeline uses JRC Global Surface Water occurrence as the primary open-water
observation layer, HydroRIVERS and OSM distance rasters as hydrographic
evidence, and the legacy V48 masks only to measure existing coverage.

The script never opens the source DEM in write/update mode.  It records a
before/after SHA-256 fingerprint so the V49-A no-terrain-modification rule is
machine-checkable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio import features
from rasterio.transform import array_bounds
from scipy import ndimage as ndi
from shapely.geometry import shape
from shapely.ops import unary_union

from v49_classify_water_objects import ClassificationConfig, classify_water_object


PROJECT_DIR = Path(r"D:\VTP\River_Bathymetry_Project")
DEFAULT_DEM = Path(r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif")
DEFAULT_JRC = Path(
    r"D:\VTP\V48_research_20261002\hydro_evidence_raw\V46_JRC_GSW1_3_occurrence_1984_2020.tif"
)
DEFAULT_HYDRO_DISTANCE = Path(r"D:\VTP\V46_dryrun_20260930\V46_distance_to_hydrorivers_m.tif")
DEFAULT_OSM_DISTANCE = Path(r"D:\VTP\V46_dryrun_20260930\V46_distance_to_osm_waterway_m.tif")
DEFAULT_HYDRO_VECTOR = Path(
    r"D:\VTP\V46_inputs\HydroRIVERS_as\HydroRIVERS_v10_as_shp\HydroRIVERS_v10_as.shp"
)
DEFAULT_DELTA_Z = PROJECT_DIR / "delta_z_full_bathymetry.tif"
DEFAULT_NETWORK_NPZ = PROJECT_DIR / "river_network_data.npz"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "V49_A_20261012"


@dataclass(frozen=True)
class InventoryConfig:
    occurrence_threshold: int = 20
    minimum_object_pixels: int = 25
    ocean_core_radius_pixels: int = 5
    ocean_restore_radius_pixels: int = 5
    ocean_seed_east_columns: int = 12
    hydro_near_m: float = 90.0
    thresholds_for_audit: tuple[int, ...] = (5, 20, 50, 90)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def grids_match(reference: rasterio.io.DatasetReader, other: rasterio.io.DatasetReader) -> bool:
    return (
        reference.shape == other.shape
        and reference.crs == other.crs
        and reference.transform.almost_equals(other.transform)
    )


def require_aligned(reference: rasterio.io.DatasetReader, datasets: Iterable[rasterio.io.DatasetReader]) -> None:
    for dataset in datasets:
        if not grids_match(reference, dataset):
            raise ValueError(
                f"Raster grid mismatch: {dataset.name} does not align with {reference.name}"
            )


def build_ocean_mask(
    water_mask: np.ndarray,
    core_radius_pixels: int = 5,
    restore_radius_pixels: int = 5,
    east_seed_columns: int = 12,
) -> np.ndarray:
    """Extract obvious open ocean while avoiding long narrow river-mouth leakage.

    A distance-to-land core removes narrow river/estuary branches.  Only core
    components reaching the eastern seed band are marine candidates.  Limited
    dilation restores the coastal fringe without geodesically flooding back up
    connected river channels.
    """

    if water_mask.ndim != 2:
        raise ValueError("water_mask must be a 2-D array")
    if not np.any(water_mask):
        return np.zeros_like(water_mask, dtype=bool)

    distance_inside_water = ndi.distance_transform_edt(water_mask)
    core = water_mask & (distance_inside_water >= float(core_radius_pixels))
    labels, count = ndi.label(core, structure=np.ones((3, 3), dtype=np.uint8))
    if count == 0:
        return np.zeros_like(water_mask, dtype=bool)

    east_start = max(0, water_mask.shape[1] - int(east_seed_columns))
    seed_ids = np.unique(labels[:, east_start:])
    seed_ids = seed_ids[seed_ids > 0]
    if seed_ids.size == 0:
        return np.zeros_like(water_mask, dtype=bool)

    ocean_core = np.isin(labels, seed_ids)
    structure = np.ones((3, 3), dtype=bool)
    restored = ndi.binary_dilation(
        ocean_core,
        structure=structure,
        iterations=int(restore_radius_pixels),
    )
    return restored & water_mask


def relabel_deterministically(mask: np.ndarray) -> tuple[np.ndarray, Dict[int, int]]:
    """8-connect label mask, then assign IDs in top-left scan order."""

    raw, count = ndi.label(mask, structure=np.ones((3, 3), dtype=np.uint8))
    if count == 0:
        return raw.astype(np.int32), {}

    slices = ndi.find_objects(raw)
    order = []
    for raw_id, slc in enumerate(slices, start=1):
        if slc is None:
            continue
        order.append((slc[0].start, slc[1].start, raw_id))
    order.sort()
    mapping = {raw_id: new_id for new_id, (_, _, raw_id) in enumerate(order, start=1)}
    out = np.zeros_like(raw, dtype=np.int32)
    for raw_id, new_id in mapping.items():
        out[raw == raw_id] = new_id
    return out, mapping


def geometries_from_labels(labels: np.ndarray, transform) -> Dict[int, object]:
    pieces: Dict[int, list] = defaultdict(list)
    mask = labels > 0
    for geometry, value in features.shapes(
        labels.astype(np.int32),
        mask=mask,
        transform=transform,
        connectivity=8,
    ):
        label_id = int(value)
        if label_id > 0:
            pieces[label_id].append(shape(geometry))
    return {label_id: unary_union(parts) for label_id, parts in pieces.items()}


def read_hydrorivers_subset(path: Path, reference: rasterio.io.DatasetReader) -> gpd.GeoDataFrame:
    bounds = reference.bounds
    transformer = Transformer.from_crs(reference.crs, "EPSG:4326", always_xy=True)
    corners = [
        transformer.transform(bounds.left, bounds.bottom),
        transformer.transform(bounds.left, bounds.top),
        transformer.transform(bounds.right, bounds.bottom),
        transformer.transform(bounds.right, bounds.top),
    ]
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    subset = gpd.read_file(path, bbox=(min(xs), min(ys), max(xs), max(ys)))
    if subset.empty:
        return subset.to_crs(reference.crs)
    return subset.to_crs(reference.crs)


def _safe_values(array: np.ndarray, mask: np.ndarray, nodata: float | int | None) -> np.ndarray:
    values = array[mask]
    if nodata is not None:
        values = values[values != nodata]
    if np.issubdtype(values.dtype, np.floating):
        values = values[np.isfinite(values)]
    return values


def _min_or_large(values: np.ndarray) -> float:
    return float(values.min()) if values.size else 1.0e12


def _hydrorivers_vector_metrics(geometry, hydro: gpd.GeoDataFrame, near_m: float) -> Mapping[str, float | int]:
    if hydro.empty:
        return {
            "hydrorivers_feature_count": 0,
            "hydrorivers_max_upland_skm": 0.0,
            "hydrorivers_max_discharge_cms": 0.0,
            "hydrorivers_max_strahler": 0,
        }
    buffered = geometry.buffer(near_m)
    hits = hydro[hydro.geometry.intersects(buffered)]
    if hits.empty:
        return {
            "hydrorivers_feature_count": 0,
            "hydrorivers_max_upland_skm": 0.0,
            "hydrorivers_max_discharge_cms": 0.0,
            "hydrorivers_max_strahler": 0,
        }
    return {
        "hydrorivers_feature_count": int(len(hits)),
        "hydrorivers_max_upland_skm": float(hits["UPLAND_SKM"].max()),
        "hydrorivers_max_discharge_cms": float(hits["DIS_AV_CMS"].max()),
        "hydrorivers_max_strahler": int(hits["ORD_STRA"].max()),
    }


def build_inventory(
    dem_path: Path,
    jrc_path: Path,
    hydro_distance_path: Path,
    osm_distance_path: Path,
    hydro_vector_path: Path,
    delta_z_path: Path,
    network_npz_path: Path,
    output_dir: Path,
    config: InventoryConfig,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    dem_hash_before = sha256_file(dem_path)

    with rasterio.open(dem_path) as dem_ds, rasterio.open(jrc_path) as jrc_ds, rasterio.open(
        hydro_distance_path
    ) as hydro_dist_ds, rasterio.open(osm_distance_path) as osm_dist_ds, rasterio.open(
        delta_z_path
    ) as dz_ds:
        require_aligned(dem_ds, [jrc_ds, hydro_dist_ds, osm_dist_ds, dz_ds])
        dem = dem_ds.read(1)
        jrc = jrc_ds.read(1)
        hydro_distance = hydro_dist_ds.read(1)
        osm_distance = osm_dist_ds.read(1)
        delta_z = dz_ds.read(1)
        transform = dem_ds.transform
        crs = dem_ds.crs
        pixel_area_m2 = abs(transform.a * transform.e)
        hydro_vector = read_hydrorivers_subset(hydro_vector_path, dem_ds)
        profile = dem_ds.profile.copy()

    network = np.load(network_npz_path, allow_pickle=True)
    union_corridor = network["union_channel_mask"].astype(bool)
    if union_corridor.shape != dem.shape:
        raise ValueError("river_network_data.npz union_channel_mask does not match DEM grid")

    jrc_valid = jrc != 255
    water_mask = jrc_valid & (jrc >= config.occurrence_threshold)
    ocean_mask = build_ocean_mask(
        water_mask,
        core_radius_pixels=config.ocean_core_radius_pixels,
        restore_radius_pixels=config.ocean_restore_radius_pixels,
        east_seed_columns=config.ocean_seed_east_columns,
    )
    inland_mask = water_mask & ~ocean_mask
    distance_to_ocean_m = ndi.distance_transform_edt(~ocean_mask) * abs(transform.a)

    labels_all, _ = relabel_deterministically(inland_mask)
    counts_all = np.bincount(labels_all.ravel())
    keep_ids = np.flatnonzero(counts_all >= config.minimum_object_pixels)
    keep_ids = keep_ids[keep_ids > 0]
    keep_mask = np.isin(labels_all, keep_ids)
    labels_kept, _ = relabel_deterministically(keep_mask)
    counts_kept = np.bincount(labels_kept.ravel())
    geometries = geometries_from_labels(labels_kept, transform)

    dz_valid = np.isfinite(delta_z)
    if dz_ds.nodata is not None:
        dz_valid &= delta_z != dz_ds.nodata
    carved_mask = dz_valid & (np.abs(delta_z) > 1.0e-6)

    records = []
    for label_id in sorted(geometries):
        object_mask = labels_kept == label_id
        cell_count = int(counts_kept[label_id])
        rows, cols = np.nonzero(object_mask)
        occ_values = _safe_values(jrc, object_mask, 255)
        dem_values = _safe_values(dem, object_mask, -9999.0)
        hydro_values = _safe_values(hydro_distance, object_mask, -9999.0)
        osm_values = _safe_values(osm_distance, object_mask, -9999.0)
        geometry = geometries[label_id]
        vector_metrics = _hydrorivers_vector_metrics(
            geometry, hydro_vector, config.hydro_near_m
        )
        evidence = {
            "is_ocean": False,
            "area_km2": cell_count * pixel_area_m2 / 1_000_000.0,
            "hydrorivers_min_m": _min_or_large(hydro_values),
            "osm_waterway_min_m": _min_or_large(osm_values),
            "hydrorivers_within_90m_fraction": float(
                np.mean(hydro_values <= config.hydro_near_m) if hydro_values.size else 0.0
            ),
            "osm_within_90m_fraction": float(
                np.mean(osm_values <= config.hydro_near_m) if osm_values.size else 0.0
            ),
            "distance_to_ocean_m": float(distance_to_ocean_m[object_mask].min()),
            **vector_metrics,
        }
        provisional_class, confidence, review_required, reason = classify_water_object(
            evidence,
            ClassificationConfig(river_near_m=config.hydro_near_m),
        )
        legacy_overlap_cells = int(np.sum(object_mask & union_corridor))
        legacy_overlap_fraction = float(np.mean(union_corridor[object_mask]))
        legacy_uncovered_cells = cell_count - legacy_overlap_cells
        if legacy_overlap_fraction >= 0.80:
            legacy_status = "FULLY_COVERED"
        elif legacy_overlap_cells > 0:
            legacy_status = "PARTIALLY_COVERED"
        else:
            legacy_status = "MISSING"
        record = {
            "object_id": f"W{config.occurrence_threshold:02d}_{label_id:04d}",
            "label_id": label_id,
            "cell_count": cell_count,
            "area_km2": cell_count * pixel_area_m2 / 1_000_000.0,
            "centroid_x": float(geometry.centroid.x),
            "centroid_y": float(geometry.centroid.y),
            "bbox_left": float(geometry.bounds[0]),
            "bbox_bottom": float(geometry.bounds[1]),
            "bbox_right": float(geometry.bounds[2]),
            "bbox_top": float(geometry.bounds[3]),
            "occurrence_mean": float(np.mean(occ_values)),
            "occurrence_p50": float(np.percentile(occ_values, 50)),
            "occurrence_p90": float(np.percentile(occ_values, 90)),
            "persistent_50_fraction": float(np.mean(occ_values >= 50)),
            "persistent_90_fraction": float(np.mean(occ_values >= 90)),
            "dem_min_m": float(np.min(dem_values)) if dem_values.size else np.nan,
            "dem_mean_m": float(np.mean(dem_values)) if dem_values.size else np.nan,
            "dem_max_m": float(np.max(dem_values)) if dem_values.size else np.nan,
            "touches_domain_boundary": bool(
                rows.min() == 0
                or cols.min() == 0
                or rows.max() == dem.shape[0] - 1
                or cols.max() == dem.shape[1] - 1
            ),
            "distance_to_ocean_m": evidence["distance_to_ocean_m"],
            "hydrorivers_min_m": evidence["hydrorivers_min_m"],
            "hydrorivers_within_90m_fraction": evidence[
                "hydrorivers_within_90m_fraction"
            ],
            "osm_waterway_min_m": evidence["osm_waterway_min_m"],
            "osm_within_90m_fraction": evidence["osm_within_90m_fraction"],
            **vector_metrics,
            "legacy_corridor_overlap_cells": legacy_overlap_cells,
            "legacy_corridor_overlap_fraction": legacy_overlap_fraction,
            "legacy_uncovered_cells": legacy_uncovered_cells,
            "legacy_uncovered_fraction": 1.0 - legacy_overlap_fraction,
            "legacy_uncovered_area_km2": legacy_uncovered_cells
            * pixel_area_m2
            / 1_000_000.0,
            "legacy_status": legacy_status,
            "legacy_carved_overlap_cells": int(np.sum(object_mask & carved_mask)),
            "legacy_carved_overlap_fraction": float(np.mean(carved_mask[object_mask])),
            "represented_by_legacy": legacy_status == "FULLY_COVERED",
            "touched_by_legacy": legacy_overlap_cells > 0,
            "provisional_class": provisional_class,
            "confidence": confidence,
            "review_required": review_required,
            "classification_reason": reason,
            "source_jrc": True,
            "source_hydrorivers_distance": True,
            "source_osm_distance": True,
            "geometry": geometry,
        }
        records.append(record)

    if np.any(ocean_mask):
        ocean_labels = ocean_mask.astype(np.int32)
        ocean_geometry = unary_union(list(geometries_from_labels(ocean_labels, transform).values()))
        ocean_record = {
            "object_id": "OCEAN_0001",
            "label_id": 0,
            "cell_count": int(ocean_mask.sum()),
            "area_km2": float(ocean_mask.sum() * pixel_area_m2 / 1_000_000.0),
            "centroid_x": float(ocean_geometry.centroid.x),
            "centroid_y": float(ocean_geometry.centroid.y),
            "bbox_left": float(ocean_geometry.bounds[0]),
            "bbox_bottom": float(ocean_geometry.bounds[1]),
            "bbox_right": float(ocean_geometry.bounds[2]),
            "bbox_top": float(ocean_geometry.bounds[3]),
            "occurrence_mean": float(np.mean(jrc[ocean_mask])),
            "occurrence_p50": float(np.percentile(jrc[ocean_mask], 50)),
            "occurrence_p90": float(np.percentile(jrc[ocean_mask], 90)),
            "persistent_50_fraction": float(np.mean(jrc[ocean_mask] >= 50)),
            "persistent_90_fraction": float(np.mean(jrc[ocean_mask] >= 90)),
            "dem_min_m": float(np.min(dem[ocean_mask])),
            "dem_mean_m": float(np.mean(dem[ocean_mask])),
            "dem_max_m": float(np.max(dem[ocean_mask])),
            "touches_domain_boundary": True,
            "distance_to_ocean_m": 0.0,
            "hydrorivers_min_m": np.nan,
            "hydrorivers_within_90m_fraction": np.nan,
            "osm_waterway_min_m": np.nan,
            "osm_within_90m_fraction": np.nan,
            "hydrorivers_feature_count": 0,
            "hydrorivers_max_upland_skm": 0.0,
            "hydrorivers_max_discharge_cms": 0.0,
            "hydrorivers_max_strahler": 0,
            "legacy_corridor_overlap_cells": int(np.sum(ocean_mask & union_corridor)),
            "legacy_corridor_overlap_fraction": float(np.mean(union_corridor[ocean_mask])),
            "legacy_uncovered_cells": int(np.sum(ocean_mask & ~union_corridor)),
            "legacy_uncovered_fraction": float(np.mean(~union_corridor[ocean_mask])),
            "legacy_uncovered_area_km2": float(
                np.sum(ocean_mask & ~union_corridor) * pixel_area_m2 / 1_000_000.0
            ),
            "legacy_status": "EXCLUDED_OCEAN",
            "legacy_carved_overlap_cells": int(np.sum(ocean_mask & carved_mask)),
            "legacy_carved_overlap_fraction": float(np.mean(carved_mask[ocean_mask])),
            "represented_by_legacy": False,
            "touched_by_legacy": bool(np.any(ocean_mask & union_corridor)),
            "provisional_class": "OCEAN",
            "confidence": "HIGH",
            "review_required": False,
            "classification_reason": "Open-water core connected to the eastern marine boundary.",
            "source_jrc": True,
            "source_hydrorivers_distance": True,
            "source_osm_distance": True,
            "geometry": ocean_geometry,
        }
        records.insert(0, ocean_record)

    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=crs)
    table = pd.DataFrame(gdf.drop(columns="geometry"))
    table_path = output_dir / "V49_water_object_table.csv"
    gpkg_path = output_dir / "V49_master_water_inventory.gpkg"
    table.to_csv(table_path, index=False, encoding="utf-8-sig")
    if gpkg_path.exists():
        gpkg_path.unlink()
    gdf.to_file(gpkg_path, layer="water_objects", driver="GPKG")

    evidence = np.zeros(dem.shape, dtype=np.uint8)
    evidence[water_mask] |= 1
    evidence[hydro_distance <= config.hydro_near_m] |= 2
    evidence[osm_distance <= config.hydro_near_m] |= 4
    evidence[union_corridor] |= 8
    evidence[carved_mask] |= 16
    evidence[ocean_mask] |= 32
    evidence_profile = profile.copy()
    evidence_profile.update(dtype="uint8", count=1, nodata=0, compress="deflate")
    with rasterio.open(output_dir / "V49_master_water_evidence.tif", "w", **evidence_profile) as dst:
        dst.write(evidence, 1)

    ocean_profile = profile.copy()
    ocean_profile.update(dtype="uint8", count=1, nodata=0, compress="deflate")
    with rasterio.open(output_dir / "V49_ocean_mask.tif", "w", **ocean_profile) as dst:
        dst.write(ocean_mask.astype(np.uint8), 1)

    # Coverage audit at multiple JRC persistence thresholds.  Each threshold
    # gets its own marine mask so ocean is never mixed into inland area totals.
    threshold_audit = {}
    for threshold in config.thresholds_for_audit:
        wm = jrc_valid & (jrc >= threshold)
        om = build_ocean_mask(
            wm,
            core_radius_pixels=config.ocean_core_radius_pixels,
            restore_radius_pixels=config.ocean_restore_radius_pixels,
            east_seed_columns=config.ocean_seed_east_columns,
        )
        im = wm & ~om
        labs, _ = relabel_deterministically(im)
        cnt = np.bincount(labs.ravel())
        ids = np.flatnonzero(cnt >= config.minimum_object_pixels)
        ids = ids[ids > 0]
        qualifying = np.isin(labs, ids)
        threshold_audit[str(threshold)] = {
            "raw_water_cells": int(wm.sum()),
            "raw_water_area_km2": float(wm.sum() * pixel_area_m2 / 1_000_000.0),
            "ocean_cells": int(om.sum()),
            "ocean_area_km2": float(om.sum() * pixel_area_m2 / 1_000_000.0),
            "inland_water_cells_all": int(im.sum()),
            "inland_water_area_km2_all": float(im.sum() * pixel_area_m2 / 1_000_000.0),
            "qualifying_object_count": int(len(ids)),
            "qualifying_inland_cells": int(qualifying.sum()),
            "qualifying_inland_area_km2": float(
                qualifying.sum() * pixel_area_m2 / 1_000_000.0
            ),
            "qualifying_legacy_corridor_cells": int(np.sum(qualifying & union_corridor)),
            "qualifying_legacy_carved_cells": int(np.sum(qualifying & carved_mask)),
        }

    inland_gdf = gdf[gdf["provisional_class"] != "OCEAN"].copy()
    class_counts = Counter(inland_gdf["provisional_class"].tolist())
    class_areas = (
        inland_gdf.groupby("provisional_class")["area_km2"].sum().to_dict()
        if not inland_gdf.empty
        else {}
    )
    fully_covered = inland_gdf[inland_gdf["legacy_status"] == "FULLY_COVERED"]
    partially_covered = inland_gdf[inland_gdf["legacy_status"] == "PARTIALLY_COVERED"]
    missing = inland_gdf[inland_gdf["legacy_status"] == "MISSING"]
    main_threshold = threshold_audit[str(config.occurrence_threshold)]
    qualifying_inland_cells = int(main_threshold["qualifying_inland_cells"])
    qualifying_legacy_corridor_cells = int(main_threshold["qualifying_legacy_corridor_cells"])
    qualifying_uncovered_cells = qualifying_inland_cells - qualifying_legacy_corridor_cells
    dem_hash_after = sha256_file(dem_path)

    audit = {
        "version": "V49-A",
        "inputs": {
            "dem": str(dem_path),
            "jrc_occurrence": str(jrc_path),
            "hydrorivers_distance": str(hydro_distance_path),
            "osm_waterway_distance": str(osm_distance_path),
            "hydrorivers_vector": str(hydro_vector_path),
            "legacy_delta_z": str(delta_z_path),
            "legacy_network_npz": str(network_npz_path),
        },
        "config": asdict(config),
        "grid": {
            "shape": list(dem.shape),
            "crs": str(crs),
            "transform": list(transform),
            "bounds": list(array_bounds(dem.shape[0], dem.shape[1], transform)),
            "pixel_area_m2": pixel_area_m2,
            "hydrorivers_features_in_domain": int(len(hydro_vector)),
        },
        "threshold_audit": threshold_audit,
        "inventory": {
            "object_count_including_ocean": int(len(gdf)),
            "inland_object_count": int(len(inland_gdf)),
            "fully_covered_by_legacy_count": int(len(fully_covered)),
            "partially_covered_by_legacy_count": int(len(partially_covered)),
            "missing_from_legacy_count": int(len(missing)),
            "objects_not_fully_covered_count": int(len(partially_covered) + len(missing)),
            "fully_covered_object_area_km2": float(fully_covered["area_km2"].sum()),
            "partially_covered_object_area_km2": float(partially_covered["area_km2"].sum()),
            "zero_overlap_object_area_km2": float(missing["area_km2"].sum()),
            "qualifying_inland_area_km2": float(
                qualifying_inland_cells * pixel_area_m2 / 1_000_000.0
            ),
            "legacy_corridor_covered_water_area_km2": float(
                qualifying_legacy_corridor_cells * pixel_area_m2 / 1_000_000.0
            ),
            "legacy_corridor_uncovered_water_area_km2": float(
                qualifying_uncovered_cells * pixel_area_m2 / 1_000_000.0
            ),
            "legacy_corridor_cell_coverage_pct": float(
                100.0 * qualifying_legacy_corridor_cells / qualifying_inland_cells
                if qualifying_inland_cells
                else 0.0
            ),
            "class_counts": dict(class_counts),
            "class_areas_km2": {k: float(v) for k, v in class_areas.items()},
            "review_required_count": int(inland_gdf["review_required"].sum()),
        },
        "dem_integrity": {
            "sha256_before": dem_hash_before,
            "sha256_after": dem_hash_after,
            "unchanged": dem_hash_before == dem_hash_after,
        },
    }
    qualifying_at_main = threshold_audit[str(config.occurrence_threshold)][
        "qualifying_object_count"
    ]
    gate = {
        "all_minimum_size_objects_accounted": int(len(inland_gdf)) == int(qualifying_at_main),
        "all_objects_classified_or_review_required": bool(
            np.all(inland_gdf["provisional_class"].astype(str).str.len() > 0)
            and np.all(
                (~inland_gdf["review_required"])
                | inland_gdf["provisional_class"].str.contains("REVIEW_REQUIRED|CANDIDATE")
            )
        ),
        "ocean_excluded_from_inland_statistics": bool(np.any(ocean_mask)),
        "dem_unchanged": dem_hash_before == dem_hash_after,
    }
    gate["pass"] = bool(all(gate.values()))
    audit["gate_A"] = gate

    audit_path = output_dir / "V49_water_coverage_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    # Static review map: DEM backdrop + detected ocean + legacy coverage +
    # missing persistent inland objects.
    fig, ax = plt.subplots(figsize=(12, 11), constrained_layout=True)
    valid_dem = dem[dem != -9999.0]
    vmin, vmax = np.percentile(valid_dem, [2, 98])
    extent = [
        transform.c,
        transform.c + transform.a * dem.shape[1],
        transform.f + transform.e * dem.shape[0],
        transform.f,
    ]
    ax.imshow(dem, extent=extent, origin="upper", cmap="terrain", vmin=vmin, vmax=vmax, alpha=0.72)
    ocean_overlay = np.ma.masked_where(~ocean_mask, ocean_mask)
    ax.imshow(
        ocean_overlay,
        extent=extent,
        origin="upper",
        cmap=ListedColormap(["#4C9FE6"]),
        alpha=0.48,
    )
    corridor_overlay = np.ma.masked_where(~union_corridor, union_corridor)
    ax.imshow(
        corridor_overlay,
        extent=extent,
        origin="upper",
        cmap=ListedColormap(["#F59E0B"]),
        alpha=0.58,
    )
    missing_mask = (labels_kept > 0) & ~union_corridor
    missing_overlay = np.ma.masked_where(~missing_mask, missing_mask)
    ax.imshow(
        missing_overlay,
        extent=extent,
        origin="upper",
        cmap=ListedColormap(["#DC2626"]),
        alpha=0.78,
    )
    ax.set_title(
        f"V49-A surface-water coverage | JRC ≥ {config.occurrence_threshold}% | min {config.minimum_object_pixels} px"
    )
    ax.set_xlabel("Easting (m, EPSG:32649)")
    ax.set_ylabel("Northing (m, EPSG:32649)")
    handles = [
        Patch(facecolor="#4C9FE6", alpha=0.48, label="Open-ocean mask"),
        Patch(facecolor="#F59E0B", alpha=0.58, label="V48 five-branch corridor"),
        Patch(
            facecolor="#DC2626",
            alpha=0.78,
            label="Qualifying inland water outside V48 corridor",
        ),
    ]
    ax.legend(handles=handles, loc="upper right", framealpha=0.90)
    note = (
        f"Inland objects: {len(inland_gdf)}\n"
        f"Not fully covered: {len(partially_covered) + len(missing)}\n"
        f"Legacy cell coverage: {audit['inventory']['legacy_corridor_cell_coverage_pct']:.2f}%"
    )
    ax.text(
        0.01,
        0.01,
        note,
        transform=ax.transAxes,
        fontsize=9,
        va="bottom",
        ha="left",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
    )
    fig.savefig(output_dir / "V49_water_coverage_map.png", dpi=180)
    plt.close(fig)

    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    parser.add_argument("--jrc", type=Path, default=DEFAULT_JRC)
    parser.add_argument("--hydro-distance", type=Path, default=DEFAULT_HYDRO_DISTANCE)
    parser.add_argument("--osm-distance", type=Path, default=DEFAULT_OSM_DISTANCE)
    parser.add_argument("--hydro-vector", type=Path, default=DEFAULT_HYDRO_VECTOR)
    parser.add_argument("--delta-z", type=Path, default=DEFAULT_DELTA_Z)
    parser.add_argument("--network-npz", type=Path, default=DEFAULT_NETWORK_NPZ)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--threshold", type=int, default=20)
    parser.add_argument("--minimum-object-pixels", type=int, default=25)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = InventoryConfig(
        occurrence_threshold=args.threshold,
        minimum_object_pixels=args.minimum_object_pixels,
    )
    audit = build_inventory(
        dem_path=args.dem,
        jrc_path=args.jrc,
        hydro_distance_path=args.hydro_distance,
        osm_distance_path=args.osm_distance,
        hydro_vector_path=args.hydro_vector,
        delta_z_path=args.delta_z,
        network_npz_path=args.network_npz,
        output_dir=args.output_dir,
        config=config,
    )
    print(json.dumps(audit["gate_A"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

