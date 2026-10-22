from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT


ROOT = Path(r"D:\VTP")
GIS = ROOT / "05-Du-lieu-GIS"
BASE = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
STAC_PROBE = ROOT / "V48_PLANETARY_S1_STAC_PROBE_20261002.json"
READ_PROBE = ROOT / "V48_PLANETARY_S1_RTC_READ_PROBE_20261002.json"
OUT_TIF = GIS / "DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif"
OUT_ASC = GIS / "DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.asc"
OUT_PRJ = GIS / "DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.prj"
MANIFEST = ROOT / "V48_SAR_OBSERVATION_RELEASE_20261002.json"
SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"

NODATA_CLASS = 255
OTSU_BINS = 512


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def signed_href(href: str) -> str:
    response = requests.get(SIGN_URL, params={"href": href}, timeout=60)
    response.raise_for_status()
    return response.json()["href"]


def otsu_threshold(values: np.ndarray, bins: int = OTSU_BINS) -> float:
    if values.size == 0:
        raise RuntimeError("No valid RTC values available for Otsu thresholding")
    hist, edges = np.histogram(values, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2.0
    hist = hist.astype(np.float64)
    w_left = np.cumsum(hist)
    w_right = np.cumsum(hist[::-1])[::-1]
    sum_left = np.cumsum(hist * centers)
    sum_right = np.cumsum((hist * centers)[::-1])[::-1]

    valid_split = (w_left[:-1] > 0) & (w_right[1:] > 0)
    between = np.full(hist.size - 1, -np.inf, dtype=np.float64)
    mu_left = np.zeros(hist.size - 1, dtype=np.float64)
    mu_right = np.zeros(hist.size - 1, dtype=np.float64)
    mu_left[valid_split] = sum_left[:-1][valid_split] / w_left[:-1][valid_split]
    mu_right[valid_split] = sum_right[1:][valid_split] / w_right[1:][valid_split]
    between[valid_split] = (
        w_left[:-1][valid_split]
        * w_right[1:][valid_split]
        * (mu_left[valid_split] - mu_right[valid_split]) ** 2
    )
    split = int(np.argmax(between))
    return float(edges[split + 1])


def write_ascii(mask: np.ndarray, transform: rasterio.Affine, nodata: int) -> None:
    nrows, ncols = mask.shape
    xll = float(transform.c)
    yll = float(transform.f + nrows * transform.e)
    cellsize = float(transform.a)
    with OUT_ASC.open("w", encoding="ascii", newline="\n") as f:
        f.write(f"ncols         {ncols}\n")
        f.write(f"nrows         {nrows}\n")
        f.write(f"xllcorner     {xll:.10f}\n")
        f.write(f"yllcorner     {yll:.10f}\n")
        f.write(f"cellsize      {cellsize:.10f}\n")
        f.write(f"NODATA_value  {nodata}\n")
        np.savetxt(f, mask, fmt="%d")


def main() -> None:
    required = [BASE, STAC_PROBE, READ_PROBE]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing observation build input(s): {missing}")

    stac = json.loads(STAC_PROBE.read_text(encoding="utf-8"))
    rtc_features = stac["collections"]["sentinel-1-rtc"]["features"]
    if len(rtc_features) != 1:
        raise RuntimeError(f"Expected exactly one RTC scene, found {len(rtc_features)}")
    feature = rtc_features[0]
    props = feature["properties"]
    asset = feature["assets"]["vv"]
    source_href = asset["href"]
    signed = signed_href(source_href)

    head = requests.head(signed, timeout=60, allow_redirects=True)
    head.raise_for_status()
    source_http = {
        "etag": head.headers.get("ETag"),
        "content_length": int(head.headers["Content-Length"]) if head.headers.get("Content-Length") else None,
        "last_modified": head.headers.get("Last-Modified"),
    }

    with rasterio.open(BASE) as base_ds:
        base = base_ds.read(1)
        base_valid = np.ones(base.shape, dtype=bool)
        if base_ds.nodata is not None:
            base_valid &= base != base_ds.nodata
        profile = base_ds.profile.copy()
        transform = base_ds.transform
        crs = base_ds.crs
        width = base_ds.width
        height = base_ds.height

        with rasterio.Env(GDAL_HTTP_MULTIRANGE="YES"):
            with rasterio.open(signed) as src:
                with WarpedVRT(
                    src,
                    crs=crs,
                    transform=transform,
                    width=width,
                    height=height,
                    src_nodata=src.nodata,
                    nodata=np.nan,
                    resampling=Resampling.average,
                    dtype="float32",
                ) as vrt:
                    vv = vrt.read(1, masked=True).astype(np.float64)

    vv_data = np.asarray(vv.filled(np.nan), dtype=np.float64)
    valid = base_valid & np.isfinite(vv_data) & (vv_data > 0.0)
    vv_db = np.full(vv_data.shape, np.nan, dtype=np.float64)
    vv_db[valid] = 10.0 * np.log10(vv_data[valid])
    threshold_db = otsu_threshold(vv_db[valid], OTSU_BINS)

    classes = np.full(vv_data.shape, NODATA_CLASS, dtype=np.uint8)
    classes[valid & (vv_db > threshold_db)] = 0
    classes[valid & (vv_db <= threshold_db)] = 1

    out_profile = profile.copy()
    out_profile.update(
        driver="GTiff",
        dtype="uint8",
        count=1,
        nodata=NODATA_CLASS,
        compress="deflate",
        predictor=2,
        tiled=True,
        blockxsize=512,
        blockysize=512,
    )
    with rasterio.open(OUT_TIF, "w", **out_profile) as dst:
        dst.write(classes, 1)
        dst.set_band_description(1, "S1_RTC_VV_OTSU_FLOOD_CLASS")
        dst.update_tags(
            V48_STATUS="FROZEN_PRE_EVALUATION_OBSERVATION",
            SOURCE_STAC_ITEM_ID=feature["id"],
            SOURCE_ASSET="vv",
            ACQUISITION_START_UTC=str(props.get("start_datetime")),
            ACQUISITION_END_UTC=str(props.get("end_datetime")),
            PROCESSING="RTC VV average-to-V48-30m then 512-bin Otsu in dB; <=threshold class 1; >threshold class 0",
            OTSU_THRESHOLD_DB=f"{threshold_db:.12f}",
            CLASS_0="observed dry candidate",
            CLASS_1="observed water/flood candidate before permanent-water exclusion",
            NODATA_CLASS=str(NODATA_CLASS),
            SENTINEL1_USED_FOR_TERRAIN_CONDITIONING="false",
            BG_FLOOD_RUN="false",
            FORMAL_EVALUATION_RUN="false",
        )

    write_ascii(classes, transform, NODATA_CLASS)
    OUT_PRJ.write_text(crs.to_wkt(), encoding="utf-8")

    counts = {
        "class_0_dry_candidate": int(np.count_nonzero(classes == 0)),
        "class_1_water_flood_candidate": int(np.count_nonzero(classes == 1)),
        "nodata": int(np.count_nonzero(classes == NODATA_CLASS)),
    }
    manifest = {
        "status": "V48_SAR_OBSERVATION_FROZEN_PRE_FORMAL_EVALUATION",
        "date": "2026-10-02",
        "formal_bg_flood_run": False,
        "formal_sar_evaluation_run": False,
        "sentinel1_used_for_terrain_conditioning": False,
        "source": {
            "provider": "Microsoft Planetary Computer Sentinel-1 RTC",
            "stac_item_id": feature["id"],
            "platform": props.get("platform"),
            "orbit_state": props.get("sat:orbit_state"),
            "relative_orbit": props.get("sat:relative_orbit"),
            "start_datetime_utc": props.get("start_datetime"),
            "end_datetime_utc": props.get("end_datetime"),
            "vv_asset_href": source_href,
            "vv_asset_http": source_http,
            "stac_probe": {"path": str(STAC_PROBE), "sha256": sha256(STAC_PROBE)},
            "range_read_probe": {"path": str(READ_PROBE), "sha256": sha256(READ_PROBE)},
        },
        "processing": {
            "script": {"path": str(Path(__file__).resolve()), "sha256": sha256(Path(__file__).resolve())},
            "target_grid_reference": {"path": str(BASE), "sha256": sha256(BASE)},
            "input_polarization": "VV",
            "rtc_to_target_resampling": "average",
            "target_crs": str(crs),
            "target_resolution_m": 30.0,
            "backscatter_transform": "10*log10(linear_RTC_VV)",
            "otsu_bins": OTSU_BINS,
            "otsu_threshold_db": threshold_db,
            "classification": {
                "0": "observed dry candidate (VV dB > Otsu threshold)",
                "1": "observed water/flood candidate (VV dB <= Otsu threshold), before permanent-water exclusion",
                "255": "NoData/excluded",
            },
            "threshold_tuning_after_build": False,
        },
        "observation": {
            "tif": {"path": str(OUT_TIF), "sha256": sha256(OUT_TIF)},
            "asc": {"path": str(OUT_ASC), "sha256": sha256(OUT_ASC)},
            "prj": {"path": str(OUT_PRJ), "sha256": sha256(OUT_PRJ)},
            "width": width,
            "height": height,
            "crs": str(crs),
            "resolution_m": 30.0,
            "nodata": NODATA_CLASS,
            "counts": counts,
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "status": manifest["status"],
        "manifest": str(MANIFEST),
        "observation_tif": str(OUT_TIF),
        "observation_sha256": manifest["observation"]["tif"]["sha256"],
        "otsu_threshold_db": threshold_db,
        "counts": counts,
        "source_stac_item_id": feature["id"],
        "source_start_utc": props.get("start_datetime"),
        "source_end_utc": props.get("end_datetime"),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
