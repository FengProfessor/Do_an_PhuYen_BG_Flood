"""Supervise the authorized frozen V49-G runs without overwriting results."""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import netCDF4 as nc
import numpy as np

from v49_prepare_hydraulic_validation import DEFAULT_OUTPUT_DIR, V48_RUNTIME
from v49_runtime_observer import atomic_json
from v49_validate_hydraulic_validation import validate_v49_g


ROOT = Path(__file__).resolve().parent
ARMS = ("CENTRAL", "LOW", "HIGH", "BASE")

FORBIDDEN_DIRS = {
    (ROOT / "V49_G_20261013").resolve(),
    (ROOT / "V49_G_POWERLOSS_RECOVERY_20261014").resolve(),
}


def is_historical_dir(output_dir: Path) -> bool:
    resolved = output_dir.resolve()
    return any(resolved == forbidden or forbidden in resolved.parents for forbidden in FORBIDDEN_DIRS)


def assert_not_historical_dir(output_dir: Path) -> None:
    if is_historical_dir(output_dir):
        raise PermissionError(
            f"Modifying historical attempt directory is strictly prohibited: {output_dir}"
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pid_alive(pid: int | None) -> bool:
    if not pid or int(pid) <= 0:
        return False
    try:
        import psutil
        if not psutil.pid_exists(int(pid)):
            return False
        proc = psutil.Process(int(pid))
        if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
            return False
        return "python" in proc.name().lower()
    except Exception:
        if os.name == "nt":
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return code.value == 259
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False


def manifest(output_dir: Path) -> dict:
    return json.loads((output_dir / "V49_G_PREPARATION_MANIFEST.json").read_text(encoding="utf-8"))


def check_cuda_vram(min_free_bytes: int = 1024 * 1024 * 1024) -> dict:
    """Verify that CUDA Device 0 has sufficient free VRAM and memory is released."""
    try:
        import cupy
        cupy.get_default_memory_pool().free_all_blocks()
        cupy.get_default_pinned_memory_pool().free_all_blocks()
        free_bytes, total_bytes = cupy.cuda.runtime.memGetInfo()
    except Exception as exc:
        raise RuntimeError(f"Unable to query CUDA Device 0 memory: {exc}")

    free_gb = free_bytes / (1024 ** 3)
    total_gb = total_bytes / (1024 ** 3)
    if free_bytes < min_free_bytes:
        raise RuntimeError(
            f"Insufficient CUDA VRAM on Device 0: {free_gb:.2f} GB free, "
            f"minimum required is {min_free_bytes / (1024 ** 3):.2f} GB"
        )
    return {
        "device_id": 0,
        "free_bytes": free_bytes,
        "total_bytes": total_bytes,
        "free_gb": round(free_gb, 3),
        "total_gb": round(total_gb, 3),
    }


def verify_runtime() -> None:
    spec = importlib.util.spec_from_file_location("v49_frozen_launch_check", V48_RUNTIME / "launch_formal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.check()
    import cupy
    if cupy.cuda.runtime.getDeviceCount() < 1:
        raise RuntimeError("The frozen formal runtime requires an available CUDA GPU")
    cupy.cuda.Device(0).compute_capability
    check_cuda_vram()


def prepare(output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    assert_not_historical_dir(output_dir)
    from v49_prepare_hydraulic_validation import prepare_v49_g
    return prepare_v49_g(output_dir)


def preflight(output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    assert_not_historical_dir(output_dir)
    verify_runtime()
    manifest_path = output_dir / "V49_G_PREPARATION_MANIFEST.json"
    if not manifest_path.exists():
        if not is_historical_dir(output_dir):
            print(f"[PREFLIGHT] Manifest missing in {output_dir}; initializing preparation...", flush=True)
            prepare(output_dir)
    report = validate_v49_g(output_dir)
    if not report["preparation_pass"]:
        failed = [key for key, value in report["preparation_checks"].items() if not value]
        raise RuntimeError(f"Frozen preparation validation failed: {failed}")
    return report


def format_time_duration(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds) or seconds < 0:
        return "N/A"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    elif minutes > 0:
        return f"{minutes}m {secs:02d}s"
    else:
        return f"{secs}s"


def format_progress_line(arm: str, prog: dict, wall_elapsed_s: float) -> str:
    sim_t = float(prog.get("simulated_time_s") or 0.0)
    end_t = float(prog.get("endtime_s") or 432000.0)
    pct = float(prog.get("progress_pct") or 0.0)
    dt = float(prog.get("dt_s") or 0.0)
    wall_elapsed_s = max(0.0, float(wall_elapsed_s or 0.0))

    sim_h = sim_t / 3600.0
    end_h = end_t / 3600.0

    if sim_t > 0 and wall_elapsed_s > 0:
        sim_rate = sim_t / wall_elapsed_s
        rem_sim_s = max(0.0, end_t - sim_t)
        eta_s = rem_sim_s / sim_rate if sim_rate > 0 else float("inf")
        eta_str = format_time_duration(eta_s)
    else:
        eta_str = "calculating..."

    elapsed_str = format_time_duration(wall_elapsed_s)
    dt_str = f"{dt:.2f}s" if dt >= 0.01 else f"{dt:.3e}s"
    return f"[{arm}] {sim_h:.1f}h / {end_h:.1f}h ({pct:.1f}%) | dt = {dt_str} | elapsed = {elapsed_str} | ETA = {eta_str}"


def progress(log_path: Path) -> dict | None:
    if not log_path.exists():
        return None
    try:
        with log_path.open("rb") as source:
            source.seek(max(0, log_path.stat().st_size - 65536))
            tail = source.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    matches = re.findall(r"t = ([\d.]+)/([\d.]+)s.*?dt = ([\deE+.-]+).*?elapsed = ([\d.]+)s", tail)
    if not matches:
        return None
    current, end, dt, elapsed = map(float, matches[-1])
    return {
        "simulated_time_s": current,
        "endtime_s": end,
        "progress_pct": (100.0 * current / end) if end > 0 else 0.0,
        "dt_s": dt,
        "engine_elapsed_s": elapsed,
    }


def verify_post_run(arm: str, output_dir: Path, result_path: Path) -> dict:
    verification = {
        "arm": arm,
        "verified_at_utc": utc_now(),
        "netcdf_valid": False,
        "discrete_budget_valid": False,
        "errors": [],
    }

    # 1. NetCDF file existence, non-emptiness, and structure
    if not result_path.exists():
        verification["errors"].append(f"Result NetCDF missing: {result_path}")
        return verification

    size_bytes = result_path.stat().st_size
    verification["size_bytes"] = size_bytes
    if size_bytes == 0:
        verification["errors"].append(f"Result NetCDF is empty: {result_path}")
        return verification

    try:
        with nc.Dataset(result_path, "r") as ds:
            required = {"time", "h", "zs", "zb", "u", "v", "x", "y"}
            missing = required - set(ds.variables.keys())
            if missing:
                verification["errors"].append(f"NetCDF missing required variables: {sorted(missing)}")
                return verification
            times = np.asarray(np.ma.filled(ds.variables["time"][:], np.nan), dtype=float)
            if times.ndim != 1 or times.size < 2 or not np.isfinite(times).all():
                verification["errors"].append("NetCDF has invalid time axis (must be 1D, >= 2 frames, all finite)")
                return verification
            if times[0] < 0.0:
                verification["errors"].append(f"NetCDF initial simulation time cannot be negative: {times[0]}s")
                return verification
            if np.any(np.diff(times) <= 0):
                verification["errors"].append("NetCDF time axis is not strictly increasing")
                return verification

            x_vals = np.asarray(ds.variables["x"][:], dtype=float)
            y_vals = np.asarray(ds.variables["y"][:], dtype=float)
            if x_vals.ndim != 1 or x_vals.size < 2 or not np.isfinite(x_vals).all():
                verification["errors"].append("NetCDF has invalid x coordinate axis (must be 1D, >= 2 points, all finite)")
                return verification
            if y_vals.ndim != 1 or y_vals.size < 2 or not np.isfinite(y_vals).all():
                verification["errors"].append("NetCDF has invalid y coordinate axis (must be 1D, >= 2 points, all finite)")
                return verification

            verification["frame_count"] = int(times.size)
            verification["first_time_s"] = float(times[0])
            verification["last_time_s"] = float(times[-1])
            verification["complete_to_120h"] = bool(times[-1] >= 432000.0 - 1.0)
            verification["netcdf_valid"] = True
    except Exception as exc:
        verification["errors"].append(f"NetCDF unreadable: {type(exc).__name__}: {exc}")
        return verification

    # 2. Discrete mass budget preservation and closure residual
    budget_path = output_dir / "results" / f"V49_G_{arm}_discrete_budget.json"
    if not budget_path.exists():
        verification["errors"].append(f"Discrete budget file missing: {budget_path}")
        return verification

    try:
        budget = json.loads(budget_path.read_text(encoding="utf-8"))
        residual = budget.get("unexplained_closure_residual_m3")
        if residual is None or not np.isfinite(residual):
            verification["errors"].append("Budget missing unexplained_closure_residual_m3 or non-finite")
            return verification
        verification["unexplained_closure_residual_m3"] = residual
        curr_vol = budget.get("current_volume_m3")
        if curr_vol is None or not np.isfinite(curr_vol):
            curr_vol = 1.0
        rel_residual = abs(residual) / max(abs(curr_vol), 1.0)
        verification["relative_closure_residual"] = rel_residual
        if abs(residual) < 1.0 or rel_residual < 1e-4:
            verification["discrete_budget_valid"] = True
        else:
            verification["errors"].append(f"Closure residual out of tolerance: {residual} m3 (rel: {rel_residual})")
    except Exception as exc:
        verification["errors"].append(f"Discrete budget unreadable: {type(exc).__name__}: {exc}")
        return verification

    return verification


def worker(arm: str, output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    assert_not_historical_dir(output_dir)
    existing = status(output_dir)
    current_pid = os.getpid()
    if existing.get("worker_alive") and existing.get("worker_pid") != current_pid:
        raise RuntimeError(
            f"A CUDA worker process (PID {existing.get('worker_pid')}) is already running on Device 0"
        )
    preflight(output_dir)
    m = manifest(output_dir)
    result_path = Path(m["configs"][arm]["planned_result"])
    if result_path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing run: {result_path}")
    result_path.parent.mkdir(parents=True, exist_ok=True)

    # Force CUDA GPU Device 0
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.chdir(V48_RUNTIME)
    sys.path.insert(0, str(V48_RUNTIME / "python"))

    import cupy
    cupy.cuda.Device(0).use()

    from bg_flood import write_txtlog
    write_txtlog._LOG_FILE = str((output_dir / "results" / f"V49_G_{arm}_engine_log.txt").resolve())
    from v49_runtime_observer import install_budget_observer
    install_budget_observer((output_dir / "results" / f"V49_G_{arm}_discrete_budget.json").resolve())
    param_path = Path(m["configs"][arm]["path"])
    if not param_path.is_absolute():
        param_path = (output_dir / param_path.name).resolve()
    else:
        param_path = param_path.resolve()
    import run_bgflood
    run_bgflood.run_model(str(param_path))


def status(output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    path = output_dir / "V49_G_EXECUTION_STATE.json"
    if not path.exists():
        return {"status": "NOT_STARTED"}
    for attempt in range(5):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            break
        except (json.JSONDecodeError, OSError):
            if attempt == 4:
                raise
            time.sleep(0.05)
    state["supervisor_alive"] = pid_alive(state.get("supervisor_pid"))
    state["worker_alive"] = pid_alive(state.get("worker_pid"))
    return state


def supervise(output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    assert_not_historical_dir(output_dir)
    existing = status(output_dir)
    if existing.get("supervisor_alive") and existing.get("supervisor_pid") != os.getpid():
        raise RuntimeError("A V49-G supervisor is already running")
    if existing.get("worker_alive"):
        raise RuntimeError(f"A CUDA worker process (PID {existing.get('worker_pid')}) is already running on Device 0")
    preflight(output_dir)
    directory = output_dir / "results"
    directory.mkdir(parents=True, exist_ok=True)
    m = manifest(output_dir)

    state_path = output_dir / "V49_G_EXECUTION_STATE.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    else:
        state = {}

    state.setdefault("schema_version", "V49-G-execution-1")
    state["status"] = "RUNNING"
    if "started_at_utc" not in state:
        state["started_at_utc"] = utc_now()
    state["supervisor_pid"] = os.getpid()
    state["worker_pid"] = None
    state.setdefault("runs", {})
    state["execution_policy"] = "One CUDA run at a time on GPU Device 0; CENTRAL -> LOW -> HIGH -> BASE (120h each)"
    state.setdefault("hydraulic_promotion_ready", False)
    state["updated_at_utc"] = utc_now()
    atomic_json(state_path, state)

    print(f"[SUPERVISOR] Commencing sequential simulation queue on CUDA Device 0: {' -> '.join(ARMS)}", flush=True)

    try:
        for arm in ARMS:
            result = Path(m["configs"][arm]["planned_result"])
            logfile = directory / f"V49_G_{arm}_run.log"

            arm_state = state["runs"].get(arm, {})
            # Check if arm is already completed, verified, and evaluated
            if arm_state.get("status") in ("EVALUATED", "MATCHED_METRICS_AVAILABLE"):
                if result.exists() and result.stat().st_size > 0:
                    print(f"[SUPERVISOR] Arm {arm} already completed and evaluated; advancing to next in queue.", flush=True)
                    continue
                else:
                    raise FileNotFoundError(
                        f"State records arm {arm} as evaluated, but result file is missing or empty: {result}"
                    )

            # Check if simulation completed but pending evaluation
            if arm_state.get("status") == "SIMULATION_COMPLETED_PENDING_EVALUATION" and result.exists() and result.stat().st_size > 0:
                print(f"[SUPERVISOR] Arm {arm} simulation completed; resuming evaluation...", flush=True)
                state["active_arm"] = arm
                state["queue"] = [value for value in ARMS if state["runs"].get(value, {}).get("status") != "EVALUATED" and value != arm]
                atomic_json(state_path, state)
                from v49_evaluate_hydraulic_validation import evaluate_available_runs
                eval_summary = evaluate_available_runs(output_dir)
                state["runs"][arm]["status"] = "EVALUATED"
                state["runs"][arm]["evaluation_status"] = eval_summary.get("status")
                state["runs"][arm]["evaluation"] = eval_summary.get("arms", {}).get(arm, {})
                atomic_json(state_path, state)
                continue

            # Check if an existing result is already complete and verified to 120h
            if result.exists() and result.stat().st_size > 0:
                check_v = verify_post_run(arm, output_dir, result)
                if check_v.get("netcdf_valid") and check_v.get("complete_to_120h") and check_v.get("discrete_budget_valid"):
                    print(f"[SUPERVISOR] Arm {arm} has verified complete 120h simulation result; advancing to evaluation...", flush=True)
                    state["active_arm"] = arm
                    state["queue"] = [value for value in ARMS if state["runs"].get(value, {}).get("status") != "EVALUATED" and value != arm]
                    state["runs"].setdefault(arm, {})
                    state["runs"][arm]["post_run_verification"] = check_v
                    state["runs"][arm]["status"] = "SIMULATION_COMPLETED_PENDING_EVALUATION"
                    atomic_json(state_path, state)
                    from v49_evaluate_hydraulic_validation import evaluate_available_runs
                    eval_summary = evaluate_available_runs(output_dir)
                    state["runs"][arm]["status"] = "EVALUATED"
                    state["runs"][arm]["evaluation_status"] = eval_summary.get("status")
                    state["runs"][arm]["evaluation"] = eval_summary.get("arms", {}).get(arm, {})
                    atomic_json(state_path, state)
                    continue
                elif check_v.get("complete_to_120h") and not check_v.get("discrete_budget_valid"):
                    raise RuntimeError(
                        f"Existing 120h run for {arm} failed post-run mass budget verification: {check_v.get('errors')}"
                    )

            if result.exists() or logfile.exists():
                raise FileExistsError(f"Existing incomplete/interrupted {arm} run requires explicit recovery, not overwrite: {result}")

            preflight(output_dir)
            state["active_arm"] = arm
            state["queue"] = [value for value in ARMS if state["runs"].get(value, {}).get("status") != "EVALUATED" and value != arm]
            state["runs"][arm] = {
                "status": "RUNNING",
                "started_at_utc": utc_now(),
                "log": str(logfile),
                "result": str(result),
                "config_sha256": m["configs"][arm]["sha256"],
            }
            atomic_json(state_path, state)

            vram_start = check_cuda_vram()
            state["runs"][arm]["vram_start_gb"] = vram_start["free_gb"]
            atomic_json(state_path, state)
            print(f"[SUPERVISOR] CUDA Device 0 VRAM verified before {arm}: {vram_start['free_gb']:.2f} GB free of {vram_start['total_gb']:.2f} GB total", flush=True)

            print(f"\n[SUPERVISOR] Launching arm {arm} on CUDA Device 0...", flush=True)

            worker_env = os.environ.copy()
            worker_env["CUDA_VISIBLE_DEVICES"] = "0"
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

            with logfile.open("x", encoding="utf-8") as log:
                process = subprocess.Popen(
                    [sys.executable, "-B", "-u", str(Path(__file__).resolve()),
                     "worker", "--arm", arm, "--output-dir", str(output_dir)],
                    cwd=ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                    env=worker_env,
                )
                state["worker_pid"] = process.pid
                atomic_json(state_path, state)

                worker_start = time.monotonic()
                last_log_print = 0.0
                last_state_write = 0.0
                log_interval = 30.0

                while process.poll() is None:
                    now = time.monotonic()
                    wall_elapsed = now - worker_start
                    p = progress(logfile)

                    if p:
                        state["runs"][arm]["progress"] = p
                        state["updated_at_utc"] = utc_now()
                        if now - last_state_write >= 10.0:
                            atomic_json(state_path, state)
                            last_state_write = now

                        if now - last_log_print >= log_interval:
                            print(format_progress_line(arm, p, wall_elapsed), flush=True)
                            last_log_print = now
                    else:
                        prev_p = state["runs"][arm].get("progress")
                        if prev_p:
                            if now - last_log_print >= log_interval:
                                print(format_progress_line(arm, prev_p, wall_elapsed), flush=True)
                                last_log_print = now
                        else:
                            if now - last_log_print >= log_interval:
                                elapsed_str = format_time_duration(wall_elapsed)
                                print(f"[{arm}] Initializing solver on CUDA Device 0... | elapsed = {elapsed_str}", flush=True)
                                last_log_print = now

                    time.sleep(2)

            state["worker_pid"] = None
            state["runs"][arm].update(returncode=process.returncode, finished_at_utc=utc_now())

            p = progress(logfile)
            if p:
                state["runs"][arm]["progress"] = p
                print(format_progress_line(arm, p, time.monotonic() - worker_start), flush=True)

            vram_finish = check_cuda_vram()
            state["runs"][arm]["vram_finish_gb"] = vram_finish["free_gb"]
            atomic_json(state_path, state)
            print(f"[SUPERVISOR] CUDA Device 0 VRAM released after {arm}: {vram_finish['free_gb']:.2f} GB free of {vram_finish['total_gb']:.2f} GB total", flush=True)

            if process.returncode:
                state["runs"][arm]["status"] = "FAILED"
                atomic_json(state_path, state)
                raise RuntimeError(f"{arm} exited with returncode {process.returncode}; inspect {logfile}")

            # R4: Post-Run Verification & Preregistered Evaluation
            print(f"[{arm}] Simulation process completed. Running automated post-run verification...", flush=True)
            v = verify_post_run(arm, output_dir, result)
            state["runs"][arm]["post_run_verification"] = v
            atomic_json(state_path, state)

            if not v["netcdf_valid"] or not v["discrete_budget_valid"]:
                state["runs"][arm]["status"] = "POST_RUN_VERIFICATION_FAILED"
                atomic_json(state_path, state)
                raise RuntimeError(f"{arm} post-run verification failed: {v.get('errors')}")

            print(f"[{arm}] Post-run verification PASSED. Triggering Sentinel-1 hydraulic evaluation...", flush=True)
            state["runs"][arm]["status"] = "SIMULATION_COMPLETED_PENDING_EVALUATION"
            atomic_json(state_path, state)

            from v49_evaluate_hydraulic_validation import evaluate_available_runs
            eval_summary = evaluate_available_runs(output_dir)
            state["runs"][arm]["status"] = "EVALUATED"
            state["runs"][arm]["evaluation_status"] = eval_summary.get("status")
            state["runs"][arm]["evaluation"] = eval_summary.get("arms", {}).get(arm, {})
            atomic_json(state_path, state)
            print(f"[{arm}] Evaluation completed successfully: status = {eval_summary.get('status')}", flush=True)

        state.update(
            status="MATCHED_RUNS_COMPLETED_PENDING_ACCEPTANCE",
            active_arm=None,
            queue=[],
            updated_at_utc=utc_now(),
        )
        atomic_json(state_path, state)
        print("[SUPERVISOR] All 4 simulation arms have completed and been evaluated.", flush=True)
        report_path = generate_summary_report(output_dir)
        print(f"[SUPERVISOR] Final summary report generated: {report_path}", flush=True)

    except (KeyboardInterrupt, SystemExit):
        print(f"\n[SUPERVISOR] Interrupted by signal. Gracefully shutting down worker PID {state.get('worker_pid')}...", flush=True)
        if "process" in locals() and process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        state.update(status="INTERRUPTED", error="Supervisor interrupted by user/signal", updated_at_utc=utc_now())
        if "active_arm" in state and state["active_arm"] in state.get("runs", {}):
            state["runs"][state["active_arm"]]["status"] = "INTERRUPTED"
        atomic_json(state_path, state)
        raise
    except Exception as exc:
        print(f"\n[SUPERVISOR ERROR] {type(exc).__name__}: {exc}", flush=True)
        if "process" in locals() and process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        state.update(status="FAILED_NEEDS_REVIEW", error=f"{type(exc).__name__}: {exc}", updated_at_utc=utc_now())
        if "active_arm" in state and state["active_arm"] in state.get("runs", {}):
            if state["runs"][state["active_arm"]].get("status") != "POST_RUN_VERIFICATION_FAILED":
                state["runs"][state["active_arm"]]["status"] = "FAILED"
        atomic_json(state_path, state)
        raise
    finally:
        state["worker_pid"] = None
        state["supervisor_pid"] = None
        atomic_json(state_path, state)


def start(output_dir: Path) -> dict:
    output_dir = output_dir.resolve()
    assert_not_historical_dir(output_dir)
    existing = status(output_dir)
    if existing.get("supervisor_alive") or existing.get("worker_alive"):
        return existing
    preflight(output_dir)
    path = output_dir / "V49_G_supervisor.log"
    if path.exists():
        raise FileExistsError("A previous supervisor log exists; inspect it before recovery")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    log = path.open("x", encoding="utf-8")
    child = subprocess.Popen(
        [sys.executable, "-B", "-u", str(Path(__file__).resolve()),
         "supervise", "--output-dir", str(output_dir)],
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    return {"status": "SUPERVISOR_LAUNCHED", "supervisor_pid": child.pid, "log": str(path)}


def generate_summary_report(output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    assert_not_historical_dir(output_dir)
    state_path = output_dir / "V49_G_EXECUTION_STATE.json"
    manifest_path = output_dir / "V49_G_PREPARATION_MANIFEST.json"
    metrics_path = output_dir / "V49_G_matched_hydraulic_metrics.json"

    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    matched_metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}

    report_lines = [
        "# V49-G Hydraulic Simulation Suite: Final Execution & Evaluation Summary Report",
        "",
        f"**Generated at (UTC):** {utc_now()}",
        f"**Execution Directory:** `{output_dir}`",
        f"**Overall Status:** `{state.get('status', 'UNKNOWN')}`",
        f"**Execution Policy:** `{state.get('execution_policy', 'One CUDA run at a time on GPU Device 0; CENTRAL -> LOW -> HIGH -> BASE (120h each)')}`",
        "",
        "---",
        "",
        "## 1. Simulation Queue & Arm Execution Record",
        "",
        "| Arm | Status | Simulated Time | Wall Duration | NetCDF Valid | Mass Residual (m³) | Relative Residual |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    runs = state.get("runs", {})
    for arm in ARMS:
        info = runs.get(arm, {})
        arm_status = info.get("status", "QUEUED")
        v = info.get("post_run_verification", {})
        nc_ok = "PASS" if v.get("netcdf_valid") else ("FAIL" if "netcdf_valid" in v else "N/A")
        res_m3 = v.get("unexplained_closure_residual_m3")
        res_str = f"{res_m3:.3e}" if res_m3 is not None else "N/A"
        rel_residual = v.get("relative_closure_residual")
        rel_str = f"{rel_residual:.3e}" if rel_residual is not None else "N/A"

        prog = info.get("progress", {})
        sim_t = prog.get("simulated_time_s", 0.0)
        sim_str = f"{sim_t/3600.0:.1f}h / 120.0h" if sim_t else ("120.0h / 120.0h" if arm_status in ("EVALUATED", "SIMULATION_COMPLETED_PENDING_EVALUATION") else "0.0h / 120.0h")

        started = info.get("started_at_utc")
        finished = info.get("finished_at_utc")
        if started and finished:
            try:
                dur = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
                dur_str = format_time_duration(dur)
            except Exception:
                dur_str = "N/A"
        elif started:
            try:
                dur = (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()
                dur_str = f"{format_time_duration(dur)} (in-progress)"
            except Exception:
                dur_str = "N/A"
        else:
            dur_str = "N/A"

        report_lines.append(f"| **{arm}** | `{arm_status}` | {sim_str} | {dur_str} | {nc_ok} | {res_str} | {rel_str} |")

    report_lines.extend([
        "",
        "---",
        "",
        "## 2. Sentinel-1 SAR Evaluation Metrics (t = 101.61h)",
        "",
        "Preregistered observation: `DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif`",
        "",
        "| Arm | CSI / IoU | F1 Score | Precision | Recall | Simulated Area (km²) | Area Bias | Frame Offset |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])

    arms_metrics = matched_metrics.get("arms", {})
    for arm in ARMS:
        m = arms_metrics.get(arm, {}).get("metrics")
        if not m and arm in runs and "evaluation" in runs[arm]:
            m = runs[arm]["evaluation"].get("metrics")
        if m:
            csi = f"{m.get('csi_iou', 0.0):.4f}" if m.get("csi_iou") is not None else "N/A"
            f1 = f"{m.get('f1', 0.0):.4f}" if m.get("f1") is not None else "N/A"
            prec = f"{m.get('precision', 0.0):.4f}" if m.get("precision") is not None else "N/A"
            rec = f"{m.get('recall', 0.0):.4f}" if m.get("recall") is not None else "N/A"
            area = f"{m.get('simulated_area_km2', 0.0):.2f}" if m.get("simulated_area_km2") is not None else "N/A"
            bias = f"{m.get('area_bias', 0.0):+.4f}" if m.get("area_bias") is not None else "N/A"
            raw_offset = arms_metrics.get(arm, {}).get("sar_frame_offset_s")
            if raw_offset is None and arm in runs and "evaluation" in runs[arm]:
                raw_offset = runs[arm]["evaluation"].get("sar_frame_offset_s")
            offset = f"{raw_offset:.1f}s" if raw_offset is not None else "N/A"
            report_lines.append(f"| **{arm}** | {csi} | {f1} | {prec} | {rec} | {area} | {bias} | {offset} |")
        else:
            report_lines.append(f"| **{arm}** | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |")

    diffs = matched_metrics.get("difference_from_base")
    if diffs:
        report_lines.extend([
            "",
            "### Differences from Frozen BASE Model",
            "",
            "| Arm | Δ CSI / IoU | Δ F1 | Δ Precision | Δ Recall | Δ Simulated Area (km²) |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
        ])
        for arm, diff in diffs.items():
            dcsi = f"{diff.get('csi_iou', 0.0):+.4f}" if "csi_iou" in diff else "N/A"
            df1 = f"{diff.get('f1', 0.0):+.4f}" if "f1" in diff else "N/A"
            dprec = f"{diff.get('precision', 0.0):+.4f}" if "precision" in diff else "N/A"
            drec = f"{diff.get('recall', 0.0):+.4f}" if "recall" in diff else "N/A"
            darea = f"{diff.get('simulated_area_km2', 0.0):+.2f}" if "simulated_area_km2" in diff else "N/A"
            report_lines.append(f"| **{arm}** | {dcsi} | {df1} | {dprec} | {drec} | {darea} |")

    report_lines.extend([
        "",
        "---",
        "",
        "## 3. Post-Run Verification & Preregistered Criteria Assessment",
        "",
        f"- **Gate-G Pass:** `{matched_metrics.get('gate_g_pass', False)}`",
        f"- **Hydraulic Promotion Ready:** `{matched_metrics.get('hydraulic_promotion_ready', False)}`",
        f"- **Interpretation:** {matched_metrics.get('interpretation', 'Evaluation pending completed matched runs.')}",
        "",
    ])

    report_text = "\n".join(report_lines) + "\n"
    report_path = output_dir / "V49_G_FINAL_SUMMARY_REPORT.md"
    report_path.write_text(report_text, encoding="utf-8")
    return report_path


def monitor(output_dir: Path, poll_interval_s: float = 30.0) -> None:
    output_dir = output_dir.resolve()
    print(f"[MONITOR] Monitoring execution in {output_dir}...")
    last_print = 0.0
    while True:
        s = status(output_dir)
        active_arm = s.get("active_arm")
        supervisor_alive = s.get("supervisor_alive", False)
        worker_alive = s.get("worker_alive", False)

        if not active_arm:
            if not supervisor_alive and not worker_alive:
                print(f"[MONITOR] No active arm and supervisor not running. Execution status: {s.get('status', 'UNKNOWN')}")
                break
            now = time.time()
            if now - last_print >= poll_interval_s:
                print(f"[MONITOR] Waiting for active arm... (supervisor alive, status: {s.get('status')})", flush=True)
                last_print = now
            time.sleep(2)
            continue

        arm_info = s.get("runs", {}).get(active_arm, {})
        p = arm_info.get("progress")
        started_at = arm_info.get("started_at_utc")
        now = time.time()
        wall_elapsed_s = 0.0
        if started_at:
            try:
                dt_start = datetime.fromisoformat(started_at)
                wall_elapsed_s = (datetime.now(timezone.utc) - dt_start).total_seconds()
            except Exception:
                wall_elapsed_s = p.get("engine_elapsed_s", 0.0) if p else 0.0
        elif p:
            wall_elapsed_s = p.get("engine_elapsed_s", 0.0)

        if now - last_print >= poll_interval_s:
            if p:
                print(format_progress_line(active_arm, p, wall_elapsed_s), flush=True)
            else:
                elapsed_str = format_time_duration(wall_elapsed_s)
                print(f"[{active_arm}] Initializing solver on CUDA Device 0... | elapsed = {elapsed_str}", flush=True)
            last_print = now

        if not supervisor_alive and not worker_alive:
            print(f"[MONITOR] Supervisor and worker not running. Final status: {s.get('status')}")
            break
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "prepare", "start", "status", "supervise", "worker", "monitor", "report"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--arm", choices=ARMS)
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    if args.action == "worker":
        if not args.arm:
            parser.error("worker requires --arm")
        worker(args.arm, args.output_dir)
    elif args.action == "supervise":
        supervise(args.output_dir)
    elif args.action == "monitor":
        monitor(args.output_dir)
    elif args.action == "report":
        report_path = generate_summary_report(args.output_dir)
        print(json.dumps({"status": "REPORT_GENERATED", "report_path": str(report_path)}, indent=2))
    elif args.action == "prepare":
        result = prepare(args.output_dir)
        print(json.dumps({"status": "PREPARATION_COMPLETE", "preparation_pass": result.get("preparation_pass")}, ensure_ascii=True, indent=2))
    else:
        result = {"preflight": preflight, "start": start, "status": status}[args.action](args.output_dir)
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
