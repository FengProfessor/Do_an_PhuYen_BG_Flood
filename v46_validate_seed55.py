"""Validate the previously frozen 55-cell coordinate seed against historical OSM.

The legacy mask is used only as a coordinate seed. Its current-OSM provenance
is not accepted as hydrologic evidence. Every retained cell must also occur in
the stable Tier-A intersection rebuilt from the 2021-11-25 Overpass attic
snapshot.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import label

ROOT = Path(r"D:/VTP")
LEGACY_SEED = ROOT / "V46_legacy_current_osm_stable_core_20260930/V46_stable_tierA_core.tif"
HISTORICAL_CORE = ROOT / "V46_stable_core_20260930/V46_stable_tierA_core.tif"
HISTORICAL_MANIFEST = ROOT / "V46_inputs/osm_historical_20211125/historical_osm_manifest.json"
OUT = ROOT / "V46_seed55_historical_validated_20260930"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(LEGACY_SEED) as a, rasterio.open(HISTORICAL_CORE) as b:
        if a.shape != b.shape or a.transform != b.transform or a.crs != b.crs:
            raise RuntimeError("legacy seed and historical stable core are not on the same grid")
        seed = a.read(1) > 0
        hist = b.read(1) > 0
        profile = a.profile.copy()
        transform = a.transform
        crs = a.crs

    seed_n = int(seed.sum())
    overlap = seed & hist
    missing = seed & ~hist
    if seed_n != 55:
        raise RuntimeError(f"expected frozen 55-cell seed, found {seed_n}")
    if np.any(missing):
        raise RuntimeError(
            f"{int(missing.sum())} frozen seed cells are not supported by historical OSM stable core"
        )

    comps, ncomp = label(overlap, np.ones((3, 3), dtype=np.uint8))
    mask_path = OUT / "V46_seed55_historical_validated_core.tif"
    comp_path = OUT / "V46_seed55_components.tif"
    p = profile.copy()
    p.update(driver="GTiff", dtype="uint8", count=1, nodata=0, compress="deflate")
    with rasterio.open(mask_path, "w", **p) as dst:
        dst.write(overlap.astype(np.uint8), 1)
    p.update(dtype="int32")
    with rasterio.open(comp_path, "w", **p) as dst:
        dst.write(comps.astype(np.int32), 1)

    rows = []
    for cid in range(1, ncomp + 1):
        rc = np.argwhere(comps == cid)
        xs, ys = [], []
        for r, c in rc:
            x, y = rasterio.transform.xy(transform, int(r), int(c), offset="center")
            xs.append(float(x))
            ys.append(float(y))
        rows.append(
            {
                "component_id": cid,
                "cells": int(len(rc)),
                "row_min": int(rc[:, 0].min()),
                "row_max": int(rc[:, 0].max()),
                "col_min": int(rc[:, 1].min()),
                "col_max": int(rc[:, 1].max()),
                "x_min": min(xs),
                "x_max": max(xs),
                "y_min": min(ys),
                "y_max": max(ys),
            }
        )
    csv_path = OUT / "V46_seed55_components.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")

    osm = json.loads(HISTORICAL_MANIFEST.read_text(encoding="utf-8"))
    summary = {
        "status": "FROZEN_55_CELL_SEED_VALIDATED_AGAINST_HISTORICAL_OSM",
        "seed_role": "coordinate_seed_only_current_osm_provenance_not_used_as_evidence",
        "legacy_seed_cells": seed_n,
        "historical_stable_cells": int(hist.sum()),
        "validated_seed_cells": int(overlap.sum()),
        "legacy_seed_cells_missing_historical_support": int(missing.sum()),
        "components": int(ncomp),
        "snapshot_utc": osm.get("snapshot_utc"),
        "historical_osm_returned_way_timestamp_max": osm.get("returned_way_timestamp_max"),
        "grid": {
            "shape": list(overlap.shape),
            "crs": str(crs),
            "transform": list(transform)[:6],
        },
        "outputs": {
            "validated_core": str(mask_path),
            "components": str(comp_path),
            "components_csv": str(csv_path),
        },
    }
    summary_path = OUT / "V46_seed55_validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "algorithm": str(Path(__file__)),
        "algorithm_sha256": sha256(Path(__file__)),
        "inputs": {
            str(LEGACY_SEED): sha256(LEGACY_SEED),
            str(HISTORICAL_CORE): sha256(HISTORICAL_CORE),
            str(HISTORICAL_MANIFEST): sha256(HISTORICAL_MANIFEST),
        },
        "outputs": {
            str(mask_path): sha256(mask_path),
            str(comp_path): sha256(comp_path),
            str(csv_path): sha256(csv_path),
            str(summary_path): sha256(summary_path),
        },
    }
    manifest_path = OUT / "V46_seed55_validation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
