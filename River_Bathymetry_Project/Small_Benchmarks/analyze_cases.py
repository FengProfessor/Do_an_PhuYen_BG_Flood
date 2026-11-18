"""Strict checks and paired synthetic comparisons; never promote partial output to PASS."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import netCDF4
import numpy as np

from build_cases import ARMS, SUITES, save_json, sha256


def read_output(folder: Path, case: dict, tolerances: dict) -> dict:
    expected = np.load(folder / "bed.npy", allow_pickle=False)
    with netCDF4.Dataset(folder / "result.nc") as ds:
        coords = {}
        for axis in ("x", "y"):
            candidates = [name for name in (axis, axis * 2) if name in ds.variables]
            if not candidates:
                raise ValueError(f"Missing {axis} coordinate")
            coords[axis] = np.asarray(ds[candidates[0]][:], dtype=float)
        times = np.asarray(ds["time"][:], dtype=float)
        if not len(times) or not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
            raise ValueError("Missing/non-finite/non-increasing output times")
        if abs(times[-1] - case["endtime_s"]) > tolerances["time_abs_s"]:
            raise ValueError(f"Incomplete simulation: t={times[-1]}, expected {case['endtime_s']}")
        ny, nx = expected.shape
        ex = case["x0"] + (np.arange(nx) + .5) * case["dx"]
        ey = case["ytop"] - (np.arange(ny) + .5) * case["dx"]
        if coords["x"].shape != (nx,) or coords["y"].shape != (ny,):
            raise ValueError(f"Grid shape mismatch: {len(coords['y'])}x{len(coords['x'])}, expected {ny}x{nx}")
        xi, yi = np.argsort(coords["x"]), np.argsort(-coords["y"])
        if not (np.allclose(coords["x"][xi], ex, rtol=0, atol=tolerances["coordinate_abs_m"])
                and np.allclose(coords["y"][yi], ey, rtol=0, atol=tolerances["coordinate_abs_m"])):
            raise ValueError("Coordinates do not match original ASC cell centers")
        fields = {}
        for name in ("zb", "h", "zs", "u", "v"):
            if name not in ds.variables:
                raise ValueError(f"Missing output variable {name}")
            variable = ds[name]
            dims = list(variable.dimensions)
            xdim = next((d for d in ("x", "xx") if d in dims), None)
            ydim = next((d for d in ("y", "yy") if d in dims), None)
            if xdim is None or ydim is None or set(dims) - {"time", xdim, ydim}:
                raise ValueError(f"Unsupported dimensions for {name}: {dims}; fixed regular grid required")
            values = np.ma.asarray(variable[:])
            if np.any(np.ma.getmaskarray(values)) or not np.all(np.isfinite(values)):
                raise ValueError(f"Masked/non-finite values in {name}")
            values = np.asarray(values, dtype=float)
            if "time" in dims:
                values = np.transpose(values, [dims.index("time"), dims.index(ydim), dims.index(xdim)])
            else:
                values = np.transpose(values, [dims.index(ydim), dims.index(xdim)])[None, :, :]
                if name != "zb":
                    raise ValueError(f"Missing time dimension in {name}")
            fields[name] = values[:, yi, :][:, :, xi]
        if any(a.shape[1:] != expected.shape for a in fields.values()):
            raise ValueError("Raster output shape mismatch")
        if any(len(fields[k]) != len(times) for k in ("h", "zs", "u", "v")):
            raise ValueError("Time axis does not match output fields")
    return dict(times=times, **fields)


def check_case(folder: Path, case: dict, tol: dict, *, require_run: bool = True) -> tuple[dict, dict | None]:
    report = {"case": case["name"], "kind": case["kind"], "status": "FAIL", "checks": {}}
    try:
        for name, digest in case["inputs"].items():
            if sha256(folder / name) != digest:
                raise ValueError(f"Input changed since preparation: {name}")
        if require_run:
            state = json.loads((folder / "run.json").read_text(encoding="utf-8"))
            if state["status"] != "COMPLETED" or state["returncode"] != 0:
                raise ValueError(f"Worker did not complete: {state['status']}")
            if sha256(folder.parent / "manifest.json") != state["manifest_sha256"]:
                raise ValueError("Manifest/tolerances changed after execution")
            if sha256(folder / "result.nc") != state["output_sha256"]:
                raise ValueError("Output changed after worker completed")
            report["runtime_digest"] = state["runtime_digest"]
            report["device"] = state["device"]
            report["wall_seconds"] = state["wall_seconds"]
        data = read_output(folder, case, tol)
        bed = np.load(folder / "bed.npy", allow_pickle=False)
        bed_error = float(np.max(abs(data["zb"] - bed)))
        identity_error = float(np.max(abs(data["zs"] - data["h"] - data["zb"])))
        minimum_h = float(data["h"].min())
        final_h = data["h"][-1]
        area = case["dx"] ** 2
        final_volume = float(final_h.sum() * area)
        initial_volume = float(np.maximum(case["zsinit_m"] - bed, 0.).sum(dtype=float) * area)
        checks = {"bed_preserved": bed_error <= tol["bed_abs_m"],
                  "h_zs_zb_identity": identity_error <= tol["identity_abs_m"],
                  "nonnegative_h": minimum_h >= tol["negative_depth_m"]}
        metrics = {"final_time_s": float(data["times"][-1]), "frames": len(data["times"]),
                   "bed_max_error_m": bed_error, "identity_max_error_m": identity_error,
                   "min_h_m": minimum_h, "final_volume_m3": final_volume,
                   "theoretical_initial_volume_m3": initial_volume,
                   "max_h_m": float(data["h"].max()),
                   "area_h_gt_0_3_m2": float((final_h > .3).sum() * area)}
        if case["kind"] == "rain":
            target = float(10. / 3_600_000 * data["times"][-1])
            error = float(abs(final_h - target).max())
            metrics.update(expected_depth_m=target, rain_max_error_m=error)
            checks["rain_analytic_depth"] = error <= tol["rain_abs_m"]
        if case["kind"] == "lake":
            error = float(abs(data["zs"] - case["zsinit_m"]).max())
            speed = float(np.hypot(data["u"], data["v"]).max())
            metrics.update(lake_max_zs_error_m=error, lake_max_speed_m_s=speed)
            checks.update(lake_level=error <= tol["lake_zs_abs_m"], lake_velocity=speed <= tol["lake_speed_m_s"])
        if case["kind"] == "river_volume":
            expected_volume = float(case["river_peak_m3_s"] * data["times"][-1])
            error = float(abs(final_volume - initial_volume - expected_volume) / max(expected_volume, 1.))
            metrics.update(expected_added_volume_m3=float(expected_volume), river_relative_volume_error=error)
            checks["closed_river_mass"] = bool(error <= tol["river_relative_volume"])
        budget_path = folder / "budget.json"
        if budget_path.exists():
            budget = json.loads(budget_path.read_text(encoding="utf-8"))
            names = ("boundary_reset", "flux_divergence", "rain", "river", "infiltration")
            flux = sum(float(budget[f"{name}_volume_m3"]) for name in names)
            start, finish = budget["initial_volume_m3"], budget["current_volume_m3"]
            if start is None or finish is None:
                raise ValueError("Budget contains no observed steps")
            residual = float(finish - start - flux)
            scale = max(abs(start), sum(abs(float(budget[f"{k}_volume_m3"])) for k in names), 1.)
            metrics.update(budget_physical_residual_m3=residual, budget_relative_residual=abs(residual) / scale,
                           clamp_added_m3=budget["clamp_added_volume_m3"],
                           clamp_removed_m3=budget["clamp_removed_volume_m3"])
            checks["budget_complete"] = abs(budget["simulated_time_s"] - case["endtime_s"]) <= tol["time_abs_s"]
            # Không trừ phần clamp để làm đẹp cân bằng: giữ nguyên phần thêm/bớt số học.
            checks["budget_residual"] = abs(residual) / scale <= tol["budget_relative_residual"]
        elif case["kind"] in ("channel", "sill"):
            checks["budget_available"] = False
        report.update(status="PASS" if all(checks.values()) else "FAIL", checks=checks, metrics=metrics)
        return report, data
    except (OSError, ValueError, KeyError, IndexError, RuntimeError) as exc:
        report["error"] = str(exc)
        return report, None


def compare_group(root: Path, domain: str, results: dict, datasets: dict,
                  names: list[str], tol: dict) -> list[dict]:
    ref_name = f"{domain}_REF"
    if ref_name not in datasets:
        return []
    ref = datasets[ref_name]
    ref_bed = np.load(root / ref_name / "bed.npy", allow_pickle=False)
    rows = []
    for name in names:
        if name not in datasets or results[name]["status"] != "PASS":
            continue
        if results[name].get("runtime_digest") != results[ref_name].get("runtime_digest"):
            raise ValueError("Cannot compare different runtimes")
        if results[name].get("device") != results[ref_name].get("device"):
            raise ValueError("Cannot compare different devices")
        item = datasets[name]
        if abs(item["times"][-1] - ref["times"][-1]) > tol["time_abs_s"]:
            raise ValueError("Comparison outputs are not at the same time")
        wet, ref_wet = item["h"][-1] > .3, ref["h"][-1] > .3
        union = wet | ref_wet
        common_wet = (item["h"][-1] > 1e-4) & (ref["h"][-1] > 1e-4)
        zs_diff = item["zs"][-1] - ref["zs"][-1]
        bed = np.load(root / name / "bed.npy", allow_pickle=False)
        rows.append({"case": name, "reference": ref_name,
                     "bed_rmse_m": float(np.sqrt(np.mean((bed - ref_bed) ** 2))),
                     "common_wet_cells": int(common_wet.sum()),
                     "zs_rmse_common_wet_m": float(np.sqrt(np.mean(zs_diff[common_wet] ** 2))) if common_wet.any() else None,
                     "h_rmse_all_cells_m": float(np.sqrt(np.mean((item["h"][-1] - ref["h"][-1]) ** 2))),
                     "wet_iou_at_0_3": float((wet & ref_wet).sum() / union.sum()) if union.any() else None,
                     "wet_union_cells": int(union.sum()),
                     "area_h_gt_0_3_m2": float(wet.sum() * 900.),
                     "bed_lowering_volume_m3": float((np.load(root / f"{domain}_RAW" / "bed.npy") - bed).sum(dtype=float) * 900.)})
    return rows


def plot_domain(root: Path, domain: str, datasets: dict) -> None:
    names = [f"{domain}_{arm}" for arm in ARMS if f"{domain}_{arm}" in datasets]
    if not names:
        return
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for name in names:
        data = datasets[name]
        bed = np.load(root / name / "bed.npy", allow_pickle=False)
        column = bed.shape[1] // 3
        yy = (np.arange(bed.shape[0]) + .5) * 30
        axes[0].plot(yy, bed[:, column], label=name)
        axes[1].plot(yy, np.where(data["h"][-1, :, column] > 1e-4, data["zs"][-1, :, column], np.nan), label=name)
    axes[0].set(title="Synthetic bed cross-section", xlabel="Distance across domain (m)", ylabel="Bed elevation (m)")
    axes[1].set(title="Water surface at saved final time", xlabel="Distance across domain (m)", ylabel="Water elevation (m)")
    for axis in axes:
        axis.grid(alpha=.2)
        axis.legend(fontsize=8)
    fig.suptitle("Synthetic benchmark: same solver, independent trapezoidal reference; not field validation")
    fig.tight_layout()
    fig.savefig(root / "reports" / f"{domain}_cross_sections.png", dpi=160)
    plt.close(fig)


def analyze(root: Path, suite: str) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    results, datasets = {}, {}
    for name in SUITES[suite]:
        result, data = check_case(root / name, manifest["cases"][name], manifest["tolerances"])
        results[name] = result
        if data is not None and result["status"] == "PASS":
            datasets[name] = data
    rows = []
    for domain in ("channel", "sill"):
        rows.extend(compare_group(root, domain, results, datasets, SUITES[suite], manifest["tolerances"]))
        plot_domain(root, domain, datasets)
    if rows:
        with (reports / f"{suite}_comparison.csv").open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    result = {"suite": suite, "status": "PASS" if all(r["status"] == "PASS" for r in results.values()) else "FAIL",
              "cases": results, "comparisons": rows,
              "meaning_of_PASS": "Predeclared numerical/input checks passed; not proof that V49 is more accurate",
              "interpretation": manifest["interpretation"]}
    save_json(reports / f"{suite}_summary.json", result)
    lines = [f"# Small benchmark: {suite}", "", f"Checks: **{result['status']}**", "",
             "PASS chỉ xác nhận các kiểm tra đã định trước. Không tự kết luận V49 tốt hơn hoặc kiểm định Phú Yên.", "",
             "| Case | Status | Evidence |", "|---|---|---|"]
    for name, item in results.items():
        evidence = item.get("error") or ", ".join(k for k, v in item["checks"].items() if not v) or "Predeclared checks passed"
        lines.append(f"| {name} | {item['status']} | {evidence} |")
    lines += ["", "Xem JSON để đọc sai số, thời gian, cân bằng và hash runtime; CSV chứa đối chứng với REF.",
              "REF là nghiệm cùng bộ giải trên đáy biết trước, không phải số đo. Không cộng/so sánh các lượt khác runtime.",
              "SIMPLE và V49 nhận cùng độ sâu, bề rộng; thể tích sửa có thể khác. Kịch bản sill minh họa vùng bảo vệ đã biết."]
    (reports / f"{suite}_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
