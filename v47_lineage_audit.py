"""Reproduce the V41 conditioning path and quantify inherited pre-V41 edits.

This is a read-only audit of the raster inputs.  It writes one JSON report and
does not modify any DEM or thesis document.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from skimage.morphology import reconstruction


ROOT = Path(r"D:\VTP")
GIS = ROOT / "05-Du-lieu-GIS"
OUT = ROOT / "V47_lineage_audit_20261001.json"
NODATA = -9999.0
DELTA_EPS = 5e-4


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_asc(name: str) -> np.ndarray:
    # V35.asc contains a duplicated six-line ESRI header; GDAL can still read
    # it, while the other files should be loaded from their text values so the
    # V41 three-decimal reproduction is exact in float64.
    if name == "PhuYen_DEM_30m_V35.asc":
        with rasterio.open(GIS / name) as src:
            return src.read(1).astype(np.float64)
    return np.loadtxt(GIS / name, skiprows=6)


def priority_flood_equivalent(dem: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Equivalent to process_dem.py for a fully populated 8-neighbour grid.

    Morphological reconstruction by erosion is the same depression-filling
    operation as the Python heap Priority-Flood used by process_dem.py.  The
    exact equivalence is checked below against the stored V41 raster.
    """
    clipped = np.where((dem < 0) & (dem != NODATA), 0.0, dem)
    valid = clipped != NODATA
    marker = np.full_like(clipped, clipped[valid].max())
    marker[0, :] = clipped[0, :]
    marker[-1, :] = clipped[-1, :]
    marker[:, 0] = clipped[:, 0]
    marker[:, -1] = clipped[:, -1]
    filled = reconstruction(
        marker,
        clipped,
        method="erosion",
        footprint=np.ones((3, 3), dtype=bool),
    )
    gradient = 0.001 * (dem.shape[1] - 1 - np.arange(dem.shape[1], dtype=float))[None, :]
    conditioned = np.where(valid, filled + gradient, NODATA)
    # process_dem.py stores three decimals in the ESRI ASCII output.
    return np.round(conditioned, 3), filled


def delta_summary(a: np.ndarray, b: np.ndarray, valid: np.ndarray) -> dict:
    delta = b - a
    changed = valid & (np.abs(delta) > DELTA_EPS)
    values = delta[changed]
    if values.size == 0:
        return {"changed_cells": 0}
    return {
        "changed_cells": int(changed.sum()),
        "min_m": float(values.min()),
        "median_m": float(np.median(values)),
        "max_m": float(values.max()),
        "sum_cell_m": float(values.sum()),
        "abs_ge_0_1m_cells": int((np.abs(values) >= 0.1).sum()),
        "abs_ge_1m_cells": int((np.abs(values) >= 1.0).sum()),
        "abs_ge_2m_cells": int((np.abs(values) >= 2.0).sum()),
    }


def main() -> None:
    raw = read_asc("PhuYen_DEM_30m.asc")
    v35 = read_asc("PhuYen_DEM_30m_V35.asc")
    v35_fixed = read_asc("PhuYen_DEM_30m_V35_fixed.asc")
    v39 = read_asc("PhuYen_DEM_30m_V39_Safe.asc")
    v41 = read_asc("PhuYen_DEM_30m_V41.asc")
    valid = v41 != NODATA

    # V35_fixed has the same raster values as V35, but a clean six-line ASCII
    # header.  Compare raw -> V35_fixed so float32 GDAL parsing of the malformed
    # V35 header does not turn harmless sub-millimetre roundoff into changes.
    raw_to_v35 = v35_fixed - raw
    raw_to_v35_mask = valid & (np.abs(raw_to_v35) > DELTA_EPS)
    v35_to_fixed = v35_fixed - v35
    v35_to_fixed_mask = valid & (np.abs(v35_to_fixed) > DELTA_EPS)
    fixed_to_v39 = v39 - v35_fixed
    fixed_to_v39_mask = valid & (np.abs(fixed_to_v39) > DELTA_EPS)

    cond_raw, fill_raw = priority_flood_equivalent(raw)
    cond_v35, fill_v35 = priority_flood_equivalent(v35_fixed)
    cond_v39, fill_v39 = priority_flood_equivalent(v39)

    exact_reproduction = valid & (cond_v39 == v41)
    v39_effect = cond_v39 - cond_v35
    v39_effect_mask = valid & (np.abs(v39_effect) > DELTA_EPS)

    report = {
        "status": "PASS" if int(exact_reproduction.sum()) == int(valid.sum()) else "FAIL",
        "purpose": "Quantify inherited edits in the V41 base used by V46.",
        "files_sha256": {
            name: sha256(GIS / name)
            for name in [
                "PhuYen_DEM_30m.asc",
                "PhuYen_DEM_30m_V35.asc",
                "PhuYen_DEM_30m_V35_fixed.asc",
                "PhuYen_DEM_30m_V39_Safe.asc",
                "PhuYen_DEM_30m_V41.asc",
            ]
        },
        "pre_v41_lineage": {
            "raw_asc_to_v35_fixed": {
                **delta_summary(raw, v35_fixed, valid),
                "all_significant_deltas_m": sorted(
                    {float(x) for x in raw_to_v35[raw_to_v35_mask]}
                ),
            },
            "v35_to_v35_fixed": delta_summary(v35, v35_fixed, valid),
            "v35_fixed_to_v39_safe": {
                **delta_summary(v35_fixed, v39, valid),
                "all_deltas_minus_2_5m": bool(
                    np.allclose(fixed_to_v39[fixed_to_v39_mask], -2.5, atol=1e-9)
                ),
            },
        },
        "v41_reproduction": {
            "valid_cells": int(valid.sum()),
            "exact_equal_cells": int(exact_reproduction.sum()),
            "max_abs_diff_m": float(np.max(np.abs(cond_v39[valid] - v41[valid]))),
        },
        "counterfactual_conditioning": {
            "v35_mock_punch_effect_after_conditioning": delta_summary(cond_raw, cond_v35, valid),
            "v39_safe_effect_after_conditioning": delta_summary(cond_v35, cond_v39, valid),
            "v39_original_edit_cells": int(fixed_to_v39_mask.sum()),
            "v39_original_edit_cells_with_final_effect": int(
                np.count_nonzero(fixed_to_v39_mask & v39_effect_mask)
            ),
            "v39_original_edit_cells_fully_removed_by_fill": int(
                np.count_nonzero(fixed_to_v39_mask & ~v39_effect_mask)
            ),
            "final_effect_cells_outside_original_v39_edit_mask": int(
                np.count_nonzero(v39_effect_mask & ~fixed_to_v39_mask)
            ),
        },
        "priority_flood": {
            "raw_raised_cells": int(np.count_nonzero(fill_raw - np.where(raw < 0, 0.0, raw) > 0)),
            "v35_fixed_raised_cells": int(
                np.count_nonzero(fill_v35 - np.where(v35_fixed < 0, 0.0, v35_fixed) > 0)
            ),
            "v39_safe_raised_cells": int(
                np.count_nonzero(fill_v39 - np.where(v39 < 0, 0.0, v39) > 0)
            ),
        },
        "interpretation": [
            "A PASS only verifies numerical reproduction of the stored V41 conditioning path.",
            "It does not validate the physical correctness of the V35 or V39_Safe edits.",
            "The provenance of the road-density layer and the generation command for V39_Safe must be audited separately.",
        ],
    }

    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
