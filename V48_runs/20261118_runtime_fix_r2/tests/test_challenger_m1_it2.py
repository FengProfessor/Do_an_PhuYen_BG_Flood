#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Empirical Adversarial Stress Test Suite - Iteration 2 Challenger
================================================================
Target: supervisor_v48_r1.py
Tests:
  1. PID Monitoring, Lifecycle & Exit Code Verification
  2. Log Parser Resilience, Word Boundary Anomaly Filtering & CFL Detection
  3. Atomic State Persistence & Fault Recovery
  4. Command Generation & Interface Conformance
  5. Process Tree Teardown (stop_process_tree) empirical multi-process termination
"""

import sys
import os
import time
import json
import math
import subprocess
import tempfile
import shutil
from pathlib import Path
import psutil

RUNTIME_DIR = Path(r"D:\VTP\V48_runs\20261004_runtime_fix_r1")
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

import supervisor_v48_r1 as sup


def test_suite_pid_monitoring():
    print("\n" + "=" * 60)
    print("SUITE 1: PID MONITORING & EXIT CODE CAPTURE")
    print("=" * 60)
    results = {}

    # 1.1 Real solver PID 21608
    alive_21608 = sup.is_pid_alive(21608)
    det_21608 = sup.get_process_details(21608)
    print(f"  [1.1] PID 21608 alive: {alive_21608}, details: {det_21608}")
    results["real_solver_21608_alive"] = alive_21608
    results["real_solver_21608_details_valid"] = (
        det_21608 is not None and
        det_21608.get("name", "").lower() == "python.exe" and
        det_21608.get("memory_mb", 0) > 30 and
        det_21608.get("status") == "running"
    )

    # 1.2 Real launcher PID 31276
    alive_31276 = sup.is_pid_alive(31276)
    print(f"  [1.2] PID 31276 alive: {alive_31276}")
    results["real_launcher_31276_alive"] = alive_31276

    # 1.3 Dead PIDs
    dead_pids = [999999, 888888, -1, 0, None]
    dead_safe = True
    for p in dead_pids:
        try:
            if sup.is_pid_alive(p) is not False or sup.get_process_details(p) is not None:
                dead_safe = False
        except Exception:
            dead_safe = False
    results["dead_pids_handled_safely"] = dead_safe
    print(f"  [1.3] Dead PIDs handled safely: {dead_safe}")

    # 1.4 String PID robustness
    try:
        sup.is_pid_alive("21608")
        type_resilient = True
    except TypeError:
        type_resilient = False
    except Exception:
        type_resilient = False
    results["string_pid_type_resilient"] = type_resilient
    print(f"  [1.4] String PID type resilient: {type_resilient}")

    # 1.5 Dynamic lifecycle transition
    mock_p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.4)"])
    m_pid = mock_p.pid
    during = sup.is_pid_alive(m_pid)
    mock_p.wait()
    time.sleep(0.1)
    after = sup.is_pid_alive(m_pid)
    results["lifecycle_transition_detected"] = (during is True and after is False)
    print(f"  [1.5] Lifecycle transition detected: {results['lifecycle_transition_detected']}")

    # 1.6 Empirical Exit Code Capture via _proc_cache / check_exit_code
    print("  [1.6] Testing empirical exit code retrieval (0 vs 42)...")
    s_exit = sup.V48Supervisor()
    p_zero = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
    p_err = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(42)"])
    
    # Pre-cache process handles
    s_exit._proc_cache[p_zero.pid] = psutil.Process(p_zero.pid)
    s_exit._proc_cache[p_err.pid] = psutil.Process(p_err.pid)
    
    p_zero.wait()
    p_err.wait()
    
    code_zero = s_exit.check_exit_code(p_zero.pid)
    code_err = s_exit.check_exit_code(p_err.pid)
    print(f"    Exit code zero returned: {code_zero} (expected 0)")
    print(f"    Exit code 42 returned:   {code_err} (expected 42)")
    results["exit_code_capture_functional"] = (code_zero == 0 and code_err == 42)

    # 1.7 Premature Exit Trapping in tick() (Resolution of failure point 1)
    print("  [1.7] Testing premature exit handling in tick() (< 40 frames)...")
    tmp_dir = Path(tempfile.mkdtemp(prefix="v48_test_premature_"))
    mock_state_file = tmp_dir / "V48_SUPERVISOR_STATE.json"
    mock_log_file = tmp_dir / "V48_SUPERVISOR.log"

    orig_state_file = sup.STATE_FILE
    orig_log_file = sup.LOG_SUPERVISOR
    orig_inspect_nc = sup.inspect_netcdf
    orig_parse_log = sup.parse_simulation_log
    orig_is_pid_alive = sup.is_pid_alive

    try:
        sup.STATE_FILE = mock_state_file
        sup.LOG_SUPERVISOR = mock_log_file
        sup.is_pid_alive = lambda pid: False
        sup.inspect_netcdf = lambda path: {"num_frames": 10, "is_valid": True, "exists": True, "latest_time_sec": 108000.0}
        sup.parse_simulation_log = lambda path, **kw: {
            "exists": True, "sim_time_sec": 108000.0, "percent": 25.0,
            "dt_sec": 0.33, "dt_stable": True, "cfl_value": 0.5, "cfl_stable": True,
            "elapsed_sec": 120000.0, "nan_inf_errors": 0, "last_saved_frame": 9, "speed_ratio": 0.8
        }

        s = sup.V48Supervisor()
        s.state["base_solver_pid"] = 999981
        s.state["base_launcher_pid"] = 999982
        s.save_state()

        s.tick()

        stage_after = s.state.get("pipeline_stage")
        completed_flag = s.state.get("stage_a_base_completed")
        print(f"    After premature exit: pipeline_stage='{stage_after}', stage_a_base_completed={completed_flag}")

        # Failure point 1 check: must be FALSE that it falsely advances
        results["premature_abort_falsely_advances_pipeline"] = (
            stage_after == "STAGE_B_PREPARE_CONDITIONED" and completed_flag is True
        )
        results["premature_abort_halts_in_error_base_failed"] = (
            stage_after == "ERROR_BASE_FAILED" and completed_flag is False
        )
        print(f"    premature_abort_falsely_advances_pipeline: {results['premature_abort_falsely_advances_pipeline']}")
        print(f"    premature_abort_halts_in_error_base_failed: {results['premature_abort_halts_in_error_base_failed']}")

    finally:
        sup.STATE_FILE = orig_state_file
        sup.LOG_SUPERVISOR = orig_log_file
        sup.inspect_netcdf = orig_inspect_nc
        sup.parse_simulation_log = orig_parse_log
        sup.is_pid_alive = orig_is_pid_alive
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return results


def test_suite_log_parser_resilience():
    print("\n" + "=" * 60)
    print("SUITE 2: LOG PARSER RESILIENCE & CFL DETECTION")
    print("=" * 60)
    results = {}
    tmp_dir = Path(tempfile.mkdtemp(prefix="v48_test_log_"))

    try:
        # 2.1 Nominal parsing
        log_nom = tmp_dir / "nom.log"
        log_nom.write_text(
            "CFL = 0.5\n"
            "t = 360000.00/432000s (83.3%) | dt = 3.300e-01 | elapsed = 390000.0s\n"
            "NetCDF frame t=367200.0s saved\n"
            "t = 367200.00/432000s (85.0%) | dt = 3.300e-01 | elapsed = 399000.0s\n",
            encoding="utf-8"
        )
        p_nom = sup.parse_simulation_log(log_nom)
        results["nominal_parsing_valid"] = (
            p_nom["sim_time_sec"] == 367200.0 and
            p_nom["percent"] == 85.0 and
            p_nom["last_saved_frame"] == 33 and
            p_nom["nan_inf_errors"] == 0 and
            p_nom["cfl_stable"] is True and
            p_nom["dt_stable"] is True and
            p_nom["speed_ratio"] > 0
        )
        print(f"  [2.1] Nominal parsing valid: {results['nominal_parsing_valid']}")

        # 2.2 NaN detection
        log_nan = tmp_dir / "nan.log"
        log_nan.write_text("Warning: cell depth encountered NaN\n", encoding="utf-8")
        p_nan = sup.parse_simulation_log(log_nan)
        results["nan_detected"] = (p_nan["nan_inf_errors"] == 1)
        print(f"  [2.2] NaN detected: {results['nan_detected']}")

        # 2.3 Inf detection
        log_inf = tmp_dir / "inf.log"
        log_inf.write_text("ERROR: Flux computed +Inf at boundary cell\n", encoding="utf-8")
        p_inf = sup.parse_simulation_log(log_inf)
        results["inf_detected"] = (p_inf["nan_inf_errors"] == 1)
        print(f"  [2.3] Inf detected: {results['inf_detected']}")

        # 2.4 CUDA error detection
        log_cuda = tmp_dir / "cuda.log"
        log_cuda.write_text("CUDA error: out of memory in GPU allocation\n", encoding="utf-8")
        p_cuda = sup.parse_simulation_log(log_cuda)
        results["cuda_error_detected"] = (p_cuda["nan_inf_errors"] == 1)
        print(f"  [2.4] CUDA error detected: {results['cuda_error_detected']}")

        # 2.5 CFL Violation Detection (Resolution of failure point 3)
        log_cfl = tmp_dir / "cfl_viol.log"
        log_cfl.write_text(
            "--- Summary ---\n"
            "CFL = 0.5\n"
            "t = 100.0/432000s (0.1%) | dt = 3.3e-01 | elapsed = 10.0s\n"
            "Warning: Courant number CFL = 0.85 exceeded theoretical stability limit 0.5\n"
            "CFL instability triggered: CFL = 1.25 > 0.5\n",
            encoding="utf-8"
        )
        p_cfl = sup.parse_simulation_log(log_cfl)
        cfl_viol = (p_cfl.get("cfl_value", 0.0) > 0.5 or p_cfl.get("cfl_stable") is False)
        results["cfl_violation_detected"] = cfl_viol
        results["cfl_value_parsed"] = p_cfl.get("cfl_value")
        results["cfl_stable_flag"] = p_cfl.get("cfl_stable")
        print(f"  [2.5] CFL violation detected: {results['cfl_violation_detected']} (cfl_value={p_cfl.get('cfl_value')}, cfl_stable={p_cfl.get('cfl_stable')})")

        # 2.6 False Positive Tests (Resolution of failure point 2)
        benign_tests = [
            ("inflow", "Applying river boundary inflow hydrograph: Q = 1500.0 m3/s"),
            ("reinforcement", "Structure reinforcement enabled at levee segment #12"),
            ("infinite", "Domain boundary condition assumed infinite extent"),
            ("nanosecond", "High precision timer resolution: 25 nanoseconds per cycle"),
            ("confluence", "River confluence mixing model active at node 45"),
            ("info", "[INFO] Boundary conditions loaded successfully")
        ]
        fps = {}
        for name, line in benign_tests:
            log_b = tmp_dir / f"benign_{name}.log"
            log_b.write_text(f"CFL = 0.5\n{line}\n", encoding="utf-8")
            p_b = sup.parse_simulation_log(log_b)
            fps[name] = (p_b["nan_inf_errors"] > 0)
            print(f"    Benign '{name}': errors={p_b['nan_inf_errors']}, false_positive={fps[name]}")

        results["false_positive_inflow"] = fps["inflow"]
        results["false_positive_reinforcement"] = fps["reinforcement"]
        results["false_positive_infinite"] = fps["infinite"]
        results["false_positive_nanosecond"] = fps["nanosecond"]
        results["false_positive_info"] = fps["info"]

        # 2.7 Empty and Missing files
        p_none = sup.parse_simulation_log(tmp_dir / "nonexistent.log")
        log_zero = tmp_dir / "zero.log"
        log_zero.write_text("", encoding="utf-8")
        p_zero = sup.parse_simulation_log(log_zero)
        results["empty_and_missing_files_handled_gracefully"] = (
            p_none["exists"] is False and p_zero["exists"] is True and p_zero["sim_time_sec"] == 0.0
        )
        print(f"  [2.7] Empty & missing files safe: {results['empty_and_missing_files_handled_gracefully']}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return results


def test_suite_state_persistence():
    print("\n" + "=" * 60)
    print("SUITE 3: ATOMIC STATE PERSISTENCE & INTEGRITY")
    print("=" * 60)
    results = {}
    tmp_dir = Path(tempfile.mkdtemp(prefix="v48_test_state_"))

    orig_state_file = sup.STATE_FILE
    orig_log_file = sup.LOG_SUPERVISOR

    try:
        sup.STATE_FILE = tmp_dir / "V48_SUPERVISOR_STATE.json"
        sup.LOG_SUPERVISOR = tmp_dir / "V48_SUPERVISOR.log"

        # 3.1 Nominal roundtrip
        s1 = sup.V48Supervisor()
        s1.state["pipeline_stage"] = "STAGE_D_MONITOR_CONDITIONED"
        s1.state["conditioned_launcher_pid"] = 88776
        s1.state["stage_a_base_completed"] = True
        s1.save_state()

        s2 = sup.V48Supervisor()
        results["nominal_roundtrip_valid"] = (
            s2.state["pipeline_stage"] == "STAGE_D_MONITOR_CONDITIONED" and
            s2.state["conditioned_launcher_pid"] == 88776 and
            s2.state["stage_a_base_completed"] is True
        )
        print(f"  [3.1] Nominal roundtrip valid: {results['nominal_roundtrip_valid']}")

        # 3.2 Atomic replace mechanism verification (Resolution of failure point 4)
        with open(RUNTIME_DIR / "supervisor_v48_r1.py", "r", encoding="utf-8") as f:
            src = f.read()
        has_atomic_replace = ("os.replace(temp_file, STATE_FILE)" in src or "os.replace(" in src) and "tempfile.NamedTemporaryFile" in src
        results["save_state_uses_atomic_file_replace"] = has_atomic_replace
        print(f"  [3.2] save_state uses atomic replace: {has_atomic_replace}")

        # 3.3 Atomic failure resistance: ensure failed write does not corrupt existing state
        # Create valid state file
        s1.save_state()
        mtime_before = sup.STATE_FILE.stat().st_mtime_ns
        content_before = sup.STATE_FILE.read_text(encoding="utf-8")

        # Mock an error during write
        orig_replace = os.replace
        try:
            def broken_replace(src, dst):
                raise OSError("Simulated atomic replace power failure")
            os.replace = broken_replace
            try:
                s1.state["pipeline_stage"] = "CORRUPTED_IN_MEMORY"
                s1.save_state()
            except OSError:
                pass  # expected
        finally:
            os.replace = orig_replace

        content_after = sup.STATE_FILE.read_text(encoding="utf-8")
        results["failed_write_leaves_original_unharmed"] = (content_before == content_after)
        print(f"  [3.3] Failed write leaves original intact: {results['failed_write_leaves_original_unharmed']}")

        # 3.4 Abnormal truncation handling
        with open(sup.STATE_FILE, "w", encoding="utf-8") as f:
            f.write('{"pipeline_stage": "STAGE_D", "trunc')
        s_trunc = sup.V48Supervisor()
        results["handled_truncation_without_crash"] = (s_trunc.state["pipeline_stage"] == "STAGE_A_MONITOR_BASE")
        print(f"  [3.4] Handled truncation without crash: {results['handled_truncation_without_crash']}")

        # 3.5 Zero byte file
        with open(sup.STATE_FILE, "w", encoding="utf-8") as f:
            pass
        s_zero = sup.V48Supervisor()
        results["zero_byte_handled_without_crash"] = (s_zero.state["pipeline_stage"] == "STAGE_A_MONITOR_BASE")
        print(f"  [3.5] Zero-byte handled without crash: {results['zero_byte_handled_without_crash']}")

    finally:
        sup.STATE_FILE = orig_state_file
        sup.LOG_SUPERVISOR = orig_log_file
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return results


def test_suite_command_generation():
    print("\n" + "=" * 60)
    print("SUITE 4: COMMAND GENERATION & INTERFACE CONFORMANCE")
    print("=" * 60)
    results = {}

    expected_py = Path(r"C:\Users\CuongHM\anaconda3\python.exe").resolve()
    actual_py = sup.PYTHON_EXE.resolve()
    results["python_interpreter_matches_anaconda"] = (expected_py == actual_py)
    print(f"  [4.1] Python interpreter matches Anaconda: {results['python_interpreter_matches_anaconda']}")

    cmd_launch = [
        str(sup.PYTHON_EXE), "-X", "utf8", "-B", str(sup.SCRIPT_LAUNCH), "--arm", "CONDITIONED"
    ]
    results["launch_cmd_flags_match_r1"] = (
        cmd_launch[1] == "-X" and
        cmd_launch[2] == "utf8" and
        cmd_launch[3] == "-B" and
        Path(cmd_launch[4]).name == "launch_formal.py" and
        cmd_launch[5] == "--arm" and
        cmd_launch[6] == "CONDITIONED"
    )
    print(f"  [4.2] Launch command flags match R1: {results['launch_cmd_flags_match_r1']}")

    p_help = subprocess.run(
        [str(sup.PYTHON_EXE), str(sup.SCRIPT_LAUNCH), "--help"],
        cwd=str(RUNTIME_DIR), capture_output=True, text=True
    )
    results["launch_formal_cli_valid"] = (p_help.returncode == 0 and "--arm {BASE,CONDITIONED}" in p_help.stdout)
    print(f"  [4.3] launch_formal.py CLI valid: {results['launch_formal_cli_valid']}")

    is_ok, msg = sup.check_release_environment()
    results["release_environment_check_passes"] = is_ok
    print(f"  [4.4] Release check passes: {is_ok} ({msg[:60]}...)")

    p_eval = subprocess.run(
        [str(sup.PYTHON_EXE), str(sup.SCRIPT_EVAL), "--help"],
        cwd=str(RUNTIME_DIR), capture_output=True, text=True
    )
    results["eval_script_cli_accepts_parameters"] = (
        p_eval.returncode == 0 and "--nc" in p_eval.stdout and "--frame" in p_eval.stdout and "--arm" in p_eval.stdout
    )
    print(f"  [4.5] eval_v48_formal.py accepts params: {results['eval_script_cli_accepts_parameters']}")

    p_diff = subprocess.run(
        [str(sup.PYTHON_EXE), str(sup.SCRIPT_DIFF), "--help"],
        cwd=str(RUNTIME_DIR), capture_output=True, text=True
    )
    results["diff_script_cli_accepts_parameters"] = (
        p_diff.returncode == 0 and "--nc-base" in p_diff.stdout and "--nc-cond" in p_diff.stdout and "--frame" in p_diff.stdout
    )
    print(f"  [4.6] diff_v48_formal.py accepts params: {results['diff_script_cli_accepts_parameters']}")

    return results


def test_suite_process_tree_teardown():
    print("\n" + "=" * 60)
    print("SUITE 5: PROCESS TREE TEARDOWN (stop_process_tree)")
    print("=" * 60)
    results = {}

    # Test 5.1: Safe on dead / invalid PIDs
    print("  [5.1] Testing stop_process_tree on invalid / dead PIDs...")
    try:
        sup.stop_process_tree(None)
        sup.stop_process_tree(-1)
        sup.stop_process_tree(9999999)
        results["invalid_pids_handled_safely"] = True
    except Exception as e:
        results["invalid_pids_handled_safely"] = False
        print(f"    Exception on invalid PID: {e}")
    print(f"    Invalid PIDs handled safely: {results['invalid_pids_handled_safely']}")

    # Test 5.2: Real 3-level process tree termination
    print("  [5.2] Spawning real 3-level process tree (Parent -> Child -> Grandchild)...")
    child_script = """
import sys, subprocess, time
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
print(f"GRANDCHILD_PID={grandchild.pid}", flush=True)
while True:
    time.sleep(1)
"""
    parent_script = f"""
import sys, subprocess, time
child = subprocess.Popen([sys.executable, "-c", '''{child_script}'''], stdout=subprocess.PIPE, text=True)
for line in child.stdout:
    if "GRANDCHILD_PID=" in line:
        print(line.strip(), flush=True)
        break
print(f"CHILD_PID={{child.pid}}", flush=True)
while True:
    time.sleep(1)
"""
    parent_proc = subprocess.Popen(
        [sys.executable, "-c", parent_script],
        stdout=subprocess.PIPE,
        text=True
    )
    parent_pid = parent_proc.pid

    # Read child and grandchild PIDs from stdout
    grandchild_pid = None
    child_pid = None
    t0 = time.time()
    while time.time() - t0 < 10.0:
        line = parent_proc.stdout.readline()
        if "GRANDCHILD_PID=" in line:
            grandchild_pid = int(line.strip().split("=")[1])
        if "CHILD_PID=" in line:
            child_pid = int(line.strip().split("=")[1])
        if grandchild_pid and child_pid:
            break

    print(f"    Created tree: Parent={parent_pid}, Child={child_pid}, Grandchild={grandchild_pid}")
    assert grandchild_pid is not None and child_pid is not None, "Failed to initialize simulated process tree"

    time.sleep(0.5)
    # Confirm all 3 are alive
    parent_alive_before = sup.is_pid_alive(parent_pid)
    child_alive_before = sup.is_pid_alive(child_pid)
    grandchild_alive_before = sup.is_pid_alive(grandchild_pid)
    print(f"    Liveness before teardown: Parent={parent_alive_before}, Child={child_alive_before}, Grandchild={grandchild_alive_before}")

    # Now execute stop_process_tree on parent
    print(f"    Invoking sup.stop_process_tree({parent_pid}, timeout=5.0)...")
    sup.stop_process_tree(parent_pid, timeout=5.0)

    time.sleep(0.5)
    parent_alive_after = sup.is_pid_alive(parent_pid)
    child_alive_after = sup.is_pid_alive(child_pid)
    grandchild_alive_after = sup.is_pid_alive(grandchild_pid)
    print(f"    Liveness after teardown: Parent={parent_alive_after}, Child={child_alive_after}, Grandchild={grandchild_alive_after}")

    results["tree_all_alive_before"] = (parent_alive_before and child_alive_before and grandchild_alive_before)
    results["parent_terminated"] = not parent_alive_after
    results["child_terminated"] = not child_alive_after
    results["grandchild_terminated"] = not grandchild_alive_after
    results["entire_tree_terminated_cleanly"] = (
        not parent_alive_after and not child_alive_after and not grandchild_alive_after
    )
    print(f"  [5.2] Entire tree terminated cleanly: {results['entire_tree_terminated_cleanly']}")

    return results


def main():
    print("=" * 80)
    print(" EMPIRICAL ADVERSARIAL STRESS TEST SUITE: SUPERVISOR_V48_R1 (ITERATION 2)")
    print("=" * 80)

    all_results = {}
    all_results["pid_monitoring"] = test_suite_pid_monitoring()
    all_results["log_parser_resilience"] = test_suite_log_parser_resilience()
    all_results["state_persistence"] = test_suite_state_persistence()
    all_results["command_generation"] = test_suite_command_generation()
    all_results["process_tree_teardown"] = test_suite_process_tree_teardown()

    print("\n" + "=" * 80)
    print(" FINAL EMPIRICAL SUMMARY")
    print("=" * 80)
    print(json.dumps(all_results, indent=2))

    return all_results


if __name__ == "__main__":
    main()
