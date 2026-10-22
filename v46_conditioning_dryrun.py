"""Audit-first dry run for V46 hydrological DEM conditioning.

This script does not modify the DEM. It converts an independently sourced
OpenStreetMap waterway snapshot into DEM-grid evidence layers, identifies
terrain cells that deserve review as possible obstructions, and writes a
per-cell audit table plus a manifest with input hashes.

The 2021 Sentinel-1 flood raster is intentionally excluded from candidate
selection so it can remain a held-out validation target.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import fiona
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform as crs_transform, transform_bounds, transform_geom
from scipy.ndimage import distance_transform_edt, minimum_filter


DEFAULT_DEM = Path(r"D:/VTP/05-Du-lieu-GIS/PhuYen_DEM_30m_V41.asc")
DEFAULT_OSM = Path(r"D:/VTP/V46_inputs/osm_historical_20211125")
DEFAULT_HYDRORIVERS = Path(
    r"D:/VTP/V46_inputs/HydroRIVERS_as/HydroRIVERS_v10_as_shp/HydroRIVERS_v10_as.shp"
)
DEFAULT_V44 = Path(r"D:/VTP/05-Du-lieu-GIS/PhuYen_DEM_30m_V44.asc")
DEFAULT_V45 = Path(r"D:/VTP/05-Du-lieu-GIS/PhuYen_DEM_30m_V45.asc")
DEFAULT_OUT = Path(r"D:/VTP/V46_dryrun_20260930")
DEFAULT_OSM_MAX_TIMESTAMP = "2021-11-25T00:00:00Z"
SUPPORTED_WATERWAYS = {"river", "stream", "canal", "drain"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def slope_degrees(dem: np.ndarray, valid: np.ndarray, xres: float, yres: float) -> np.ndarray:
    work = dem.astype(np.float64, copy=True)
    if not np.all(valid):
        finite_fill = float(np.nanmedian(work[valid]))
        work[~valid] = finite_fill
    gy, gx = np.gradient(work, yres, xres)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    slope[~valid] = np.nan
    return slope


def _load_osm_xml(
    path: Path, dst_crs, seen_way_ids: set[int], max_timestamp: str | None
) -> tuple[list[tuple[dict, int]], dict[int, dict], Counter, int, int]:
    root = ET.parse(path).getroot()
    nodes = {
        int(node.attrib["id"]): (float(node.attrib["lon"]), float(node.attrib["lat"]))
        for node in root.findall("node")
    }
    shapes: list[tuple[dict, int]] = []
    way_meta: dict[int, dict] = {}
    type_counts: Counter[str] = Counter()
    skipped_missing_nodes = 0
    skipped_post_cutoff = 0
    for way in root.findall("way"):
        tags = {t.attrib["k"]: t.attrib["v"] for t in way.findall("tag")}
        waterway = tags.get("waterway")
        if waterway not in SUPPORTED_WATERWAYS:
            continue
        way_id = int(way.attrib["id"])
        if way_id in seen_way_ids:
            continue
        timestamp = way.attrib.get("timestamp")
        if max_timestamp and timestamp and timestamp > max_timestamp:
            skipped_post_cutoff += 1
            continue
        coords_ll = []
        for nd in way.findall("nd"):
            ref = int(nd.attrib["ref"])
            if "lon" in nd.attrib and "lat" in nd.attrib:
                coords_ll.append((float(nd.attrib["lon"]), float(nd.attrib["lat"])))
            elif ref in nodes:
                coords_ll.append(nodes[ref])
        if len(coords_ll) < 2:
            skipped_missing_nodes += 1
            continue
        xs, ys = zip(*coords_ll)
        tx, ty = crs_transform("EPSG:4326", dst_crs, list(xs), list(ys))
        seen_way_ids.add(way_id)
        shapes.append(({
            "type": "LineString",
            "coordinates": list(zip(tx, ty)),
        }, way_id))
        way_meta[way_id] = {
            "waterway": waterway,
            "name": tags.get("name"),
            "name_en": tags.get("name:en"),
            "osm_timestamp": timestamp,
            "osm_version": way.attrib.get("version"),
        }
        type_counts[waterway] += 1
    return shapes, way_meta, type_counts, skipped_missing_nodes, skipped_post_cutoff


def load_osm_waterways(
    path: Path, dst_crs, max_timestamp: str | None
) -> tuple[list[tuple[dict, int]], dict[int, dict], dict]:
    source_files = sorted(path.glob("*.osm")) if path.is_dir() else [path]
    if not source_files:
        raise FileNotFoundError(f"No OSM source files found under {path}")

    shapes: list[tuple[dict, int]] = []
    way_meta: dict[int, dict] = {}
    type_counts: Counter[str] = Counter()
    skipped_missing_nodes = 0
    skipped_post_cutoff = 0
    seen_way_ids: set[int] = set()
    for source in source_files:
        if source.suffix.lower() not in {".osm", ".xml"}:
            continue
        s, m, c, skipped, skipped_time = _load_osm_xml(
            source, dst_crs, seen_way_ids, max_timestamp
        )
        shapes.extend(s)
        way_meta.update(m)
        type_counts.update(c)
        skipped_missing_nodes += skipped
        skipped_post_cutoff += skipped_time

    snapshot_manifest_path = path / "historical_osm_manifest.json" if path.is_dir() else None
    snapshot_manifest = None
    if snapshot_manifest_path is not None and snapshot_manifest_path.exists():
        snapshot_manifest = json.loads(snapshot_manifest_path.read_text(encoding="utf-8"))
        snapshot_utc = snapshot_manifest.get("snapshot_utc")
        if max_timestamp and snapshot_utc and snapshot_utc != max_timestamp:
            raise ValueError(f"OSM snapshot mismatch: manifest={snapshot_utc}, requested={max_timestamp}")
    meta = {
        "source_files": [str(p) for p in source_files],
        "source_file_sha256": {str(p): sha256(p) for p in source_files},
        "source_scope": "Historical OpenStreetMap snapshot from Overpass attic/date query",
        "snapshot_manifest": None if snapshot_manifest_path is None or not snapshot_manifest_path.exists() else str(snapshot_manifest_path),
        "snapshot_manifest_sha256": None if snapshot_manifest_path is None or not snapshot_manifest_path.exists() else sha256(snapshot_manifest_path),
        "snapshot_utc": None if snapshot_manifest is None else snapshot_manifest.get("snapshot_utc"),
        "temporal_filter": max_timestamp,
        "copyright": "OpenStreetMap contributors; ODbL",
        "waterway_way_count": len(shapes),
        "waterway_type_counts": dict(sorted(type_counts.items())),
        "skipped_missing_nodes": skipped_missing_nodes,
        "skipped_post_cutoff": skipped_post_cutoff,
    }
    return shapes, way_meta, meta


def load_hydrorivers(
    path: Path, dst_crs, dem_bounds
) -> tuple[list[tuple[dict, int]], dict[int, dict], dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    bbox_ll = transform_bounds(dst_crs, "EPSG:4326", *dem_bounds, densify_pts=21)
    shapes: list[tuple[dict, int]] = []
    reach_meta: dict[int, dict] = {}
    with fiona.open(path) as src:
        for feat in src.filter(bbox=bbox_ll):
            props = dict(feat["properties"])
            reach_id = int(props["HYRIV_ID"])
            geom = transform_geom(src.crs, dst_crs, feat["geometry"], precision=3)
            shapes.append((geom, reach_id))
            reach_meta[reach_id] = {
                "next_down": int(props["NEXT_DOWN"]),
                "main_riv": int(props["MAIN_RIV"]),
                "length_km": float(props["LENGTH_KM"]),
                "catch_skm": float(props["CATCH_SKM"]),
                "upland_skm": float(props["UPLAND_SKM"]),
                "dis_av_cms": float(props["DIS_AV_CMS"]),
                "ord_stra": int(props["ORD_STRA"]),
            }

    stem = path.with_suffix("")
    sidecars = [p for p in (stem.with_suffix(ext) for ext in [".shp", ".shx", ".dbf", ".prj"]) if p.exists()]
    meta = {
        "path": str(path),
        "source_page": "https://www.hydrosheds.org/products/hydrorivers",
        "version": "HydroRIVERS v1.0 Asia",
        "selection_rule": "Official HydroRIVERS reaches intersecting the DEM lon/lat bounds",
        "bbox_wgs84": list(map(float, bbox_ll)),
        "reach_count": len(shapes),
        "source_file_sha256": {str(p): sha256(p) for p in sidecars},
    }
    return shapes, reach_meta, meta


def aligned_delta(base_path: Path, other_path: Path, base: np.ndarray, base_profile: dict) -> np.ndarray | None:
    if not other_path.exists():
        return None
    with rasterio.open(other_path) as src:
        if src.shape != base.shape or src.transform != base_profile["transform"] or src.crs != base_profile["crs"]:
            raise ValueError(f"Grid mismatch: {other_path}")
        return src.read(1).astype(np.float64) - base.astype(np.float64)


def write_float_tif(path: Path, arr: np.ndarray, profile: dict, nodata: float = -9999.0) -> None:
    p = profile.copy()
    p.update(driver="GTiff", dtype="float32", count=1, compress="deflate", nodata=nodata)
    out = np.where(np.isfinite(arr), arr, nodata).astype(np.float32)
    with rasterio.open(path, "w", **p) as dst:
        dst.write(out, 1)


def write_uint8_tif(path: Path, arr: np.ndarray, profile: dict) -> None:
    p = profile.copy()
    p.update(driver="GTiff", dtype="uint8", count=1, compress="deflate", nodata=0)
    with rasterio.open(path, "w", **p) as dst:
        dst.write(arr.astype(np.uint8), 1)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    ap.add_argument("--osm", type=Path, default=DEFAULT_OSM)
    ap.add_argument("--osm-max-timestamp", default=DEFAULT_OSM_MAX_TIMESTAMP)
    ap.add_argument("--hydrorivers", type=Path, default=DEFAULT_HYDRORIVERS)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--corridor-cells", type=float, default=2.0)
    ap.add_argument("--hydro-corridor-cells", type=float, default=3.0)
    ap.add_argument("--relief-threshold-m", type=float, default=1.0)
    ap.add_argument("--relief-window", type=int, default=5)
    ap.add_argument("--max-slope-deg", type=float, default=5.0)
    ap.add_argument("--max-elevation-m", type=float, default=20.0)
    ap.add_argument("--compare-v44", type=Path, default=DEFAULT_V44)
    ap.add_argument("--compare-v45", type=Path, default=DEFAULT_V45)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.dem) as src:
        dem = src.read(1).astype(np.float64)
        profile = src.profile.copy()
        transform = src.transform
        bounds = src.bounds
        crs = src.crs
        nodata = src.nodata
        if crs is None:
            raise ValueError("Base DEM has no CRS")
        valid = np.isfinite(dem)
        if nodata is not None:
            valid &= dem != nodata

    xres = float(abs(transform.a))
    yres = float(abs(transform.e))
    if not np.isclose(xres, yres):
        raise ValueError(f"Expected square DEM cells, got {xres} x {yres}")
    cellsize = xres

    shapes, way_meta, osm_meta = load_osm_waterways(
        args.osm, crs, args.osm_max_timestamp or None
    )
    if not shapes:
        raise RuntimeError("No supported OSM waterways were found")

    way_id_raster = rasterize(
        shapes,
        out_shape=dem.shape,
        transform=transform,
        fill=0,
        dtype="int64",
        all_touched=True,
    )
    waterway_mask = way_id_raster > 0
    if not np.any(waterway_mask):
        raise RuntimeError("OSM waterways do not intersect the DEM grid")

    dist_cells, nearest = distance_transform_edt(~waterway_mask, return_indices=True)
    dist_m = dist_cells * cellsize
    nearest_way_id = way_id_raster[nearest[0], nearest[1]]

    hydro_shapes, reach_meta, hydro_meta = load_hydrorivers(args.hydrorivers, crs, bounds)
    if not hydro_shapes:
        raise RuntimeError("No HydroRIVERS reaches intersect the DEM grid")
    hydro_id_raster = rasterize(
        hydro_shapes,
        out_shape=dem.shape,
        transform=transform,
        fill=0,
        dtype="int32",
        all_touched=True,
    )
    hydro_mask = hydro_id_raster > 0
    hydro_dist_cells, hydro_nearest = distance_transform_edt(~hydro_mask, return_indices=True)
    hydro_dist_m = hydro_dist_cells * cellsize
    nearest_hydro_id = hydro_id_raster[hydro_nearest[0], hydro_nearest[1]]

    dem_for_min = np.where(valid, dem, np.inf)
    local_min = minimum_filter(dem_for_min, size=args.relief_window, mode="nearest")
    relief = np.where(valid, dem - local_min, np.nan)
    slope = slope_degrees(dem, valid, xres, yres)

    corridor_m = args.corridor_cells * cellsize
    hydro_corridor_m = args.hydro_corridor_cells * cellsize
    terrain_obstruction = (
        valid
        & (relief >= args.relief_threshold_m)
        & (slope <= args.max_slope_deg)
        & (dem <= args.max_elevation_m)
    )
    near_osm = dist_m <= corridor_m
    near_hydro = hydro_dist_m <= hydro_corridor_m
    candidate = terrain_obstruction & (near_osm | near_hydro)
    consensus = terrain_obstruction & near_osm & near_hydro
    candidate_tier = np.zeros(dem.shape, dtype=np.uint8)
    candidate_tier[candidate] = 1
    candidate_tier[consensus] = 2

    delta_v44 = aligned_delta(args.dem, args.compare_v44, dem, profile)
    delta_v45 = aligned_delta(args.dem, args.compare_v45, dem, profile)
    delta_v45_v44 = None if delta_v44 is None or delta_v45 is None else delta_v45 - delta_v44

    rows, cols = np.nonzero(candidate)
    csv_path = args.out_dir / "V46_obstruction_candidates.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "row", "col", "x", "y", "original_z_m", "distance_to_osm_m",
            "nearest_osm_way_id", "nearest_osm_waterway", "nearest_osm_name",
            "distance_to_hydrorivers_m", "nearest_hyriv_id", "hyriv_upland_skm",
            "hyriv_dis_av_cms", "hyriv_strahler_order",
            "local_relief_m", "slope_deg", "v44_minus_v41_m", "v45_minus_v41_m",
            "v45_minus_v44_m",
            "evidence_count", "reason_code", "review_status",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r, c in zip(rows.tolist(), cols.tolist()):
            x, y = rasterio.transform.xy(transform, r, c, offset="center")
            wid = int(nearest_way_id[r, c])
            wm = way_meta.get(wid, {})
            hid = int(nearest_hydro_id[r, c])
            hm = reach_meta.get(hid, {})
            has_osm = bool(near_osm[r, c])
            has_hydro = bool(near_hydro[r, c])
            evidence_count = 1 + int(has_osm) + int(has_hydro)
            if has_osm and has_hydro:
                reason_code = "OSM_HYDRORIVERS_PLUS_TERRAIN"
                review_status = "TIER_A_CONSENSUS_CANDIDATE"
            elif has_osm:
                reason_code = "OSM_PLUS_TERRAIN"
                review_status = "TIER_B_OSM_ONLY_REVIEW"
            else:
                reason_code = "HYDRORIVERS_PLUS_TERRAIN"
                review_status = "TIER_B_HYDRORIVERS_ONLY_REVIEW"
            writer.writerow({
                "row": r,
                "col": c,
                "x": f"{x:.3f}",
                "y": f"{y:.3f}",
                "original_z_m": f"{dem[r, c]:.3f}",
                "distance_to_osm_m": f"{dist_m[r, c]:.3f}",
                "nearest_osm_way_id": wid,
                "nearest_osm_waterway": wm.get("waterway"),
                "nearest_osm_name": wm.get("name") or wm.get("name_en") or "",
                "distance_to_hydrorivers_m": f"{hydro_dist_m[r, c]:.3f}",
                "nearest_hyriv_id": hid,
                "hyriv_upland_skm": hm.get("upland_skm", ""),
                "hyriv_dis_av_cms": hm.get("dis_av_cms", ""),
                "hyriv_strahler_order": hm.get("ord_stra", ""),
                "local_relief_m": f"{relief[r, c]:.3f}",
                "slope_deg": f"{slope[r, c]:.3f}",
                "v44_minus_v41_m": "" if delta_v44 is None else f"{delta_v44[r, c]:.3f}",
                "v45_minus_v41_m": "" if delta_v45 is None else f"{delta_v45[r, c]:.3f}",
                "v45_minus_v44_m": "" if delta_v45_v44 is None else f"{delta_v45_v44[r, c]:.3f}",
                "evidence_count": evidence_count,
                "reason_code": reason_code,
                "review_status": review_status,
            })

    mask_path = args.out_dir / "V46_obstruction_candidates.tif"
    tier_path = args.out_dir / "V46_obstruction_candidate_tier.tif"
    distance_path = args.out_dir / "V46_distance_to_osm_waterway_m.tif"
    hydro_distance_path = args.out_dir / "V46_distance_to_hydrorivers_m.tif"
    relief_path = args.out_dir / "V46_local_relief_m.tif"
    write_uint8_tif(mask_path, candidate, profile)
    write_uint8_tif(tier_path, candidate_tier, profile)
    write_float_tif(distance_path, np.where(valid, dist_m, np.nan), profile)
    write_float_tif(hydro_distance_path, np.where(valid, hydro_dist_m, np.nan), profile)
    write_float_tif(relief_path, relief, profile)

    v44_changed = None if delta_v44 is None else np.abs(delta_v44) > 1e-3
    v45_changed = None if delta_v45 is None else np.abs(delta_v45) > 1e-3
    v45_added_changed = None if delta_v45_v44 is None else np.abs(delta_v45_v44) > 1e-3
    candidate_count = int(candidate.sum())
    consensus_count = int(consensus.sum())

    def overlap(mask: np.ndarray | None) -> dict | None:
        if mask is None:
            return None
        shared = int(np.sum(candidate & mask))
        return {
            "changed_cells": int(mask.sum()),
            "candidate_overlap_cells": shared,
            "candidate_overlap_fraction": 0.0 if candidate_count == 0 else shared / candidate_count,
            "changed_overlap_fraction": 0.0 if int(mask.sum()) == 0 else shared / int(mask.sum()),
        }

    summary = {
        "status": "DRY_RUN_ONLY_NO_DEM_MODIFICATION",
        "scientific_holdout": {
            "sentinel1_2021_used_for_candidate_selection": False,
            "note": "2021 Sentinel-1 flood extent is intentionally reserved for later validation.",
        },
        "base_dem": {
            "path": str(args.dem),
            "sha256": sha256(args.dem),
            "shape": list(dem.shape),
            "crs": str(crs),
            "cellsize_m": cellsize,
            "nodata": nodata,
        },
        "osm": {
            "path": str(args.osm),
            "sha256": sha256(args.osm) if args.osm.is_file() else None,
            **osm_meta,
        },
        "hydrorivers": hydro_meta,
        "parameters": {
            "corridor_cells": args.corridor_cells,
            "corridor_m": corridor_m,
            "hydro_corridor_cells": args.hydro_corridor_cells,
            "hydro_corridor_m": hydro_corridor_m,
            "relief_threshold_m": args.relief_threshold_m,
            "relief_window": args.relief_window,
            "max_slope_deg": args.max_slope_deg,
            "max_elevation_m": args.max_elevation_m,
            "supported_waterways": sorted(SUPPORTED_WATERWAYS),
        },
        "results": {
            "waterway_grid_cells": int(waterway_mask.sum()),
            "hydrorivers_grid_cells": int(hydro_mask.sum()),
            "candidate_cells": candidate_count,
            "candidate_area_km2": candidate_count * cellsize * cellsize / 1_000_000.0,
            "tier_a_consensus_cells": consensus_count,
            "tier_a_consensus_area_km2": consensus_count * cellsize * cellsize / 1_000_000.0,
            "tier_b_single_source_cells": candidate_count - consensus_count,
            "candidate_relief_min_m": None if candidate_count == 0 else float(np.nanmin(relief[candidate])),
            "candidate_relief_median_m": None if candidate_count == 0 else float(np.nanmedian(relief[candidate])),
            "candidate_relief_max_m": None if candidate_count == 0 else float(np.nanmax(relief[candidate])),
            "v44_legacy_overlap": overlap(v44_changed),
            "v45_total_lineage_overlap": overlap(v45_changed),
            "v45_added_vs_v44_overlap": overlap(v45_added_changed),
        },
        "outputs": {
            "candidate_csv": str(csv_path),
            "candidate_mask": str(mask_path),
            "candidate_tier": str(tier_path),
            "distance_to_osm": str(distance_path),
            "distance_to_hydrorivers": str(hydro_distance_path),
            "local_relief": str(relief_path),
        },
        "limitations": [
            "Tier A is source consensus only; it is not yet an approved DEM cut.",
            "No cut depth or conditioned elevation is proposed in this stage.",
            "Flow accumulation, JRC pre-2021 water occurrence, MERIT Hydro and clean HAND are not yet integrated.",
            "OSM is an Overpass attic snapshot fixed at 2021-11-25T00:00:00Z, before the held-out 2021-11-30 Sentinel-1 flood acquisition; later OSM edits are excluded.",
            "HydroRIVERS is coarser and omits small channels; distance tolerance is therefore wider than for OSM.",
        ],
    }

    summary_path = args.out_dir / "V46_dryrun_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "algorithm": "v46_conditioning_dryrun.py",
        "algorithm_sha256": sha256(Path(__file__)),
        "inputs": {
            str(args.dem): sha256(args.dem),
            **(
                {str(args.osm): sha256(args.osm)}
                if args.osm.is_file()
                else osm_meta["source_file_sha256"]
            ),
            **hydro_meta["source_file_sha256"],
            **({str(args.compare_v44): sha256(args.compare_v44)} if args.compare_v44.exists() else {}),
            **({str(args.compare_v45): sha256(args.compare_v45)} if args.compare_v45.exists() else {}),
        },
        "outputs": {
            str(p): sha256(p)
            for p in [
                csv_path,
                mask_path,
                tier_path,
                distance_path,
                hydro_distance_path,
                relief_path,
                summary_path,
            ]
        },
    }
    manifest_path = args.out_dir / "V46_dryrun_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": summary["status"],
        "osm_waterway_ways": osm_meta["waterway_way_count"],
        "hydrorivers_reaches": hydro_meta["reach_count"],
        "candidate_cells": candidate_count,
        "tier_a_consensus_cells": consensus_count,
        "candidate_area_km2": summary["results"]["candidate_area_km2"],
        "summary": str(summary_path),
        "manifest": str(manifest_path),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
