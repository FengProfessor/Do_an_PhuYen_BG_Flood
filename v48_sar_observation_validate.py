from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(r"D:\VTP")
MANIFEST = ROOT / "V48_SAR_OBSERVATION_RELEASE_20261002.json"
OUT = ROOT / "V48_SAR_OBSERVATION_VALIDATION_20261002.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_file(item: dict, failures: list[str], label: str) -> Path | None:
    path = Path(item.get("path", ""))
    if not path.is_file():
        failures.append(f"missing {label}: {path}")
        return None
    expected = item.get("sha256")
    if not expected:
        failures.append(f"missing pinned sha256 for {label}: {path}")
    elif sha256(path).lower() != str(expected).lower():
        failures.append(f"hash mismatch for {label}: {path}")
    return path


def parse_utc(value: object, failures: list[str], label: str) -> None:
    if not isinstance(value, str) or not value:
        failures.append(f"missing {label}")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        failures.append(f"invalid ISO datetime for {label}: {value}")
        return
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        failures.append(f"{label} is not explicitly UTC: {value}")


def main() -> None:
    failures: list[str] = []
    if not MANIFEST.is_file():
        raise FileNotFoundError(f"Missing SAR observation release manifest: {MANIFEST}")

    m = json.loads(MANIFEST.read_text(encoding="utf-8"))

    if m.get("status") != "V48_SAR_OBSERVATION_FROZEN_PRE_FORMAL_EVALUATION":
        failures.append("unexpected observation release status")
    if m.get("formal_bg_flood_run") is not False:
        failures.append("manifest must record formal_bg_flood_run=false")
    if m.get("formal_sar_evaluation_run") is not False:
        failures.append("manifest must record formal_sar_evaluation_run=false")
    if m.get("sentinel1_used_for_terrain_conditioning") is not False:
        failures.append("Sentinel-1 must remain held out from terrain conditioning")

    source = m.get("source", {})
    if source.get("provider") != "Microsoft Planetary Computer Sentinel-1 RTC":
        failures.append("unexpected Sentinel-1 observation provider")
    if not source.get("stac_item_id"):
        failures.append("missing source STAC item id")
    if source.get("orbit_state") != "descending":
        failures.append("source orbit state drifted from probed descending acquisition")
    if source.get("relative_orbit") != 120:
        failures.append("source relative orbit drifted from probed orbit 120")
    parse_utc(source.get("start_datetime_utc"), failures, "source start acquisition UTC")
    parse_utc(source.get("end_datetime_utc"), failures, "source end acquisition UTC")
    if not str(source.get("vv_asset_href", "")).startswith("https://"):
        failures.append("missing HTTPS VV source asset href")
    source_http = source.get("vv_asset_http", {})
    if not any(source_http.get(k) is not None for k in ("etag", "content_length", "last_modified")):
        failures.append("source HTTP identity metadata is empty")
    check_file(source.get("stac_probe", {}), failures, "STAC probe")
    check_file(source.get("range_read_probe", {}), failures, "range-read probe")

    processing = m.get("processing", {})
    script_path = check_file(processing.get("script", {}), failures, "processing script")
    base_path = check_file(processing.get("target_grid_reference", {}), failures, "target grid reference")
    if processing.get("input_polarization") != "VV":
        failures.append("input polarization must be VV")
    if processing.get("rtc_to_target_resampling") != "average":
        failures.append("RTC-to-target resampling must remain average")
    if processing.get("target_crs") != "EPSG:32649":
        failures.append("target CRS must remain EPSG:32649")
    if float(processing.get("target_resolution_m", -1)) != 30.0:
        failures.append("target resolution must remain 30 m")
    if processing.get("backscatter_transform") != "10*log10(linear_RTC_VV)":
        failures.append("unexpected backscatter transform")
    if processing.get("otsu_bins") != 512:
        failures.append("Otsu bin count must remain 512")
    threshold = processing.get("otsu_threshold_db")
    if not isinstance(threshold, (int, float)) or not np.isfinite(float(threshold)):
        failures.append("Otsu threshold is missing or non-finite")
    expected_classes = {
        "0": "observed dry candidate (VV dB > Otsu threshold)",
        "1": "observed water/flood candidate (VV dB <= Otsu threshold), before permanent-water exclusion",
        "255": "NoData/excluded",
    }
    if processing.get("classification") != expected_classes:
        failures.append("classification semantics differ from frozen V48 definition")
    if processing.get("threshold_tuning_after_build") is not False:
        failures.append("threshold_tuning_after_build must remain false")

    observation = m.get("observation", {})
    tif_path = check_file(observation.get("tif", {}), failures, "observation GeoTIFF")
    check_file(observation.get("asc", {}), failures, "observation ASCII grid")
    check_file(observation.get("prj", {}), failures, "observation projection file")

    observed_counts: dict[str, int] | None = None
    observed_classes: list[int] | None = None
    if tif_path is not None and base_path is not None:
        with rasterio.open(base_path) as base_ds, rasterio.open(tif_path) as obs_ds:
            if obs_ds.width != base_ds.width or obs_ds.height != base_ds.height:
                failures.append("observation dimensions do not match V48 base grid")
            if obs_ds.crs != base_ds.crs:
                failures.append("observation CRS does not match V48 base grid")
            if obs_ds.transform != base_ds.transform:
                failures.append("observation transform does not match V48 base grid")
            if obs_ds.dtypes[0] != "uint8":
                failures.append(f"observation dtype must be uint8, found {obs_ds.dtypes[0]}")
            if obs_ds.nodata != 255:
                failures.append(f"observation nodata must be 255, found {obs_ds.nodata}")
            arr = obs_ds.read(1)
            unique, counts = np.unique(arr, return_counts=True)
            observed_classes = [int(v) for v in unique.tolist()]
            invalid = sorted(set(observed_classes) - {0, 1, 255})
            if invalid:
                failures.append(f"unexpected observation class values: {invalid}")
            if 0 not in observed_classes or 1 not in observed_classes:
                failures.append("observation must contain both class 0 and class 1")
            observed_counts = {
                "class_0_dry_candidate": int(np.count_nonzero(arr == 0)),
                "class_1_water_flood_candidate": int(np.count_nonzero(arr == 1)),
                "nodata": int(np.count_nonzero(arr == 255)),
            }
            if observation.get("counts") != observed_counts:
                failures.append("manifest class counts do not match observation GeoTIFF")
            if observation.get("width") != obs_ds.width or observation.get("height") != obs_ds.height:
                failures.append("manifest dimensions do not match observation GeoTIFF")
            if observation.get("crs") != str(obs_ds.crs):
                failures.append("manifest CRS does not match observation GeoTIFF")
            if float(observation.get("resolution_m", -1)) != float(obs_ds.res[0]):
                failures.append("manifest resolution does not match observation GeoTIFF")
            if observation.get("nodata") != 255:
                failures.append("manifest nodata must be 255")

            tags = obs_ds.tags()
            if tags.get("SOURCE_STAC_ITEM_ID") != source.get("stac_item_id"):
                failures.append("GeoTIFF source STAC item tag does not match manifest")
            if tags.get("ACQUISITION_START_UTC") != str(source.get("start_datetime_utc")):
                failures.append("GeoTIFF acquisition start tag does not match manifest")
            if tags.get("ACQUISITION_END_UTC") != str(source.get("end_datetime_utc")):
                failures.append("GeoTIFF acquisition end tag does not match manifest")
            if tags.get("CLASS_0") != "observed dry candidate":
                failures.append("GeoTIFF CLASS_0 semantic tag mismatch")
            if tags.get("CLASS_1") != "observed water/flood candidate before permanent-water exclusion":
                failures.append("GeoTIFF CLASS_1 semantic tag mismatch")
            if tags.get("SENTINEL1_USED_FOR_TERRAIN_CONDITIONING") != "false":
                failures.append("GeoTIFF must record Sentinel-1 held out from terrain conditioning")

    result = {
        "status": "PASS_V48_SAR_OBSERVATION_VALIDATION" if not failures else "FAIL_V48_SAR_OBSERVATION_VALIDATION",
        "manifest": str(MANIFEST),
        "manifest_sha256": sha256(MANIFEST),
        "processing_script": str(script_path) if script_path else None,
        "observation_tif": str(tif_path) if tif_path else None,
        "observed_classes": observed_classes,
        "observed_counts": observed_counts,
        "failures": failures,
        "formal_bg_flood_run": False,
        "formal_sar_evaluation_run": False,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
