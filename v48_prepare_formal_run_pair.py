from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(r"D:\VTP")
GIS = ROOT / "05-Du-lieu-GIS"
BG = ROOT / "BG_Flood_Project" / "BG_Flood"

GATE = ROOT / "V48_REMEDIATION_GATE_STATUS_20261002.json"
PREREG = ROOT / "V48_SAR_preregistration_20261002.json"
PREREG_VALIDATION = ROOT / "V48_SAR_preregistration_validation_20261002.json"
CONTRACT = ROOT / "V48_BG_Flood_contract_20261002.json"
RUN_MANIFEST = ROOT / "V48_BG_Flood_RUN_MANIFEST_20261002.json"

BASE_TIF = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"
BASE_ASC = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS_FORMAL.asc"
BASE_PRJ = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS_FORMAL.prj"
COND_TIF = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.tif"
COND_ASC = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.asc"

SOURCE_CONFIG = BG / "BG_param_PhuYen_30m_V48_FROZEN.txt"
BASE_CONFIG = BG / "BG_param_PhuYen_30m_V48_FORMAL_BASE.txt"
COND_CONFIG = BG / "BG_param_PhuYen_30m_V48_FORMAL_CONDITIONED.txt"
PAIR_MANIFEST = ROOT / "V48_FORMAL_RUN_PAIR_PREP_20261002.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ref(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path), "sha256": sha256(path)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def grid_signature(path: Path) -> dict:
    with rasterio.open(path) as ds:
        return {
            "width": ds.width,
            "height": ds.height,
            "transform": list(ds.transform)[:6],
            "crs": str(ds.crs),
            "res": [float(ds.res[0]), float(ds.res[1])],
        }


def materialize_base_ascii() -> dict:
    with rasterio.open(BASE_TIF) as src:
        data = src.read(1)
        transform = src.transform
        ncols = src.width
        nrows = src.height
        xll = transform.c
        yll = transform.f + nrows * transform.e
        cellsize = transform.a
        nodata_out = -9999.0
        if src.nodata is not None:
            data = data.copy()
            data[data == src.nodata] = nodata_out
        crs_wkt = src.crs.to_wkt() if src.crs else ""

    with BASE_ASC.open("w", encoding="utf-8", newline="\n") as f:
        f.write(f"ncols         {ncols}\n")
        f.write(f"nrows         {nrows}\n")
        f.write(f"xllcorner     {xll}\n")
        f.write(f"yllcorner     {yll}\n")
        f.write(f"cellsize      {cellsize}\n")
        f.write(f"NODATA_value  {nodata_out:g}\n")
        np.savetxt(f, data, fmt="%.9g")
    BASE_PRJ.write_text(crs_wkt, encoding="utf-8")

    with rasterio.open(BASE_TIF) as tif, rasterio.open(BASE_ASC) as asc:
        require(asc.width == tif.width and asc.height == tif.height, "BASE ASC dimensions differ from BASE TIF")
        require(asc.transform == tif.transform, "BASE ASC transform differs from BASE TIF")
        tif_data = tif.read(1).astype(np.float64)
        asc_data = asc.read(1).astype(np.float64)
        if tif.nodata is not None:
            valid = tif_data != tif.nodata
        else:
            valid = np.ones(tif_data.shape, dtype=bool)
        max_abs_diff = float(np.max(np.abs(tif_data[valid] - asc_data[valid]))) if np.any(valid) else 0.0
        require(max_abs_diff <= 1e-6, f"BASE ASC round-trip differs from TIF: max abs diff {max_abs_diff}")
    return {
        "asc": ref(BASE_ASC),
        "prj": ref(BASE_PRJ),
        "roundtrip_max_abs_diff_m": max_abs_diff,
    }


def config_for_arm(source: str, bathy_rel: str, outfile_rel: str, arm: str) -> str:
    lines = source.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("bathy ="):
            out.append(f"bathy = {bathy_rel};")
        elif stripped.startswith("outfile ="):
            out.append(f"outfile = {outfile_rel};")
        elif stripped.startswith("# Exact frozen V48 terrain input"):
            out.append(f"# Formal V48 {arm} terrain input")
        elif stripped.startswith("# Pre-SAR output name"):
            out.append("# Formal run output; inputs are frozen by V48_FORMAL_RUN_PAIR_PREP_20261002.json")
        else:
            out.append(line)
    return "\n".join(out).rstrip() + "\n"


def normalized_shared_config(text: str) -> str:
    normalized: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("bathy ="):
            normalized.append("bathy = <ARM_TERRAIN>;")
        elif stripped.startswith("outfile ="):
            normalized.append("outfile = <ARM_OUTPUT>;")
        elif stripped.startswith("# Formal V48 ") and stripped.endswith(" terrain input"):
            normalized.append("# Formal V48 <ARM> terrain input")
        else:
            normalized.append(line)
    return "\n".join(normalized).rstrip() + "\n"


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    validation = json.loads(PREREG_VALIDATION.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    run_manifest = json.loads(RUN_MANIFEST.read_text(encoding="utf-8"))

    require(gate.get("overall_status") == "READY_FOR_FORMAL_EVALUATION", "V48 remediation gate is not READY")
    require(validation.get("status") == "READY_FOR_FORMAL_EVALUATION", "SAR preregistration validator is not READY")
    require(validation.get("integrity_failures") == [], "SAR preregistration has integrity failures")
    require(validation.get("formal_evaluation_blockers") == [], "SAR preregistration still has blockers")
    require(run_manifest.get("status") == "FROZEN_PRE_FORMAL_BG_FLOOD_RUN", "run manifest is not frozen pre-run")
    require(run_manifest.get("formal_bg_flood_run_started") is False, "formal BG_Flood run has already started according to run manifest")
    require(sha256(CONTRACT).lower() == prereg["hydrodynamic_contract"]["sha256"].lower(), "contract hash drift")
    require(sha256(BASE_TIF).lower() == prereg["model_arms"]["V48_BASE_COPERNICUS"]["terrain_sha256"].lower(), "BASE TIF hash drift")
    require(sha256(COND_TIF).lower() == prereg["model_arms"]["V48_CONDITIONED"]["formal_run_terrain_sha256"].lower(), "CONDITIONED TIF hash drift")

    base_grid = grid_signature(BASE_TIF)
    cond_grid = grid_signature(COND_TIF)
    require(base_grid == cond_grid, "BASE and CONDITIONED terrain grids differ")

    base_ascii = materialize_base_ascii()

    source = SOURCE_CONFIG.read_text(encoding="utf-8")
    base_text = config_for_arm(
        source,
        "../../05-Du-lieu-GIS/PhuYen_DEM_30m_V48_BASE_COPERNICUS_FORMAL.asc",
        "results/V48_FORMAL_BASE.nc",
        "BASE",
    )
    cond_text = config_for_arm(
        source,
        "../../05-Du-lieu-GIS/PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.asc",
        "results/V48_FORMAL_CONDITIONED.nc",
        "CONDITIONED",
    )
    BASE_CONFIG.write_text(base_text, encoding="utf-8", newline="\n")
    COND_CONFIG.write_text(cond_text, encoding="utf-8", newline="\n")

    base_normalized = normalized_shared_config(base_text)
    cond_normalized = normalized_shared_config(cond_text)
    require(base_normalized == cond_normalized, "Formal arm configs differ in fields other than bathy/outfile/arm comment")

    epoch = datetime.fromisoformat(prereg["hydrodynamic_contract"]["run_epoch_utc"].replace("Z", "+00:00"))
    obs = datetime.fromisoformat(prereg["local_observation"]["acquisition_midpoint_utc"].replace("Z", "+00:00"))
    elapsed_s = (obs - epoch).total_seconds()
    dt_out = int(contract["parameters"]["outputtimestep_s"])
    endtime = int(contract["parameters"]["endtime_s"])
    planned = list(range(dt_out, endtime + 1, dt_out))
    nearest = min(planned, key=lambda t: (abs(t - elapsed_s), t))
    frame_offset = abs(nearest - elapsed_s)
    require(frame_offset <= prereg["frame_selection_rule"]["maximum_allowed_offset_s"], "planned nearest frame exceeds preregistered offset limit")

    pair = {
        "status": "READY_TO_START_FORMAL_BG_FLOOD_PAIR",
        "date": "2026-10-02",
        "formal_bg_flood_run_started": False,
        "formal_sar_evaluation_run": False,
        "gate": ref(GATE),
        "preregistration": ref(PREREG),
        "preregistration_validation": ref(PREREG_VALIDATION),
        "contract": ref(CONTRACT),
        "frozen_run_manifest": ref(RUN_MANIFEST),
        "run_epoch_utc": prereg["hydrodynamic_contract"]["run_epoch_utc"],
        "observation_midpoint_utc": prereg["local_observation"]["acquisition_midpoint_utc"],
        "expected_observation_elapsed_s": elapsed_s,
        "planned_nearest_output_elapsed_s": nearest,
        "planned_frame_offset_s": frame_offset,
        "maximum_allowed_frame_offset_s": prereg["frame_selection_rule"]["maximum_allowed_offset_s"],
        "shared_config_normalized_sha256": text_sha256(base_normalized),
        "base": {
            "terrain_tif": ref(BASE_TIF),
            "terrain_ascii_materialization": base_ascii,
            "config": ref(BASE_CONFIG),
            "planned_output": str(BG / "results" / "V48_FORMAL_BASE.nc"),
            "command": "python -u python/run_bgflood.py BG_param_PhuYen_30m_V48_FORMAL_BASE.txt",
        },
        "conditioned": {
            "terrain_tif": ref(COND_TIF),
            "terrain_asc": ref(COND_ASC),
            "config": ref(COND_CONFIG),
            "planned_output": str(BG / "results" / "V48_FORMAL_CONDITIONED.nc"),
            "command": "python -u python/run_bgflood.py BG_param_PhuYen_30m_V48_FORMAL_CONDITIONED.txt",
        },
        "verified": {
            "gate_ready": True,
            "zero_prereg_blockers": True,
            "zero_prereg_integrity_failures": True,
            "terrain_grids_identical": True,
            "base_ascii_roundtrip_within_1e_6_m": True,
            "arm_configs_identical_except_terrain_output_and_arm_comment": True,
            "planned_frame_within_preregistered_offset": True,
            "formal_runs_not_started": True,
        },
    }
    PAIR_MANIFEST.write_text(json.dumps(pair, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(pair, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
