from __future__ import annotations

import json
from pathlib import Path

import requests


ROOT = Path(r"D:\VTP")
OUT = ROOT / "V48_PLANETARY_S1_STAC_PROBE_20261002.json"
URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"


def search(collection: str) -> dict:
    payload = {
        "collections": [collection],
        "bbox": [109.20, 13.00, 109.30, 13.10],
        "datetime": "2021-11-29T22:30:00Z/2021-11-29T22:45:00Z",
        "limit": 20,
    }
    response = requests.post(URL, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return {
        "request": payload,
        "matched": data.get("context", {}).get("matched"),
        "features": data.get("features", []),
    }


def main() -> None:
    result = {
        "status": "METADATA_PROBE_ONLY_NO_FORMAL_EVALUATION",
        "date": "2026-10-02",
        "endpoint": URL,
        "collections": {},
    }
    errors = {}
    for collection in ("sentinel-1-grd", "sentinel-1-rtc"):
        try:
            result["collections"][collection] = search(collection)
        except Exception as exc:
            errors[collection] = f"{type(exc).__name__}: {exc}"
    result["errors"] = errors
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {
        "output": str(OUT),
        "counts": {
            key: len(value.get("features", []))
            for key, value in result["collections"].items()
        },
        "errors": errors,
        "item_ids": {
            key: [feature.get("id") for feature in value.get("features", [])]
            for key, value in result["collections"].items()
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
