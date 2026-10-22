from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(r"D:\VTP")
SOURCE = ROOT / "V48_research_20261002/candidate_baseline_strict_1_2/V46_obstruction_candidate_tier.tif"
OUT_DIR = ROOT / "V48_research_20261002/topology_raw815"
CORE = OUT_DIR / "V48_baseline815_core.tif"
MANIFEST = OUT_DIR / "V48_baseline815_core_manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with rasterio.open(SOURCE) as src:
        tier = src.read(1)
        profile = src.profile.copy()

    core = (tier == 2).astype(np.uint8)
    profile.update(dtype="uint8", count=1, nodata=0, compress="deflate")
    with rasterio.open(CORE, "w", **profile) as dst:
        dst.write(core, 1)

    manifest = {
        "status": "PASS",
        "purpose": "Raw-Copernicus V48 baseline Tier-A core for topology dry-run",
        "source_tier_raster": str(SOURCE),
        "source_sha256": sha256(SOURCE),
        "core": str(CORE),
        "core_sha256": sha256(CORE),
        "core_cells": int(core.sum()),
        "sentinel1_2021_used": False,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
