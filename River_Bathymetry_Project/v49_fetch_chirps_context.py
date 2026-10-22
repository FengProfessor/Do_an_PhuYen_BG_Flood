"""Acquire CHIRPS pentad context separately from frozen V49-G forcing."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import fiona
import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds
from shapely.geometry import box, shape
from shapely.ops import transform as geometry_transform, unary_union

PROJECT = Path("D:/VTP/River_Bathymetry_Project")
OUT = PROJECT / "V49_RESEARCH_20261014/CHIRPS_CONTEXT"
URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/pentads/global/cogs/chirps-v3.0.2021.11.6.cog"
DOC = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/README-CHIRPSv3.0.txt"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sources = []
    for url, name in [(URL, "chirps-v3.0.2021.11.6.cog"), (DOC, "README-CHIRPSv3.0.txt")]:
        path = OUT / name
        response = requests.head(url, timeout=(10, 45)) if path.exists() else requests.get(url, timeout=(10, 45))
        response.raise_for_status()
        if not path.exists():
            path.write_bytes(response.content)
        if response.headers.get("Content-Length"):
            assert path.stat().st_size == int(response.headers["Content-Length"])
        sources.append({"url": url, "path": str(path), "bytes": path.stat().st_size,
                        "sha256": digest(path), "http_last_modified": response.headers.get("Last-Modified"),
                        "http_etag": response.headers.get("ETag")})
    with rasterio.open(PROJECT / "V49_R3_20261013/E/V49_E_hydraulic_bed.tif") as dem:
        domain = box(*dem.bounds)
        crs = dem.crs
        geographic_bounds = transform_bounds(crs, "EPSG:4326", *dem.bounds, densify_pts=21)
    with fiona.open(PROJECT / "V49_R3_20261013/C/V49_waterbody_classification.gpkg", layer="classified_objects") as objects:
        ocean = unary_union([shape(f["geometry"]) for f in objects if f["properties"]["final_class"] == "OCEAN"])
    outside_ocean = domain.difference(ocean)
    with rasterio.open(OUT / "chirps-v3.0.2021.11.6.cog") as src:
        assert str(src.crs) == "EPSG:4326"
        native_window = from_bounds(*geographic_bounds, transform=src.transform)
        left, top = math.floor(native_window.col_off), math.floor(native_window.row_off)
        right = math.ceil(native_window.col_off + native_window.width)
        bottom = math.ceil(native_window.row_off + native_window.height)
        window = Window(left, top, right - left, bottom - top)
        values = src.read(1, window=window, masked=True)
        # This source COG has no GDAL NoData tag, but contains -9999 ocean
        # sentinels. CHC diagnostics documents -9999 missing values. Do not
        # convert them into zero rain or include them in spatial averages.
        negative = np.unique(values.data[values.data < 0])
        assert np.all(negative == -9999), "Unrecognized negative rainfall value"
        values = np.ma.masked_where(values.data == -9999, values)
        transform = src.window_transform(window)
        profile = src.profile.copy()
        profile.update(driver="GTiff", height=values.shape[0], width=values.shape[1],
                       transform=transform, count=1, compress="deflate", nodata=-9999)
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
        crop = OUT / "V49_CHIRPS_v3_202111_pentad6_native_crop.tif"
        with rasterio.open(crop, "w", **profile) as dst:
            dst.write(values.filled(-9999), 1)
        native = {"crs": str(src.crs), "resolution_deg": src.res, "global_shape": src.shape,
                  "source_declared_nodata": src.nodata, "observed_missing_sentinel": -9999,
                  "crop_declared_nodata": -9999, "tags": src.tags(), "crop_shape": values.shape,
                  "crop_transform": list(transform)[:6]}
    converter = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    weights, data = [], []
    for row, col in np.ndindex(values.shape):
        if np.ma.getmaskarray(values)[row, col] or not np.isfinite(values[row, col]):
            continue
        assert values[row, col] >= 0
        x0, y0 = transform * (col, row)
        x1, y1 = transform * (col + 1, row + 1)
        polygon = geometry_transform(converter.transform, box(x0, y1, x1, y0))
        area = polygon.intersection(outside_ocean).area
        if area > 0:
            weights.append(area)
            data.append(float(values[row, col]))
    weights, data = np.asarray(weights), np.asarray(data)
    assert len(data) > 0 and weights.sum() > 0
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "data_acquisition_pass": True,
              "sources": sources, "product": "CHIRPS v3.0 final pentad", "date_labels": "2021-11-26 through 2021-11-30",
              "units": "mm per pentad", "native_grid": native,
              "crop_path": str(crop), "crop_sha256": digest(crop),
              "sampling": "Native CHIRPS cell values weighted by projected footprint overlap with V49 rectangle minus R3 OCEAN inventory; no resampling",
              "intersecting_valid_native_cells": len(data), "covered_area_km2": float(weights.sum() / 1e6),
              "outside_inventory_ocean_area_km2": outside_ocean.area / 1e6,
              "coverage_fraction": float(weights.sum() / outside_ocean.area),
              "area_weighted_pentad_mean_mm": float(np.average(data, weights=weights)),
              "native_cell_min_mm": float(data.min()), "native_cell_max_mm": float(data.max()),
              "exact_model_120h_window_match": False, "scientific_validation_complete": False,
              "active_forcing_modified": False, "hydraulic_promotion_ready": False,
              "limitations": ["Pentad date labels are not proven to represent the exact V49 2021-11-25T17Z to 2021-11-30T17Z window.",
                              "CHIRPS combines satellite and stations; local station membership and ERA5 gap-fill influence are not checked here.",
                              "Outside the inventory ocean polygon is not a surveyed land mask; coastal CHIRPS NoData remains excluded.",
                              "This gridded rainfall context supplies no hourly gauge, WSE, discharge or surveyed bathymetry."]}
    (OUT / "V49_CHIRPS_context_register.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("data_acquisition_pass", "intersecting_valid_native_cells", "covered_area_km2",
                     "coverage_fraction", "area_weighted_pentad_mean_mm", "native_cell_min_mm", "native_cell_max_mm",
                     "exact_model_120h_window_match")}, indent=2))


if __name__ == "__main__":
    main()
