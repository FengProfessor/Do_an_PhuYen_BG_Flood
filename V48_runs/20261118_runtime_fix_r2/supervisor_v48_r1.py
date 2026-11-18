#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V48 Formal Sequential GPU Supervisor (R1 Pipeline)
===================================================
Automates and oversees the entire end-to-end execution of V48 R1:
  Step A: Monitor BASE simulation (PID 21608 / PID 31276) until 40 frames (120h / 432,000s),
          verifying clean termination, 0 NaN/Inf, and NetCDF file integrity.
  Step B: Verify release environment (launch_formal.py --check) and ensure complete GPU VRAM release.
  Step C: Formally launch CONDITIONED arm via launch_formal.py --arm CONDITIONED.
  Step D: Continuously supervise CONDITIONED arm, verifying CFL <= 0.5, 0 NaN/Inf, and frame output.
  Step E: Immediately at Frame 33 (102.0h / 367,200s), execute SAR evaluation (eval_v48_formal.py)
          and differential analysis (diff_v48_formal.py).
  Step F: Supervise CONDITIONED arm until 40 frames (120h) completion.

Provides:
  --status: Instantaneous reporting of PIDs, simulation time, ETA, GPU load, and pipeline status.
  --watch / --daemon: Resilient polling supervisor loop with state persistence in V48_SUPERVISOR_STATE.json
                      and logging in V48_SUPERVISOR.log.
  --once: Run a single supervision tick (useful for test suites or scheduled tasks).
"""

import os
import sys
import time
import json
import re
import argparse
import math
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import psutil

ROOT = Path(__file__).resolve().parent
PYTHON_EXE = Path(sys.executable).resolve()

# Target files
LOG_SUPERVISOR = ROOT / "results" / "V48_SUPERVISOR.log"
STATE_FILE = ROOT / "results" / "V48_SUPERVISOR_STATE.json"

NC_BASE = ROOT / "results" / "V48_FORMAL_BASE_R1.nc"
LOG_BASE = ROOT / "results" / "V48_FORMAL_BASE_R1.log"

NC_COND = ROOT / "results" / "V48_FORMAL_CONDITIONED_R1.nc"
LOG_COND = ROOT / "results" / "V48_FORMAL_CONDITIONED_R1.log"
LAUNCHER_COND_LOG = ROOT / "results" / "V48_FORMAL_CONDITIONED_LAUNCHER.log"

SCRIPT_LAUNCH = ROOT / "launch_formal.py"
SCRIPT_EVAL = ROOT / "eval_v48_formal.py"
SCRIPT_DIFF = ROOT / "diff_v48_formal.py"

TOTAL_SIM_SECONDS = 432000.0  # 120.0 hours
OUTPUT_TIMESTEP = 10800.0     # 3.0 hours
TOTAL_FRAMES = 40             # 0 to 39
FRAME_33_TIME_SEC = 367200.0  # 102.0 hours
REQUIRED_FREE_VRAM_MIB = 12288   # >= 12.0 GiB free VRAM required
STAGE_B_TIMEOUT_SECONDS = 300.0  # 5 minutes maximum wait for VRAM release

# Precompiled patterns for robust log parsing and stability verification
NAN_INF_PATTERN = re.compile(r'(?i)\b(?:nan|inf|-inf|\+inf)\b')
ANOMALY_PATTERN = re.compile(
    r'(?i)(?:cuda\s+error|stability\s+alert|numerical\s+instability|1\.#(?:qnan|snan|ind|inf))'
)
CFL_CONFIG_PATTERN = re.compile(r'(?i)\bCFL\s*=\s*([0-9\.]+)')
CFL_DYNAMIC_PATTERN = re.compile(r'(?i)\b(?:cfl|courant)\s*=\s*([0-9\.eE+-]+)')
STEP_PATTERN = re.compile(
    r't\s*=\s*([0-9\.]+)/([0-9\.]+)s\s*\(([0-9\.]+)%\)\s*\|\s*dt\s*=\s*([0-9\.eE+-]+)\s*\|\s*elapsed\s*=\s*([0-9\.]+)s'
)
FRAME_PATTERN = re.compile(r'NetCDF frame t=([0-9\.]+)s saved')


def log_msg(msg, to_console=True):
    """Logs message with UTC+7 timestamp to file and console."""
    tz = timezone(timedelta(hours=7))
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S ICT")
    line = f"[{now_str}] {msg}"
    if to_console:
        print(line, flush=True)
    LOG_SUPERVISOR.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_SUPERVISOR, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_pid_alive(pid):
    """Checks whether a given PID is currently active."""
    if pid is None or pid <= 0:
        return False
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def stop_process_tree(pid, timeout=10.0):
    """
    Gracefully terminates a process and all child/descendant processes.
    First sends proc.terminate() (SIGTERM), waits up to timeout seconds,
    then escalates to proc.kill() (SIGKILL) if any process remains alive.
    """
    if pid is None or pid <= 0:
        return
    try:
        parent = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return

    try:
        children = parent.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        children = []

    all_procs = children + [parent]
    log_msg(f"Terminating PID {pid} and {len(children)} child processes...")
    for p in all_procs:
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    gone, alive = psutil.wait_procs(all_procs, timeout=timeout)
    if alive:
        log_msg(f"Processes {[p.pid for p in alive]} did not exit within {timeout}s; escalating to kill()...")
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        psutil.wait_procs(alive, timeout=5.0)


def get_process_details(pid):
    """Returns dictionary of process metrics if alive."""
    if not is_pid_alive(pid):
        return None
    try:
        proc = psutil.Process(pid)
        return {
            "pid": pid,
            "name": proc.name(),
            "cpu_seconds": proc.cpu_times().user + proc.cpu_times().system,
            "memory_mb": proc.memory_info().rss / (1024 * 1024),
            "create_time": datetime.fromtimestamp(proc.create_time()).strftime("%Y-%m-%d %H:%M:%S"),
            "status": proc.status()
        }
    except Exception as e:
        return {"pid": pid, "error": str(e)}


def query_gpu_status():
    """Queries NVIDIA RTX A4000 GPU status via nvidia-smi."""
    gpu_info = {
        "available": False,
        "utilization_pct": 0,
        "memory_used_mib": 0,
        "memory_total_mib": 0,
        "temperature_c": 0,
        "power_w": 0.0,
        "compute_processes": []
    }
    try:
        res = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(',')]
            if len(parts) >= 5:
                gpu_info["available"] = True
                gpu_info["utilization_pct"] = int(float(parts[0]))
                gpu_info["memory_used_mib"] = int(float(parts[1]))
                gpu_info["memory_total_mib"] = int(float(parts[2]))
                gpu_info["temperature_c"] = int(float(parts[3]))
                gpu_info["power_w"] = float(parts[4])
    except Exception:
        pass

    try:
        res_p = subprocess.run(
            ['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5
        )
        if res_p.returncode == 0:
            lines = [l.strip() for l in res_p.stdout.strip().splitlines() if l.strip()]
            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 2:
                    try:
                        p_pid = int(parts[0])
                        p_name = parts[1]
                        gpu_info["compute_processes"].append({"pid": p_pid, "name": p_name})
                    except ValueError:
                        pass
    except Exception:
        pass

    return gpu_info


def parse_simulation_log(log_path, head_bytes=32768, tail_bytes=100000):
    """
    Parses simulation log file header and tail for:
      - Initial model CFL configuration and dynamic step Courant number
      - Current sim time t, max time, percent, dt, elapsed wall seconds
      - Verification of timestep dt finiteness and CFL Courant stability (CFL <= 0.5)
      - Anomaly counts (NaN, Inf, CUDA errors, stability alerts) using word boundaries
      - Latest frame written
      - Rolling speed ratio (sim_sec / wall_sec)
    """
    log_path = Path(log_path)
    if not log_path.is_file():
        return {
            "exists": False,
            "file_size_bytes": 0,
            "sim_time_sec": 0.0,
            "percent": 0.0,
            "dt_sec": 0.0,
            "dt_stable": False,
            "cfl_value": 0.5,
            "cfl_stable": True,
            "elapsed_sec": 0.0,
            "nan_inf_errors": 0,
            "last_saved_frame": -1,
            "speed_ratio": 0.0
        }

    file_size = log_path.stat().st_size

    # 1. Read header to extract initial configuration (CFL, grid params)
    with open(log_path, 'rb') as f:
        head_content = f.read(min(file_size, head_bytes)).decode('utf-8', errors='ignore')
    m_cfl_cfg = CFL_CONFIG_PATTERN.search(head_content)
    cfl_configured = float(m_cfl_cfg.group(1)) if m_cfl_cfg else 0.5

    # 2. Read tail to monitor active timesteps and scan for runtime anomalies
    with open(log_path, 'rb') as f:
        if file_size > tail_bytes:
            f.seek(file_size - tail_bytes)
        tail_content = f.read().decode('utf-8', errors='ignore')

    lines = tail_content.splitlines()

    nan_inf_count = 0
    sim_time_sec = 0.0
    percent = 0.0
    dt_sec = 0.0
    elapsed_sec = 0.0
    last_saved_frame = -1
    cfl_dynamic = None

    timesteps = []
    for line in lines:
        if NAN_INF_PATTERN.search(line) or ANOMALY_PATTERN.search(line):
            nan_inf_count += 1

        m_step = STEP_PATTERN.search(line)
        if m_step:
            t_val = float(m_step.group(1))
            pct_val = float(m_step.group(3))
            dt_val = float(m_step.group(4))
            elap_val = float(m_step.group(5))
            sim_time_sec = t_val
            percent = pct_val
            dt_sec = dt_val
            elapsed_sec = elap_val
            timesteps.append((t_val, elap_val))

        m_cfl_dyn = CFL_DYNAMIC_PATTERN.search(line)
        if m_cfl_dyn:
            cfl_dynamic = float(m_cfl_dyn.group(1))

        m_frame = FRAME_PATTERN.search(line)
        if m_frame:
            f_time = float(m_frame.group(1))
            frame_num = int(round(f_time / OUTPUT_TIMESTEP)) - 1
            if frame_num > last_saved_frame:
                last_saved_frame = frame_num

    # Compute rolling speed ratio over recent entries in the tail
    speed_ratio = 0.0
    if len(timesteps) >= 2:
        t_first, e_first = timesteps[0]
        t_last, e_last = timesteps[-1]
        delta_sim = t_last - t_first
        delta_wall = e_last - e_first
        if delta_wall > 0:
            speed_ratio = delta_sim / delta_wall

    cfl_value = cfl_dynamic if cfl_dynamic is not None else cfl_configured
    cfl_stable = bool(cfl_value is not None and cfl_value <= 0.5 + 1e-6)
    dt_stable = bool(math.isfinite(dt_sec) and dt_sec > 0.0)

    return {
        "exists": True,
        "file_size_bytes": file_size,
        "sim_time_sec": sim_time_sec,
        "percent": percent,
        "dt_sec": dt_sec,
        "dt_stable": dt_stable,
        "cfl_value": cfl_value,
        "cfl_stable": cfl_stable,
        "elapsed_sec": elapsed_sec,
        "nan_inf_errors": nan_inf_count,
        "last_saved_frame": last_saved_frame,
        "speed_ratio": speed_ratio
    }


def inspect_netcdf(nc_path):
    """Inspects NetCDF dataset for frame count, timestamps, and integrity."""
    nc_path = Path(nc_path)
    if not nc_path.is_file():
        return {
            "exists": False,
            "num_frames": 0,
            "latest_time_sec": 0.0,
            "is_valid": False,
            "error": "File does not exist"
        }
    try:
        import netCDF4 as nc
        with nc.Dataset(nc_path, 'r') as ds:
            times = ds.variables['time'][:]
            num_frames = len(times)
            latest_time = float(times[-1]) if num_frames > 0 else 0.0
            return {
                "exists": True,
                "file_size_bytes": nc_path.stat().st_size,
                "num_frames": num_frames,
                "latest_time_sec": latest_time,
                "is_valid": True,
                "error": None
            }
    except Exception as e:
        return {
            "exists": True,
            "file_size_bytes": nc_path.stat().st_size if nc_path.is_file() else 0,
            "num_frames": 0,
            "latest_time_sec": 0.0,
            "is_valid": False,
            "error": str(e)
        }


def check_release_environment():
    """Executes launch_formal.py --check to verify release hashes."""
    try:
        cmd = [str(PYTHON_EXE), "-X", "utf8", "-B", str(SCRIPT_LAUNCH), "--check"]
        res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=15)
        is_pass = (res.returncode == 0 and "PASS:" in res.stdout)
        return is_pass, res.stdout.strip()
    except Exception as e:
        return False, str(e)


class V48Supervisor:
    """Manages the full automated sequential pipeline state machine."""

    def __init__(self):
        self.state = self.load_state()
        self._proc_cache = {}
        # Pre-cache process handles while active to guarantee exit code retrieval upon termination
        for key in ("base_solver_pid", "base_launcher_pid", "conditioned_launcher_pid"):
            pid = self.state.get(key)
            if pid and is_pid_alive(pid):
                try:
                    self._proc_cache[pid] = psutil.Process(pid)
                except Exception:
                    pass
        if not STATE_FILE.is_file():
            self.save_state()

    def default_state(self):
        return {
            "pipeline_stage": "STAGE_A_MONITOR_BASE",
            "base_solver_pid": 21608,
            "base_launcher_pid": 31276,
            "base_solver_exit_code": None,
            "base_launcher_exit_code": None,
            "conditioned_launcher_pid": None,
            "conditioned_solver_pid": None,
            "conditioned_launcher_exit_code": None,
            "stage_a_base_completed": False,
            "stage_b_env_verified": False,
            "stage_b_wait_start_epoch": None,
            "stage_c_cond_launched": False,
            "stage_e_frame_33_evaluated": False,
            "stage_f_cond_completed": False,
            "last_checked_iso": "",
            "evaluation_artifacts": {}
        }

    def load_state(self):
        if STATE_FILE.is_file():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    state = self.default_state()
                    state.update(loaded)
                    return state
            except Exception as e:
                log_msg(f"Warning: Failed reading {STATE_FILE}: {e}; initializing fresh state")
        return self.default_state()

    def save_state(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.state["last_checked_iso"] = datetime.now(timezone.utc).isoformat()
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=STATE_FILE.parent,
                prefix=f"{STATE_FILE.stem}_",
                suffix=".tmp",
                delete=False
            ) as f:
                temp_file = Path(f.name)
                json.dump(self.state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, STATE_FILE)
        except Exception as e:
            log_msg(f"ERROR: Failed writing state atomically to {STATE_FILE}: {e}")
            if temp_file and temp_file.is_file():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise e

    def check_exit_code(self, pid):
        """
        Queries exit code for a PID if terminated.
        Returns None if process is still running; int exit code (0, 1, etc.) if terminated.
        """
        if not pid or pid <= 0:
            return None
        proc = self._proc_cache.get(pid)
        if proc is None and is_pid_alive(pid):
            try:
                proc = psutil.Process(pid)
                self._proc_cache[pid] = proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return None

        if proc is not None:
            try:
                return proc.wait(timeout=0)
            except psutil.TimeoutExpired:
                return None
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None

    def get_status_report(self):
        """Generates comprehensive status snapshot for CLI and monitoring."""
        gpu = query_gpu_status()
        base_log = parse_simulation_log(LOG_BASE)
        base_nc = inspect_netcdf(NC_BASE)
        cond_log = parse_simulation_log(LOG_COND)
        cond_nc = inspect_netcdf(NC_COND)

        base_solver_alive = is_pid_alive(self.state.get("base_solver_pid"))
        base_launcher_alive = is_pid_alive(self.state.get("base_launcher_pid"))

        cond_launcher_pid = self.state.get("conditioned_launcher_pid")
        cond_launcher_alive = is_pid_alive(cond_launcher_pid) if cond_launcher_pid else False

        # Calculate BASE ETA
        base_rem_sec = max(0.0, TOTAL_SIM_SECONDS - base_log["sim_time_sec"])
        base_rate = base_log["speed_ratio"] if base_log["speed_ratio"] > 0 else 0.7081
        base_eta_wall_sec = base_rem_sec / base_rate if base_rate > 0 else 0
        base_eta_hours = base_eta_wall_sec / 3600.0

        tz = timezone(timedelta(hours=7))
        projected_completion = (datetime.now(tz) + timedelta(seconds=base_eta_wall_sec)).strftime("%Y-%m-%d %H:%M:%S ICT")

        report = {
            "supervisor_time_ict": datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S ICT"),
            "pipeline_stage": self.state.get("pipeline_stage"),
            "gpu": {
                "available": gpu["available"],
                "utilization_pct": gpu["utilization_pct"],
                "memory_used_mib": gpu["memory_used_mib"],
                "memory_total_mib": gpu["memory_total_mib"],
                "temperature_c": gpu["temperature_c"],
                "power_w": gpu["power_w"],
                "compute_apps_count": len(gpu["compute_processes"])
            },
            "base_arm": {
                "solver_pid": self.state.get("base_solver_pid"),
                "solver_alive": base_solver_alive,
                "launcher_pid": self.state.get("base_launcher_pid"),
                "launcher_alive": base_launcher_alive,
                "sim_time_sec": base_log["sim_time_sec"],
                "sim_time_hours": base_log["sim_time_sec"] / 3600.0,
                "progress_percent": base_log["percent"],
                "current_dt_sec": base_log["dt_sec"],
                "dt_stable": base_log.get("dt_stable", True),
                "cfl_value": base_log.get("cfl_value", 0.5),
                "cfl_stable": base_log.get("cfl_stable", True),
                "elapsed_wall_hours": base_log["elapsed_sec"] / 3600.0,
                "speed_ratio": base_log["speed_ratio"],
                "nan_inf_errors": base_log["nan_inf_errors"],
                "nc_frames_recorded": base_nc["num_frames"],
                "nc_file_size_gb": base_nc.get("file_size_bytes", 0) / (1024**3),
                "remaining_sim_hours": base_rem_sec / 3600.0,
                "estimated_wall_hours_left": base_eta_hours,
                "projected_completion_ict": projected_completion,
                "completed": self.state.get("stage_a_base_completed")
            },
            "conditioned_arm": {
                "launcher_pid": cond_launcher_pid,
                "launcher_alive": cond_launcher_alive,
                "log_exists": cond_log["exists"],
                "sim_time_sec": cond_log["sim_time_sec"],
                "current_dt_sec": cond_log["dt_sec"],
                "dt_stable": cond_log.get("dt_stable", True),
                "cfl_value": cond_log.get("cfl_value", 0.5),
                "cfl_stable": cond_log.get("cfl_stable", True),
                "progress_percent": cond_log["percent"],
                "nan_inf_errors": cond_log["nan_inf_errors"],
                "nc_frames_recorded": cond_nc["num_frames"],
                "frame_33_evaluated": self.state.get("stage_e_frame_33_evaluated"),
                "completed": self.state.get("stage_f_cond_completed")
            },
            "milestones": {
                "base_completed_40_frames": self.state.get("stage_a_base_completed"),
                "env_and_vram_verified": self.state.get("stage_b_env_verified"),
                "conditioned_launched": self.state.get("stage_c_cond_launched"),
                "frame_33_evaluated": self.state.get("stage_e_frame_33_evaluated"),
                "conditioned_completed": self.state.get("stage_f_cond_completed")
            }
        }
        return report

    def print_status(self):
        """Displays clear human-readable status table."""
        rep = self.get_status_report()
        b = rep["base_arm"]
        c = rep["conditioned_arm"]
        g = rep["gpu"]

        print("=" * 80)
        print(" V48 R1 SEQUENTIAL GPU SUPERVISOR STATUS REPORT")
        print("=" * 80)
        print(f"Time (ICT):        {rep['supervisor_time_ict']}")
        print(f"Pipeline Stage:    {rep['pipeline_stage']}")
        print(f"GPU Load:          {g['utilization_pct']}% | VRAM: {g['memory_used_mib']} / {g['memory_total_mib']} MiB | Temp: {g['temperature_c']}°C | Power: {g['power_w']} W")
        print("-" * 80)
        print("BASE ARM STATUS:")
        print(f"  Solver PID:      {b['solver_pid']} (Alive: {b['solver_alive']})")
        print(f"  Launcher PID:    {b['launcher_pid']} (Alive: {b['launcher_alive']})")
        print(f"  Simulation Time: {b['sim_time_sec']:.1f} s ({b['sim_time_hours']:.2f} h / 120.0 h) [{b['progress_percent']:.1f}%]")
        print(f"  Time Step dt:    {b['current_dt_sec']:.4f} s | CFL: {b.get('cfl_value', 0.5)} (Stable: {b.get('cfl_stable', True)}) | Speed: {b['speed_ratio']:.3f}x real-time")
        print(f"  NetCDF Frames:   {b['nc_frames_recorded']} / 40 frames ({b['nc_file_size_gb']:.2f} GB)")
        print(f"  NaN/Inf Errors:  {b['nan_inf_errors']}")
        print(f"  Remaining Time:  ~{b['estimated_wall_hours_left']:.2f} wall hours -> Projected ETA: {b['projected_completion_ict']}")
        print(f"  Status Flag:     {'COMPLETED (120h)' if b['completed'] else 'RUNNING (Wait for finish)'}")
        print("-" * 80)
        print("CONDITIONED ARM STATUS:")
        print(f"  Launcher PID:    {c['launcher_pid']} (Alive: {c['launcher_alive']})")
        print(f"  Simulation Time: {c['sim_time_sec']:.1f} s [{c['progress_percent']:.1f}%]")
        print(f"  Time Step dt:    {c.get('current_dt_sec', 0.0):.4f} s | CFL: {c.get('cfl_value', 0.5)} (Stable: {c.get('cfl_stable', True)})")
        print(f"  NetCDF Frames:   {c['nc_frames_recorded']} / 40")
        print(f"  NaN/Inf Errors:  {c['nan_inf_errors']}")
        print(f"  Frame 33 Eval:   {'COMPLETED (SAR & Delta h evaluated)' if c['frame_33_evaluated'] else 'PENDING'}")
        print(f"  Status Flag:     {'COMPLETED' if c['completed'] else ('RUNNING' if c['launcher_alive'] else 'WAITING_FOR_BASE')}")
        print("=" * 80)

    def execute_frame_33_evaluations(self):
        """
        Executes formal SAR evaluation and differential analysis at Frame 33.
        """
        log_msg("=== TRIGGERING AUTOMATED EVALUATION AT FRAME 33 (102.0h / 367,200s) ===")

        # 1. Run eval_v48_formal.py explicitly specifying --nc for CONDITIONED
        cmd_eval = [
            str(PYTHON_EXE), str(SCRIPT_EVAL),
            "--nc", str(NC_COND),
            "--frame", "33",
            "--arm", "CONDITIONED"
        ]
        log_msg(f"Executing: {' '.join(cmd_eval)}")
        res_eval = subprocess.run(cmd_eval, cwd=str(ROOT), capture_output=True, text=True)
        if res_eval.returncode != 0:
            log_msg(f"ERROR: eval_v48_formal.py failed with exit {res_eval.returncode}:\n{res_eval.stderr}")
            return False
        log_msg(f"eval_v48_formal.py succeeded:\n{res_eval.stdout}")

        # 2. Run diff_v48_formal.py
        cmd_diff = [
            str(PYTHON_EXE), str(SCRIPT_DIFF),
            "--nc-base", str(NC_BASE),
            "--nc-cond", str(NC_COND),
            "--frame", "33",
            "--out-dir", str(ROOT / "results")
        ]
        log_msg(f"Executing: {' '.join(cmd_diff)}")
        res_diff = subprocess.run(cmd_diff, cwd=str(ROOT), capture_output=True, text=True)
        if res_diff.returncode != 0:
            log_msg(f"ERROR: diff_v48_formal.py failed with exit {res_diff.returncode}:\n{res_diff.stderr}")
            return False
        log_msg(f"diff_v48_formal.py succeeded:\n{res_diff.stdout}")

        # 3. Verify existence of outputs
        f_eval_json = ROOT / "results" / "SAR_vs_V48_CONDITIONED_frame_33_metrics.json"
        f_diff_json = ROOT / "results" / "V48_DIFF_CONDITIONED_vs_BASE_frame_33.json"
        f_diff_png = ROOT / "results" / "V48_DIFF_depth_map_frame_33.png"

        if f_eval_json.is_file() and f_diff_json.is_file() and f_diff_png.is_file():
            self.state["stage_e_frame_33_evaluated"] = True
            self.state["evaluation_artifacts"] = {
                "sar_eval_json": str(f_eval_json),
                "diff_json": str(f_diff_json),
                "diff_png": str(f_diff_png)
            }
            self.save_state()
            log_msg("SUCCESS: Frame 33 SAR evaluation and differential analysis completed and verified.")
            return True
        else:
            log_msg("ERROR: Expected Frame 33 evaluation artifacts were not created.")
            return False

    def tick(self):
        """
        Executes one evaluation step of the supervisor state machine.
        """
        stage = self.state.get("pipeline_stage", "STAGE_A_MONITOR_BASE")

        # ---------------------------------------------------------------------
        # STAGE A: MONITOR BASE ARM
        # ---------------------------------------------------------------------
        if stage == "STAGE_A_MONITOR_BASE":
            solver_pid = self.state.get("base_solver_pid")
            launcher_pid = self.state.get("base_launcher_pid")

            base_solver_alive = is_pid_alive(solver_pid)
            base_launcher_alive = is_pid_alive(launcher_pid)
            base_nc = inspect_netcdf(NC_BASE)
            base_log = parse_simulation_log(LOG_BASE)

            # Capture process exit codes if processes have terminated
            solver_code = self.check_exit_code(solver_pid)
            if solver_code is not None:
                self.state["base_solver_exit_code"] = solver_code

            launcher_code = self.check_exit_code(launcher_pid)
            if launcher_code is not None:
                self.state["base_launcher_exit_code"] = launcher_code

            # Check if simulation is still actively computing on GPU
            if base_solver_alive or base_launcher_alive:
                rem_sec = max(0.0, TOTAL_SIM_SECONDS - base_log["sim_time_sec"])
                speed = base_log["speed_ratio"] if base_log["speed_ratio"] > 0 else 0.7081
                eta_h = (rem_sec / speed) / 3600.0 if speed > 0 else 0
                log_msg(
                    f"Stage A Active: BASE PID {solver_pid} at t = {base_log['sim_time_sec']:.1f}s "
                    f"({base_log['percent']:.1f}%), {base_nc['num_frames']}/40 frames. ETA: ~{eta_h:.2f}h."
                )
                self.save_state()
                return

            # Both processes have terminated: conduct comprehensive multi-criteria validation
            log_msg("BASE processes have terminated. Evaluating termination integrity...")

            # 1. Premature exit check (< 40 frames or < 431,999.0s)
            if base_nc["num_frames"] < TOTAL_FRAMES or base_log["sim_time_sec"] < TOTAL_SIM_SECONDS - 1.0:
                log_msg(
                    f"CRITICAL: BASE solver terminated prematurely! Recorded only {base_nc['num_frames']}/40 frames "
                    f"(sim_time = {base_log['sim_time_sec']:.1f}s / {TOTAL_SIM_SECONDS}s). Aborting pipeline."
                )
                self.state["pipeline_stage"] = "ERROR_BASE_FAILED"
                self.save_state()
                return

            # 2. Exit code verification (must be 0)
            solver_ec = self.state.get("base_solver_exit_code")
            launcher_ec = self.state.get("base_launcher_exit_code")
            if (solver_ec is not None and solver_ec != 0) or (launcher_ec is not None and launcher_ec != 0):
                log_msg(
                    f"CRITICAL: BASE process exited with non-zero exit code (solver={solver_ec}, launcher={launcher_ec})! "
                    "Aborting pipeline."
                )
                self.state["pipeline_stage"] = "ERROR_BASE_FAILED"
                self.save_state()
                return

            # 3. NetCDF dataset validity & final timestamp extent
            if not base_nc.get("is_valid", False):
                log_msg(f"CRITICAL: BASE NetCDF dataset is invalid or corrupt: {base_nc.get('error')}! Aborting pipeline.")
                self.state["pipeline_stage"] = "ERROR_BASE_FAILED"
                self.save_state()
                return

            if base_nc.get("latest_time_sec", 0.0) < TOTAL_SIM_SECONDS - 1.0:
                log_msg(
                    f"CRITICAL: BASE NetCDF latest timestamp ({base_nc.get('latest_time_sec', 0.0):.1f}s) "
                    f"is less than required end time {TOTAL_SIM_SECONDS - 1.0}s! Aborting pipeline."
                )
                self.state["pipeline_stage"] = "ERROR_BASE_FAILED"
                self.save_state()
                return

            # 4. Numerical stability & NaN/Inf errors & CFL stability
            if base_log.get("nan_inf_errors", 0) > 0:
                log_msg(
                    f"CRITICAL: BASE simulation terminated with {base_log['nan_inf_errors']} NaN/Inf errors! "
                    "Aborting pipeline."
                )
                self.state["pipeline_stage"] = "ERROR_BASE_FAILED"
                self.save_state()
                return

            if not base_log.get("cfl_stable", True):
                log_msg(
                    f"CRITICAL: BASE simulation violated CFL limit (CFL = {base_log.get('cfl_value')} > 0.5)! "
                    "Aborting pipeline."
                )
                self.state["pipeline_stage"] = "ERROR_BASE_FAILED"
                self.save_state()
                return

            # All 40 frames verified, exit code 0 verified, NetCDF valid, 0 NaN/Inf, CFL stable -> Advance to Stage B
            log_msg(
                f"STAGE A COMPLETE: BASE arm achieved {base_nc['num_frames']}/40 frames "
                f"(t = {base_log['sim_time_sec']:.1f} s, latest_nc_t = {base_nc.get('latest_time_sec', 0.0):.1f} s). "
                f"Clean termination with exit code 0."
            )
            self.state["stage_a_base_completed"] = True
            self.state["pipeline_stage"] = "STAGE_B_PREPARE_CONDITIONED"
            self.save_state()

        # ---------------------------------------------------------------------
        # STAGE B: PREPARE CONDITIONED & VERIFY VRAM RELEASE
        # ---------------------------------------------------------------------
        elif stage == "STAGE_B_PREPARE_CONDITIONED":
            log_msg("STAGE B: Verifying GPU release and release environment integrity...")
            wait_start = self.state.get("stage_b_wait_start_epoch")
            if wait_start is None:
                wait_start = time.time()
                self.state["stage_b_wait_start_epoch"] = wait_start
                self.save_state()

            elapsed_wait = time.time() - wait_start
            gpu = query_gpu_status()

            if not gpu.get("available", False):
                if elapsed_wait >= STAGE_B_TIMEOUT_SECONDS:
                    log_msg(f"CRITICAL: GPU query failed or GPU unavailable after {elapsed_wait:.0f}s timeout!")
                    self.state["pipeline_stage"] = "ERROR_VRAM_RELEASE_TIMEOUT"
                    self.save_state()
                    return
                log_msg(f"Waiting for GPU detection ({elapsed_wait:.0f}/{STAGE_B_TIMEOUT_SECONDS:.0f}s)...")
                return

            free_vram_mib = gpu["memory_total_mib"] - gpu["memory_used_mib"]
            compute_procs = gpu.get("compute_processes", [])
            gpu_busy = (len(compute_procs) > 0) or (free_vram_mib < REQUIRED_FREE_VRAM_MIB)

            if gpu_busy:
                if elapsed_wait >= STAGE_B_TIMEOUT_SECONDS:
                    log_msg(
                        f"CRITICAL: GPU VRAM release timed out after {elapsed_wait:.0f}s! "
                        f"Free VRAM: {free_vram_mib} MiB (required >= {REQUIRED_FREE_VRAM_MIB} MiB), "
                        f"active compute apps: {compute_procs}"
                    )
                    self.state["pipeline_stage"] = "ERROR_VRAM_RELEASE_TIMEOUT"
                    self.save_state()
                    return
                log_msg(
                    f"GPU still busy ({elapsed_wait:.0f}/{STAGE_B_TIMEOUT_SECONDS:.0f}s). "
                    f"Free VRAM: {free_vram_mib} MiB (need >= {REQUIRED_FREE_VRAM_MIB} MiB), "
                    f"active apps: {len(compute_procs)}. Waiting for release..."
                )
                return

            # Check release hashes
            env_ok, env_out = check_release_environment()
            if not env_ok:
                log_msg(f"CRITICAL: Release check failed prior to launching CONDITIONED:\n{env_out}")
                self.state["pipeline_stage"] = "ERROR_RELEASE_CHECK_FAILED"
                self.save_state()
                return

            log_msg(f"Release environment verified ({env_out}). GPU VRAM free ({free_vram_mib} MiB >= {REQUIRED_FREE_VRAM_MIB} MiB). Ready to launch CONDITIONED.")
            self.state["stage_b_env_verified"] = True
            self.state["pipeline_stage"] = "STAGE_C_LAUNCH_CONDITIONED"
            self.save_state()

        # ---------------------------------------------------------------------
        # STAGE C: LAUNCH CONDITIONED ARM
        # ---------------------------------------------------------------------
        elif stage == "STAGE_C_LAUNCH_CONDITIONED":
            log_msg("STAGE C: Formally launching CONDITIONED arm via launch_formal.py --arm CONDITIONED...")

            # Clean pre-existing conditioned launcher log if any
            cmd_launch = [
                str(PYTHON_EXE), "-X", "utf8", "-B", str(SCRIPT_LAUNCH), "--arm", "CONDITIONED"
            ]

            LAUNCHER_COND_LOG.parent.mkdir(parents=True, exist_ok=True)
            launcher_log_file = open(LAUNCHER_COND_LOG, "w", encoding="utf-8")
            proc = subprocess.Popen(
                cmd_launch,
                cwd=str(ROOT),
                stdout=launcher_log_file,
                stderr=subprocess.STDOUT
            )

            self.state["conditioned_launcher_pid"] = proc.pid
            try:
                self._proc_cache[proc.pid] = psutil.Process(proc.pid)
            except Exception:
                pass
            self.state["stage_c_cond_launched"] = True
            self.state["pipeline_stage"] = "STAGE_D_MONITOR_CONDITIONED"
            self.save_state()
            log_msg(f"Spawned CONDITIONED launcher PID {proc.pid}. Monitoring started.")

        # ---------------------------------------------------------------------
        # STAGE D: MONITOR CONDITIONED ARM
        # ---------------------------------------------------------------------
        elif stage == "STAGE_D_MONITOR_CONDITIONED":
            c_pid = self.state.get("conditioned_launcher_pid")
            c_alive = is_pid_alive(c_pid)
            c_log = parse_simulation_log(LOG_COND)
            c_nc = inspect_netcdf(NC_COND)

            # Check CFL and NaN/Inf anomalies
            if c_log["exists"]:
                if c_log["nan_inf_errors"] > 0:
                    log_msg(f"CRITICAL: CONDITIONED run encountered {c_log['nan_inf_errors']} NaN/Inf errors! Terminating runaway processes...")
                    stop_process_tree(c_pid, timeout=10.0)
                    self.state["pipeline_stage"] = "ERROR_CONDITIONED_FAILED"
                    self.save_state()
                    return

                if not c_log["cfl_stable"]:
                    log_msg(f"CRITICAL: CONDITIONED run violated CFL stability limit: CFL = {c_log['cfl_value']} > 0.5! Terminating runaway processes...")
                    stop_process_tree(c_pid, timeout=10.0)
                    self.state["pipeline_stage"] = "ERROR_CONDITIONED_FAILED"
                    self.save_state()
                    return

                if not c_log["dt_stable"] and c_log["sim_time_sec"] > 0.0:
                    log_msg(f"CRITICAL: CONDITIONED non-finite or negative timestep dt = {c_log['dt_sec']}! Terminating runaway processes...")
                    stop_process_tree(c_pid, timeout=10.0)
                    self.state["pipeline_stage"] = "ERROR_CONDITIONED_FAILED"
                    self.save_state()
                    return

            # Check for Frame 33 Milestone
            if not self.state.get("stage_e_frame_33_evaluated"):
                if c_nc["num_frames"] >= 34 or c_log["sim_time_sec"] >= FRAME_33_TIME_SEC:
                    log_msg(f"Milestone reached: Frame 33 achieved (t = {c_log['sim_time_sec']:.1f} s, {c_nc['num_frames']} frames)!")
                    success = self.execute_frame_33_evaluations()
                    if success:
                        self.state["stage_e_frame_33_evaluated"] = True
                        self.save_state()

            # Check for full 40 frame completion
            if (not c_alive and c_nc["num_frames"] >= TOTAL_FRAMES) or (c_nc["num_frames"] >= TOTAL_FRAMES and c_log["sim_time_sec"] >= TOTAL_SIM_SECONDS - 1.0):
                log_msg(f"STAGE F COMPLETE: CONDITIONED arm successfully reached {c_nc['num_frames']}/40 frames (120h).")
                self.state["stage_f_cond_completed"] = True
                self.state["pipeline_stage"] = "PIPELINE_COMPLETE"
                self.save_state()
            elif not c_alive and c_nc["num_frames"] < TOTAL_FRAMES:
                # Process exited prematurely before 40 frames
                log_msg(
                    f"CRITICAL: CONDITIONED launcher PID {c_pid} exited prematurely before reaching 40 frames! "
                    f"Recorded {c_nc['num_frames']}/40 frames (sim_time = {c_log['sim_time_sec']:.1f}s). Halting."
                )
                stop_process_tree(c_pid, timeout=5.0)
                self.state["pipeline_stage"] = "ERROR_CONDITIONED_FAILED"
                self.save_state()
                return
            else:
                log_msg(
                    f"Stage D Active: CONDITIONED PID {c_pid} at t = {c_log['sim_time_sec']:.1f}s "
                    f"({c_log['percent']:.1f}%), dt = {c_log['dt_sec']:.4f}s, {c_nc['num_frames']}/40 frames. "
                    f"CFL = {c_log['cfl_value']} (stable)."
                )

        self.save_state()

    def run_loop(self, poll_interval=30):
        """Runs the continuous supervision loop."""
        log_msg(f"Starting V48 Supervisor loop (poll interval: {poll_interval}s)...")
        try:
            while True:
                self.tick()
                stage = self.state.get("pipeline_stage")
                if stage in ("PIPELINE_COMPLETE", "ERROR_BASE_FAILED", "ERROR_RELEASE_CHECK_FAILED", "ERROR_CONDITIONED_FAILED", "ERROR_VRAM_RELEASE_TIMEOUT"):
                    log_msg(f"Supervisor loop terminating at state: {stage}")
                    break
                time.sleep(poll_interval)
        except KeyboardInterrupt:
            log_msg("Supervisor interrupted by user (Ctrl+C). State persisted.")


def main():
    parser = argparse.ArgumentParser(description="V48 Formal Sequential GPU Supervisor (R1)")
    parser.add_argument("--status", action="store_true", help="Print instantaneous status report and exit")
    parser.add_argument("--watch", "--daemon", dest="daemon", action="store_true", help="Run persistent supervisor loop")
    parser.add_argument("--once", action="store_true", help="Run a single supervisor tick and exit")
    parser.add_argument("--poll-interval", type=int, default=30, help="Polling interval in seconds for --daemon (default: 30)")
    parser.add_argument("--test-eval-frame33", action="store_true", help="Test execution of Frame 33 evaluation routines")
    args = parser.parse_args()

    supervisor = V48Supervisor()

    if args.status:
        supervisor.print_status()
        return

    if args.test_eval_frame33:
        log_msg("Running Frame 33 evaluation test...")
        supervisor.execute_frame_33_evaluations()
        return

    if args.once:
        log_msg("Running single supervisor tick...")
        supervisor.tick()
        supervisor.print_status()
        return

    if args.daemon:
        supervisor.run_loop(poll_interval=args.poll_interval)
        return

    # Default: if no flag given, print status
    supervisor.print_status()


if __name__ == "__main__":
    main()
