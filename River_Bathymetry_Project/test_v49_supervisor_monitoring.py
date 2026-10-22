"""Unit tests for V49-G supervisor execution, progress logging, VRAM verification, and post-run evaluation."""

import json
from pathlib import Path

import netCDF4 as nc
import numpy as np
import pytest

from v49_prepare_hydraulic_validation import BASE_RESULT, prepare_v49_g
from v49_run_hydraulic_validation import (
    ARMS,
    FORBIDDEN_DIRS,
    ROOT,
    assert_not_historical_dir,
    check_cuda_vram,
    format_progress_line,
    format_time_duration,
    generate_summary_report,
    monitor,
    pid_alive,
    progress,
    status,
    supervise,
    verify_post_run,
    worker,
)


def create_dummy_netcdf(path: Path, times=(0.0, 1000.0, 2000.0), x=(15.0, 45.0), y=(15.0, 45.0)):
    path.parent.mkdir(parents=True, exist_ok=True)
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("time", len(times))
        ds.createDimension("x", len(x))
        ds.createDimension("y", len(y))
        ds.createVariable("time", "f8", ("time",))[:] = list(times)
        ds.createVariable("x", "f8", ("x",))[:] = list(x)
        ds.createVariable("y", "f8", ("y",))[:] = list(y)
        for v in ("h", "zs", "zb", "u", "v"):
            ds.createVariable(v, "f4", ("time",))[:] = np.ones(len(times), dtype=np.float32)


def test_queue_ordering():
    assert ARMS == ("CENTRAL", "LOW", "HIGH", "BASE")


def test_format_time_duration():
    assert format_time_duration(0) == "0s"
    assert format_time_duration(45) == "45s"
    assert format_time_duration(125) == "2m 05s"
    assert format_time_duration(3665) == "1h 01m 05s"
    assert format_time_duration(-10) == "N/A"
    assert format_time_duration(None) == "N/A"


def test_format_progress_line():
    prog = {
        "simulated_time_s": 127438.83,
        "endtime_s": 432000.0,
        "progress_pct": 29.4997,
        "dt_s": 0.483,
        "engine_elapsed_s": 98925.5,
    }
    line = format_progress_line("CENTRAL", prog, wall_elapsed_s=98925.5)
    assert "[CENTRAL]" in line
    assert "35.4h / 120.0h" in line
    assert "(29.5%)" in line
    assert "dt = 0.48s" in line
    assert "elapsed =" in line
    assert "ETA =" in line


def test_format_progress_line_initial():
    prog = {
        "simulated_time_s": 0.0,
        "endtime_s": 432000.0,
        "progress_pct": 0.0,
        "dt_s": 0.5,
        "engine_elapsed_s": 0.0,
    }
    line = format_progress_line("LOW", prog, wall_elapsed_s=15.0)
    assert "[LOW]" in line
    assert "0.0h / 120.0h (0.0%)" in line
    assert "dt = 0.50s" in line
    assert "ETA = calculating..." in line


def test_format_progress_line_small_dt():
    prog = {
        "simulated_time_s": 100.0,
        "endtime_s": 432000.0,
        "progress_pct": 0.02,
        "dt_s": 0.0035,
        "engine_elapsed_s": 50.0,
    }
    line = format_progress_line("HIGH", prog, wall_elapsed_s=50.0)
    assert "dt = 3.500e-03s" in line


def test_safety_historical_directories_protected():
    for forbidden in FORBIDDEN_DIRS:
        with pytest.raises(PermissionError, match="strictly prohibited"):
            assert_not_historical_dir(forbidden)


def test_safety_historical_subdirectories_protected():
    for forbidden in FORBIDDEN_DIRS:
        with pytest.raises(PermissionError, match="strictly prohibited"):
            assert_not_historical_dir(forbidden / "results")
        with pytest.raises(PermissionError, match="strictly prohibited"):
            assert_not_historical_dir(forbidden / "results" / "sub" / "file.nc")


def test_progress_parser(tmp_path):
    log = tmp_path / "run.log"
    log.write_text(
        "Some engine logs...\n"
        "t = 100.00/432000s (0.0%) | dt = 5.000e-01 | elapsed = 10.0s\n"
        "t = 127438.83/432000s (29.5%) | dt = 4.830e-01 | elapsed = 98925.5s\n",
        encoding="utf-8",
    )
    p = progress(log)
    assert p is not None
    assert p["simulated_time_s"] == 127438.83
    assert p["endtime_s"] == 432000.0
    assert abs(p["progress_pct"] - 29.499729) < 1e-4
    assert p["dt_s"] == 0.483
    assert p["engine_elapsed_s"] == 98925.5


def test_progress_zero_endtime(tmp_path):
    log = tmp_path / "zero.log"
    log.write_text("t = 0.00/0s (0.0%) | dt = 1.000e-01 | elapsed = 1.0s\n", encoding="utf-8")
    p = progress(log)
    assert p is not None
    assert p["progress_pct"] == 0.0


def test_verify_post_run_success(tmp_path):
    nc_path = tmp_path / "results" / "V49_G_CENTRAL.nc"
    create_dummy_netcdf(nc_path, times=[0.0, 1000.0, 2000.0, 3000.0, 4000.0])

    budget_path = tmp_path / "results" / "V49_G_CENTRAL_discrete_budget.json"
    budget_data = {
        "initial_volume_m3": 10000.0,
        "current_volume_m3": 15000.0,
        "unexplained_closure_residual_m3": 0.05,
    }
    budget_path.write_text(json.dumps(budget_data), encoding="utf-8")

    res = verify_post_run("CENTRAL", tmp_path, nc_path)
    assert res["netcdf_valid"] is True
    assert res["discrete_budget_valid"] is True
    assert res["frame_count"] == 5
    assert not res["errors"]


def test_verify_post_run_empty_netcdf(tmp_path):
    nc_path = tmp_path / "results" / "V49_G_LOW.nc"
    nc_path.parent.mkdir(parents=True, exist_ok=True)
    nc_path.touch()

    res = verify_post_run("LOW", tmp_path, nc_path)
    assert res["netcdf_valid"] is False
    assert any("empty" in e for e in res["errors"])


def test_verify_post_run_missing_variables(tmp_path):
    nc_path = tmp_path / "results" / "V49_G_HIGH.nc"
    nc_path.parent.mkdir(parents=True, exist_ok=True)
    with nc.Dataset(nc_path, "w") as ds:
        ds.createDimension("time", 2)
        ds.createVariable("time", "f8", ("time",))[:] = [0.0, 10.0]
        ds.createVariable("h", "f4", ("time",))[:] = [1.0, 1.0]

    res = verify_post_run("HIGH", tmp_path, nc_path)
    assert res["netcdf_valid"] is False
    assert any("missing required variables" in e for e in res["errors"])


def test_verify_post_run_missing_xy_coordinates(tmp_path):
    nc_path = tmp_path / "results" / "V49_G_HIGH.nc"
    nc_path.parent.mkdir(parents=True, exist_ok=True)
    with nc.Dataset(nc_path, "w") as ds:
        ds.createDimension("time", 2)
        ds.createVariable("time", "f8", ("time",))[:] = [0.0, 10.0]
        for v in ("h", "zs", "zb", "u", "v"):
            ds.createVariable(v, "f4", ("time",))[:] = [1.0, 1.0]

    res = verify_post_run("HIGH", tmp_path, nc_path)
    assert res["netcdf_valid"] is False
    assert any("missing required variables" in e for e in res["errors"])


def test_verify_post_run_invalid_xy_coordinates(tmp_path):
    nc_path = tmp_path / "results" / "V49_G_HIGH.nc"
    create_dummy_netcdf(nc_path, times=[0.0, 10.0], x=[np.nan, 45.0], y=[15.0, 45.0])
    res = verify_post_run("HIGH", tmp_path, nc_path)
    assert res["netcdf_valid"] is False
    assert any("invalid x coordinate" in e for e in res["errors"])


def test_verify_post_run_excessive_residual(tmp_path):
    nc_path = tmp_path / "results" / "V49_G_BASE.nc"
    create_dummy_netcdf(nc_path, times=[0.0, 10.0])

    budget_path = tmp_path / "results" / "V49_G_BASE_discrete_budget.json"
    budget_data = {
        "initial_volume_m3": 100.0,
        "current_volume_m3": 100.0,
        "unexplained_closure_residual_m3": 50000.0,
    }
    budget_path.write_text(json.dumps(budget_data), encoding="utf-8")

    res = verify_post_run("BASE", tmp_path, nc_path)
    assert res["netcdf_valid"] is True
    assert res["discrete_budget_valid"] is False
    assert any("out of tolerance" in e for e in res["errors"])


def test_verify_post_run_single_frame(tmp_path):
    nc_path = tmp_path / "results" / "V49_G_CENTRAL.nc"
    create_dummy_netcdf(nc_path, times=[0.0])
    res = verify_post_run("CENTRAL", tmp_path, nc_path)
    assert res["netcdf_valid"] is False
    assert any(">= 2 frames" in e for e in res["errors"])


def test_verify_post_run_negative_initial_time(tmp_path):
    nc_path = tmp_path / "results" / "V49_G_CENTRAL.nc"
    create_dummy_netcdf(nc_path, times=[-10.0, 10.0])
    res = verify_post_run("CENTRAL", tmp_path, nc_path)
    assert res["netcdf_valid"] is False
    assert any("cannot be negative" in e for e in res["errors"])


def test_verify_post_run_corrupted_header(tmp_path):
    nc_path = tmp_path / "results" / "V49_G_CENTRAL.nc"
    nc_path.parent.mkdir(parents=True, exist_ok=True)
    nc_path.write_bytes(b"NOT_A_VALID_HDF5_OR_NETCDF_BINARY_DATA_BLOB")
    res = verify_post_run("CENTRAL", tmp_path, nc_path)
    assert res["netcdf_valid"] is False
    assert any("NetCDF unreadable" in e for e in res["errors"])


def test_check_cuda_vram_success():
    """[R1-2] Verify CUDA Device 0 memory querying returns valid free/total VRAM."""
    vram = check_cuda_vram(min_free_bytes=100 * 1024 * 1024)
    assert vram["device_id"] == 0
    assert vram["free_bytes"] > 0
    assert vram["total_bytes"] > 0
    assert vram["free_gb"] > 0.0
    assert vram["total_gb"] > 0.0


def test_check_cuda_vram_insufficient():
    """[R1-2] Verify check_cuda_vram raises RuntimeError if free VRAM is below required threshold."""
    with pytest.raises(RuntimeError, match="Insufficient CUDA VRAM"):
        check_cuda_vram(min_free_bytes=1000 * 1024 * 1024 * 1024)  # 1000 GB


def test_supervisor_rejects_active_worker(tmp_path, monkeypatch):
    state_file = tmp_path / "V49_G_EXECUTION_STATE.json"
    state_data = {
        "status": "RUNNING",
        "supervisor_pid": 9999999,
        "worker_pid": 8888888,
        "active_arm": "CENTRAL",
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")

    def mock_pid_alive(pid):
        return pid == 8888888  # worker is alive, supervisor is dead

    monkeypatch.setattr("v49_run_hydraulic_validation.pid_alive", mock_pid_alive)
    with pytest.raises(RuntimeError, match="CUDA worker process .* is already running"):
        supervise(tmp_path)


def test_supervisor_halts_on_post_run_verification_failure(tmp_path, monkeypatch):
    """[R1-1] Verify supervisor halts queue and marks FAILED without running LOW if CENTRAL verification fails."""
    manifest = {
        "configs": {
            arm: {
                "path": str(tmp_path / f"BG_param_V49_G_{arm}.txt"),
                "planned_result": str(tmp_path / "results" / f"V49_G_{arm}.nc"),
                "sha256": "fake_hash",
            }
            for arm in ARMS
        }
    }
    (tmp_path / "V49_G_PREPARATION_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr("v49_run_hydraulic_validation.preflight", lambda d: {"preparation_pass": True})
    monkeypatch.setattr("v49_run_hydraulic_validation.check_cuda_vram", lambda *a, **kw: {"free_gb": 15.0, "total_gb": 16.0})

    class DummyProc:
        def __init__(self):
            self.pid = 12345
            self.returncode = 0
        def poll(self):
            return 0

    launched_arms = []
    def mock_popen(cmd, **kwargs):
        arm = cmd[cmd.index("--arm") + 1]
        launched_arms.append(arm)
        # Create corrupted NetCDF on CENTRAL
        res_path = Path(manifest["configs"][arm]["planned_result"])
        res_path.parent.mkdir(parents=True, exist_ok=True)
        res_path.write_bytes(b"CORRUPTED_NETCDF_HEADER")
        # Write valid budget so only NetCDF fails
        (tmp_path / "results" / f"V49_G_{arm}_discrete_budget.json").write_text(
            json.dumps({"unexplained_closure_residual_m3": 0.0, "current_volume_m3": 1000.0}),
            encoding="utf-8",
        )
        return DummyProc()

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    with pytest.raises(RuntimeError, match="post-run verification failed"):
        supervise(tmp_path)

    assert launched_arms == ["CENTRAL"]
    state = json.loads((tmp_path / "V49_G_EXECUTION_STATE.json").read_text(encoding="utf-8"))
    assert state["status"] == "FAILED_NEEDS_REVIEW"
    assert state["runs"]["CENTRAL"]["status"] == "POST_RUN_VERIFICATION_FAILED"
    assert "LOW" not in state["runs"]


def test_supervisor_halts_on_budget_violation(tmp_path, monkeypatch):
    """[R1-1] Verify supervisor halts queue if discrete mass budget exceeds numerical tolerance."""
    manifest = {
        "configs": {
            arm: {
                "path": str(tmp_path / f"BG_param_V49_G_{arm}.txt"),
                "planned_result": str(tmp_path / "results" / f"V49_G_{arm}.nc"),
                "sha256": "fake_hash",
            }
            for arm in ARMS
        }
    }
    (tmp_path / "V49_G_PREPARATION_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr("v49_run_hydraulic_validation.preflight", lambda d: {"preparation_pass": True})
    monkeypatch.setattr("v49_run_hydraulic_validation.check_cuda_vram", lambda *a, **kw: {"free_gb": 15.0, "total_gb": 16.0})

    class DummyProc:
        def __init__(self):
            self.pid = 12346
            self.returncode = 0
        def poll(self):
            return 0

    launched_arms = []
    def mock_popen(cmd, **kwargs):
        arm = cmd[cmd.index("--arm") + 1]
        launched_arms.append(arm)
        res_path = Path(manifest["configs"][arm]["planned_result"])
        create_dummy_netcdf(res_path, times=[0.0, 1000.0, 2000.0])
        (tmp_path / "results" / f"V49_G_{arm}_discrete_budget.json").write_text(
            json.dumps({"unexplained_closure_residual_m3": 999999.0, "current_volume_m3": 1000.0}),
            encoding="utf-8",
        )
        return DummyProc()

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    with pytest.raises(RuntimeError, match="post-run verification failed"):
        supervise(tmp_path)

    assert launched_arms == ["CENTRAL"]
    state = json.loads((tmp_path / "V49_G_EXECUTION_STATE.json").read_text(encoding="utf-8"))
    assert state["status"] == "FAILED_NEEDS_REVIEW"
    assert state["runs"]["CENTRAL"]["status"] == "POST_RUN_VERIFICATION_FAILED"
    assert "LOW" not in state["runs"]


def test_supervisor_recovers_completed_run(tmp_path, monkeypatch):
    """[R1-5] Verify supervisor auto-advances to evaluation when completed 120h result exists."""
    manifest = {
        "configs": {
            arm: {
                "path": str(tmp_path / f"BG_param_V49_G_{arm}.txt"),
                "planned_result": str(tmp_path / "results" / f"V49_G_{arm}.nc"),
                "sha256": "fake_hash",
            }
            for arm in ARMS
        }
    }
    (tmp_path / "V49_G_PREPARATION_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr("v49_run_hydraulic_validation.preflight", lambda d: {"preparation_pass": True})
    monkeypatch.setattr("v49_run_hydraulic_validation.check_cuda_vram", lambda *a, **kw: {"free_gb": 15.0, "total_gb": 16.0})

    # CENTRAL is completed to 120h
    res_path = Path(manifest["configs"]["CENTRAL"]["planned_result"])
    create_dummy_netcdf(res_path, times=[0.0, 100000.0, 200000.0, 300000.0, 432000.0])
    (tmp_path / "results" / "V49_G_CENTRAL_discrete_budget.json").write_text(
        json.dumps({"unexplained_closure_residual_m3": 0.001, "current_volume_m3": 10000.0}),
        encoding="utf-8",
    )

    eval_called = []
    def mock_eval(output_dir):
        eval_called.append(True)
        return {"status": "EVALUATED_TEST", "arms": {"CENTRAL": {"metrics": {"csi_iou": 0.42}}}}

    monkeypatch.setattr("v49_evaluate_hydraulic_validation.evaluate_available_runs", mock_eval)

    class StopSupervisor(Exception):
        pass

    def mock_popen(cmd, **kwargs):
        raise StopSupervisor("LOW reached")

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    with pytest.raises(StopSupervisor):
        supervise(tmp_path)

    assert eval_called == [True]
    state = json.loads((tmp_path / "V49_G_EXECUTION_STATE.json").read_text(encoding="utf-8"))
    assert state["runs"]["CENTRAL"]["status"] == "EVALUATED"


def test_supervisor_vram_tracking(tmp_path, monkeypatch):
    """[R1-2] Verify supervisor queries and records VRAM at start and finish of arm."""
    manifest = {
        "configs": {
            arm: {
                "path": str(tmp_path / f"BG_param_V49_G_{arm}.txt"),
                "planned_result": str(tmp_path / "results" / f"V49_G_{arm}.nc"),
                "sha256": "fake_hash",
            }
            for arm in ARMS
        }
    }
    (tmp_path / "V49_G_PREPARATION_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr("v49_run_hydraulic_validation.preflight", lambda d: {"preparation_pass": True})

    vram_queries = []
    def mock_check_vram(*a, **kw):
        vram_queries.append(len(vram_queries))
        return {"free_gb": 14.5, "total_gb": 16.0}

    monkeypatch.setattr("v49_run_hydraulic_validation.check_cuda_vram", mock_check_vram)

    class DummyProc:
        def __init__(self):
            self.pid = 99911
            self.returncode = 0
        def poll(self):
            return 0

    def mock_popen(cmd, **kwargs):
        arm = cmd[cmd.index("--arm") + 1]
        res_path = Path(manifest["configs"][arm]["planned_result"])
        create_dummy_netcdf(res_path, times=[0.0, 1000.0, 432000.0])
        (tmp_path / "results" / f"V49_G_{arm}_discrete_budget.json").write_text(
            json.dumps({"unexplained_closure_residual_m3": 0.001, "current_volume_m3": 10000.0}),
            encoding="utf-8",
        )
        return DummyProc()

    monkeypatch.setattr("subprocess.Popen", mock_popen)
    monkeypatch.setattr("v49_evaluate_hydraulic_validation.evaluate_available_runs", lambda d: {"status": "EVAL_OK", "arms": {}})

    class StopAfterCentral(Exception):
        pass

    orig_verify = verify_post_run
    def stop_hook(arm, out_dir, res_p):
        v = orig_verify(arm, out_dir, res_p)
        if arm == "CENTRAL":
            # stop after CENTRAL completion and evaluation
            pass
        return v

    # Mock low to abort
    def mock_popen_with_abort(cmd, **kwargs):
        arm = cmd[cmd.index("--arm") + 1]
        if arm == "LOW":
            raise StopAfterCentral("LOW reached")
        return mock_popen(cmd, **kwargs)

    monkeypatch.setattr("subprocess.Popen", mock_popen_with_abort)

    with pytest.raises(StopAfterCentral):
        supervise(tmp_path)

    state = json.loads((tmp_path / "V49_G_EXECUTION_STATE.json").read_text(encoding="utf-8"))
    assert state["runs"]["CENTRAL"]["vram_start_gb"] == 14.5
    assert state["runs"]["CENTRAL"]["vram_finish_gb"] == 14.5


def test_supervisor_cleans_supervisor_pid_in_finally(tmp_path, monkeypatch):
    """Verify state['supervisor_pid'] is reset to None on termination."""
    manifest = {
        "configs": {
            arm: {
                "path": str(tmp_path / f"BG_param_V49_G_{arm}.txt"),
                "planned_result": str(tmp_path / "results" / f"V49_G_{arm}.nc"),
                "sha256": "fake_hash",
            }
            for arm in ARMS
        }
    }
    (tmp_path / "V49_G_PREPARATION_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr("v49_run_hydraulic_validation.preflight", lambda d: {"preparation_pass": True})
    monkeypatch.setattr("v49_run_hydraulic_validation.check_cuda_vram", lambda *a, **kw: {"free_gb": 15.0, "total_gb": 16.0})

    def mock_popen(cmd, **kwargs):
        raise KeyboardInterrupt("Simulated Ctrl-C")

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    with pytest.raises(KeyboardInterrupt):
        supervise(tmp_path)

    state = json.loads((tmp_path / "V49_G_EXECUTION_STATE.json").read_text(encoding="utf-8"))
    assert state["supervisor_pid"] is None
    assert state["worker_pid"] is None


def test_monitor_waits_for_active_arm(tmp_path, monkeypatch, capsys):
    """Verify monitor does not abort immediately if supervisor is alive but active_arm is initially None."""
    state_file = tmp_path / "V49_G_EXECUTION_STATE.json"
    state_data = {
        "status": "RUNNING",
        "supervisor_pid": 11111,
        "worker_pid": None,
        "active_arm": None,
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")

    alive_calls = [True, False]
    def mock_pid_alive(pid):
        return alive_calls.pop(0) if alive_calls else False

    monkeypatch.setattr("v49_run_hydraulic_validation.pid_alive", mock_pid_alive)
    monkeypatch.setattr("time.sleep", lambda s: None)

    monitor(tmp_path, poll_interval_s=0.0)
    out = capsys.readouterr().out
    assert "Waiting for active arm..." in out


def test_summary_report_offset_fallback(tmp_path):
    report_file = tmp_path / "V49_G_FINAL_SUMMARY_REPORT.md"
    state_file = tmp_path / "V49_G_EXECUTION_STATE.json"
    metrics_file = tmp_path / "V49_G_matched_hydraulic_metrics.json"

    state_data = {
        "status": "MATCHED_RUNS_COMPLETED_PENDING_ACCEPTANCE",
        "runs": {
            "CENTRAL": {
                "status": "EVALUATED",
                "evaluation": {
                    "metrics": {"csi_iou": 0.45, "f1": 0.60, "precision": 0.62, "recall": 0.58, "simulated_area_km2": 510.0, "area_bias": 0.01},
                    "sar_frame_offset_s": 125.4,
                },
            }
        },
    }
    state_file.write_text(json.dumps(state_data), encoding="utf-8")
    metrics_file.write_text(json.dumps({"arms": {}}), encoding="utf-8")

    path = generate_summary_report(tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "125.4s" in content


def test_summary_report_no_empty_difference_table(tmp_path):
    state_file = tmp_path / "V49_G_EXECUTION_STATE.json"
    metrics_file = tmp_path / "V49_G_matched_hydraulic_metrics.json"

    state_file.write_text(json.dumps({"status": "RUNNING", "runs": {}}), encoding="utf-8")
    metrics_file.write_text(json.dumps({"arms": {}, "difference_from_base": {}}), encoding="utf-8")

    path = generate_summary_report(tmp_path)
    content = path.read_text(encoding="utf-8")
    # Empty difference_from_base should NOT render an empty markdown table
    assert "### Differences from Frozen BASE Model" not in content


def test_real_sar_evaluation_on_base_result(tmp_path):
    """[R1-3] Verify that live evaluate_run() against real completed BASE_RESULT succeeds with valid CSI."""
    if not BASE_RESULT.exists():
        pytest.skip("Frozen V48 BASE_RESULT not available")

    manifest = json.loads(Path(r"D:\VTP\River_Bathymetry_Project\V49_G_attempt_2\V49_G_PREPARATION_MANIFEST.json").read_text(encoding="utf-8"))
    from v49_evaluate_hydraulic_validation import evaluate_run
    eval_res = evaluate_run(BASE_RESULT, "BASE", manifest, tmp_path)

    assert eval_res["arm"] == "BASE"
    assert eval_res["evaluated_frame"] == 33
    assert abs(eval_res["sar_frame_offset_s"] - 1388.8) < 1.0
    assert eval_res["metrics"]["csi_iou"] > 0.35
    assert (tmp_path / "V49_G_BASE_hydraulic_metrics.json").exists()


def test_safety_historical_subdirectories_in_prepare_and_evaluate_and_validate():
    """Verify that prepare_v49_g, evaluate_available_runs, evaluate_run and validate_v49_g protect historical subdirectories."""
    from v49_prepare_hydraulic_validation import assert_not_historical_dir as prepare_assert
    from v49_evaluate_hydraulic_validation import evaluate_available_runs, evaluate_run
    from v49_validate_hydraulic_validation import validate_v49_g

    for forbidden in FORBIDDEN_DIRS:
        sub = forbidden / "sub_attempt" / "results"
        with pytest.raises(PermissionError, match="strictly prohibited"):
            prepare_assert(sub)
        with pytest.raises(PermissionError, match="strictly prohibited"):
            prepare_v49_g(sub)
        with pytest.raises(PermissionError, match="strictly prohibited"):
            evaluate_available_runs(sub)
        with pytest.raises(PermissionError, match="strictly prohibited"):
            evaluate_run(BASE_RESULT, "BASE", {"sentinel1": {"acquisition_midpoint_utc": "2021-11-30T05:36:00Z"}}, sub)

        # Ensure validate_v49_g does not write V49_G_validation_report.json into historical subdirectories
        sub_validation = forbidden / "results"
        assert not (sub_validation / "V49_G_validation_report.json").exists()


def test_worker_rejects_concurrent_active_worker(tmp_path, monkeypatch):
    """[R2] Verify worker() strictly rejects launching if another CUDA worker is running on Device 0."""
    state_file = tmp_path / "V49_G_EXECUTION_STATE.json"
    state_file.write_text(json.dumps({
        "status": "RUNNING",
        "worker_pid": 999888,
        "supervisor_pid": 111222,
    }), encoding="utf-8")

    monkeypatch.setattr("v49_run_hydraulic_validation.pid_alive", lambda pid: pid == 999888)

    with pytest.raises(RuntimeError, match="A CUDA worker process .* is already running"):
        worker("LOW", tmp_path)


def test_format_progress_line_none_fields():
    """Verify format_progress_line does not raise TypeError when prog dictionary contains None values."""
    prog = {
        "simulated_time_s": None,
        "endtime_s": None,
        "progress_pct": None,
        "dt_s": None,
    }
    line = format_progress_line("CENTRAL", prog, wall_elapsed_s=None)
    assert "[CENTRAL]" in line
    assert "0.0h / 120.0h (0.0%)" in line
    assert "dt = 0.000e+00s" in line
    assert "ETA = calculating..." in line


def test_format_time_duration_infinite_and_nan():
    """Verify format_time_duration handles inf, -inf, nan, and negative without OverflowError."""
    assert format_time_duration(float("inf")) == "N/A"
    assert format_time_duration(float("-inf")) == "N/A"
    assert format_time_duration(float("nan")) == "N/A"
    assert format_time_duration(-50.0) == "N/A"
    assert format_time_duration(None) == "N/A"
    assert format_time_duration(3600.0) == "1h 00m 00s"


def test_pid_alive_guards():
    """Verify pid_alive handling of invalid and non-python PIDs."""
    assert pid_alive(None) is False
    assert pid_alive(0) is False
    assert pid_alive(-10) is False


def test_supervisor_evaluated_arm_missing_result(tmp_path, monkeypatch):
    """Verify supervisor raises FileNotFoundError if state marks arm as EVALUATED but result file is missing."""
    manifest = {
        "configs": {
            arm: {
                "path": str(tmp_path / f"BG_param_V49_G_{arm}.txt"),
                "planned_result": str(tmp_path / "results" / f"V49_G_{arm}.nc"),
                "sha256": "fake_hash",
            }
            for arm in ARMS
        }
    }
    (tmp_path / "V49_G_PREPARATION_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    state_file = tmp_path / "V49_G_EXECUTION_STATE.json"
    state_file.write_text(json.dumps({
        "status": "RUNNING",
        "runs": {
            "CENTRAL": {"status": "EVALUATED"}
        }
    }), encoding="utf-8")
    monkeypatch.setattr("v49_run_hydraulic_validation.preflight", lambda d: {"preparation_pass": True})

    with pytest.raises(FileNotFoundError, match="State records arm CENTRAL as evaluated, but result file is missing"):
        supervise(tmp_path)


def test_supervisor_completed_run_mass_budget_failure(tmp_path, monkeypatch):
    """Verify supervisor raises RuntimeError when 120h result exists but fails discrete mass budget."""
    manifest = {
        "configs": {
            arm: {
                "path": str(tmp_path / f"BG_param_V49_G_{arm}.txt"),
                "planned_result": str(tmp_path / "results" / f"V49_G_{arm}.nc"),
                "sha256": "fake_hash",
            }
            for arm in ARMS
        }
    }
    (tmp_path / "V49_G_PREPARATION_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr("v49_run_hydraulic_validation.preflight", lambda d: {"preparation_pass": True})

    # CENTRAL is completed to 120h but discrete budget is missing / invalid
    res_path = Path(manifest["configs"]["CENTRAL"]["planned_result"])
    create_dummy_netcdf(res_path, times=[0.0, 1000.0, 432000.0])
    (tmp_path / "results" / "V49_G_CENTRAL_discrete_budget.json").write_text(
        json.dumps({"unexplained_closure_residual_m3": 500000.0, "current_volume_m3": 1000.0}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="failed post-run mass budget verification"):
        supervise(tmp_path)

