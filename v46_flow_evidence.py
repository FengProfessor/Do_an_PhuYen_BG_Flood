"""Terrain-derived drainage evidence for the V46 stable candidate core.

The base DEM file is never modified. Pysheds performs standard pit/depression
filling only on an in-memory copy so D8 flow accumulation can be used as an
independent evidence feature for candidate review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from pysheds.grid import Grid


ROOT = Path(r"D:/VTP")
DEFAULT_DEM = ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m_V41.asc"
DEFAULT_CORE = ROOT / "V46_stable_core_20260930/V46_stable_tierA_core.tif"
DEFAULT_OUT = ROOT / "V46_flow_evidence_20260930"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    ap.add_argument("--stable-core", type=Path, default=DEFAULT_CORE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.dem) as src:
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
        shape = src.shape
        cell_area_km2 = abs(transform.a * transform.e) / 1_000_000.0

    with rasterio.open(args.stable_core) as src:
        if src.shape != shape or src.transform != transform or src.crs != crs:
            raise ValueError("Stable core is not aligned with the base DEM")
        stable = src.read(1) > 0

    grid = Grid.from_raster(str(args.dem))
    dem = grid.read_raster(str(args.dem))
    pit_filled = grid.fill_pits(dem)
    depression_filled = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(depression_filled)
    fdir = grid.flowdir(inflated)
    acc = np.asarray(grid.accumulation(fdir), dtype=np.float64)
    if acc.shape != shape:
        raise ValueError(f"Unexpected accumulation shape: {acc.shape} != {shape}")

    acc_path = args.out_dir / "V46_V41_D8_flow_accumulation_cells.tif"
    p = profile.copy()
    p.update(driver="GTiff", dtype="float32", count=1, compress="deflate", nodata=0.0)
    with rasterio.open(acc_path, "w", **p) as dst:
        dst.write(acc.astype(np.float32), 1)
        dst.set_band_description(1, "D8 flow accumulation in contributing cells")
        dst.update_tags(
            SOURCE_DEM=str(args.dem),
            METHOD="pysheds fill_pits + fill_depressions + resolve_flats + D8 accumulation",
            BASE_DEM_MODIFIED="false",
        )

    rows, cols = np.nonzero(stable)
    csv_path = args.out_dir / "V46_stable_core_flow_evidence.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["row", "col", "x", "y", "flow_acc_cells", "upstream_area_km2"],
        )
        writer.writeheader()
        for r, c in zip(rows.tolist(), cols.tolist()):
            x, y = rasterio.transform.xy(transform, r, c, offset="center")
            writer.writerow({
                "row": r,
                "col": c,
                "x": f"{x:.3f}",
                "y": f"{y:.3f}",
                "flow_acc_cells": f"{acc[r, c]:.3f}",
                "upstream_area_km2": f"{acc[r, c] * cell_area_km2:.6f}",
            })

    vals = acc[stable]
    area = vals * cell_area_km2
    q = np.quantile(area, [0.0, 0.25, 0.5, 0.75, 0.9, 0.95, 1.0]).tolist()
    summary = {
        "status": "FLOW_EVIDENCE_ONLY_NO_BASE_DEM_MODIFICATION",
        "base_dem": {"path": str(args.dem), "sha256": sha256(args.dem)},
        "stable_core": {"path": str(args.stable_core), "sha256": sha256(args.stable_core)},
        "method": "pysheds D8 after in-memory pit/depression fill and flat resolution",
        "cell_area_km2": cell_area_km2,
        "stable_core_cells": int(stable.sum()),
        "upstream_area_km2_quantiles": {
            "min": q[0], "p25": q[1], "median": q[2], "p75": q[3],
            "p90": q[4], "p95": q[5], "max": q[6],
        },
        "threshold_context": {
            "cells_ge_500": int((vals >= 500).sum()),
            "area_ge_0_45_km2": int((area >= 0.45).sum()),
            "area_ge_10_km2": int((area >= 10.0).sum()),
            "note": "Threshold counts are diagnostics only; they do not approve or reject a breach.",
        },
        "outputs": {"accumulation_raster": str(acc_path), "stable_core_csv": str(csv_path)},
    }
    summary_path = args.out_dir / "V46_flow_evidence_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "algorithm": str(Path(__file__)),
        "algorithm_sha256": sha256(Path(__file__)),
        "inputs": {
            str(args.dem): sha256(args.dem),
            str(args.stable_core): sha256(args.stable_core),
        },
        "outputs": {
            str(acc_path): sha256(acc_path),
            str(csv_path): sha256(csv_path),
            str(summary_path): sha256(summary_path),
        },
    }
    manifest_path = args.out_dir / "V46_flow_evidence_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "stable_core_cells": int(stable.sum()),
        "median_upstream_area_km2": q[2],
        "cells_area_ge_10_km2": int((area >= 10.0).sum()),
        "summary": str(summary_path),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
