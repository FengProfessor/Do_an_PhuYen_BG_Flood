"""Portable runner for the project's actual Python runtime; serial, bounded, auditable."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
import zipfile

from build_cases import HERE, METHOD, SUITES, prepare, save_json, sha256


def runtime_python(runtime: Path) -> Path:
    runtime = runtime.resolve()
    candidates = [runtime / "python", runtime]
    for candidate in candidates:
        if (candidate / "run_bgflood.py").is_file() and (candidate / "bg_flood").is_dir():
            return candidate
    raise FileNotFoundError(f"Expected run_bgflood.py and bg_flood/ in {runtime} or its python/ directory")


def fingerprint(runtime: Path) -> dict:
    source = runtime_python(runtime)
    files = {p.relative_to(source).as_posix(): sha256(p) for p in sorted(source.rglob("*.py"))
             if "__pycache__" not in p.parts and ".venv" not in p.parts}
    observer = HERE.parent / "v49_runtime_observer.py"
    packages = {}
    for name in ("numpy", "netCDF4", "rasterio", "cupy", "cupy-cuda11x", "cupy-cuda12x"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    data = {"source_files": files, "observer_sha256": sha256(observer),
            "benchmark_code": {p.name: sha256(p) for p in sorted(HERE.glob("*.py"))},
            "python": sys.version, "packages": packages}
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    return dict(data, digest=digest, runtime_path=str(source), interpreter=sys.executable)


def verify_prepared(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if sha256(METHOD) != manifest["method"]["sha256"]:
        raise ValueError("Method1 source changed since prepare. Prepare a fresh output folder.")
    for name, digest in manifest["benchmark_code"].items():
        if sha256(HERE / name) != digest:
            raise ValueError(f"Benchmark code changed since prepare: {name}. Prepare again.")
    for name, case in manifest["cases"].items():
        for filename, digest in case["inputs"].items():
            if sha256(root / name / filename) != digest:
                raise ValueError(f"Prepared input changed: {name}/{filename}")
        saved_case = json.loads((root / name / "case.json").read_text(encoding="utf-8"))
        if saved_case != case:
            raise ValueError(f"case.json differs from manifest: {name}")
    return manifest


def worker(runtime: Path, folder: Path, device: str) -> None:
    source = runtime_python(runtime)
    folder = folder.resolve()
    os.chdir(folder)
    sys.path.insert(0, str(source))
    if device == "cpu":
        # Chọn backend trước khi nạp runtime; không sửa mã/bước thời gian của solver.
        sys.modules["cupy"] = None
    else:
        import cupy
        cupy.cuda.Device(0).use()
    from bg_flood import gpu_backend, write_txtlog
    import run_bgflood
    if not Path(run_bgflood.__file__).resolve().is_relative_to(source):
        raise RuntimeError("Imported wrong runtime")
    actual_gpu = bool(gpu_backend.is_gpu)
    if actual_gpu != (device == "cuda"):
        raise RuntimeError(f"Backend mismatch: requested {device}, actual GPU={actual_gpu}")
    write_txtlog._LOG_FILE = str(folder / "engine.log")
    from bg_flood.read_input import read_param_file, read_bathy_data
    case = json.loads((folder / "case.json").read_text(encoding="utf-8"))
    param, forcing = read_param_file(str(folder / "BG_param.txt"))
    param, _ = read_bathy_data(forcing, param)
    expected_shape = tuple(case["shape"])
    if (param.ny, param.nx) != expected_shape:
        raise ValueError(f"Runtime input grid {(param.ny, param.nx)} != prepared {expected_shape}; no cropping allowed")
    sys.path.insert(0, str(HERE.parent))
    from v49_runtime_observer import install_budget_observer
    from bg_flood import flow_gpu, mainloop
    required_flow = ("update_ev_vec", "add_rain_vec", "add_river_vec", "apply_infiltration_gpu", "adv_kernel_vec")
    missing = [name for name in required_flow if not hasattr(flow_gpu, name)]
    missing += ["mainloop." + name for name in ("update_bnd", "flow_gpu") if not hasattr(mainloop, name)]
    if missing and case["kind"] in ("channel", "sill"):
        raise RuntimeError(f"Budget observer incompatible with this runtime: {missing}; use the actual R1 runtime")
    # Kiểm tra tính tương thích trước khi gắn hook, tránh gắn dở rồi chạy solver.
    budget = None if missing else install_budget_observer(folder / "budget.json")
    save_json(folder / "worker_metadata.json", {"runtime_driver": str(Path(run_bgflood.__file__).resolve()),
              "device": device, "python": sys.version, "grid_shape": list(expected_shape),
              "observer": "UNAVAILABLE_FOR_OLD_RUNTIME" if missing else "Existing read-only discrete budget observer",
              "missing_observer_api": missing})
    run_bgflood.run_model(str(folder / "BG_param.txt"))
    if budget is not None:
        save_json(folder / "budget.json", budget)


def archive_failed(folder: Path) -> None:
    archive = folder / "attempts" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive.mkdir(parents=True)
    for name in ("result.nc", "run.json", "console.log", "engine.log", "budget.json", "worker_metadata.json"):
        source, dest = folder / name, archive / name
        if source.is_file():
            # Các đường dẫn cố định chỉ thuộc thư mục ca thử hiện tại.
            if not dest.resolve().is_relative_to(folder.resolve()):
                raise ValueError("Archive path escaped case directory")
            source.rename(dest)


def run_suite(root: Path, runtime: Path, suite: str, device: str,
              timeout: float, retry_failed: bool = False) -> dict:
    from analyze_cases import analyze
    root, runtime = root.resolve(), runtime.resolve()
    verify_prepared(root)
    identity = fingerprint(runtime)
    lock = root / ".running.lock"
    # Không khởi động hai bộ thử trên cùng thư mục. File khóa còn lại sau mất điện
    # được giữ để người dùng kiểm tra tiến trình trước khi bỏ khóa.
    with lock.open("x", encoding="ascii") as f:
        f.write(str(os.getpid()))
    try:
        if suite != "smoke":
            smoke = analyze(root, "smoke")
            if smoke["status"] != "PASS":
                raise RuntimeError("Smoke checks must PASS first; inspect reports/smoke_summary.md")
            for item in smoke["cases"].values():
                if item["runtime_digest"] != identity["digest"] or item["device"] != device:
                    raise RuntimeError("Run smoke with this exact runtime and device before channel/sill/depth")
        save_json(root / f"runtime_{identity['digest'][:12]}.json", identity)
        for name in SUITES[suite]:
            folder = root / name
            state_path = folder / "run.json"
            if fingerprint(runtime)["digest"] != identity["digest"]:
                raise RuntimeError("Runtime changed during suite")
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state["status"] == "COMPLETED":
                    if state["runtime_digest"] != identity["digest"] or state["device"] != device:
                        raise RuntimeError(f"{name} belongs to another runtime/device; use a new output directory")
                    if sha256(folder / "result.nc") != state["output_sha256"]:
                        raise RuntimeError(f"{name} output changed after completion")
                    print(f"[Benchmark] Reuse verified completed case: {name}", flush=True)
                    continue
                if not retry_failed:
                    raise RuntimeError(f"{name} has an earlier failed/incomplete attempt; use --retry-failed or new output")
                archive_failed(folder)
            if (folder / "result.nc").exists():
                raise FileExistsError(f"Untracked output exists: {folder / 'result.nc'}")
            state = {"case": name, "status": "RUNNING", "runtime_digest": identity["digest"],
                     "device": device, "timeout_seconds": timeout, "returncode": None,
                     "manifest_sha256": sha256(root / "manifest.json"),
                     "started_utc": datetime.now(timezone.utc).isoformat()}
            save_json(state_path, state)
            command = [sys.executable, "-X", "utf8", "-u", str(Path(__file__).resolve()),
                       "_worker", "--runtime", str(runtime), "--folder", str(folder), "--device", device]
            start = time.monotonic()
            print(f"[Benchmark] Run {name}, timeout {timeout:g}s, {device}", flush=True)
            try:
                env = os.environ.copy()
                env["MPLBACKEND"] = "Agg"
                with (folder / "console.log").open("w", encoding="utf-8") as log:
                    completed = subprocess.run(command, cwd=folder, stdout=log, stderr=subprocess.STDOUT,
                                               timeout=timeout, env=env, check=False,
                                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                state["returncode"] = completed.returncode
                state["status"] = "COMPLETED" if completed.returncode == 0 and (folder / "result.nc").exists() else "FAILED"
                if state["status"] == "COMPLETED":
                    state["output_sha256"] = sha256(folder / "result.nc")
            except subprocess.TimeoutExpired:
                state["status"] = "TIMEOUT"
            except KeyboardInterrupt:
                state["status"] = "INTERRUPTED"
                raise
            finally:
                state["wall_seconds"] = round(time.monotonic() - start, 4)
                save_json(state_path, state)
            if fingerprint(runtime)["digest"] != identity["digest"]:
                state["status"] = "RUNTIME_CHANGED"
                save_json(state_path, state)
                raise RuntimeError("Runtime changed while case was running")
            print(f"[Benchmark] {name}: {state['status']} in {state['wall_seconds']}s", flush=True)
        result = analyze(root, suite)
        geometry = json.loads((root / "geometry_checks.json").read_text(encoding="utf-8"))
        if any(item["status"] != "PASS" for item in geometry.values()):
            raise RuntimeError("Geometry checks failed")
        return result
    finally:
        lock.unlink(missing_ok=True)


def bundle(root: Path) -> Path:
    destination = root / f"benchmark_report_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.zip"
    paths = [root / "manifest.json", root / "geometry_checks.json"]
    paths += list(root.glob("runtime_*.json")) + list((root / "reports").glob("*"))
    for case in json.loads((root / "manifest.json").read_text(encoding="utf-8"))["cases"]:
        paths += [root / case / name for name in ("case.json", "BG_param.txt", "run.json", "worker_metadata.json", "budget.json", "console.log")]
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for path in paths:
            if path.is_file():
                z.write(path, path.relative_to(root).as_posix())
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Generate all small inputs without running the solver")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--channel-seconds", type=float, default=3600.)
    p = sub.add_parser("doctor", help="Check runtime layout and installed packages; no simulation")
    p.add_argument("--runtime", type=Path, required=True)
    p = sub.add_parser("run", help="Run cases serially and analyze; requires actual project Python runtime")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--suite", choices=SUITES, default="smoke")
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    p.add_argument("--timeout", type=float, default=900., help="Wall seconds allowed PER CASE")
    p.add_argument("--retry-failed", action="store_true")
    p = sub.add_parser("_worker", help=argparse.SUPPRESS)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--folder", type=Path, required=True)
    p.add_argument("--device", choices=("cpu", "cuda"), required=True)
    for command in ("analyze", "bundle"):
        p = sub.add_parser(command)
        p.add_argument("--out", type=Path, required=True)
        if command == "analyze":
            p.add_argument("--suite", choices=SUITES, default="smoke")
    args = parser.parse_args()
    if args.command == "_worker":
        worker(args.runtime, args.folder, args.device)
        return 0
    try:
        if args.command == "doctor":
            data = fingerprint(args.runtime)
            print(json.dumps({"status": "FILES_FOUND_NOT_SOLVER_VALIDATION", "path": data["runtime_path"],
                              "python_files": len(data["source_files"]), "digest": data["digest"], "packages": data["packages"]}, indent=2))
        elif args.command == "prepare":
            data = prepare(args.out, args.channel_seconds)
            print(f"[Benchmark] Prepared {len(data['cases'])} cases: {args.out.resolve()}")
        elif args.command == "run":
            if not 1 <= args.timeout <= 86400:
                raise ValueError("timeout must be 1..86400 seconds per case")
            result = run_suite(args.out, args.runtime, args.suite, args.device, args.timeout, args.retry_failed)
            print(f"[Benchmark] {args.suite}: {result['status']}; see {args.out / 'reports'}")
            return 0 if result["status"] == "PASS" else 2
        elif args.command == "analyze":
            from analyze_cases import analyze
            verify_prepared(args.out)
            result = analyze(args.out, args.suite)
            print(f"[Benchmark] {args.suite}: {result['status']}")
            return 0 if result["status"] == "PASS" else 2
        elif args.command == "bundle":
            print(f"[Benchmark] Report bundle: {bundle(args.out)}")
        return 0
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"[Benchmark] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
