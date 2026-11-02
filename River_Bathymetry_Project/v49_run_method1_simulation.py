"""Supervise and execute V49 Method 1 (Cách 1) Hydraulic Simulation Suite on CUDA Device 0.

Scope: SCOPE_B1_41 (41 reaches W >= 60m + V48 66 cuts)
Arms: CENTRAL, LOW, HIGH
Policy: One CUDA run at a time on GPU Device 0; CENTRAL -> LOW -> HIGH (120h each)
"""

from __future__ import annotations

import argparse
import ctypes
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

ROOT = Path("D:/VTP")
PROJECT_DIR = ROOT / "River_Bathymetry_Project"
V48_RUNTIME = ROOT / "V48_runs" / "20261004_runtime_fix_r1"
RUN_DIR = PROJECT_DIR / "V49_Method1_Runs"
RESULTS_DIR = RUN_DIR / "results"
GIS_DIR = ROOT / "05-Du-lieu-GIS"
ARMS = ("CENTRAL", "LOW", "HIGH")

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def atomic_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)

def pid_alive(pid: int | None) -> bool:
    if not pid or int(pid) <= 0:
        return False
    try:
        import psutil
        if not psutil.pid_exists(int(pid)):
            return False
        p = psutil.Process(int(pid))
        if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
            return False
        return "python" in p.name().lower()
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

def check_cuda_vram(min_free_bytes: int = 1024 * 1024 * 1024) -> dict:
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

def build_bg_param_content(arm: str) -> str:
    asc_path = (RUN_DIR / f"V49_Method1_ScopeB1_{arm}.asc").resolve()
    out_nc = (RESULTS_DIR / f"V49_Method1_ScopeB1_{arm}.nc").resolve()
    
    return f"""# ==============================================================================
# BG_Flood Configuration - V49 Method 1 Scope B1 ({arm})
# Production Tier: 41 Reaches (W >= 60m) + V48 66 Cuts
# Generated: {utc_now()}
# ==============================================================================

# Terrain input
bathy = {asc_path.as_posix()};
dx = 30;
dy = 30;

# Mask policy
mask = 9999.0;
minmask = -4.0;

# Manning roughness map
frictionmodel = -1;
roughnessmap = ../../05-Du-lieu-GIS/PhuYen_manning_30m_V43.asc;

# River forcings
river = xa_lu_BaHa_Nov2021_V40_sync.txt, 270030, 270630, 1441000, 1443000;
river = xa_lu_BanThach_V43.txt, 276000, 277000, 1424500, 1425500;
river = xa_lu_KyLo_V40_sync.txt, 289000, 290000, 1476500, 1477500;
river = xa_lu_TuyAn_V40_sync.txt, 301000, 302000, 1473500, 1474500;

# Rainfall and infiltration
rainfile = ../../Scenarios/rain_v34_era5_x2.txt;
rainunits = m/s;
il = ../../05-Du-lieu-GIS/il_30m_V36.asc;
cl = ../../05-Du-lieu-GIS/cl_30m_V36.asc;

# Cold-start water-surface policy
zsinit = 1.0;
zsoffset = 0.0;

# Boundary conditions
left = 0;
right = 2;
top = 2;
bottom = 2;

# Simulation window: 120 h, output every 3 h (41 frames)
endtime = 432000;
outputtimestep = 10800;

# Output
outfile = {out_nc.as_posix()};
outvars = zs, h, zb, u, v;
"""

def prepare() -> dict:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    configs = {}
    for arm in ARMS:
        asc_path = RUN_DIR / f"V49_Method1_ScopeB1_{arm}.asc"
        if not asc_path.exists():
            raise FileNotFoundError(f"Missing materialized ASC raster: {asc_path}")
        
        param_file = RUN_DIR / f"BG_param_V49_Method1_ScopeB1_{arm}.txt"
        param_content = build_bg_param_content(arm)
        param_file.write_text(param_content, encoding="utf-8")
        
        configs[arm] = {
            "param_file": str(param_file),
            "asc_file": str(asc_path),
            "output_nc": str(RESULTS_DIR / f"V49_Method1_ScopeB1_{arm}.nc"),
            "log_file": str(RESULTS_DIR / f"V49_Method1_ScopeB1_{arm}_run.log"),
        }

    manifest = {
        "schema_version": "V49-Method1-ScopeB1-1",
        "created_at_utc": utc_now(),
        "scope": "SCOPE_B1_41",
        "description": "V49 Method 1 DHG Clamped 41 reaches (W >= 60m) + V48 66 Cuts",
        "canonical_minmask": -4.0,
        "runtime_dir": str(V48_RUNTIME),
        "arms": ARMS,
        "configs": configs,
    }
    manifest_path = RUN_DIR / "V49_Method1_MANIFEST.json"
    atomic_json(manifest_path, manifest)
    return manifest

def preflight() -> dict:
    manifest_path = RUN_DIR / "V49_Method1_MANIFEST.json"
    if not manifest_path.exists():
        prepare()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    vram = check_cuda_vram()

    # Check forcing files
    required_files = [
        GIS_DIR / "PhuYen_manning_30m_V43.asc",
        ROOT / "Scenarios" / "rain_v34_era5_x2.txt",
        GIS_DIR / "il_30m_V36.asc",
        GIS_DIR / "cl_30m_V36.asc",
        V48_RUNTIME / "xa_lu_BaHa_Nov2021_V40_sync.txt",
        V48_RUNTIME / "xa_lu_BanThach_V43.txt",
        V48_RUNTIME / "xa_lu_KyLo_V40_sync.txt",
        V48_RUNTIME / "xa_lu_TuyAn_V40_sync.txt",
    ]
    for rf in required_files:
        if not rf.exists():
            raise FileNotFoundError(f"Missing required forcing file: {rf}")

    for arm in ARMS:
        asc = Path(manifest["configs"][arm]["asc_file"])
        if not asc.exists() or asc.stat().st_size == 0:
            raise FileNotFoundError(f"Missing or empty ASC file for {arm}: {asc}")

    return {
        "status": "PREFLIGHT_PASS",
        "vram": vram,
        "manifest": str(manifest_path),
        "arms_ready": list(ARMS),
    }

def format_time_duration(seconds: float) -> str:
    s = int(round(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h}h {m:02d}m {sec:02d}s"
    elif m > 0:
        return f"{m}m {sec:02d}s"
    return f"{sec}s"

PROGRESS_RE = re.compile(
    r"t\s*=\s*(?P<sim_t>[0-9.]+)/(?P<end_t>[0-9.]+)s\s*\((?P<pct>[0-9.]+)%\)\s*\|\s*dt\s*=\s*(?P<dt>[0-9.eE+-]+)\s*\|\s*elapsed\s*=\s*(?P<elapsed>[0-9.]+)s"
)

def parse_progress(logfile: Path) -> dict | None:
    if not logfile.exists() or logfile.stat().st_size == 0:
        return None
    try:
        with logfile.open("r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-20:]
            for line in reversed(lines):
                m = PROGRESS_RE.search(line)
                if m:
                    return {
                        "simulated_time_s": float(m.group("sim_t")),
                        "endtime_s": float(m.group("end_t")),
                        "progress_pct": float(m.group("pct")),
                        "dt_s": float(m.group("dt")),
                        "engine_elapsed_s": float(m.group("elapsed")),
                    }
    except Exception:
        pass
    return None

def status() -> dict:
    state_path = RUN_DIR / "V49_Method1_EXECUTION_STATE.json"
    if not state_path.exists():
        return {"status": "NOT_STARTED"}
    for _ in range(5):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            break
        except Exception:
            time.sleep(0.05)
    else:
        return {"status": "READ_ERROR"}

    state["supervisor_alive"] = pid_alive(state.get("supervisor_pid"))
    state["worker_alive"] = pid_alive(state.get("worker_pid"))
    return state

def worker(arm: str) -> None:
    manifest = json.loads((RUN_DIR / "V49_Method1_MANIFEST.json").read_text(encoding="utf-8"))
    param_path = Path(manifest["configs"][arm]["param_file"]).resolve()
    
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.chdir(V48_RUNTIME)
    sys.path.insert(0, str(V48_RUNTIME / "python"))

    import cupy
    cupy.cuda.Device(0).use()

    from bg_flood import write_txtlog
    write_txtlog._LOG_FILE = str((RESULTS_DIR / f"V49_Method1_ScopeB1_{arm}_engine_log.txt").resolve())

    # Install discrete mass budget observer
    sys.path.insert(0, str(PROJECT_DIR))
    from v49_runtime_observer import install_budget_observer
    install_budget_observer((RESULTS_DIR / f"V49_Method1_ScopeB1_{arm}_discrete_budget.json").resolve())

    import run_bgflood
    run_bgflood.run_model(str(param_path))

def supervise() -> None:
    preflight()
    manifest = json.loads((RUN_DIR / "V49_Method1_MANIFEST.json").read_text(encoding="utf-8"))
    state_path = RUN_DIR / "V49_Method1_EXECUTION_STATE.json"

    state = {
        "schema_version": "V49-Method1-execution-1",
        "status": "RUNNING",
        "queue": list(ARMS),
        "active_arm": None,
        "runs": {},
        "supervisor_pid": os.getpid(),
        "worker_pid": None,
        "started_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
    }
    atomic_json(state_path, state)

    try:
        for arm in ARMS:
            logfile = RESULTS_DIR / f"V49_Method1_ScopeB1_{arm}_run.log"
            result_nc = RESULTS_DIR / f"V49_Method1_ScopeB1_{arm}.nc"

            state["active_arm"] = arm
            state["queue"] = [a for a in ARMS if a != arm and state["runs"].get(a, {}).get("status") != "COMPLETED"]
            state["runs"][arm] = {
                "status": "RUNNING",
                "started_at_utc": utc_now(),
                "log": str(logfile),
                "result": str(result_nc),
            }
            atomic_json(state_path, state)

            vram = check_cuda_vram()
            state["runs"][arm]["vram_start_gb"] = vram["free_gb"]
            print(f"[SUPERVISOR] Launching {arm} on GPU Device 0 ({vram['free_gb']:.1f} GB free)...", flush=True)

            worker_env = os.environ.copy()
            worker_env["CUDA_VISIBLE_DEVICES"] = "0"
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

            with logfile.open("w", encoding="utf-8") as log:
                proc = subprocess.Popen(
                    [sys.executable, "-B", "-u", str(Path(__file__).resolve()), "worker", "--arm", arm],
                    cwd=PROJECT_DIR,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                    env=worker_env,
                )
                state["worker_pid"] = proc.pid
                atomic_json(state_path, state)

                worker_start = time.monotonic()
                last_print = 0.0

                while proc.poll() is None:
                    now = time.monotonic()
                    p = parse_progress(logfile)
                    if p:
                        state["runs"][arm]["progress"] = p
                        state["updated_at_utc"] = utc_now()
                        atomic_json(state_path, state)

                        if now - last_print >= 30.0:
                            sim_h = p["simulated_time_s"] / 3600.0
                            end_h = p["endtime_s"] / 3600.0
                            pct = p["progress_pct"]
                            dt = p["dt_s"]
                            el_str = format_time_duration(now - worker_start)
                            rate = p["simulated_time_s"] / max(now - worker_start, 1.0)
                            rem_s = (p["endtime_s"] - p["simulated_time_s"]) / max(rate, 1e-6)
                            eta_str = format_time_duration(rem_s)
                            print(f"[{arm}] {sim_h:.1f}h / {end_h:.1f}h ({pct:.1f}%) | dt = {dt:.3f}s | elapsed = {el_str} | ETA = {eta_str}", flush=True)
                            last_print = now
                    else:
                        if now - last_print >= 30.0:
                            el_str = format_time_duration(now - worker_start)
                            print(f"[{arm}] Initializing BG_Flood solver on CUDA Device 0... | elapsed = {el_str}", flush=True)
                            last_print = now

                    time.sleep(2)

            state["worker_pid"] = None
            state["runs"][arm]["finished_at_utc"] = utc_now()

            if proc.returncode != 0:
                state["runs"][arm]["status"] = "FAILED"
                state["status"] = "FAILED"
                atomic_json(state_path, state)
                raise RuntimeError(f"Arm {arm} failed with return code {proc.returncode}; see {logfile}")

            state["runs"][arm]["status"] = "COMPLETED"
            atomic_json(state_path, state)
            print(f"[SUPERVISOR] Arm {arm} completed successfully!", flush=True)

        state.update(
            status="ALL_ARMS_COMPLETED",
            active_arm=None,
            queue=[],
            updated_at_utc=utc_now(),
        )
        atomic_json(state_path, state)
        print("[SUPERVISOR] All simulation arms (CENTRAL, LOW, HIGH) have completed!", flush=True)

    finally:
        state["supervisor_pid"] = None
        state["worker_pid"] = None
        atomic_json(state_path, state)

def start() -> dict:
    s = status()
    if s.get("supervisor_alive") or s.get("worker_alive"):
        return {"status": "ALREADY_RUNNING", "supervisor_pid": s.get("supervisor_pid"), "worker_pid": s.get("worker_pid")}

    prepare()
    preflight()

    sup_log = RUN_DIR / "V49_Method1_supervisor.log"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    log = sup_log.open("a", encoding="utf-8")

    child = subprocess.Popen(
        [sys.executable, "-B", "-u", str(Path(__file__).resolve()), "supervise"],
        cwd=PROJECT_DIR,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    return {
        "status": "SUPERVISOR_LAUNCHED",
        "supervisor_pid": child.pid,
        "log": str(sup_log),
        "scope": "SCOPE_B1_41",
        "first_arm": "CENTRAL",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "preflight", "start", "supervise", "worker", "status"))
    parser.add_argument("--arm", choices=ARMS)
    args = parser.parse_args()

    if args.action == "worker":
        if not args.arm:
            parser.error("worker requires --arm")
        worker(args.arm)
    elif args.action == "supervise":
        supervise()
    elif args.action == "prepare":
        res = prepare()
        print(json.dumps(res, indent=2))
    elif args.action == "preflight":
        res = preflight()
        print(json.dumps(res, indent=2))
    elif args.action == "start":
        res = start()
        print(json.dumps(res, indent=2))
    elif args.action == "status":
        res = status()
        print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
