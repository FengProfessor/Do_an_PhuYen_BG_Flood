"""Exercise the real frozen solver with and without budget observation."""

import json
import subprocess
import sys
from pathlib import Path

import netCDF4
import numpy as np
import pytest

from v49_evaluate_hydraulic_validation import contingency, nearest_frame


ROOT = Path(__file__).resolve().parent
RUNTIME = Path(r"D:\VTP\V48_runs\20261004_runtime_fix_r1\python")


def test_budget_observer_does_not_change_solver_result(tmp_path):
    dem = tmp_path / "dem.asc"
    with dem.open("w", encoding="utf-8") as stream:
        stream.write("ncols 32\nnrows 32\nxllcorner 270000\nyllcorner 1415000\ncellsize 30\nNODATA_value -9999\n")
        np.savetxt(stream, np.zeros((32, 32)), fmt="%.1f")
    rain = tmp_path / "rain.txt"
    rain.write_text("0 10\n3600 10\n", encoding="utf-8")
    bootstrap = """
import sys
from pathlib import Path
sys.modules['cupy'] = None
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
if sys.argv[4] == 'observed':
    from v49_runtime_observer import install_budget_observer
    install_budget_observer(Path(sys.argv[5]))
import run_bgflood
run_bgflood.run_model(sys.argv[3])
"""
    results = []
    for mode in ("original", "observed"):
        output = tmp_path / f"{mode}.nc"
        config = tmp_path / f"{mode}.txt"
        config.write_text(
            f"bathy={dem.as_posix()};\ndx=30;\ndy=30;\nminmask=-4;\n"
            f"rainfile={rain.as_posix()};\nrainunits=mm/h;\nzsinit=0;\nil=0;\ncl=0;\n"
            f"left=0;\nright=0;\ntop=0;\nbottom=0;\nendtime=3600;\n"
            f"outputtimestep=1200;\noutfile={output.as_posix()};\noutvars=h,zb,zs,u,v;\n", encoding="utf-8")
        with (tmp_path / f"{mode}.log").open("w", encoding="utf-8") as log:
            done = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", bootstrap,
                                   str(RUNTIME), str(ROOT), str(config), mode, str(tmp_path / "budget.json")],
                                  cwd=tmp_path, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        assert done.returncode == 0, (tmp_path / f"{mode}.log").read_text(encoding="utf-8")[-4000:]
        with netCDF4.Dataset(output) as dataset:
            results.append({name: np.asarray(dataset[name][:]) for name in ("h", "zs", "u", "v", "time")})
    for name in results[0]:
        np.testing.assert_array_equal(results[0][name], results[1][name])
    budget = json.loads((tmp_path / "budget.json").read_text(encoding="utf-8"))
    assert budget["rain_volume_m3"] == pytest.approx(9216.0, rel=1e-5)
    assert abs(budget["unexplained_closure_residual_m3"]) < 0.1


def test_frame_selection_keeps_frozen_time_rule():
    assert nearest_frame([0, 10800, 21600], 16200, 5400) == (1, 5400.0)
    with pytest.raises(ValueError):
        nearest_frame([0, 100], 20000, 5400)
    with pytest.raises(ValueError):
        nearest_frame([0, np.nan, 100], 90, 5400)


def test_contingency_uses_only_preregistered_mask():
    result = contingency(np.array([True, True, False, False]),
                         np.array([True, False, True, True]),
                         np.array([True, True, True, False]), 0.0009)
    assert (result["TP"], result["FP"], result["FN"], result["TN"]) == (1, 1, 1, 0)
    assert result["csi_iou"] == pytest.approx(1 / 3)
