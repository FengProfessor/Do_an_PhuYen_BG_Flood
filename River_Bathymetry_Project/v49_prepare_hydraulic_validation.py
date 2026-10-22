"""Prepare the evidence-frozen V49-G BG_Flood comparison without launching long runs.

Comparable Gate-G arms are BASE, CENTRAL, LOW and HIGH under the canonical
V48 R1 ``minmask=-4.0`` contract.  The historical five-branch terrain is
recorded only as a diagnostic because valid cells extend below -4 m; running
it unchanged would silently change the modeled domain relative to the other
arms.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import geopandas as gpd
import netCDF4 as nc
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import mapping

from v49_estimate_reach_geometry import DEFAULT_DEM, EXPECTED_DEM_SHA256
from v49_synthesize_hydraulic_bed import (
    DEFAULT_C1_EVIDENCE,
    DEFAULT_C1_GATE,
    DEFAULT_GEOMETRY,
    DEFAULT_LEGACY_NETWORK,
    MODIFICATION_EPS_M,
    authorized_reach_ids,
    load_protected_mask,
    sha256_file,
    split_pipe,
    synthesize_reach_delta,
    validate_authorized_evidence,
)


PROJECT_DIR = Path(r"D:\VTP\River_Bathymetry_Project")
V48_RUNTIME = Path(r"D:\VTP\V48_runs\20261004_runtime_fix_r1")
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "V49_G_attempt_2"
HISTORICAL_OUTPUT_DIR = PROJECT_DIR / "V49_G_20261013"

FORBIDDEN_DIRS = {
    HISTORICAL_OUTPUT_DIR.resolve(),
    (PROJECT_DIR / "V49_G_POWERLOSS_RECOVERY_20261014").resolve(),
}


def is_historical_dir(output_dir: Path) -> bool:
    resolved = output_dir.resolve()
    return any(resolved == forbidden or forbidden in resolved.parents for forbidden in FORBIDDEN_DIRS)


def assert_not_historical_dir(output_dir: Path) -> None:
    if is_historical_dir(output_dir):
        raise PermissionError(
            f"Modifying historical attempt directory is strictly prohibited: {output_dir}"
        )
CENTRAL_DEM = PROJECT_DIR / "V49_E_20261012" / "V49_E_hydraulic_bed.tif"
LEGACY_DEM = PROJECT_DIR / "PhuYen_DEM_30m_with_Full_River_Bathymetry.tif"
BASE_ASC = Path(r"D:\VTP\05-Du-lieu-GIS\PhuYen_DEM_30m_V48_BASE_COPERNICUS_FORMAL.asc")
BASE_CONFIG = V48_RUNTIME / "BG_param_PhuYen_30m_V48_FORMAL_BASE_R1.txt"
BASE_RESULT = V48_RUNTIME / "results" / "V48_FORMAL_BASE_R1.nc"
V48_CONTRACT = V48_RUNTIME / "V48_BG_Flood_contract_R1.json"
V48_PREREG = V48_RUNTIME / "V48_SAR_preregistration_R1.json"
SAR_TIF = Path(r"D:\VTP\05-Du-lieu-GIS\DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif")

CANONICAL_MINMASK = -4.0
EXPECTED_CENTRAL_SHA256 = "181115942dc88a95503a1e193b2f90149e918b6f8354a262085b293e11df2552"
EXPECTED_LEGACY_SHA256 = "0f4b9de6e9849e1cd3f5fa8dd060b37433238506a027eb5a91f4c836c3852476"


def _grid_signature(path: Path) -> dict:
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        nodata = src.nodata
        valid = np.isfinite(data)
        if nodata is not None:
            valid &= data != nodata
        return {
            "width": src.width,
            "height": src.height,
            "crs": str(src.crs),
            "transform": tuple(float(v) for v in src.transform)[:6],
            "nodata": nodata,
            "valid_min_m": float(data[valid].min()),
            "valid_max_m": float(data[valid].max()),
            "valid_cells_le_canonical_minmask": int((valid & (data <= CANONICAL_MINMASK)).sum()),
        }


def _same_grid(a: dict, b: dict) -> bool:
    return (
        a["width"] == b["width"]
        and a["height"] == b["height"]
        and a["crs"] == b["crs"]
        and np.allclose(a["transform"], b["transform"], rtol=0.0, atol=1.0e-9)
    )


def _write_raster(path: Path, array: np.ndarray, profile: dict, nodata: float | None) -> None:
    out_profile = profile.copy()
    out_profile.update(driver="GTiff", dtype="float32", count=1, nodata=nodata, compress="deflate")
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(array.astype(np.float32), 1)


def _build_variant(depth_field: str, label: str, output_dir: Path) -> dict:
    reaches = gpd.read_file(DEFAULT_GEOMETRY, layer="reach_geometry")
    gate = pd.read_csv(DEFAULT_C1_GATE)
    objects = gpd.read_file(DEFAULT_C1_EVIDENCE, layer="audited_water_objects")
    ids = authorized_reach_ids(reaches, gate)
    validate_authorized_evidence(reaches, objects, ids)
    authorized = reaches[reaches.reach_id.astype(str).isin(ids)].sort_values("reach_id")

    source_hash_before = sha256_file(DEFAULT_DEM)
    if source_hash_before != EXPECTED_DEM_SHA256:
        raise RuntimeError(f"Source DEM hash mismatch before V49-G {label}: {source_hash_before}")

    with rasterio.open(DEFAULT_DEM) as src:
        dem = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        transform = src.transform
        nodata = src.nodata
        pixel_area_m2 = abs(float(transform.a * transform.e - transform.b * transform.d))
    valid = np.isfinite(dem)
    if nodata is not None:
        valid &= dem != nodata
    protected = load_protected_mask(DEFAULT_LEGACY_NETWORK, dem.shape)

    merged_delta = np.zeros(dem.shape, dtype=np.float32)
    authorized_mask = np.zeros(dem.shape, dtype=bool)
    traces: list[dict] = []
    for _, reach in authorized.iterrows():
        object_ids = split_pipe(reach.v49c_object_ids)
        associated_objects = objects[objects.object_id.astype(str).isin(object_ids)]
        class_mask = rasterize(
            [(mapping(geom), 1) for geom in associated_objects.geometry if geom is not None and not geom.is_empty],
            out_shape=dem.shape,
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=False,
        ).astype(bool)
        delta, allowed, trace = synthesize_reach_delta(
            dem,
            valid,
            transform,
            reach,
            class_mask,
            protected,
            depth_field=depth_field,
        )
        authorized_mask |= allowed
        merged_delta = np.maximum(merged_delta, delta)
        traces.append(trace)

    merged_delta[~authorized_mask] = 0.0
    merged_delta[protected] = 0.0
    out = dem.copy()
    out[valid] = dem[valid] - merged_delta[valid]
    effective_delta = np.zeros_like(dem, dtype=np.float32)
    effective_delta[valid] = dem[valid] - out[valid]
    effective_delta[effective_delta <= MODIFICATION_EPS_M] = 0.0

    dem_path = output_dir / f"V49_G_{label}_hydraulic_bed.tif"
    delta_path = output_dir / f"V49_G_{label}_delta_z.tif"
    _write_raster(dem_path, out, profile, nodata)
    delta_profile = profile.copy()
    delta_profile.update(nodata=0.0)
    _write_raster(delta_path, effective_delta, delta_profile, 0.0)

    modified = effective_delta > MODIFICATION_EPS_M
    audit = {
        "arm": label,
        "depth_field": depth_field,
        "authorized_reach_ids": ids,
        "modified_pixel_count": int(modified.sum()),
        "authorized_mask_pixel_count": int(authorized_mask.sum()),
        "outside_authorized_mask_modified_pixel_count": int((modified & ~authorized_mask).sum()),
        "protected_structure_modified_pixel_count": int((modified & protected).sum()),
        "raised_pixel_count": int((valid & (out > dem + MODIFICATION_EPS_M)).sum()),
        "lowering_volume_m3": float(effective_delta.sum(dtype=np.float64) * pixel_area_m2),
        "max_lowering_m": float(effective_delta.max(initial=0.0)),
        "source_dem_sha256_before": source_hash_before,
        "source_dem_sha256_after": sha256_file(DEFAULT_DEM),
        "output_dem_sha256": sha256_file(dem_path),
        "delta_sha256": sha256_file(delta_path),
        "reach_trace": traces,
    }
    audit["variant_invariance_pass"] = bool(
        audit["source_dem_sha256_before"] == audit["source_dem_sha256_after"] == EXPECTED_DEM_SHA256
        and audit["outside_authorized_mask_modified_pixel_count"] == 0
        and audit["protected_structure_modified_pixel_count"] == 0
        and audit["raised_pixel_count"] == 0
        and audit["modified_pixel_count"] > 0
    )
    (output_dir / f"V49_G_{label}_terrain_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return audit


def _write_ascii(tif_path: Path, asc_path: Path) -> dict:
    with rasterio.open(tif_path) as src:
        data = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        with rasterio.open(
            asc_path,
            "w",
            driver="AAIGrid",
            width=src.width,
            height=src.height,
            count=1,
            dtype="float32",
            crs=src.crs,
            transform=src.transform,
            nodata=-9999.0,
            DECIMAL_PRECISION=9,
        ) as dst:
            dst.write(data, 1)
    with rasterio.open(asc_path) as check:
        roundtrip = check.read(1).astype(np.float32)
        grid_ok = bool(
            check.width == profile["width"]
            and check.height == profile["height"]
            and check.crs == profile["crs"]
            and check.transform == profile["transform"]
        )
    max_abs_error = float(np.max(np.abs(roundtrip.astype(np.float64) - data.astype(np.float64))))
    return {
        "path": str(asc_path),
        "sha256": sha256_file(asc_path),
        "grid_roundtrip_ok": grid_ok,
        "max_value_roundtrip_error_m": max_abs_error,
    }


def _normalized_config(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("bathy ="):
            lines.append("bathy = <ARM_TERRAIN>;")
        elif line.lower().startswith("outfile ="):
            lines.append("outfile = <ARM_RESULT>;")
        else:
            lines.append(re.sub(r"\s+", " ", line))
    return "\n".join(lines)


def _make_config(arm: str, terrain_asc: Path, output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    terrain_asc = terrain_asc.resolve()
    result_path = (output_dir / "results" / f"V49_G_{arm}.nc").resolve()
    result_path.parent.mkdir(parents=True, exist_ok=True)
    text = BASE_CONFIG.read_text(encoding="utf-8")
    replacement_bathy = f"bathy = {terrain_asc.as_posix()};"
    replacement_out = f"outfile = {result_path.as_posix()};"
    text = re.sub(r"(?m)^bathy\s*=.*$", replacement_bathy, text, count=1)
    text = re.sub(r"(?m)^outfile\s*=.*$", replacement_out, text, count=1)
    path = (output_dir / f"BG_param_V49_G_{arm}.txt").resolve()
    path.write_text(text, encoding="utf-8")
    normalized = _normalized_config(text)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "normalized_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "terrain_asc": str(terrain_asc),
        "planned_result": str(result_path),
    }


def _inspect_base_result() -> dict:
    if not BASE_RESULT.exists():
        return {"path": str(BASE_RESULT), "exists": False}
    with nc.Dataset(BASE_RESULT, "r") as ds:
        times = np.asarray(ds.variables["time"][:], dtype=float)
    return {
        "path": str(BASE_RESULT),
        "exists": True,
        "sha256": sha256_file(BASE_RESULT),
        "frame_count": int(times.size),
        "first_time_s": float(times[0]) if times.size else None,
        "last_time_s": float(times[-1]) if times.size else None,
        "last_time_h": float(times[-1] / 3600.0) if times.size else None,
        "frame_33_available": bool(times.size > 33),
        "frame_33_time_s": float(times[33]) if times.size > 33 else None,
        "complete_to_120h": bool(times.size and times[-1] >= 432000.0 - 1.0),
    }


def prepare_v49_g(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict:
    output_dir = output_dir.resolve()
    assert_not_historical_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if sha256_file(DEFAULT_DEM) != EXPECTED_DEM_SHA256:
        raise RuntimeError("V49 source DEM does not match the frozen Copernicus hash")
    if sha256_file(CENTRAL_DEM) != EXPECTED_CENTRAL_SHA256:
        raise RuntimeError("V49 CENTRAL terrain hash differs from the accepted V49-E output")
    if sha256_file(LEGACY_DEM) != EXPECTED_LEGACY_SHA256:
        raise RuntimeError("Legacy five-branch terrain hash changed")

    low = _build_variant("depth_low_m", "LOW", output_dir)
    high = _build_variant("depth_high_m", "HIGH", output_dir)

    with rasterio.open(DEFAULT_DEM) as src:
        base = src.read(1).astype(np.float32)
    with rasterio.open(CENTRAL_DEM) as src:
        central = src.read(1).astype(np.float32)
    with rasterio.open(output_dir / "V49_G_LOW_hydraulic_bed.tif") as src:
        low_dem = src.read(1).astype(np.float32)
    with rasterio.open(output_dir / "V49_G_HIGH_hydraulic_bed.tif") as src:
        high_dem = src.read(1).astype(np.float32)
    low_dz = base - low_dem
    central_dz = base - central
    high_dz = base - high_dem
    ordering_tol = 2.0e-5
    sensitivity_ordering = {
        "low_le_central_violation_pixels": int((low_dz > central_dz + ordering_tol).sum()),
        "central_le_high_violation_pixels": int((central_dz > high_dz + ordering_tol).sum()),
    }
    sensitivity_ordering["pass"] = bool(
        sensitivity_ordering["low_le_central_violation_pixels"] == 0
        and sensitivity_ordering["central_le_high_violation_pixels"] == 0
    )

    base_grid = _grid_signature(DEFAULT_DEM)
    central_grid = _grid_signature(CENTRAL_DEM)
    low_grid = _grid_signature(output_dir / "V49_G_LOW_hydraulic_bed.tif")
    high_grid = _grid_signature(output_dir / "V49_G_HIGH_hydraulic_bed.tif")
    legacy_grid = _grid_signature(LEGACY_DEM)
    comparable_grids_match = all(_same_grid(base_grid, g) for g in (central_grid, low_grid, high_grid))

    ascii_outputs = {
        "BASE": {
            "path": str(BASE_ASC),
            "sha256": sha256_file(BASE_ASC),
            "reused_frozen_v48_r1_ascii": True,
        },
        "CENTRAL": _write_ascii(CENTRAL_DEM, output_dir / "V49_G_CENTRAL_hydraulic_bed.asc"),
        "LOW": _write_ascii(output_dir / "V49_G_LOW_hydraulic_bed.tif", output_dir / "V49_G_LOW_hydraulic_bed.asc"),
        "HIGH": _write_ascii(output_dir / "V49_G_HIGH_hydraulic_bed.tif", output_dir / "V49_G_HIGH_hydraulic_bed.asc"),
    }

    configs = {
        arm: _make_config(arm, Path(info["path"]), output_dir)
        for arm, info in ascii_outputs.items()
    }
    base_normalized = configs["BASE"]["normalized_sha256"]
    normalized_configs_identical = all(info["normalized_sha256"] == base_normalized for info in configs.values())

    contract = json.loads(V48_CONTRACT.read_text(encoding="utf-8"))
    prereg = json.loads(V48_PREREG.read_text(encoding="utf-8"))
    base_result = _inspect_base_result()
    obs = prereg["local_observation"]
    hydro = prereg["hydrodynamic_contract"]
    eval_design = prereg["evaluation_design"]
    report = {
        "schema_version": "V49-G-preparation-1",
        "status": "PREPARED_PENDING_MATCHED_BG_FLOOD_RUNS",
        "gate_g_pass": False,
        "hydraulic_promotion_ready": False,
        "comparable_arms": ["BASE", "CENTRAL", "LOW", "HIGH"],
        "diagnostic_only_arm": "LEGACY_FIVE_BRANCH",
        "mask_policy": {
            "canonical_minmask": CANONICAL_MINMASK,
            "comparable_arms_policy": "Use the unchanged V48 R1 minmask=-4.0 for BASE/CENTRAL/LOW/HIGH.",
            "legacy_policy": (
                "Diagnostic/non-comparable only. The five-branch terrain contains valid cells <= -4.0 m; "
                "running it with the canonical minmask would mask real terrain and violate matched-domain fairness."
            ),
            "legacy_valid_cells_le_minmask": legacy_grid["valid_cells_le_canonical_minmask"],
        },
        "terrain": {
            "BASE": {"path": str(DEFAULT_DEM), "sha256": EXPECTED_DEM_SHA256, "grid": base_grid},
            "CENTRAL": {"path": str(CENTRAL_DEM), "sha256": EXPECTED_CENTRAL_SHA256, "grid": central_grid},
            "LOW": {"path": str(output_dir / "V49_G_LOW_hydraulic_bed.tif"), "sha256": low["output_dem_sha256"], "grid": low_grid},
            "HIGH": {"path": str(output_dir / "V49_G_HIGH_hydraulic_bed.tif"), "sha256": high["output_dem_sha256"], "grid": high_grid},
            "LEGACY_FIVE_BRANCH": {"path": str(LEGACY_DEM), "sha256": EXPECTED_LEGACY_SHA256, "grid": legacy_grid},
        },
        "variant_audits": {"LOW": low, "HIGH": high},
        "sensitivity_ordering": sensitivity_ordering,
        "comparable_grids_match": comparable_grids_match,
        "ascii_outputs": ascii_outputs,
        "configs": configs,
        "normalized_comparable_configs_identical_except_terrain_and_output": normalized_configs_identical,
        "v48_r1_contract": {"path": str(V48_CONTRACT), "sha256": sha256_file(V48_CONTRACT)},
        "engine_semantics": contract["engine_semantics"],
        "forcing": contract["forcing"],
        "parameters": contract["parameters"],
        "run_epoch_utc": hydro["run_epoch_utc"],
        "run_epoch_local": hydro["run_epoch_local"],
        "sentinel1": {
            "path": str(SAR_TIF),
            "sha256": obs["tif"]["sha256"],
            "acquisition_midpoint_utc": obs["acquisition_midpoint_utc"],
            "interpretation": prereg["interpretation"],
            "wet_depth_threshold_m": eval_design["wet_depth_threshold_m"],
            "permanent_water_threshold": eval_design["permanent_water_mask"]["threshold"],
            "hand_validity_rule": eval_design["hand_validity_mask"]["include_where"],
            "frame_selection_rule": prereg["frame_selection_rule"],
            "metrics": prereg["metrics"],
        },
        "existing_base_result": base_result,
        "metric_availability": {
            "sentinel1_extent": "AVAILABLE_FOR_BASE_NOW; PENDING_NEW_RUNS_FOR_CENTRAL_LOW_HIGH",
            "gauge_wse_timing": "UNAVAILABLE_NO_VERIFIED_SERIES_WITH_DATUM_AND_LINEAGE",
            "surveyed_high_water_marks": "UNAVAILABLE_NO_VERIFIED_LOCAL_DATASET",
            "known_wet_dry_points": "UNAVAILABLE_NO_FROZEN_OBSERVATION_SET",
            "velocity_sanity": "PENDING_MATCHED_RUNS",
            "mass_balance": "PENDING_MATCHED_RUNS",
        },
        "execution_note": (
            "Preparation does not launch CENTRAL/LOW/HIGH BG_Flood simulations. The existing BASE result reaches about 105 h "
            "and contains the preregistered Sentinel-1 comparison frame, but is not a complete 120 h formal run."
        ),
    }
    report["preparation_pass"] = bool(
        low["variant_invariance_pass"]
        and high["variant_invariance_pass"]
        and sensitivity_ordering["pass"]
        and comparable_grids_match
        and normalized_configs_identical
        and all(
            arm == "BASE" or info.get("grid_roundtrip_ok") and info.get("max_value_roundtrip_error_m", 1.0) <= 2.0e-5
            for arm, info in ascii_outputs.items()
        )
        and base_grid["valid_cells_le_canonical_minmask"] == 0
        and central_grid["valid_cells_le_canonical_minmask"] == 0
        and low_grid["valid_cells_le_canonical_minmask"] == 0
        and high_grid["valid_cells_le_canonical_minmask"] == 0
        and legacy_grid["valid_cells_le_canonical_minmask"] > 0
    )
    for name in ("SAR_vs_V48_BASE_frame_33_metrics.json", "SAR_vs_V48_BASE_frame_33_contingency.png"):
        src = V48_RUNTIME / "results" / name
        if not src.exists():
            src = HISTORICAL_OUTPUT_DIR / name
        dst = output_dir / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
    (output_dir / "V49_G_PREPARATION_MANIFEST.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(prepare_v49_g(), ensure_ascii=True, indent=2))
