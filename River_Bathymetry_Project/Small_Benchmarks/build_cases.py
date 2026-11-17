"""Small synthetic inputs using the actual Method1 raster functions, not a new solver."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, box

HERE = Path(__file__).resolve().parent
METHOD = HERE.parent / "V49_Method1_DHG_Clamped/v49_method1_dhg_clamped.py"
DX = 30.0
X0, YTOP = 270000.0, 1478000.0
ARMS = ("REF", "RAW", "SIMPLE", "V49")
SUITES = {
    "smoke": ["grid", "rain_mm", "rain_ms", "lake", "river_volume"],
    "channel": [f"channel_{arm}" for arm in ARMS],
    "sill": [f"sill_{arm}" for arm in ARMS],
    "depth": ["channel_REF", "channel_V49", "channel_HALF", "channel_DOUBLE"],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def load_method():
    spec = importlib.util.spec_from_file_location("small_benchmark_method1", METHOD)
    if spec is None or spec.loader is None:
        raise ImportError(METHOD)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_asc(path: Path, data: np.ndarray) -> None:
    ny, nx = data.shape
    with path.open("w", encoding="ascii", newline="\n") as f:
        f.write(f"ncols {nx}\nnrows {ny}\nxllcorner {X0}\n")
        f.write(f"yllcorner {YTOP - ny * DX}\ncellsize {DX}\nNODATA_value -9999\n")
        np.savetxt(f, data, fmt="%.9f")
    path.with_suffix(".prj").write_text(rasterio.crs.CRS.from_epsg(32649).to_wkt(), encoding="ascii")


def method_dem(module, raw: np.ndarray, protected: np.ndarray, out: Path,
               depth: float = 2.0, duplicate: bool = False, crossing: bool = False) -> np.ndarray:
    """Exercise the production rasterizer/merger/writer with synthetic supplied depths."""
    ny, nx = raw.shape
    center_y = YTOP - ny * DX / 2
    line = LineString([(X0 + 3 * DX, center_y), (X0 + (nx - 1) * DX, center_y)])
    row = dict(reach_id="synthetic_1", width_m=240.0, in_scope_b3_89=True,
               v49c_object_ids="water", wse_proxy_upstream_m=1.0,
               wse_proxy_downstream_m=0.0, dhg1_low_m=depth * 0.5,
               dhg1_central_m=depth, dhg1_high_m=depth * 2,
               in_scope_b1_41=True, in_scope_a_21=True, in_scope_b2_82=True,
               in_v49_e_2=True, geometry=line)
    rows = [row]
    if duplicate:
        rows.append(dict(row, reach_id="synthetic_duplicate"))
    if crossing:
        vertical = LineString([(X0 + nx * DX / 2, YTOP - 3 * DX),
                               (X0 + nx * DX / 2, YTOP - (ny - 3) * DX)])
        rows.append(dict(row, reach_id="synthetic_crossing", geometry=vertical))
    reaches = gpd.GeoDataFrame(rows, crs="EPSG:32649")
    objects = gpd.GeoDataFrame([dict(object_id="water", geometry=box(
        X0, YTOP - ny * DX, X0 + nx * DX, YTOP))], crs="EPSG:32649")
    profile = dict(driver="GTiff", height=ny, width=nx, count=1,
                   dtype="float32", crs="EPSG:32649", nodata=-9999.0,
                   transform=from_origin(X0, YTOP, DX, DX))
    old_shape, old_transform = module.GRID_SHAPE, module.GRID_TRANSFORM
    # Hàm gốc dùng gốc tọa độ và bước 30 m cố định; giữ hai giá trị đó,
    # chỉ thu nhỏ kích thước trong module đã nạp riêng cho tiến trình này.
    module.GRID_SHAPE, module.GRID_TRANSFORM = raw.shape, profile["transform"]
    try:
        footprints = module.precompute_reach_footprints(reaches, objects, protected)
        result = module.generate_method1_carved_rasters(
            reaches, footprints, raw, profile, protected, np.zeros_like(raw),
            {"synthetic": True, "v48_cuts": 0}, out,
        )
        path = Path(result["rasters"]["SCOPE_B1_41_CENTRAL"]["dem_tif_path"])
        with rasterio.open(path) as ds:
            return ds.read(1)
    finally:
        module.GRID_SHAPE, module.GRID_TRANSFORM = old_shape, old_transform


def geometry_checks(module, raw: np.ndarray, protected: np.ndarray,
                    first: np.ndarray, out: Path) -> dict:
    duplicate = method_dem(module, raw, protected, out / "duplicate", duplicate=True)
    crossed = method_dem(module, raw, protected, out / "crossing", crossing=True)
    z = np.array([[-4.5, -3.8, -3.5, -3.0, 0.0, 2.0]], dtype=np.float32)
    proposals = np.full_like(z, 5.0)
    clamped, _, _ = module.clamp_bed_elevation(z, proposals)
    weights = module.raised_cosine_weights_vectorized(np.array([0., 60., 120., 180.]), 120.)
    checks = {
        "no_raised_cells": bool(np.all(first <= raw + 1e-6)),
        "protected_unchanged": bool(np.array_equal(first[protected], raw[protected])),
        "duplicate_reach_unchanged": bool(np.array_equal(first, duplicate)),
        "crossing_not_sum_depth": bool(np.max(raw - crossed) <= 2. + 1e-6),
        "crossing_adds_new_cells": bool(np.count_nonzero(raw - crossed > 1e-6) > np.count_nonzero(raw - first > 1e-6)),
        "below_floor_unchanged": bool(np.array_equal(clamped[0, :3], z[0, :3])),
        "above_floor_not_lower_than_floor": bool(np.all(clamped[z >= -3.5] >= -3.5)),
        "taper_center_half_edge": bool(np.allclose(weights, [1., .5, 0., 0.], atol=1e-12)),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
            "protected_cells": int(protected.sum()), "method_sha256": sha256(METHOD),
            "scope": "Production raster functions on synthetic supplied depth; not DHG depth calibration"}


def make_case(root: Path, name: str, bed: np.ndarray, *, end: float, kind: str,
              initial_zs: float = -100., rain: str | None = None,
              river: bool = False, closed: bool = True, peak: float = 200.) -> dict:
    folder = root / name
    folder.mkdir()
    bed = np.asarray(bed, dtype=np.float32)
    write_asc(folder / "bed.asc", bed)
    np.save(folder / "bed.npy", bed, allow_pickle=False)
    ny, nx = bed.shape
    lines = ["# Synthetic verification only; no Phu Yen observation or calibrated bathymetry.",
             "bathy = bed.asc;", "dx = 30;", "dy = 30;", "mask = 9999;", "minmask = -4;",
             "frictionmodel = -1;", "cf = 0.035;", "il = 0;", "cl = 0;",
             f"zsinit = {initial_zs};", "zsoffset = 0;", "left = 0;",
             f"right = {0 if closed else 2};", "top = 0;", "bottom = 0;",
             "CFL = 0.4;", "eps = 0.0001;", "smallnc = 0;",
             f"endtime = {end};", f"outputtimestep = {min(60., end)};",
             "outfile = result.nc;", "outvars = zb, h, zs, u, v;"]
    if rain:
        rate = 10. if rain == "mm/h" else 10. / 3_600_000
        (folder / "rain.txt").write_text(f"0 {rate:.16g}\n{end + 3600} {rate:.16g}\n", encoding="ascii")
        lines += ["rainfile = rain.txt;", f"rainunits = {rain};"]
    if river:
        if kind == "river_volume":
            points = [(0., peak), (end + 3600, peak)]
        else:
            points = [(0., 0.), (end * .2, peak), (end * .6, peak), (end, 0.), (end + 3600, 0.)]
        (folder / "river.txt").write_text("".join(f"{t:g} {q:g}\n" for t, q in points), encoding="ascii")
        cy = YTOP - ny * DX / 2
        # Nguồn nằm trong miền, cách biên >= ba ô, không trùng ô biên đóng.
        lines += [f"river = river.txt, {X0 + 3 * DX}, {X0 + 5 * DX}, {cy - DX}, {cy + DX};"]
    (folder / "BG_param.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    input_names = ["bed.asc", "bed.prj", "bed.npy", "BG_param.txt"]
    input_names += [p for p in ("rain.txt", "river.txt") if (folder / p).exists()]
    case = {"name": name, "kind": kind, "shape": [ny, nx], "dx": DX,
            "x0": X0, "ytop": YTOP, "endtime_s": end, "zsinit_m": initial_zs,
            "closed": closed, "rain_units": rain, "river_peak_m3_s": peak if river else 0.,
            "inputs": {p: sha256(folder / p) for p in input_names}}
    save_json(folder / "case.json", case)
    return case


def plot_inputs(root: Path, domain: str, beds: dict[str, np.ndarray]) -> None:
    import matplotlib.pyplot as plt
    target = root / "reports"
    target.mkdir(exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.5), sharex=True, sharey=True)
    low = min(float(a.min()) for a in beds.values())
    high = max(float(a.max()) for a in beds.values())
    for axis, (name, data) in zip(axes.flat, beds.items()):
        plot = axis.imshow(data, origin="upper", extent=(0, data.shape[1] * DX, 0, data.shape[0] * DX),
                           vmin=low, vmax=high, cmap="terrain")
        axis.set(title=name, xlabel="Local x (m)", ylabel="Local y (m)")
    fig.colorbar(plot, ax=list(axes.flat), label="Synthetic bed elevation (m)", shrink=.75)
    fig.suptitle(f"{domain}: synthetic INPUTS only; supplied depth, not observed river bathymetry")
    fig.savefig(target / f"{domain}_inputs.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def prepare(root: Path, channel_seconds: float = 3600.) -> dict:
    if not 300 <= channel_seconds <= 21600:
        raise ValueError("channel-seconds must be 300..21600 (pilot/transient, not assumed steady)")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    module = load_method()
    cases = []
    rr, cc = np.indices((32, 48))
    grid = (-3.8 + rr * .07 + cc * .013).astype(np.float32)
    cases.append(make_case(root, "grid", grid, end=1., kind="grid"))
    for units, name in [("mm/h", "rain_mm"), ("m/s", "rain_ms")]:
        cases.append(make_case(root, name, np.zeros((32, 32)), end=3600., kind="rain", rain=units))
    rr, cc = np.indices((32, 32))
    lake = -.5 + .3 * np.sin(cc / 5.) * np.cos(rr / 7.)
    cases.append(make_case(root, "lake", lake, end=120., kind="lake", initial_zs=1.))
    cases.append(make_case(root, "river_volume", np.zeros((32, 32)), end=60.,
                           kind="river_volume", river=True, peak=10.))
    rr, cc = np.indices((64, 128))
    xx = (cc + .5) * DX
    distance = abs((rr + .5) * DX - 960.)
    plane = (.0005 * (128 * DX - xx)).astype(np.float32)
    channel_mask = (distance < 120.) & (xx >= 90.) & (xx <= 3810.)
    # REF hình thang được lập độc lập với cos²; độ sâu 2 m cấp như nhau
    # cho SIMPLE và Method1. Chỉ kiểm tra biểu diễn DEM, không suy ra Qbf.
    trapezoid = np.clip((120. - distance) / 78., 0., 1.) * channel_mask
    geometry_reports = {}
    for domain in ("channel", "sill"):
        raw = plane.copy()
        protected = np.zeros_like(raw, dtype=bool)
        if domain == "sill":
            protected = (abs(xx - 1920.) <= 30.) & (distance <= 180.)
            raw[protected] += .8
        ref = raw - np.float32(2. * trapezoid)
        ref[protected] = raw[protected]
        simple = raw - np.float32(2. * channel_mask)
        v49 = method_dem(module, raw, protected, root / "geometry" / domain / "production")
        beds = dict(REF=ref, RAW=raw, SIMPLE=simple, V49=v49)
        plot_inputs(root, domain, beds)
        for arm, bed in beds.items():
            cases.append(make_case(root, f"{domain}_{arm}", bed, end=channel_seconds,
                                   kind=domain, river=True, closed=False))
            np.save(root / f"{domain}_{arm}" / "protected.npy", protected, allow_pickle=False)
            cases[-1]["inputs"]["protected.npy"] = sha256(root / f"{domain}_{arm}" / "protected.npy")
            save_json(root / f"{domain}_{arm}" / "case.json", cases[-1])
        geometry_reports[domain] = geometry_checks(module, raw, protected, v49, root / "geometry" / domain)
        if domain == "channel":
            for arm, depth in [("HALF", 1.), ("DOUBLE", 4.)]:
                bed = method_dem(module, raw, protected, root / "geometry" / arm, depth=depth)
                cases.append(make_case(root, f"channel_{arm}", bed, end=channel_seconds,
                                       kind=domain, river=True, closed=False))
    save_json(root / "geometry_checks.json", geometry_reports)
    manifest = {
        "schema": "small-benchmarks-1", "status": "PREPARED_NOT_SIMULATED", "suites": SUITES,
        "method": {"path": str(METHOD), "sha256": sha256(METHOD)},
        "benchmark_code": {p.name: sha256(p) for p in HERE.glob("*.py")},
        "cases": {case["name"]: case for case in cases},
        "tolerances": {"bed_abs_m": 1e-5, "coordinate_abs_m": 1e-5,
                       "rain_abs_m": 1e-5, "lake_zs_abs_m": 1e-4,
                       "lake_speed_m_s": 1e-4, "river_relative_volume": .01,
                       "identity_abs_m": 1e-4, "negative_depth_m": -1e-6,
                       "time_abs_s": 1., "budget_relative_residual": .01},
        "interpretation": "Synthetic module/solver verification, not independent Phu Yen validation. "
                          "Depth is supplied equally to SIMPLE and V49; DHG estimation is not tested. "
                          "REF is same-solver reference, not an exact hydraulic solution. "
                          "SIMPLE has the same width/depth but no taper/protection; volumes differ.",
    }
    save_json(root / "manifest.json", manifest)
    return manifest
