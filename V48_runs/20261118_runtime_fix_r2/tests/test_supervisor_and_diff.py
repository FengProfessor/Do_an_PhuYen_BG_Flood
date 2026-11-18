#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Unit & Integration Test Suite for V48 R1 Supervisor & Differential Evaluator
==========================================================================================
Tests:
  1. Supervisor state persistence and transitions (V48Supervisor, V48_SUPERVISOR_STATE.json).
  2. Process and GPU diagnostics (is_pid_alive, get_process_details, query_gpu_status).
  3. Simulation log parsing and Courant / NaN / Inf error detection.
  4. NetCDF inspection on formal R1 outputs (V48_FORMAL_BASE_R1.nc).
  5. Formal release environment and cryptographic hash verification (launch_formal.py --check).
  6. Differential evaluator mathematical invariants and Common Evaluation Mask consistency.
  7. Supervisor status reporting and milestone tracking.
"""

import os
import sys
import time
import json
import tempfile
import shutil
from pathlib import Path
import pytest
import numpy as np

# Ensure parent run directory is on path
RUN_DIR = Path(__file__).resolve().parent.parent
if str(RUN_DIR) not in sys.path:
    sys.path.insert(0, str(RUN_DIR))

import supervisor_v48_r1 as sup
import diff_v48_formal as diff


class TestSupervisorCore:
    """Tests for supervisor process supervision, logging, and state management."""

    def test_supervisor_state_persistence(self, tmp_path):
        """Verifies state serialization, deserialization, and key schema integrity."""
        test_state_file = tmp_path / "test_supervisor_state.json"
        
        orig_state_file = sup.STATE_FILE
        try:
            sup.STATE_FILE = test_state_file
            supervisor = sup.V48Supervisor()
            
            # Default state structure verification
            state = supervisor.state
            assert state["pipeline_stage"] == "STAGE_A_MONITOR_BASE"
            assert state["base_solver_pid"] == 21608
            assert state["base_launcher_pid"] == 31276
            assert state["stage_a_base_completed"] is False
            assert state["stage_e_frame_33_evaluated"] is False
            
            # Modify and save
            supervisor.state["pipeline_stage"] = "STAGE_B_PREPARE_CONDITIONED"
            supervisor.state["stage_a_base_completed"] = True
            supervisor.save_state()
            
            assert test_state_file.is_file()
            
            # Reload in a new instance
            supervisor_loaded = sup.V48Supervisor()
            assert supervisor_loaded.state["pipeline_stage"] == "STAGE_B_PREPARE_CONDITIONED"
            assert supervisor_loaded.state["stage_a_base_completed"] is True
            assert "last_checked_iso" in supervisor_loaded.state
        finally:
            sup.STATE_FILE = orig_state_file

    def test_pid_diagnostics(self):
        """Verifies process liveness query for existing self vs non-existent PID."""
        my_pid = os.getpid()
        assert sup.is_pid_alive(my_pid) is True
        
        proc_info = sup.get_process_details(my_pid)
        assert proc_info is not None
        assert proc_info["pid"] == my_pid
        assert proc_info["memory_mb"] > 0
        
        # Dead / non-existent PID
        fake_pid = 9999999
        assert sup.is_pid_alive(fake_pid) is False
        assert sup.get_process_details(fake_pid) is None

    def test_gpu_query_structure(self):
        """Verifies nvidia-smi GPU query returns standard dictionary schema."""
        gpu = sup.query_gpu_status()
        assert isinstance(gpu, dict)
        for key in ["available", "utilization_pct", "memory_used_mib", "memory_total_mib", "temperature_c", "compute_processes"]:
            assert key in gpu
        if gpu["available"]:
            assert gpu["memory_total_mib"] > 0
            assert gpu["temperature_c"] > 0

    def test_parse_simulation_log_healthy(self, tmp_path):
        """Tests parsing of normal simulation steps, timestamps, and frames."""
        dummy_log = tmp_path / "test_sim.log"
        dummy_content = (
            "Model Running... [GPU mode]\n"
            "t = 360000.00/432000s (83.3%) | dt = 3.300e-01 | elapsed = 390000.0s\n"
            "t = 367200.00/432000s (85.0%) | dt = 3.302e-01 | elapsed = 398000.0s\n"
            "NetCDF frame t=367200.125s saved in 4.2s\n"
            "t = 367201.00/432000s (85.0%) | dt = 3.302e-01 | elapsed = 398001.5s\n"
        )
        dummy_log.write_text(dummy_content, encoding="utf-8")
        
        res = sup.parse_simulation_log(dummy_log)
        assert res["exists"] is True
        assert res["sim_time_sec"] == 367201.0
        assert res["percent"] == 85.0
        assert res["dt_sec"] == 0.3302
        assert res["nan_inf_errors"] == 0
        assert res["last_saved_frame"] == 33
        assert res["speed_ratio"] > 0

    def test_parse_simulation_log_anomalies(self, tmp_path):
        """Tests detection of NaN/Inf and CUDA errors in simulation log."""
        dummy_log = tmp_path / "test_anomaly.log"
        dummy_content = (
            "t = 1000.00/432000s (0.2%) | dt = 3.300e-01 | elapsed = 100.0s\n"
            "Warning: cell depth contains NaN at row 100 col 200\n"
            "Warning: velocity is Inf\n"
            "CUDA error: an illegal memory access was encountered\n"
        )
        dummy_log.write_text(dummy_content, encoding="utf-8")
        
        res = sup.parse_simulation_log(dummy_log)
        assert res["nan_inf_errors"] >= 2

    def test_release_check(self):
        """Verifies launch_formal.py --check passes 100% cryptographic hashes."""
        is_pass, output = sup.check_release_environment()
        assert is_pass is True
        assert "PASS: runtime, dependencies, inputs, configs, tests and preregistration hashes match." in output

    def test_supervisor_status_report(self):
        """Tests full get_status_report dictionary schema and live PID monitoring."""
        supervisor = sup.V48Supervisor()
        report = supervisor.get_status_report()
        
        assert "supervisor_time_ict" in report
        assert "pipeline_stage" in report
        assert "gpu" in report
        assert "base_arm" in report
        assert "conditioned_arm" in report
        assert "milestones" in report
        
        b = report["base_arm"]
        assert b["solver_pid"] == 21608
        assert b["nc_frames_recorded"] >= 34
        assert b["sim_time_hours"] >= 102.0
        assert "cfl_value" in b
        assert "cfl_stable" in b
        assert "dt_stable" in b

    def test_anomaly_regex_word_boundaries_no_false_positives(self, tmp_path):
        """Verifies zero false positives on domain terms (inflow, infiltration, [INFO], infinite)."""
        dummy_log = tmp_path / "test_inflow.log"
        dummy_content = (
            "--- Tong ket tham so ---\n"
            "  CFL = 0.5\n"
            "[INFO] Boundary inflow Q = 1500 m3/s\n"
            "Soil infiltration rate: 15 mm/hr\n"
            "River boundary inflow: 400 m3/s\n"
            "Infinite precision not required\n"
            "t = 1000.00/432000s (0.2%) | dt = 3.300e-01 | elapsed = 100.0s\n"
        )
        dummy_log.write_text(dummy_content, encoding="utf-8")
        res = sup.parse_simulation_log(dummy_log)
        assert res["nan_inf_errors"] == 0, f"Expected 0 errors on inflow/infiltration, got {res['nan_inf_errors']}"

    def test_anomaly_regex_catches_true_anomalies(self, tmp_path):
        """Verifies regex detects nan, inf, -inf, +inf, CUDA error, stability alerts."""
        test_cases = [
            ("Detected NaN in cell depth", 1),
            ("Velocity magnitude is Inf m/s", 1),
            ("Flux value is -inf", 1),
            ("Value is +inf", 1),
            ("CUDA error: out of memory", 1),
            ("[STABILITY ALERT] CRITICAL NUMERICAL INSTABILITY: Non-finite CFL dt", 1),
            ("Matrix cell: 1.#QNAN", 1),
            ("Matrix cell: 1.#INF", 1),
        ]
        for line, expected_count in test_cases:
            dummy_log = tmp_path / "test_case.log"
            dummy_log.write_text(f"CFL = 0.5\n{line}\n", encoding="utf-8")
            res = sup.parse_simulation_log(dummy_log)
            assert res["nan_inf_errors"] == expected_count, f"Failed on line: {line!r}"

    def test_cfl_extraction_and_stability(self, tmp_path):
        """Tests dual-buffer CFL parameter extraction and CFL <= 0.5 stability verification."""
        # 1. Healthy configuration
        healthy_log = tmp_path / "healthy_cfl.log"
        healthy_log.write_text(
            "--- Param Summary ---\n"
            "  CFL = 0.5\n"
            "t = 100.0/432000s (0.1%) | dt = 3.300e-01 | elapsed = 10.0s\n",
            encoding="utf-8"
        )
        res_h = sup.parse_simulation_log(healthy_log)
        assert res_h["cfl_value"] == 0.5
        assert res_h["cfl_stable"] is True
        assert res_h["dt_stable"] is True

        # 2. Dynamic CFL above limit
        unstable_log = tmp_path / "unstable_cfl.log"
        unstable_log.write_text(
            "--- Param Summary ---\n"
            "  CFL = 0.5\n"
            "t = 100.0/432000s (0.1%) | dt = 3.300e-01 | elapsed = 10.0s\n"
            "cfl = 0.75 | courant violated\n",
            encoding="utf-8"
        )
        res_u = sup.parse_simulation_log(unstable_log)
        assert res_u["cfl_value"] == 0.75
        assert res_u["cfl_stable"] is False

        # 3. Invalid timestep dt
        inval_dt_log = tmp_path / "inval_dt.log"
        inval_dt_log.write_text(
            "  CFL = 0.5\n"
            "t = 100.0/432000s (0.1%) | dt = -1.000e-01 | elapsed = 10.0s\n",
            encoding="utf-8"
        )
        res_dt = sup.parse_simulation_log(inval_dt_log)
        assert res_dt["dt_stable"] is False

    def test_supervisor_stage_a_premature_exit_trapped(self, tmp_path, monkeypatch):
        """Verifies supervisor transitions to ERROR_BASE_FAILED when solver dies with < 40 frames."""
        test_state_file = tmp_path / "test_premature_state.json"
        monkeypatch.setattr(sup, "STATE_FILE", test_state_file)
        monkeypatch.setattr(sup, "LOG_SUPERVISOR", tmp_path / "test_sup.log")

        # Mock processes dead
        monkeypatch.setattr(sup, "is_pid_alive", lambda pid: False)
        # Mock NetCDF with only 34 frames
        monkeypatch.setattr(sup, "inspect_netcdf", lambda path: {
            "exists": True, "num_frames": 34, "latest_time_sec": 367200.0, "is_valid": True, "error": None
        })
        # Mock simulation log at Frame 34
        monkeypatch.setattr(sup, "parse_simulation_log", lambda path, head_bytes=32768, tail_bytes=100000: {
            "exists": True, "sim_time_sec": 371000.0, "percent": 85.8, "dt_sec": 1.4, "dt_stable": True,
            "elapsed_sec": 398000.0, "nan_inf_errors": 0, "cfl_value": 0.5, "cfl_stable": True,
            "last_saved_frame": 33, "speed_ratio": 0.7
        })

        supervisor = sup.V48Supervisor()
        supervisor.tick()

        assert supervisor.state["pipeline_stage"] == "ERROR_BASE_FAILED"
        assert supervisor.state["stage_a_base_completed"] is False

    def test_supervisor_stage_a_nonzero_exit_code_trapped(self, tmp_path, monkeypatch):
        """Verifies supervisor transitions to ERROR_BASE_FAILED when solver exits with non-zero code."""
        test_state_file = tmp_path / "test_exitcode_state.json"
        monkeypatch.setattr(sup, "STATE_FILE", test_state_file)
        monkeypatch.setattr(sup, "LOG_SUPERVISOR", tmp_path / "test_sup.log")

        monkeypatch.setattr(sup, "is_pid_alive", lambda pid: False)
        monkeypatch.setattr(sup, "inspect_netcdf", lambda path: {
            "exists": True, "num_frames": 40, "latest_time_sec": 432000.0, "is_valid": True, "error": None
        })
        monkeypatch.setattr(sup, "parse_simulation_log", lambda path, head_bytes=32768, tail_bytes=100000: {
            "exists": True, "sim_time_sec": 432000.0, "percent": 100.0, "dt_sec": 1.4, "dt_stable": True,
            "elapsed_sec": 432000.0, "nan_inf_errors": 0, "cfl_value": 0.5, "cfl_stable": True,
            "last_saved_frame": 39, "speed_ratio": 0.7
        })

        supervisor = sup.V48Supervisor()
        monkeypatch.setattr(supervisor, "check_exit_code", lambda pid: 1)
        supervisor.tick()

        assert supervisor.state["pipeline_stage"] == "ERROR_BASE_FAILED"
        assert supervisor.state["stage_a_base_completed"] is False

    def test_supervisor_stage_a_nominal_40_frames_advance(self, tmp_path, monkeypatch):
        """Verifies supervisor cleanly advances to STAGE_B_PREPARE_CONDITIONED when all 40 frames and code 0."""
        test_state_file = tmp_path / "test_nominal_state.json"
        monkeypatch.setattr(sup, "STATE_FILE", test_state_file)
        monkeypatch.setattr(sup, "LOG_SUPERVISOR", tmp_path / "test_sup.log")

        monkeypatch.setattr(sup, "is_pid_alive", lambda pid: False)
        monkeypatch.setattr(sup, "inspect_netcdf", lambda path: {
            "exists": True, "num_frames": 40, "latest_time_sec": 432000.0, "is_valid": True, "error": None
        })
        monkeypatch.setattr(sup, "parse_simulation_log", lambda path, head_bytes=32768, tail_bytes=100000: {
            "exists": True, "sim_time_sec": 432000.0, "percent": 100.0, "dt_sec": 1.4, "dt_stable": True,
            "elapsed_sec": 432000.0, "nan_inf_errors": 0, "cfl_value": 0.5, "cfl_stable": True,
            "last_saved_frame": 39, "speed_ratio": 0.7
        })

        supervisor = sup.V48Supervisor()
        monkeypatch.setattr(supervisor, "check_exit_code", lambda pid: 0)
        supervisor.tick()

        assert supervisor.state["pipeline_stage"] == "STAGE_B_PREPARE_CONDITIONED"
        assert supervisor.state["stage_a_base_completed"] is True

    def test_atomic_state_persistence_resilience(self, tmp_path, monkeypatch):
        """Verifies atomic state saving creates clean file and handles mock exceptions gracefully."""
        test_state_file = tmp_path / "atomic_state.json"
        monkeypatch.setattr(sup, "STATE_FILE", test_state_file)
        monkeypatch.setattr(sup, "LOG_SUPERVISOR", tmp_path / "test_sup.log")

        supervisor = sup.V48Supervisor()
        supervisor.state["pipeline_stage"] = "STAGE_B_PREPARE_CONDITIONED"
        supervisor.save_state()

        assert test_state_file.is_file()
        content = json.loads(test_state_file.read_text(encoding="utf-8"))
        assert content["pipeline_stage"] == "STAGE_B_PREPARE_CONDITIONED"

        # Verify that mock failure in os.replace preserves existing state file
        def failing_replace(src, dst):
            raise OSError("Mock disk failure")

        monkeypatch.setattr(os, "replace", failing_replace)
        with pytest.raises(OSError):
            supervisor.state["pipeline_stage"] = "CORRUPT"
            supervisor.save_state()

        # Existing state file is untouched
        content_after = json.loads(test_state_file.read_text(encoding="utf-8"))
        assert content_after["pipeline_stage"] == "STAGE_B_PREPARE_CONDITIONED"

    def test_process_tree_teardown_mock(self, monkeypatch):
        """Verifies stop_process_tree terminates parent and children cleanly."""
        terminated_pids = []
        killed_pids = []

        class MockProc:
            def __init__(self, pid):
                self.pid = pid
            def children(self, recursive=True):
                return [MockProc(self.pid + 100)]
            def terminate(self):
                terminated_pids.append(self.pid)
            def kill(self):
                killed_pids.append(self.pid)

        monkeypatch.setattr(sup.psutil, "Process", lambda pid: MockProc(pid))
        monkeypatch.setattr(sup.psutil, "wait_procs", lambda procs, timeout: (procs, []))

        sup.stop_process_tree(12345, timeout=1.0)
        assert 12345 in terminated_pids
        assert 12445 in terminated_pids

    def test_stage_b_vram_and_timeout(self, tmp_path, monkeypatch):
        """Verifies Stage B timeout transition to ERROR_VRAM_RELEASE_TIMEOUT."""
        test_state_file = tmp_path / "test_stage_b.json"
        monkeypatch.setattr(sup, "STATE_FILE", test_state_file)
        monkeypatch.setattr(sup, "LOG_SUPERVISOR", tmp_path / "test_sup.log")

        supervisor = sup.V48Supervisor()
        supervisor.state["pipeline_stage"] = "STAGE_B_PREPARE_CONDITIONED"
        supervisor.state["stage_b_wait_start_epoch"] = time.time() - 350.0  # Expired > 300s

        # Mock GPU busy
        monkeypatch.setattr(sup, "query_gpu_status", lambda: {
            "available": True, "utilization_pct": 50, "memory_used_mib": 10000,
            "memory_total_mib": 16376, "temperature_c": 60, "power_w": 100.0,
            "compute_processes": [{"pid": 9999, "name": "python.exe"}]
        })

        supervisor.tick()
        assert supervisor.state["pipeline_stage"] == "ERROR_VRAM_RELEASE_TIMEOUT"

    def test_stage_d_premature_exit_and_teardown(self, tmp_path, monkeypatch):
        """Verifies Stage D premature exit transitions to ERROR_CONDITIONED_FAILED and tears down processes."""
        test_state_file = tmp_path / "test_stage_d.json"
        monkeypatch.setattr(sup, "STATE_FILE", test_state_file)
        monkeypatch.setattr(sup, "LOG_SUPERVISOR", tmp_path / "test_sup.log")

        supervisor = sup.V48Supervisor()
        supervisor.state["pipeline_stage"] = "STAGE_D_MONITOR_CONDITIONED"
        supervisor.state["conditioned_launcher_pid"] = 88888

        monkeypatch.setattr(sup, "is_pid_alive", lambda pid: False)
        monkeypatch.setattr(sup, "inspect_netcdf", lambda path: {
            "exists": True, "num_frames": 20, "latest_time_sec": 216000.0, "is_valid": True, "error": None
        })
        monkeypatch.setattr(sup, "parse_simulation_log", lambda path, head_bytes=32768, tail_bytes=100000: {
            "exists": True, "sim_time_sec": 216000.0, "percent": 50.0, "dt_sec": 1.4, "dt_stable": True,
            "elapsed_sec": 200000.0, "nan_inf_errors": 0, "cfl_value": 0.5, "cfl_stable": True,
            "last_saved_frame": 19, "speed_ratio": 0.7
        })

        teardown_called = []
        monkeypatch.setattr(sup, "stop_process_tree", lambda pid, timeout=5.0: teardown_called.append(pid))

        supervisor.tick()
        assert supervisor.state["pipeline_stage"] == "ERROR_CONDITIONED_FAILED"
        assert 88888 in teardown_called


class TestDifferentialEvaluator:
    """Tests for diff_v48_formal.py mathematics, coordinate alignment, and masks."""

    def test_load_netcdf_frame_alignment(self):
        """Tests NetCDF frame loading and ascending y-coordinate flip."""
        nc_base = sup.NC_BASE
        assert nc_base.is_file()
        
        h_arr, zb_arr, sim_t = diff.load_netcdf_frame(nc_base, frame_idx=33)
        assert h_arr.shape == (2100, 2100)
        assert sim_t >= 367200.0
        assert not np.isnan(h_arr).any()
        assert np.min(h_arr) >= 0.0
        
        # Verify alignment against 66 applied cells base elevations
        df_cells = diff.pd.read_csv(diff.DEFAULT_CELLS_CSV)
        rows = df_cells['row'].values
        cols = df_cells['col'].values
        expected_base_z = df_cells['base_z_m'].values
        
        zb_at_cells = zb_arr[rows, cols]
        max_diff = np.max(np.abs(zb_at_cells - expected_base_z))
        assert max_diff < 1e-6, f"Coordinate flip mismatch on zb: max diff = {max_diff}"

    def test_gis_mask_generation(self):
        """Verifies Common Evaluation Mask cell count and permanent water exclusion."""
        sar, water, hand = diff.load_and_align_gis_layers(
            diff.DEFAULT_SAR, diff.DEFAULT_WATER, diff.DEFAULT_HAND, target_shape=(2100, 2100)
        )
        assert sar.shape == (2100, 2100)
        assert water.shape == (2100, 2100)
        assert hand.shape == (2100, 2100)
        
        valid_obs = np.isin(sar, [0, 1])
        not_perm_water = (water <= 0.5)
        valid_hand = (hand >= 0.0)
        eval_mask = valid_obs & not_perm_water & valid_hand
        
        # Preregistration frozen count: 2,848,260 cells
        total_eval_cells = int(np.sum(eval_mask))
        assert total_eval_cells == 2848260, f"Common Evaluation Mask count drift: {total_eval_cells} != 2848260"

    def test_differential_analysis_baseline_self(self, tmp_path):
        """
        Executes complete differential analysis of BASE vs BASE in a temp directory.
        Mathematical invariants:
          - Delta h = 0.0 everywhere.
          - Delta CSI = 0.0, Delta Recall = 0.0, Delta Precision = 0.0, Delta F1 = 0.0.
          - Net volume change = 0.0 m3.
          - Output JSON and PNG map exist and are non-empty.
        """
        out_dir = tmp_path / "diff_test_out"
        report, out_json, out_png = diff.run_differential_analysis(
            nc_base=sup.NC_BASE,
            nc_cond=sup.NC_BASE,
            frame_idx=33,
            out_dir=out_dir
        )
        
        assert Path(out_json).is_file()
        assert Path(out_png).is_file()
        assert Path(out_png).stat().st_size > 100000  # Multi-megabyte 300 DPI image
        
        # Levee 66 cells stats
        levee = report["levee_66_cells_statistics"]
        assert levee["applied_cells_count"] == 66
        assert levee["cumulative_dem_cut_sum_m"] > 35.0
        assert levee["delta_h_mean_m"] == 0.0
        assert levee["delta_volume_levee_cells_m3"] == 0.0
        
        # Flow transfer stats
        flow = report["flow_transfer_statistics"]
        assert flow["tuyhoa_floodplain_hand_le_3p5m"]["net_volume_change_m3"] == 0.0
        assert flow["tuyhoa_corridor_box"]["cells_deepened_gt_1mm"] == 0
        assert flow["evaluation_domain"]["total_cells"] == 2848260
        
        # Contingency deltas
        deltas = report["comparative_contingency_metrics"]["delta_metrics"]
        assert deltas["delta_TP"] == 0
        assert deltas["delta_FP"] == 0
        assert deltas["delta_FN"] == 0
        assert deltas["delta_TN"] == 0
        assert deltas["delta_csi"] == 0.0
        assert deltas["delta_recall"] == 0.0
        assert deltas["delta_precision"] == 0.0
        assert deltas["delta_f1"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
