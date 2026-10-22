from __future__ import annotations

import json
from pathlib import Path

import rasterio
import requests
from rasterio.windows import Window


ROOT = Path(r"D:\VTP")
STAC = ROOT / "V48_PLANETARY_S1_STAC_PROBE_20261002.json"
OUT = ROOT / "V48_PLANETARY_S1_RTC_READ_PROBE_20261002.json"
SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"


def signed_href(href: str) -> str:
    response = requests.get(SIGN_URL, params={"href": href}, timeout=60)
    response.raise_for_status()
    return response.json()["href"]


def inspect_asset(name: str, href: str) -> dict:
    signed = signed_href(href)
    with rasterio.Env(GDAL_HTTP_MULTIRANGE="YES"):
        with rasterio.open(signed) as ds:
            row = ds.height // 2
            col = ds.width // 2
            sample = ds.read(1, window=Window(col, row, 1, 1), masked=True)
            return {
                "asset": name,
                "source_href": href,
                "driver": ds.driver,
                "width": ds.width,
                "height": ds.height,
                "dtype": ds.dtypes[0],
                "count": ds.count,
                "crs": str(ds.crs),
                "transform": list(ds.transform)[:6],
                "bounds": list(ds.bounds),
                "nodata": ds.nodata,
                "center_sample": None if bool(sample.mask.all()) else float(sample.compressed()[0]),
            }


def main() -> None:
    stac = json.loads(STAC.read_text(encoding="utf-8"))
    feature = stac["collections"]["sentinel-1-rtc"]["features"][0]
    assets = feature["assets"]
    result = {
        "status": "PASS_METADATA_AND_RANGE_READ" ,
        "stac_item_id": feature["id"],
        "start_datetime": feature["properties"].get("start_datetime"),
        "end_datetime": feature["properties"].get("end_datetime"),
        "assets": {},
    }
    for name in ("vv", "vh"):
        result["assets"][name] = inspect_asset(name, assets[name]["href"])
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
