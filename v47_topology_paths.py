"""Build upstream/downstream topology and constrained cut proposals for V47.

Unlike V46, this audit accepts any non-empty historical core raster instead of
hard-coding the 55-cell legacy seed. Historical OSM, D8, upstream area, HAND,
JRC GSW 1984-2020, and HydroRIVERS provide the evidence. This stage never
modifies the DEM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform as crs_transform
from scipy.ndimage import binary_dilation, label

ROOT = Path(r"D:/VTP")
DEM = ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m_V41.asc"
CORE = ROOT / "V46_stable_core_20260930/V46_stable_tierA_core.tif"
CORE_MANIFEST = ROOT / "V46_stable_core_20260930/V46_stable_core_manifest.json"
STRICT = ROOT / "V46_dryrun_sensitivity/strict_1_2/V46_obstruction_candidates.csv"
OSM = ROOT / "V46_inputs/osm_historical_20211125"
HYDRO = ROOT / "V46_hydro_evidence_20260930"
OUT = ROOT / "V47_topology_historical407_20261001"

D8_DELTA = {
    1: (0, 1),
    2: (1, 1),
    4: (1, 0),
    8: (1, -1),
    16: (0, -1),
    32: (-1, -1),
    64: (-1, 0),
    128: (-1, 1),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_osm_ways(folder: Path, dst_crs):
    ways = {}
    for fp in sorted(folder.glob("*.osm")):
        root = ET.parse(fp).getroot()
        for way in root.findall("way"):
            wid = int(way.attrib["id"])
            if wid in ways:
                continue
            tags = {t.attrib["k"]: t.attrib["v"] for t in way.findall("tag")}
            pts = [
                (float(nd.attrib["lon"]), float(nd.attrib["lat"]))
                for nd in way.findall("nd")
                if "lon" in nd.attrib and "lat" in nd.attrib
            ]
            if len(pts) < 2:
                continue
            xs, ys = zip(*pts)
            tx, ty = crs_transform("EPSG:4326", dst_crs, list(xs), list(ys))
            ways[wid] = {
                "coords": list(zip(tx, ty)),
                "waterway": tags.get("waterway"),
                "name": tags.get("name") or tags.get("name:en") or "",
                "timestamp": way.attrib.get("timestamp"),
                "version": way.attrib.get("version"),
            }
    return ways


def ordered_cells(coords, transform, shape, step_m=10.0):
    cells = []
    for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
        distance = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(math.ceil(distance / step_m)))
        for k in range(n + 1):
            t = k / n
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            r, c = rasterio.transform.rowcol(transform, x, y)
            cell = (int(r), int(c))
            if 0 <= r < shape[0] and 0 <= c < shape[1] and (not cells or cells[-1] != cell):
                cells.append(cell)
    return cells


def mode_int(series) -> int:
    vals = [int(x) for x in series if pd.notna(x)]
    return Counter(vals).most_common(1)[0][0] if vals else 0


def d8_trace(start, d8, max_steps=600):
    """Return downstream cells and step index from a D8 cell."""
    out = {}
    current = tuple(start)
    shape = d8.shape
    for step in range(max_steps + 1):
        if current in out:
            break
        out[current] = step
        code = int(d8[current])
        if code not in D8_DELTA:
            break
        dr, dc = D8_DELTA[code]
        nxt = (current[0] + dr, current[1] + dc)
        if not (0 <= nxt[0] < shape[0] and 0 <= nxt[1] < shape[1]):
            break
        current = nxt
    return out


def anchor_candidates(center, uparea, hand, jrc, radius=4, topn=24):
    """Rank nearby routing cells; keep several so D8 connectivity decides topology."""
    r0, c0 = center
    rows = []
    nr, nc = uparea.shape
    for r in range(max(0, r0 - radius), min(nr, r0 + radius + 1)):
        for c in range(max(0, c0 - radius), min(nc, c0 + radius + 1)):
            if not np.isfinite(uparea[r, c]) or uparea[r, c] < 0:
                continue
            off = max(abs(r - r0), abs(c - c0))
            j = float(jrc[r, c]) if jrc[r, c] != 255 else -1.0
            h = float(hand[r, c]) if hand[r, c] > -9000 else 1e9
            rows.append(
                {
                    "cell": (r, c),
                    "offset": off,
                    "uparea": float(uparea[r, c]),
                    "jrc": j,
                    "hand": h,
                }
            )
    rows.sort(key=lambda z: (z["offset"], -z["uparea"], -z["jrc"], z["hand"]))
    return rows[:topn]


def find_d8_anchor_pair(path_a, path_b, d8, uparea, hand, jrc):
    """Find a directly connected D8 pair near the two OSM path flanks."""
    side_a = anchor_candidates(path_a, uparea, hand, jrc)
    side_b = anchor_candidates(path_b, uparea, hand, jrc)
    candidates = []

    for aa in side_a:
        trace = d8_trace(aa["cell"], d8)
        for bb in side_b:
            steps = trace.get(bb["cell"])
            if steps is None or steps == 0:
                continue
            if bb["uparea"] + 1e-9 < aa["uparea"]:
                continue
            candidates.append(
                (aa["offset"] + bb["offset"], steps, -min(aa["uparea"], bb["uparea"]), "A_TO_B", aa, bb)
            )

    for bb in side_b:
        trace = d8_trace(bb["cell"], d8)
        for aa in side_a:
            steps = trace.get(aa["cell"])
            if steps is None or steps == 0:
                continue
            if aa["uparea"] + 1e-9 < bb["uparea"]:
                continue
            candidates.append(
                (aa["offset"] + bb["offset"], steps, -min(aa["uparea"], bb["uparea"]), "B_TO_A", aa, bb)
            )

    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    _, steps, _, direction, aa, bb = candidates[0]
    if direction == "A_TO_B":
        up, down = aa, bb
    else:
        up, down = bb, aa
    return {"direction": direction, "up": up, "down": down, "trace_steps": int(steps)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", type=Path, default=DEM)
    ap.add_argument("--core", type=Path, default=CORE)
    ap.add_argument("--core-manifest", type=Path, default=CORE_MANIFEST)
    ap.add_argument("--strict-csv", type=Path, default=STRICT)
    ap.add_argument("--osm-dir", type=Path, default=OSM)
    ap.add_argument("--hydro-dir", type=Path, default=HYDRO)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--max-cut-m", type=float, default=3.0)
    ap.add_argument("--max-modified-cells", type=int, default=8)
    ap.add_argument("--max-path-span-cells", type=int, default=20)
    ap.add_argument("--strict-max-cut-m", type=float, default=1.0)
    ap.add_argument("--strict-max-modified-cells", type=int, default=4)
    args = ap.parse_args()
    if args.max_cut_m <= 0:
        raise RuntimeError("--max-cut-m must be positive")
    if args.max_modified_cells <= 0:
        raise RuntimeError("--max-modified-cells must be positive")
    if args.max_path_span_cells <= 0:
        raise RuntimeError("--max-path-span-cells must be positive")
    if not (0 < args.strict_max_cut_m <= args.max_cut_m):
        raise RuntimeError("--strict-max-cut-m must be positive and <= --max-cut-m")
    if not (0 < args.strict_max_modified_cells <= args.max_modified_cells):
        raise RuntimeError(
            "--strict-max-modified-cells must be positive and <= --max-modified-cells"
        )
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.dem) as src:
        dem = src.read(1).astype(np.float64)
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
        shape = src.shape
    with rasterio.open(args.core) as src:
        core = src.read(1) > 0
        if src.shape != shape or src.transform != transform or src.crs != crs:
            raise RuntimeError("historical core grid mismatch")
    core_cells = int(core.sum())
    if core_cells <= 0:
        raise RuntimeError("historical core is empty")

    def read_hydro(name):
        with rasterio.open(args.hydro_dir / name) as src:
            if src.shape != shape or src.transform != transform or src.crs != crs:
                raise RuntimeError(f"grid mismatch: {name}")
            return src.read(1)

    d8 = read_hydro("V46_V41_D8.tif")
    uparea = read_hydro("V46_V41_upstream_area_km2.tif")
    hand = read_hydro("V46_V41_HAND_drain_1km2.tif")
    jrc = read_hydro("V46_JRC_GSW1_3_occurrence_1984_2020.tif")
    filled = read_hydro("V46_V41_filled_for_routing_only.tif")

    comps, ncomp = label(core, np.ones((3, 3), np.uint8))
    candidates = pd.read_csv(args.strict_csv)
    candidates = candidates[candidates.review_status == "TIER_A_CONSENSUS_CANDIDATE"].copy()
    candidates["component_id"] = [
        int(comps[int(r), int(c)]) for r, c in zip(candidates.row, candidates.col)
    ]
    candidates = candidates[candidates.component_id > 0]
    if len(candidates) != core_cells:
        raise RuntimeError(
            f"historical strict candidate table covers {len(candidates)}/{core_cells} core cells"
        )

    ways = load_osm_ways(args.osm_dir, crs)
    component_rows = []
    cut_rows = []
    features = []

    for cid in range(1, ncomp + 1):
        mask = comps == cid
        rc = np.argwhere(mask)
        group = candidates[candidates.component_id == cid]
        if group.empty:
            continue

        wid = mode_int(group.nearest_osm_way_id)
        hid = mode_int(group.nearest_hyriv_id)
        way = ways.get(wid)
        decision = "REJECT"
        reasons = []
        proposed = []
        projection = []
        path_span = 0
        max_offset = 999
        anchor = None

        buffer1 = binary_dilation(mask, iterations=1)
        buffer2 = binary_dilation(mask, iterations=2)
        jvals = jrc[buffer1 & (jrc != 255)]
        jmax = float(jvals.max()) if jvals.size else 0.0
        uvals = uparea[buffer2 & (uparea >= 0)]
        umax = float(uvals.max()) if uvals.size else 0.0
        hvals = hand[buffer2 & (hand > -9000)]
        hmin = float(hvals.min()) if hvals.size else None
        hmed = float(np.median(hvals)) if hvals.size else None

        if way is None:
            reasons.append("NO_HISTORICAL_OSM_GEOMETRY")
        else:
            path_cells = ordered_cells(way["coords"], transform, shape, step_m=10.0)
            if not path_cells:
                reasons.append("OSM_WAY_OUTSIDE_GRID")
            else:
                parr = np.asarray(path_cells, dtype=int)
                for r, c in rc:
                    dist = np.maximum(np.abs(parr[:, 0] - r), np.abs(parr[:, 1] - c))
                    idx = int(np.argmin(dist))
                    projection.append((int(r), int(c), idx, int(dist[idx])))
                max_offset = max(x[3] for x in projection)
                idxs = [x[2] for x in projection]
                i0 = max(0, min(idxs) - 2)
                i1 = min(len(path_cells) - 1, max(idxs) + 2)
                path_span = i1 - i0 + 1
                if max_offset > 1:
                    reasons.append("COMPONENT_GT_1_CELL_FROM_HISTORICAL_OSM_CENTERLINE")
                if path_span > args.max_path_span_cells:
                    reasons.append("PATH_SPAN_EXCEEDS_CAP")

                topology = find_d8_anchor_pair(
                    path_cells[i0], path_cells[i1], d8, uparea, hand, jrc
                )
                if topology is None:
                    reasons.append("NO_DIRECT_D8_UPSTREAM_DOWNSTREAM_TOPOLOGY")
                else:
                    if topology["direction"] == "A_TO_B":
                        up_i, down_i = i0, i1
                    else:
                        up_i, down_i = i1, i0
                    up_cell = topology["up"]["cell"]
                    down_cell = topology["down"]["cell"]
                    up_fill = float(filled[up_cell])
                    down_fill = float(filled[down_cell])
                    anchor = {
                        "up": up_cell,
                        "down": down_cell,
                        "up_path_index": up_i,
                        "down_path_index": down_i,
                        "up_z": float(dem[up_cell]),
                        "down_z": float(dem[down_cell]),
                        "up_fill": up_fill,
                        "down_fill": down_fill,
                        "up_area": float(uparea[up_cell]),
                        "down_area": float(uparea[down_cell]),
                        "up_hand": float(hand[up_cell]) if hand[up_cell] > -9000 else None,
                        "down_hand": float(hand[down_cell]) if hand[down_cell] > -9000 else None,
                        "trace_steps": topology["trace_steps"],
                        "up_snap_offset": topology["up"]["offset"],
                        "down_snap_offset": topology["down"]["offset"],
                    }
                    if anchor["down_area"] + 1e-9 < anchor["up_area"]:
                        reasons.append("D8_UPSTREAM_AREA_DECREASES_DOWNSTREAM")
                    if down_fill > up_fill + 0.001:
                        reasons.append("D8_FILLED_ELEVATION_RISES_DOWNSTREAM")

                    denom = abs(down_i - up_i) or 1
                    for r, c, path_i, offset in projection:
                        if up_i < down_i:
                            frac = (path_i - up_i) / denom
                        else:
                            frac = (up_i - path_i) / denom
                        frac = min(1.0, max(0.0, float(frac)))
                        target = up_fill + (down_fill - up_fill) * frac
                        original = float(dem[r, c])
                        cut = max(0.0, original - target)
                        if cut > 1e-6:
                            proposed.append(
                                (r, c, path_i, offset, original, target, original - cut, cut)
                            )

                    max_cut = max((x[7] for x in proposed), default=0.0)
                    n_cut = len(proposed)
                    if max_cut > args.max_cut_m + 1e-9:
                        reasons.append("CUT_DEPTH_EXCEEDS_GLOBAL_CAP")
                    if n_cut > args.max_modified_cells:
                        reasons.append("MODIFIED_CELLS_EXCEED_GLOBAL_CAP")
                    if n_cut == 0:
                        reasons.append("NO_POSITIVE_CUT_NEEDED")
                    supplemental = jmax >= 25.0 or umax >= 0.5
                    if not supplemental:
                        reasons.append("NO_JRC25_OR_UPSTREAM_AREA_0_5KM2_SUPPORT")

                    geometry_ok = max_offset <= 1 and path_span <= args.max_path_span_cells
                    d8_ok = (
                        anchor["down_area"] + 1e-9 >= anchor["up_area"]
                        and down_fill <= up_fill + 0.001
                    )
                    constrained_ok = (
                        max_cut <= args.max_cut_m + 1e-9
                        and n_cut <= args.max_modified_cells
                        and n_cut > 0
                    )
                    if geometry_ok and d8_ok and supplemental and constrained_ok:
                        if (
                            max_cut <= args.strict_max_cut_m + 1e-9
                            and n_cut <= args.strict_max_modified_cells
                        ):
                            decision = "AUTO_APPROVE_STRICT"
                        else:
                            decision = "REVIEW_APPROVE_BOUNDED"

                    seg = path_cells[min(up_i, down_i) : max(up_i, down_i) + 1]
                    if up_i > down_i:
                        seg = list(reversed(seg))
                    xs, ys = [], []
                    for r, c in seg:
                        x, y = rasterio.transform.xy(transform, r, c, offset="center")
                        xs.append(x)
                        ys.append(y)
                    lon, lat = crs_transform(crs, "EPSG:4326", xs, ys)
                    features.append(
                        {
                            "type": "Feature",
                            "properties": {
                                "component_id": cid,
                                "decision": decision,
                                "osm_way_id": wid,
                                "hydrorivers_id": hid,
                                "topology_method": "DIRECT_D8_TRACE",
                                "d8_trace_steps": anchor["trace_steps"],
                            },
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [
                                    [float(x), float(y)] for x, y in zip(lon, lat)
                                ],
                            },
                        }
                    )

        max_cut = max((x[7] for x in proposed), default=0.0)
        n_cut = len(proposed)
        cut_volume = sum(x[7] for x in proposed) * abs(transform.a * transform.e)
        component_rows.append(
            {
                "component_id": cid,
                "component_cells": int(mask.sum()),
                "osm_way_id": wid,
                "osm_waterway": None if way is None else way["waterway"],
                "osm_name": None if way is None else way["name"],
                "osm_timestamp": None if way is None else way["timestamp"],
                "hydrorivers_id": hid,
                "max_projection_offset_cells": max_offset,
                "path_span_cells": path_span,
                "topology_method": None if anchor is None else "DIRECT_D8_TRACE",
                "d8_trace_steps": None if anchor is None else anchor["trace_steps"],
                "jrc_occurrence_buffer_max_pct": jmax,
                "upstream_area_buffer_max_km2": umax,
                "hand1_buffer_min_m": hmin,
                "hand1_buffer_median_m": hmed,
                "proposed_cut_cells": n_cut,
                "proposed_cut_max_m": max_cut,
                "proposed_cut_volume_m3": cut_volume,
                "upstream_anchor_row": None if anchor is None else anchor["up"][0],
                "upstream_anchor_col": None if anchor is None else anchor["up"][1],
                "downstream_anchor_row": None if anchor is None else anchor["down"][0],
                "downstream_anchor_col": None if anchor is None else anchor["down"][1],
                "upstream_anchor_z_m": None if anchor is None else anchor["up_z"],
                "downstream_anchor_z_m": None if anchor is None else anchor["down_z"],
                "upstream_anchor_filled_z_m": None if anchor is None else anchor["up_fill"],
                "downstream_anchor_filled_z_m": None if anchor is None else anchor["down_fill"],
                "upstream_anchor_area_km2": None if anchor is None else anchor["up_area"],
                "downstream_anchor_area_km2": None if anchor is None else anchor["down_area"],
                "upstream_anchor_hand_m": None if anchor is None else anchor["up_hand"],
                "downstream_anchor_hand_m": None if anchor is None else anchor["down_hand"],
                "upstream_anchor_snap_offset_cells": None if anchor is None else anchor["up_snap_offset"],
                "downstream_anchor_snap_offset_cells": None if anchor is None else anchor["down_snap_offset"],
                "decision": decision,
                "reason_codes": ";".join(reasons) if reasons else "ALL_GATES_PASS",
            }
        )

        for r, c, path_i, offset, original, target, new, cut in proposed:
            x, y = rasterio.transform.xy(transform, r, c, offset="center")
            cut_rows.append(
                {
                    "component_id": cid,
                    "row": r,
                    "col": c,
                    "x": x,
                    "y": y,
                    "original_z_m": original,
                    "target_profile_z_m": target,
                    "proposed_z_m": new,
                    "cut_depth_m": cut,
                    "osm_way_id": wid,
                    "hydrorivers_id": hid,
                    "osm_projection_offset_cells": offset,
                    "jrc_occurrence_buffer_max_pct": jmax,
                    "upstream_area_buffer_max_km2": umax,
                    "hand1_m": float(hand[r, c]) if hand[r, c] > -9000 else None,
                    "decision": decision,
                    "reason_code": "HISTORICAL_OSM+HYDRORIVERS+DIRECT_D8+HAND+JRC_OR_UPAREA+CONSTRAINED_PROFILE",
                }
            )

    comp = pd.DataFrame(component_rows)
    cuts = pd.DataFrame(cut_rows)
    comp_path = args.out_dir / "V46_topology_components.csv"
    cut_path = args.out_dir / "V46_proposed_cut_cells.csv"
    geo_path = args.out_dir / "V46_candidate_paths.geojson"
    comp.to_csv(comp_path, index=False, encoding="utf-8-sig")
    cuts.to_csv(cut_path, index=False, encoding="utf-8-sig")
    geo_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
        encoding="utf-8",
    )

    approved = cuts[cuts.decision == "AUTO_APPROVE_STRICT"] if not cuts.empty else cuts
    mask = np.zeros(shape, np.uint8)
    if not approved.empty:
        mask[approved.row.astype(int), approved.col.astype(int)] = 1
    mask_path = args.out_dir / "V46_auto_approved_strict_cut_mask.tif"
    p = profile.copy()
    p.update(driver="GTiff", dtype="uint8", nodata=0, compress="deflate", count=1)
    with rasterio.open(mask_path, "w", **p) as dst:
        dst.write(mask, 1)

    summary = {
        "status": "TOPOLOGY_AND_CUT_DRY_RUN_NO_DEM_MODIFICATION",
        "seed_cells": core_cells,
        "core_scope": "historical_strict_tierA_core",
        "components": int(len(comp)),
        "decision_counts": comp.decision.value_counts().to_dict() if not comp.empty else {},
        "direct_d8_topology_components": int(comp.topology_method.notna().sum()) if not comp.empty else 0,
        "auto_approved_components": int((comp.decision == "AUTO_APPROVE_STRICT").sum()) if not comp.empty else 0,
        "bounded_review_components": int((comp.decision == "REVIEW_APPROVE_BOUNDED").sum()) if not comp.empty else 0,
        "auto_approved_cut_cells": int(len(approved)),
        "auto_approved_cut_volume_m3": float(
            approved.cut_depth_m.sum() * abs(transform.a * transform.e)
            if not approved.empty
            else 0.0
        ),
        "constraints": {
            "historical_osm_projection_max_offset_cells": 1,
            "direct_d8_topology_required": True,
            "auto_strict_max_cut_m": args.strict_max_cut_m,
            "auto_strict_max_modified_cells_per_component": args.strict_max_modified_cells,
            "bounded_max_cut_m": args.max_cut_m,
            "bounded_max_modified_cells_per_component": args.max_modified_cells,
            "max_path_span_cells": args.max_path_span_cells,
            "supplemental_evidence": "JRC occurrence >=25% within 1 cell OR D8 upstream area >=0.5 km2 within 2 cells",
        },
        "invariants": {
            "dem_modified": False,
            "seed_current_osm_used_as_evidence": False,
            "sentinel1_2021_used": False,
            "historical_osm_required": True,
            "jrc_temporal_coverage": "1984-2020",
            "d8_source_dem": str(args.dem),
            "d8_source_dem_sha256": sha256(args.dem),
        },
        "outputs": {
            "components": str(comp_path),
            "cuts": str(cut_path),
            "paths": str(geo_path),
            "auto_mask": str(mask_path),
        },
    }
    summary_path = args.out_dir / "V46_topology_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    inputs = [
        args.dem,
        args.core,
        args.core_manifest,
        args.strict_csv,
        args.hydro_dir / "V46_V41_D8.tif",
        args.hydro_dir / "V46_V41_upstream_area_km2.tif",
        args.hydro_dir / "V46_V41_HAND_drain_1km2.tif",
        args.hydro_dir / "V46_JRC_GSW1_3_occurrence_1984_2020.tif",
        args.hydro_dir / "V46_V41_filled_for_routing_only.tif",
        args.osm_dir / "historical_osm_manifest.json",
    ]
    outputs = [comp_path, cut_path, geo_path, mask_path, summary_path]
    manifest = {
        "algorithm": str(Path(__file__)),
        "algorithm_sha256": sha256(Path(__file__)),
        "inputs": {str(p): sha256(p) for p in inputs},
        "outputs": {str(p): sha256(p) for p in outputs},
    }
    manifest_path = args.out_dir / "V46_topology_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "seed_cells": summary["seed_cells"],
                "components": summary["components"],
                "direct_d8_topology_components": summary["direct_d8_topology_components"],
                "decision_counts": summary["decision_counts"],
                "auto_cut_cells": summary["auto_approved_cut_cells"],
                "summary": str(summary_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
