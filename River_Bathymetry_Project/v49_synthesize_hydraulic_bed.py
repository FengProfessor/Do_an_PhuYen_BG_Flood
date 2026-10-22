"""V49-E conservative hydraulic-bed synthesis.

V49-E is the first V49 phase allowed to create a new elevation raster.  It
never edits the V48/Copernicus source DEM in place.  Automatic synthesis is
restricted to reaches that pass both V49-D geometry authorization and the
V49-C.1 fixed-water gate.

The implementation deliberately avoids the legacy five-branch assumptions:
no named-branch depth, bounding box, hard-coded route, ocean outlet level, or
global monotonic lowering is used.  Each authorized reach is synthesized from
its V49-D width and preliminary hydraulic-bed profile, then coupled to 2-D
with a raised-cosine lateral taper.  The verified 187-cell Dong Cam structure
mask is locked to zero modification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import xy
from shapely.geometry import Point, mapping

from v49_estimate_reach_geometry import DEFAULT_DEM, EXPECTED_DEM_SHA256


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


PROJECT_DIR = Path(r"D:\VTP\River_Bathymetry_Project")
DEFAULT_GEOMETRY = PROJECT_DIR / "V49_D_20261012" / "V49_reach_geometry.gpkg"
DEFAULT_C1_GATE = PROJECT_DIR / "V49_C1_20261012" / "V49_C1_v49e_reach_gate.csv"
DEFAULT_C1_EVIDENCE = PROJECT_DIR / "V49_C1_20261012" / "V49_C1_fixed_water_evidence.gpkg"
DEFAULT_GRAPH = PROJECT_DIR / "V49_B_20261012" / "V49_hydrograph.gpkg"
DEFAULT_LEGACY_NETWORK = PROJECT_DIR / "river_network_data.npz"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "V49_E_20261012"

AUTHORIZED_CLASS = "RIVER_STREAM"
CONFLUENCE_TOLERANCE_M = 0.75
MODIFICATION_EPS_M = 1.0e-6


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def boolish(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def split_pipe(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    return [part.strip() for part in str(value).split("|") if part.strip()]


def raised_cosine_weight(distance_m: float, half_width_m: float) -> float:
    """Raised-cosine cross-channel taper, 1 at centerline and 0 at bank."""

    if half_width_m <= 0.0:
        raise ValueError("half_width_m must be positive")
    if distance_m <= 0.0:
        return 1.0
    if distance_m >= half_width_m:
        return 0.0
    xi = distance_m / half_width_m
    return float(math.cos(0.5 * math.pi * xi) ** 2)


def linear_bed_target(upstream_m: float, downstream_m: float, fraction: float) -> float:
    fraction = min(max(float(fraction), 0.0), 1.0)
    return float(upstream_m + fraction * (downstream_m - upstream_m))


def authorized_reach_ids(reaches: gpd.GeoDataFrame, gate: pd.DataFrame) -> list[str]:
    """Return the deterministic C.1 ∩ D authorization set."""

    gate_ids = {
        str(row.reach_id)
        for row in gate.itertuples(index=False)
        if boolish(getattr(row, "c1_authorized_for_v49e", False))
    }
    d_ids = {
        str(row.reach_id)
        for row in reaches.itertuples(index=False)
        if boolish(getattr(row, "geometry_authorized_for_v49e", False))
    }
    return sorted(gate_ids & d_ids)


def validate_authorized_evidence(
    reaches: gpd.GeoDataFrame,
    audited_objects: gpd.GeoDataFrame,
    reach_ids: Iterable[str],
) -> None:
    objects = audited_objects.set_index(audited_objects.object_id.astype(str), drop=False)
    for reach_id in reach_ids:
        row = reaches[reaches.reach_id.astype(str) == str(reach_id)]
        if len(row) != 1:
            raise RuntimeError(f"Expected exactly one V49-D row for {reach_id}; got {len(row)}")
        reach = row.iloc[0]
        classes = split_pipe(reach.v49c_eligible_classes)
        if classes != [AUTHORIZED_CLASS]:
            raise RuntimeError(f"{reach_id} is not an unambiguous {AUTHORIZED_CLASS} reach: {classes}")
        object_ids = split_pipe(reach.v49c_object_ids)
        if not object_ids:
            raise RuntimeError(f"{reach_id} has no associated V49-C object")
        for object_id in object_ids:
            if object_id not in objects.index:
                raise RuntimeError(f"{reach_id} references missing C.1 object {object_id}")
            obj = objects.loc[object_id]
            if str(obj.fixed_water_status) != "CONFIRMED_PERSISTENT":
                raise RuntimeError(
                    f"{reach_id} object {object_id} is not CONFIRMED_PERSISTENT: {obj.fixed_water_status}"
                )
            if not boolish(obj.automatic_carving_allowed_by_c1):
                raise RuntimeError(f"{reach_id} object {object_id} is not allowed by C.1")


def reach_corridor_mask(
    geometry,
    width_m: float,
    out_shape: tuple[int, int],
    transform,
) -> np.ndarray:
    if width_m <= 0.0 or not math.isfinite(width_m):
        raise ValueError(f"Invalid reach width: {width_m}")
    corridor = geometry.buffer(width_m / 2.0, cap_style=2, join_style=2)
    return rasterize(
        [(mapping(corridor), 1)],
        out_shape=out_shape,
        transform=transform,
        fill=0,
        dtype="uint8",
        all_touched=False,
    ).astype(bool)


def reach_thalweg_mask(geometry, out_shape: tuple[int, int], transform) -> np.ndarray:
    return rasterize(
        [(mapping(geometry), 1)],
        out_shape=out_shape,
        transform=transform,
        fill=0,
        dtype="uint8",
        all_touched=True,
    ).astype(bool)


def synthesize_reach_delta(
    dem: np.ndarray,
    valid_dem: np.ndarray,
    transform,
    reach: pd.Series,
    class_mask: np.ndarray,
    protected_mask: np.ndarray,
    depth_field: str = "depth_est_m",
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Build one reach's 2-D lowering field and trace metadata."""

    if depth_field not in {"depth_est_m", "depth_low_m", "depth_high_m"}:
        raise ValueError(f"Unsupported V49-D depth field: {depth_field}")
    line = reach.geometry
    width_m = float(reach.width_m)
    half_width_m = width_m / 2.0
    depth_m = float(getattr(reach, depth_field))
    bed_up = float(reach.preliminary_bed_upstream_m)
    bed_down = float(reach.preliminary_bed_downstream_m)
    if not all(math.isfinite(v) for v in (width_m, depth_m, bed_up, bed_down)):
        raise RuntimeError(f"Non-finite V49-D geometry for {reach.reach_id}")
    if depth_m <= 0.0:
        raise RuntimeError(f"Non-positive V49-D depth for {reach.reach_id}: {depth_m}")
    if bed_down > bed_up + CONFLUENCE_TOLERANCE_M:
        raise RuntimeError(
            f"{reach.reach_id} preliminary bed rises downstream by {bed_down - bed_up:.3f} m"
        )

    corridor = reach_corridor_mask(line, width_m, dem.shape, transform)
    thalweg = reach_thalweg_mask(line, dem.shape, transform) & corridor
    allowed = corridor & class_mask & valid_dem & ~protected_mask
    delta = np.zeros(dem.shape, dtype=np.float32)

    rr, cc = np.where(allowed)
    if len(rr) == 0:
        raise RuntimeError(f"{reach.reach_id} has no valid raster cells inside its authorized corridor")
    xs, ys = xy(transform, rr, cc, offset="center")
    line_length = float(line.length)
    for row_i, col_i, x_coord, y_coord in zip(rr, cc, xs, ys):
        point = Point(float(x_coord), float(y_coord))
        distance_m = float(line.distance(point))
        # V49-D depth is a reach-scale inferred channel depth.  Apply it to
        # the local DEM/water-surface proxy instead of extending the two
        # preliminary endpoint elevations as a rigid grade line through
        # unsupported terrain.  This bounds incision by the evidence-backed
        # depth estimate and avoids arbitrary deep cuts between sparse water
        # objects.  Preliminary endpoint beds remain junction-QA evidence.
        center_lowering = depth_m
        weight = 1.0 if thalweg[row_i, col_i] else raised_cosine_weight(distance_m, half_width_m)
        delta[row_i, col_i] = np.float32(center_lowering * weight)

    delta[~allowed] = 0.0
    modified = delta > MODIFICATION_EPS_M
    trace = {
        "reach_id": str(reach.reach_id),
        "water_class": AUTHORIZED_CLASS,
        "width_m": width_m,
        "depth_est_m": float(reach.depth_est_m),
        "depth_low_m": float(reach.depth_low_m),
        "depth_high_m": float(reach.depth_high_m),
        "selected_depth_field": depth_field,
        "selected_depth_m": depth_m,
        "bed_upstream_m": bed_up,
        "bed_downstream_m": bed_down,
        "corridor_and_class_pixel_count": int(allowed.sum()),
        "class_mask_pixel_count": int(class_mask.sum()),
        "thalweg_pixel_count": int((thalweg & allowed).sum()),
        "modified_pixel_count_premerge": int(modified.sum()),
        "max_lowering_m_premerge": float(delta.max(initial=0.0)),
        "longitudinal_method": "LOCAL_DEM_SURFACE_MINUS_V49D_REACH_DEPTH_NO_GLOBAL_MONOTONIC_FILTER",
        "lateral_method": "RAISED_COSINE_CENTRAL_WIDTH",
    }
    return delta, allowed, trace


def load_protected_mask(path: Path, expected_shape: tuple[int, int]) -> np.ndarray:
    data = np.load(path, allow_pickle=False)
    if "dong_cam_mask" not in data.files:
        raise RuntimeError(f"Missing dong_cam_mask in {path}")
    mask = data["dong_cam_mask"].astype(bool)
    if mask.shape != expected_shape:
        raise RuntimeError(f"Dong Cam mask shape {mask.shape} does not match DEM {expected_shape}")
    return mask


def _write_raster(path: Path, array: np.ndarray, profile: dict, dtype: str, nodata) -> None:
    out_profile = profile.copy()
    out_profile.update(dtype=dtype, count=1, nodata=nodata, compress="deflate")
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(array.astype(dtype), 1)


def _incident_ids(value: object) -> list[str]:
    return split_pipe(value)


def build_final_confluence_checks(
    d_confluences: gpd.GeoDataFrame,
    authorized_ids: set[str],
) -> pd.DataFrame:
    rows: list[dict] = []
    for _, item in d_confluences.iterrows():
        incoming = _incident_ids(item.incoming_reach_ids)
        outgoing = _incident_ids(item.outgoing_reach_ids)
        incident = set(incoming + outgoing)
        if not incident.intersection(authorized_ids):
            continue
        rise = float(item.max_apparent_downstream_bed_rise_m)
        structure_context = boolish(item.structure_context)
        tidal_context = boolish(item.tidal_context)
        if rise <= CONFLUENCE_TOLERANCE_M:
            state = "PASS_NO_UNEXPLAINED_BED_INVERSION"
            explanation = "V49-D incident-bed ordering remains non-inverting at this V49-E scope boundary."
        elif structure_context:
            state = "PASS_EXPLICIT_STRUCTURE_CONTROL"
            explanation = str(item.control_explanation)
        elif tidal_context:
            state = "PASS_EXPLICIT_TIDAL_BACKWATER_CONTROL"
            explanation = str(item.control_explanation)
        else:
            state = "REVIEW_REQUIRED_BED_INVERSION"
            explanation = "Apparent downstream bed rise lacks a documented structure/tidal control."
        rows.append(
            {
                "node_id": str(item.node_id),
                "incoming_reach_ids": " | ".join(incoming),
                "outgoing_reach_ids": " | ".join(outgoing),
                "authorized_incident_reach_ids": " | ".join(sorted(incident.intersection(authorized_ids))),
                "all_incident_authorized": incident.issubset(authorized_ids),
                "max_apparent_downstream_bed_rise_m": rise,
                "structure_context": structure_context,
                "tidal_context": tidal_context,
                "final_bed_state": state,
                "control_explanation": explanation,
            }
        )
    return pd.DataFrame(rows)


def _write_map(delta: np.ndarray, valid: np.ndarray, output_dir: Path) -> None:
    display = np.where(valid, delta, np.nan)
    fig, ax = plt.subplots(figsize=(10, 8))
    image = ax.imshow(display, origin="upper")
    ax.set_title("V49-E authorized hydraulic-bed lowering (m)")
    ax.set_xlabel("column")
    ax.set_ylabel("row")
    fig.colorbar(image, ax=ax, label="lowering (m)")
    fig.tight_layout()
    fig.savefig(output_dir / "V49_E_delta_z_map.png", dpi=180)
    plt.close(fig)


def build_v49_e(
    geometry_path: Path = DEFAULT_GEOMETRY,
    c1_gate_path: Path = DEFAULT_C1_GATE,
    c1_evidence_path: Path = DEFAULT_C1_EVIDENCE,
    graph_path: Path = DEFAULT_GRAPH,
    dem_path: Path = DEFAULT_DEM,
    legacy_network_path: Path = DEFAULT_LEGACY_NETWORK,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    dem_hash_before = sha256_file(dem_path)
    if dem_hash_before != EXPECTED_DEM_SHA256:
        raise RuntimeError(f"Source DEM hash mismatch before V49-E: {dem_hash_before}")

    reaches = gpd.read_file(geometry_path, layer="reach_geometry")
    d_confluences = gpd.read_file(geometry_path, layer="confluence_checks")
    gate = pd.read_csv(c1_gate_path)
    audited_objects = gpd.read_file(c1_evidence_path, layer="audited_water_objects")
    ids = authorized_reach_ids(reaches, gate)
    if not ids:
        raise RuntimeError("C.1 ∩ D authorizes zero reaches; V49-E has nothing safe to synthesize")
    validate_authorized_evidence(reaches, audited_objects, ids)
    authorized = reaches[reaches.reach_id.astype(str).isin(ids)].copy()

    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        transform = src.transform
        nodata = src.nodata
        pixel_area_m2 = abs(float(transform.a * transform.e - transform.b * transform.d))
    valid = np.isfinite(dem)
    if nodata is not None:
        valid &= dem != nodata
    protected = load_protected_mask(legacy_network_path, dem.shape)

    merged_delta = np.zeros(dem.shape, dtype=np.float32)
    winner = np.full(dem.shape, -1, dtype=np.int16)
    authorized_mask = np.zeros(dem.shape, dtype=bool)
    reach_traces: list[dict] = []
    for idx, (_, reach) in enumerate(authorized.sort_values("reach_id").iterrows()):
        object_ids = split_pipe(reach.v49c_object_ids)
        associated_objects = audited_objects[audited_objects.object_id.astype(str).isin(object_ids)]
        class_mask = rasterize(
            [(mapping(geom), 1) for geom in associated_objects.geometry if geom is not None and not geom.is_empty],
            out_shape=dem.shape,
            transform=transform,
            fill=0,
            dtype="uint8",
            all_touched=False,
        ).astype(bool)
        delta, allowed, trace = synthesize_reach_delta(
            dem, valid, transform, reach, class_mask, protected
        )
        authorized_mask |= allowed
        take = delta > merged_delta
        merged_delta[take] = delta[take]
        winner[take] = idx
        reach_traces.append(trace)

    merged_delta[~authorized_mask] = 0.0
    merged_delta[protected] = 0.0
    output_dem = dem.copy()
    output_dem[valid] = dem[valid] - merged_delta[valid]
    output_dem[~valid] = dem[~valid]
    # The source/output DEM is float32.  Very small tapered edge changes can
    # round back to the original cell value at large elevations.  Make the
    # stored delta and all volume accounting represent the actual float32 DEM
    # difference, not an unobservable pre-quantization lowering.
    effective_delta = np.zeros(dem.shape, dtype=np.float32)
    effective_delta[valid] = dem[valid] - output_dem[valid]
    effective_delta[effective_delta <= MODIFICATION_EPS_M] = 0.0
    merged_delta = effective_delta
    winner[merged_delta <= MODIFICATION_EPS_M] = -1

    dem_out_path = output_dir / "V49_E_hydraulic_bed.tif"
    delta_path = output_dir / "V49_E_delta_z.tif"
    mask_path = output_dir / "V49_E_authorized_mask.tif"
    _write_raster(dem_out_path, output_dem, profile, "float32", nodata)
    delta_profile = profile.copy()
    _write_raster(delta_path, merged_delta, delta_profile, "float32", 0.0)
    mask_profile = profile.copy()
    _write_raster(mask_path, authorized_mask.astype(np.uint8), mask_profile, "uint8", 0)

    volume_rows: list[dict] = []
    sorted_authorized = authorized.sort_values("reach_id").reset_index(drop=True)
    for idx, reach in sorted_authorized.iterrows():
        cells = winner == idx
        dz_values = merged_delta[cells]
        volume_rows.append(
            {
                "reach_id": str(reach.reach_id),
                "water_class": AUTHORIZED_CLASS,
                "modified_pixel_count": int((dz_values > MODIFICATION_EPS_M).sum()),
                "modified_area_m2": float((dz_values > MODIFICATION_EPS_M).sum() * pixel_area_m2),
                "lowering_volume_m3": float(dz_values.sum(dtype=np.float64) * pixel_area_m2),
                "max_lowering_m": float(dz_values.max(initial=0.0)),
                "mean_lowering_modified_m": float(dz_values[dz_values > MODIFICATION_EPS_M].mean())
                if np.any(dz_values > MODIFICATION_EPS_M)
                else 0.0,
                "depth_est_m": float(reach.depth_est_m),
                "uncertainty_class": str(reach.uncertainty_class),
                "v49c_object_ids": str(reach.v49c_object_ids),
            }
        )
    volume_table = pd.DataFrame(volume_rows)
    volume_table.to_csv(output_dir / "V49_E_modification_volume_by_reach.csv", index=False, encoding="utf-8-sig")

    adjustments = pd.DataFrame(
        columns=[
            "reach_id",
            "chainage_m",
            "original_target_bed_m",
            "adjusted_target_bed_m",
            "adjustment_m",
            "reason",
            "evidence_or_control",
        ]
    )
    adjustments.to_csv(output_dir / "V49_E_longitudinal_adjustments.csv", index=False, encoding="utf-8-sig")

    final_confluences = build_final_confluence_checks(d_confluences, set(ids))
    final_confluences.to_csv(output_dir / "V49_E_confluence_checks.csv", index=False, encoding="utf-8-sig")

    for _, row in sorted_authorized.iterrows():
        rid = str(row.reach_id)
        vol = volume_table[volume_table.reach_id == rid].iloc[0]
        match = authorized.index[authorized.reach_id.astype(str) == rid][0]
        authorized.loc[match, "e_authorized"] = True
        authorized.loc[match, "e_modified_pixels"] = int(vol.modified_pixel_count)
        authorized.loc[match, "e_lowering_volume_m3"] = float(vol.lowering_volume_m3)
        authorized.loc[match, "e_max_lowering_m"] = float(vol.max_lowering_m)
        authorized.loc[match, "e_water_class"] = AUTHORIZED_CLASS
        authorized.loc[match, "e_longitudinal_method"] = (
            "LOCAL_DEM_SURFACE_MINUS_V49D_REACH_DEPTH_NO_GLOBAL_MONOTONIC_FILTER"
        )
        authorized.loc[match, "e_lateral_method"] = "RAISED_COSINE_CENTRAL_WIDTH"

    gpkg = output_dir / "V49_E_hydraulic_bed.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    authorized.to_file(gpkg, layer="authorized_reaches", driver="GPKG")

    _write_map(merged_delta, valid, output_dir)

    dem_hash_after = sha256_file(dem_path)
    modified = merged_delta > MODIFICATION_EPS_M
    outside_count = int((modified & ~authorized_mask).sum())
    protected_modified = int((modified & protected).sum())
    unresolved = (
        final_confluences[final_confluences.final_bed_state.astype(str).str.startswith("REVIEW_REQUIRED")]
        if not final_confluences.empty
        else final_confluences
    )
    audit = {
        "schema_version": "V49-E-hydraulic-bed-1",
        "inputs": {
            "geometry": str(geometry_path),
            "c1_gate": str(c1_gate_path),
            "c1_evidence": str(c1_evidence_path),
            "graph": str(graph_path),
            "source_dem": str(dem_path),
            "legacy_network_for_protected_mask": str(legacy_network_path),
        },
        "source_hashes": {
            "dem_expected_sha256": EXPECTED_DEM_SHA256,
            "dem_sha256_before": dem_hash_before,
            "dem_sha256_after": dem_hash_after,
            "output_dem_sha256": sha256_file(dem_out_path),
            "delta_z_sha256": sha256_file(delta_path),
        },
        "source_dem_unchanged": dem_hash_before == dem_hash_after == EXPECTED_DEM_SHA256,
        "authorized_reach_ids": ids,
        "authorized_reach_count": len(ids),
        "modified_pixel_count": int(modified.sum()),
        "authorized_mask_pixel_count": int(authorized_mask.sum()),
        "outside_authorized_mask_modified_pixel_count": outside_count,
        "protected_structure_pixel_count": int(protected.sum()),
        "protected_structure_modified_pixel_count": protected_modified,
        "total_lowering_volume_m3": float(merged_delta.sum(dtype=np.float64) * pixel_area_m2),
        "max_lowering_m": float(merged_delta.max(initial=0.0)),
        "modification_by_reach": volume_rows,
        "reach_trace": reach_traces,
        "forced_longitudinal_adjustment_count": 0,
        "global_monotonic_filter_used": False,
        "legacy_named_branch_depth_used": False,
        "confluence_check_count": int(len(final_confluences)),
        "confluence_state_counts": dict(Counter(final_confluences.final_bed_state.astype(str)))
        if not final_confluences.empty
        else {},
        "unresolved_confluence_count": int(len(unresolved)),
        "gate_e_preliminary_status": "PASS"
        if (
            dem_hash_before == dem_hash_after == EXPECTED_DEM_SHA256
            and outside_count == 0
            and protected_modified == 0
            and len(unresolved) == 0
            and modified.any()
        )
        else "FAIL",
        "scientific_limits": [
            "V49-E modifies only the two reaches currently admitted by C.1 ∩ D; all other reaches remain unchanged.",
            "Within an admitted reach, V49-E modifies only cells that also lie inside its associated C.1 CONFIRMED_PERSISTENT water-object polygons.",
            "V49-D bed inputs are inferred from surface/terrain and discharge proxies, not surveyed bathymetry.",
            "The 30 m raster limits representation of narrow lateral tapers; the continuous raised-cosine function is sampled at cell centers.",
            "No global monotonic correction is applied; documented hydraulic controls and pre-existing lower terrain are not erased.",
        ],
    }
    (output_dir / "V49_E_hydraulic_bed_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--c1-gate", type=Path, default=DEFAULT_C1_GATE)
    parser.add_argument("--c1-evidence", type=Path, default=DEFAULT_C1_EVIDENCE)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    parser.add_argument("--legacy-network", type=Path, default=DEFAULT_LEGACY_NETWORK)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = build_v49_e(
        geometry_path=args.geometry,
        c1_gate_path=args.c1_gate,
        c1_evidence_path=args.c1_evidence,
        graph_path=args.graph,
        dem_path=args.dem,
        legacy_network_path=args.legacy_network,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
