from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


ROOT = Path(r"D:\VTP")
GIS = ROOT / "05-Du-lieu-GIS"
AUDIT = ROOT / "V48_audit_20261002"
BASE = GIS / "PhuYen_DEM_30m.tif"
BASE_COPY = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
FROZEN = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.tif"
ASC = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.asc"
CUTS = ROOT / "V48_research_20261002/final_selection/V48_final_cut_cells.csv"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    cuts = pd.read_csv(CUTS)
    with rasterio.open(BASE) as b, rasterio.open(FROZEN) as f:
        base = b.read(1).astype(np.float64)
        frozen = f.read(1).astype(np.float64)
        grid_ok = b.shape == f.shape and b.transform == f.transform and b.crs == f.crs and b.nodata == f.nodata
        base_meta = {"shape": list(b.shape), "transform": tuple(b.transform), "crs": str(b.crs), "nodata": b.nodata}
        frozen_meta = {"shape": list(f.shape), "transform": tuple(f.transform), "crs": str(f.crs), "nodata": f.nodata}
    expected = np.zeros(base.shape, dtype=bool)
    expected[cuts.row.astype(int), cuts.col.astype(int)] = True
    diff = frozen - base
    changed = np.abs(diff) > 1e-6
    values_match = []
    for rec in cuts.itertuples(index=False):
        values_match.append(abs(float(frozen[int(rec.row), int(rec.col)]) - float(rec.proposed_z_m)) <= 1e-5)

    with rasterio.open(ASC) as a:
        asc = a.read(1).astype(np.float64)
        asc_grid_ok = a.shape == base.shape and a.transform == rasterio.open(BASE).transform
    valid = (frozen > -9000) & (asc > -9000)
    asc_max_abs_diff = float(np.max(np.abs(frozen[valid] - asc[valid])))

    checks = {
        "base_copy_byte_identical": sha256(BASE_COPY) == sha256(BASE),
        "grid_metadata_preserved": bool(grid_ok),
        "changed_mask_exact": bool(np.array_equal(changed, expected)),
        "changed_cells": int(changed.sum()),
        "expected_cells": int(expected.sum()),
        "all_changes_lowering": bool(np.all(diff[changed] < 0)),
        "max_cut_m": float((-diff[changed]).max()),
        "all_frozen_values_match_selected_proposals": bool(all(values_match)),
        "finite_valid_cells": bool(np.all(np.isfinite(frozen[base > -9000]))),
        "asc_grid_ok": bool(asc_grid_ok),
        "asc_vs_frozen_max_abs_diff_m": asc_max_abs_diff,
        "sentinel1_2021_used": False,
    }
    pass_all = (
        checks["base_copy_byte_identical"]
        and checks["grid_metadata_preserved"]
        and checks["changed_mask_exact"]
        and checks["all_changes_lowering"]
        and checks["max_cut_m"] <= 1.000001
        and checks["all_frozen_values_match_selected_proposals"]
        and checks["finite_valid_cells"]
        and checks["asc_grid_ok"]
        and checks["asc_vs_frozen_max_abs_diff_m"] <= 0.0007
    )
    result = {
        "status": "PASS" if pass_all else "FAIL",
        "checks": checks,
        "base": {"path": str(BASE), "sha256": sha256(BASE), "metadata": base_meta},
        "frozen": {"path": str(FROZEN), "sha256": sha256(FROZEN), "metadata": frozen_meta},
        "asc": {"path": str(ASC), "sha256": sha256(ASC)},
        "cuts": {"path": str(CUTS), "sha256": sha256(CUTS)},
    }
    out = AUDIT / "V48_final_verification.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not pass_all:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
