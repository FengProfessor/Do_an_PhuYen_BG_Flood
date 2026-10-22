"""Read only the frozen observation/support rasters, never model NetCDF."""
import hashlib
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling

ROOT = Path("D:/VTP")
P = ROOT / "River_Bathymetry_Project"
manifest = json.loads((P / "V49_G_20261013/V49_G_PREPARATION_MANIFEST.json").read_text())
paths = {"sar": Path(manifest["sentinel1"]["path"]),
         "water": ROOT / "05-Du-lieu-GIS/water_density_30m.tif",
         "hand": ROOT / "BG_Flood_Project/BG_Flood/Teamwork_Validation/PhuYen_HAND_30m.tif"}
with rasterio.open(ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif") as dem:
    shape, transform, crs = dem.shape, dem.transform, dem.crs
arrays, sources = {}, {}
for key, path in paths.items():
    dtype, missing = ("uint8", 255) if key == "sar" else ("float32", -9999)
    target = np.full(shape, missing, dtype=dtype)
    with rasterio.open(path) as src:
        reproject(source=rasterio.band(src, 1), destination=target,
                  src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                  dst_transform=transform, dst_crs=crs, dst_nodata=missing, resampling=Resampling.nearest)
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        sources[key] = {"path": str(path), "sha256": h.hexdigest(), "native_nodata": src.nodata}
    arrays[key] = target
sar, water, hand = arrays["sar"], arrays["water"], arrays["hand"]
assert sources["sar"]["sha256"] == manifest["sentinel1"]["sha256"]
mask = np.isin(sar, [0, 1]) & (water <= manifest["sentinel1"]["permanent_water_threshold"]) & (hand >= 0)
water_missing = (water == -9999) | ~np.isfinite(water)
hand_missing = (hand == -9999) | ~np.isfinite(hand)
values, counts = np.unique(sar, return_counts=True)
mask_count = int(mask.sum())
wet_count = int((mask & (sar == 1)).sum())
mask_area = mask_count * 900.0 / 1e6
assert 0 <= mask_area <= shape[0] * shape[1] * 900.0 / 1e6
report = {"scope": "Static raster/mask audit only; no SAR classification accuracy claim or active NetCDF read",
          "sources": sources, "sar_aligned_class_counts": {str(v): int(n) for v, n in zip(values, counts)},
          "primary_mask_cells": mask_count, "primary_mask_area_km2": mask_area,
          "observed_wet_cells_in_primary_mask": wet_count,
          "observed_wet_area_km2": wet_count * 900.0 / 1e6,
          "water_missing_cells_on_grid": int(water_missing.sum()),
          "water_missing_cells_in_primary_mask": int((water_missing & mask).sum()),
          "hand_missing_cells_in_primary_mask": int((hand_missing & mask).sum()),
          "sar_unknown_cells_on_grid": int((~np.isin(sar, [0, 1])).sum()),
          "physical_SAR_observability_verified": False, "hydraulic_promotion_ready": False}
(P / "V49_RESEARCH_20261014/V49_static_mask_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "sources"}, indent=2))
