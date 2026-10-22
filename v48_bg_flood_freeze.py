from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(r"D:\VTP")
ENGINE_ROOT = ROOT / "BG_Flood_Project" / "BG_Flood"
DEM_ASC = ROOT / "05-Du-lieu-GIS" / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.asc"
DEM_TIF = ROOT / "05-Du-lieu-GIS" / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.tif"
DEM_PRJ = ROOT / "05-Du-lieu-GIS" / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.prj"
SOURCE_CONFIG = ENGINE_ROOT / "BG_param_PhuYen_30m_V45.txt"
OUT_CONFIG = ENGINE_ROOT / "BG_param_PhuYen_30m_V48_FROZEN.txt"
OUT_CONTRACT = ROOT / "V48_BG_Flood_contract_20261002.json"
CLOSED_LOOP_SUMMARY = ROOT / "V48_closed_loop_direct_20261002" / "V48_closed_loop_direct_summary.json"
CLOSED_LOOP_RELEASE = ROOT / "V48_CLOSED_LOOP_FROZEN_RELEASE_20261002.json"

MINMASK = -4.0
ZSINIT = 1.0
ZSOFFSET = 0.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def asc_stats(path: Path) -> dict:
    with path.open("r", encoding="ascii") as f:
        header = {}
        for _ in range(6):
            key, value = f.readline().split()[:2]
            header[key.lower()] = float(value)
        values = np.loadtxt(f)
    nodata = header["nodata_value"]
    valid = values[values != nodata]
    return {
        "ncols": int(header["ncols"]),
        "nrows": int(header["nrows"]),
        "cellsize_m": float(header["cellsize"]),
        "nodata_value": float(nodata),
        "nodata_cells": int(np.count_nonzero(values == nodata)),
        "valid_cells": int(valid.size),
        "valid_min_m": float(valid.min()),
        "valid_max_m": float(valid.max()),
        "valid_negative_cells": int(np.count_nonzero(valid < 0.0)),
        "valid_le_minus_1m_cells": int(np.count_nonzero(valid <= -1.0)),
        "valid_cells_le_minmask": int(np.count_nonzero(valid <= MINMASK)),
    }


def main() -> None:
    config = """# ==============================================================================
# BG_Flood Configuration - Phu Yen 30 m V48 frozen input contract (pre-SAR)
# Frozen 2026-10-02. Do not edit in place; regenerate a new version if any input changes.
# ==============================================================================

# Exact frozen V48 terrain input
bathy = ../../05-Du-lieu-GIS/PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.asc;
dx = 30;
dy = 30;

# Mask policy: V48 valid minimum is -3.0 m. Keep all real negative terrain.
# BG_Flood read_input.py masks bathy <= minmask and converts ASC NoData to mask.
mask = 9999.0;
minmask = -4.0;

# Manning roughness map inherited from the evidenced V45 hydrodynamic setup
frictionmodel = -1;
roughnessmap = ../../05-Du-lieu-GIS/PhuYen_manning_30m_V43.asc;

# River forcings inherited from the evidenced V45 hydrodynamic setup
river = xa_lu_BaHa_Nov2021_V40_sync.txt, 270030, 270630, 1441000, 1443000;
river = xa_lu_BanThach_V43.txt, 276000, 277000, 1424500, 1425500;
river = xa_lu_KyLo_V40_sync.txt, 289000, 290000, 1476500, 1477500;
river = xa_lu_TuyAn_V40_sync.txt, 301000, 302000, 1473500, 1474500;

# Rainfall and infiltration inherited from the evidenced V45 hydrodynamic setup
rainfile = ../../Scenarios/rain_v34_era5_x2.txt;
il = ../../05-Du-lieu-GIS/il_30m_V36.asc;
cl = ../../05-Du-lieu-GIS/cl_30m_V36.asc;

# Cold-start water-surface policy. In current BG_Flood code this is a global WSE,
# not a water depth: zs=max(zsinit+zsoffset, zb), h=max(zs-zb, 0).
zsinit = 1.0;
zsoffset = 0.0;

# Boundary conditions inherited from V45
left = 0;
right = 2;
top = 2;
bottom = 2;

# Simulation window inherited from V45: 120 h, output every 3 h
endtime = 432000;
outputtimestep = 10800;

# Pre-SAR output name. Formal run remains gated by the SAR preregistration.
outfile = results/PhuYen_30m_V48_CLOSED_LOOP_FROZEN_PRE_SAR.nc;
outvars = zs, h, zb, u, v;
"""
    OUT_CONFIG.write_text(config, encoding="utf-8", newline="\n")

    stats = asc_stats(DEM_ASC)
    if stats["valid_cells_le_minmask"] != 0:
        raise RuntimeError("Selected minmask would mask one or more valid V48 DEM cells")
    if not stats["nodata_value"] <= MINMASK:
        raise RuntimeError("ASC NoData sentinel would not be captured by the selected minmask")

    forcing_paths = {
        "river_ba_ha": ENGINE_ROOT / "xa_lu_BaHa_Nov2021_V40_sync.txt",
        "river_ban_thach": ENGINE_ROOT / "xa_lu_BanThach_V43.txt",
        "river_ky_lo": ENGINE_ROOT / "xa_lu_KyLo_V40_sync.txt",
        "river_tuy_an": ENGINE_ROOT / "xa_lu_TuyAn_V40_sync.txt",
        "rainfall": ROOT / "Scenarios" / "rain_v34_era5_x2.txt",
        "initial_loss": ROOT / "05-Du-lieu-GIS" / "il_30m_V36.asc",
        "continuous_loss": ROOT / "05-Du-lieu-GIS" / "cl_30m_V36.asc",
        "manning": ROOT / "05-Du-lieu-GIS" / "PhuYen_manning_30m_V43.asc",
    }
    engine_paths = {
        "read_input": ENGINE_ROOT / "python" / "bg_flood" / "read_input.py",
        "param": ENGINE_ROOT / "python" / "bg_flood" / "param.py",
        "initial_conditions": ENGINE_ROOT / "python" / "bg_flood" / "initial_conditions.py",
        "init_evolv": ENGINE_ROOT / "python" / "bg_flood" / "init_evolv.py",
    }
    required = [DEM_ASC, DEM_TIF, DEM_PRJ, SOURCE_CONFIG, CLOSED_LOOP_SUMMARY, CLOSED_LOOP_RELEASE, *forcing_paths.values(), *engine_paths.values()]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing contract input(s): {missing}")

    closed_loop = json.loads(CLOSED_LOOP_SUMMARY.read_text(encoding="utf-8"))
    contract = {
        "status": "FROZEN_BG_FLOOD_INPUT_CONTRACT_PRE_SAR_NOT_EXECUTED",
        "date": "2026-10-02",
        "bg_flood_run": False,
        "sentinel1_2021_used": False,
        "config": {"path": str(OUT_CONFIG), "sha256": sha256(OUT_CONFIG)},
        "terrain": {
            "asc": {"path": str(DEM_ASC), "sha256": sha256(DEM_ASC)},
            "tif": {"path": str(DEM_TIF), "sha256": sha256(DEM_TIF)},
            "prj": {"path": str(DEM_PRJ), "sha256": sha256(DEM_PRJ)},
            "stats": stats,
            "minmask": MINMASK,
            "minmask_policy": "Pin minmask 1.0 m below the exact frozen DEM valid minimum (-3.0 m). This preserves every valid negative terrain cell while masking the -9999 ASC NoData sentinel under the pinned reader semantics.",
        },
        "initial_state": {
            "zsinit_m": ZSINIT,
            "zsoffset_m": ZSOFFSET,
            "semantics": "Cold start uses global water-surface elevation: zs=max(zsinit+zsoffset, zb), h=max(zs-zb, 0).",
            "lineage": "Inherited from BG_param_PhuYen_30m_V45.txt; this freeze records the previously used value and does not claim an independent V48 calibration.",
        },
        "parameters": {
            "dx_m": 30,
            "dy_m": 30,
            "frictionmodel": -1,
            "boundaries": {"left": 0, "right": 2, "top": 2, "bottom": 2},
            "endtime_s": 432000,
            "outputtimestep_s": 10800,
            "outvars": ["zs", "h", "zb", "u", "v"],
        },
        "forcing": {name: {"path": str(path), "sha256": sha256(path)} for name, path in forcing_paths.items()},
        "engine_semantics": {name: {"path": str(path), "sha256": sha256(path)} for name, path in engine_paths.items()},
        "provenance": {
            "source_v45_config": {"path": str(SOURCE_CONFIG), "sha256": sha256(SOURCE_CONFIG)},
            "forcing_lineage_note": "The exact files are frozen here because they are directly referenced by the evidenced V45 configuration. Their scientific lineage into V48 remains inherited rather than independently re-derived for V48.",
            "closed_loop_summary": {"path": str(CLOSED_LOOP_SUMMARY), "sha256": sha256(CLOSED_LOOP_SUMMARY)},
            "closed_loop_release": {"path": str(CLOSED_LOOP_RELEASE), "sha256": sha256(CLOSED_LOOP_RELEASE)},
        },
        "release_gate": {
            "closed_loop_status": closed_loop.get("status"),
            "closed_loop_final_strict_components": closed_loop.get("convergence", {}).get("final_strict_components"),
            "closed_loop_iterations_with_new_cuts": closed_loop.get("convergence", {}).get("iterations_with_new_cuts"),
            "formal_bg_flood_run_allowed": False,
            "reason": "Closed-loop terrain is frozen and the input contract is deterministic. Formal BG_Flood remains gated until the SAR preregistration validator reports READY_FOR_FORMAL_EVALUATION.",
        },
    }
    OUT_CONTRACT.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"config": str(OUT_CONFIG), "contract": str(OUT_CONTRACT), "minmask": MINMASK, "zsinit": ZSINIT, "valid_cells_le_minmask": stats["valid_cells_le_minmask"]}, indent=2))


if __name__ == "__main__":
    main()
