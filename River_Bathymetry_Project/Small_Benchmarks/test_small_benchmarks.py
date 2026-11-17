"""Software tests use synthetic NetCDF fixtures, never recorded as solver results."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

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
    assert len(manifest["cases"]) == 15
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
