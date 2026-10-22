import numpy as np
import pytest
from affine import Affine
from pyproj import CRS
from v49_build_hydro_conditioned_dem import condition_array, drainage_graph


def test_closed_interior_pit_is_filled_and_all_cells_drain():
    data = np.tile(np.arange(7, 0, -1, dtype=float), (7, 1))
    data[3, 3] = -10.
    valid = np.ones(data.shape, dtype=bool)
    conditioned, direction, accumulation, checks = condition_array(data, valid, Affine(30., 0., 0., 0., -30., 210.), CRS.from_epsg(32649))
    assert conditioned[3, 3] >= 3.
    assert checks["every_valid_cell_drains_to_an_explicit_outlet"]
    assert checks["outlet_accumulation_sum_cells"] == 49.
    np.testing.assert_array_equal(data[3, 3], -10.)


def test_cycle_is_detected_independently_of_conditioning():
    directions = np.array([[1, 16]], dtype=np.int16)
    valid = np.ones((1, 2), dtype=bool)
    _, cycles, _, _ = drainage_graph(directions, valid)
    assert cycles == 2


@pytest.mark.parametrize("elevation", [0., 100.])
def test_flat_plateau_has_no_interior_artificial_outlets(elevation):
    data = np.full((9, 9), elevation, dtype=float)
    valid = np.ones(data.shape, dtype=bool)
    conditioned, _, _, checks = condition_array(data, valid, Affine(30., 0., 0., 0., -30., 270.), CRS.from_epsg(32649))
    assert checks["internal_unresolved_cells"] == 0
    assert checks["every_valid_cell_drains_to_an_explicit_outlet"]
    assert float((conditioned - data).max()) < 1e-6
