"""Software tests use synthetic NetCDF fixtures, never recorded as solver results."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import netCDF4
import numpy as np
import pytest
import rasterio

from analyze_cases import check_case
from build_cases import prepare, sha256
from run_benchmarks import runtime_python, verify_prepared


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp("synthetic_benchmark_tests") / "inputs"
    manifest = prepare(root)
    return root, manifest


def test_production_geometry_constraints(prepared):
    root, _ = prepared
    checks = json.loads((root / "geometry_checks.json").read_text(encoding="utf-8"))
    assert all(value["status"] == "PASS" for value in checks.values())
    assert checks["sill"]["protected_cells"] > 0


def test_independent_reference_and_equal_shared_inputs(prepared):
    root, manifest = prepared
    assert len(manifest["cases"]) == 20
    reference = np.load(root / "channel_REF/bed.npy")
    v49 = np.load(root / "channel_V49/bed.npy")
    assert not np.allclose(reference, v49)
    configs = [(root / f"channel_{arm}/BG_param.txt").read_text() for arm in ("REF", "RAW", "SIMPLE", "V49")]
    assert len(set(configs)) == 1
    flows = [sha256(root / f"channel_{arm}/river.txt") for arm in ("REF", "RAW", "SIMPLE", "V49")]
    assert len(set(flows)) == 1
    assert manifest["method"]["sha256"]


def test_preserves_known_sill_and_no_raise(prepared):
    root, _ = prepared
    raw = np.load(root / "sill_RAW/bed.npy")
    simple = np.load(root / "sill_SIMPLE/bed.npy")
    v49 = np.load(root / "sill_V49/bed.npy")
    mask = np.load(root / "sill_V49/protected.npy")
    assert np.array_equal(v49[mask], raw[mask])
    assert np.any(simple[mask] < raw[mask])
    assert np.all(v49 <= raw + 1e-6)


def test_ascii_roundtrip_asymmetric_grid(prepared):
    root, _ = prepared
    expected = np.load(root / "grid/bed.npy")
    with rasterio.open(root / "grid/bed.asc") as ds:
        np.testing.assert_allclose(ds.read(1), expected, rtol=0, atol=1e-6)
        assert ds.shape == (32, 48)
        assert ds.xy(0, 0) == (270015., 1477985.)
        assert str(ds.crs) == "EPSG:32649"


def test_verification_rejects_changed_inputs(prepared, tmp_path):
    root, _ = prepared
    copy = tmp_path / "changed"
    shutil.copytree(root, copy)
    with (copy / "grid/bed.asc").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="input changed"):
        verify_prepared(copy)


def test_prepare_does_not_overwrite(prepared):
    root, _ = prepared
    with pytest.raises(FileExistsError):
        prepare(root)


def test_runtime_layout_rejects_wrong_folder(tmp_path):
    with pytest.raises(FileNotFoundError):
        runtime_python(tmp_path)


def write_fixture(folder: Path, case: dict, defect: str = "") -> None:
    """Artificial output to test the validator only; no numerical solver is called."""
    bed = np.load(folder / "bed.npy")
    ny, nx = bed.shape
    y = case["ytop"] - (np.arange(ny) + .5) * 30
    x = case["x0"] + (np.arange(nx) + .5) * 30
    if defect == "shift":
        x += 15
    times = [0., case["endtime_s"] if defect != "partial" else case["endtime_s"] / 2]
    if defect == "reverse":
        y, bed = y[::-1], bed[::-1]
    with netCDF4.Dataset(folder / "result.nc", "w") as ds:
        for dim, length in (("time", 2), ("y", ny), ("x", nx)):
            ds.createDimension(dim, length)
            ds.createVariable(dim, "f8", (dim,))[:] = dict(time=times, y=y, x=x)[dim]
        ds.setncattr("fixture_only", "NOT A SOLVER RUN")
        depths = np.stack([np.zeros_like(bed), np.full_like(bed, .01)])
        if defect == "unit":
            depths /= 3_600_000
        for name in ("h", "zs", "zb", "u", "v"):
            var = ds.createVariable(name, "f8", ("time", "y", "x"))
            data = dict(h=depths, zs=depths + bed, zb=np.stack([bed, bed]),
                        u=np.zeros_like(depths), v=np.zeros_like(depths))[name]
            if defect == "bed" and name == "zb":
                data = data + .1
            if defect == "nan" and name == "h":
                data[1, 0, 0] = np.nan
            var[:] = data


@pytest.mark.parametrize("defect,expected", [("", "PASS"), ("reverse", "PASS"),
                          ("shift", "FAIL"), ("partial", "FAIL"),
                          ("unit", "FAIL"), ("bed", "FAIL"), ("nan", "FAIL")])
def test_validator_accepts_valid_and_rejects_bad_outputs(prepared, tmp_path, defect, expected):
    root, manifest = prepared
    folder = tmp_path / "fixture"
    shutil.copytree(root / "rain_mm", folder)
    case = manifest["cases"]["rain_mm"]
    write_fixture(folder, case, defect)
    report, _ = check_case(folder, case, manifest["tolerances"], require_run=False)
    assert report["status"] == expected, report


def test_requires_actual_completed_worker(prepared, tmp_path):
    root, manifest = prepared
    folder = tmp_path / "fixture"
    shutil.copytree(root / "rain_mm", folder)
    case = manifest["cases"]["rain_mm"]
    write_fixture(folder, case)
    report, _ = check_case(folder, case, manifest["tolerances"])
    assert report["status"] == "FAIL"
    assert "run.json" in report["error"]


def test_equal_volume_control_and_isolated_protection(prepared):
    root, manifest = prepared
    raw = np.load(root / "channel_RAW/bed.npy").astype(float)
    v49 = np.load(root / "channel_V49/bed.npy").astype(float)
    eq = np.load(root / "channel_RECT_EQVOL/bed.npy").astype(float)
    mask = raw - v49 > 1e-6
    np.testing.assert_array_equal(mask, raw - eq > 1e-6)
    assert mask.sum() == 992
    assert abs((raw - eq).sum() - (raw - v49).sum()) / (raw - v49).sum() <= 1e-6
    assert manifest["cases"]["channel_RECT_EQVOL"]["control"]["uniform_depth_m"] == pytest.approx(1.009515, abs=1e-6)
    protected = np.load(root / "sill_V49/protected.npy")
    sill_raw = np.load(root / "sill_RAW/bed.npy")
    simple = np.load(root / "sill_SIMPLE/bed.npy")
    rectp = np.load(root / "sill_RECT_PROTECTED/bed.npy")
    np.testing.assert_array_equal(rectp[protected], sill_raw[protected])
    np.testing.assert_array_equal(rectp[~protected], simple[~protected])
    unprotected = np.load(root / "sill_V49_UNPROTECTED/bed.npy")
    v49p = np.load(root / "sill_V49/bed.npy")
    np.testing.assert_array_equal(unprotected[~protected], v49p[~protected])
    assert np.any(unprotected[protected] < v49p[protected])


def test_closed_initial_fields_are_small_wet_and_asymmetric(prepared):
    root, manifest = prepared
    for name, shape in (("closed_one", (16, 16)), ("closed_multi", (32, 32))):
        initial = np.load(root / name / "initial_h.npy")
        assert initial.shape == shape and initial.dtype == np.float64
        assert initial.min() >= 2 and initial.max() <= 2.05
        assert not np.allclose(initial, initial[::-1])
        assert manifest["cases"][name]["endtime_s"] == 300
        assert "cf = 0;" in (root / name / "BG_param.txt").read_text()


@pytest.mark.parametrize("defect", ("", "mass", "wall", "internal", "nan", "no_motion", "clamp", "missing"))
def test_closed_validator_rejects_physical_failures(prepared, tmp_path, defect):
    root, manifest = prepared
    folder = tmp_path / "closed_fixture"
    shutil.copytree(root / "closed_one", folder)
    case = manifest["cases"]["closed_one"]
    write_fixture(folder, case)
    initial = np.load(folder / "initial_h.npy")
    with netCDF4.Dataset(folder / "result.nc", "r+") as ds:
        ds["h"][:] = np.stack([initial, initial])
        ds["zs"][:] = np.stack([initial, initial])
    vol = float(initial.sum() * 900)
    budget = {"schema": "r3-boundary-budget-1", "all_values_finite": True,
              "initial_volume_m3": vol, "current_volume_m3": vol, "max_relative_volume_drift": 0.,
              "max_abs_wall_flux_m3_s": 0., "max_abs_internal_flux_mismatch_m3_s": 0.,
              "clamp_added_m3": 0., "clamp_removed_m3": 0., "boundary_depth_change_max_m": .01,
              "simulated_time_s": 300., "step_count": 10}
    key = {"mass": "max_relative_volume_drift", "wall": "max_abs_wall_flux_m3_s",
           "internal": "max_abs_internal_flux_mismatch_m3_s", "nan": "current_volume_m3",
           "no_motion": "boundary_depth_change_max_m", "clamp": "clamp_added_m3"}.get(defect)
    if key:
        budget[key] = float("nan") if defect == "nan" else 0. if defect == "no_motion" else .1
    if defect != "missing":
        (folder / "boundary_budget.json").write_text(json.dumps(budget), encoding="utf-8")
    report, _ = check_case(folder, case, manifest["tolerances"], require_run=False)
    assert report["status"] == ("PASS" if not defect else "FAIL"), report


@pytest.mark.parametrize("version,expected", (("r2", "FAIL"), ("r3", "PASS")))
def test_real_runtime_operator_regression(tmp_path, version, expected):
    repo = Path(__file__).resolve().parents[2]
    runtime = repo / "V48_runs" / f"20261118_runtime_fix_{version}"
    output = tmp_path / f"operator_{version}.json"
    done = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).with_name("operator_checks.py")),
                           "--runtime", str(runtime), "--out", str(output), "--device", "cpu"],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == (0 if expected == "PASS" else 2), done.stdout + done.stderr
    report = json.loads(output.read_text())
    assert len(report["cases"]) == 12 and report["status"] == expected
    if version == "r2":
        assert any(r["wall_max_abs_m3_s"] > 2. for r in report["cases"])
