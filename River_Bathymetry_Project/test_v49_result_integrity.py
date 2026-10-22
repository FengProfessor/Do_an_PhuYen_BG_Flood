"""Reject structurally present results with corrupt time or shifted geography."""
import netCDF4
import numpy as np
import pytest
from affine import Affine
from v49_validate_hydraulic_validation import _inspect_result
from v49_evaluate_hydraulic_validation import nearest_frame, verify_result_coordinates


@pytest.mark.parametrize("times", [[0., np.nan, 432000.], [0., 432000., 100.], [0., 0., 432000.]])
def test_invalid_time_axis_cannot_be_completed_or_sar_available(tmp_path, times):
    path = tmp_path / "bad.nc"
    with netCDF4.Dataset(path, "w") as dataset:
        dataset.createDimension("time", 3)
        dataset.createVariable("time", "f8", ("time",))[:] = times
        for name in ["zs", "h", "zb", "u", "v"]:
            dataset.createVariable(name, "f4", ("time",))[:] = 1.
    state = _inspect_result(path, 100., 5400., 432000.)
    assert state["status"] == "INVALID_TIME_AXIS"
    assert not state["sar_frame_available"] and not state["complete_to_endtime"]


def test_masked_time_is_not_a_valid_observation_frame():
    times = np.ma.array([0., 100., 200.], mask=[False, True, False])
    with pytest.raises(ValueError, match="finite"):
        nearest_frame(times, 100., 5400.)


def test_result_coordinates_require_positions_not_only_dimensions():
    transform = Affine(30., 0., 0., 0., -30., 60.)
    verify_result_coordinates([15., 45.], [15., 45.], (2, 2), transform)
    with pytest.raises(ValueError, match="cell centers"):
        verify_result_coordinates([45., 75.], [15., 45.], (2, 2), transform)
