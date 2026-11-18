"""Exercise the rainfall loader/source and DEM-to-mesh-to-NetCDF paths."""
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

import netCDF4
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.modules["cupy"] = None  # These regressions must not share the live V45 GPU.
sys.path.insert(0, os.environ.get("V48_TEST_ENGINE", str(ROOT / "python")))
from bg_flood.forcing import Forcing, StaticForcingP
from bg_flood.initial_conditions import interpolate_bathy, setedges
from bg_flood.mesh import init_mesh
from bg_flood.model import Model, Loop
from bg_flood.param import Param
from bg_flood.read_forcing import prepare_forcing
from bg_flood.read_input import read_bathy_data, read_param_str_forcing
from bg_flood.updateforcing import add_rain_vec
from bg_flood.write_output import init_save_to_netcdf, save_to_netcdf


class RuntimeFixTests(unittest.TestCase):
    def load_rain(self, path, text, configured_units=""):
        path.write_text(text, encoding="utf-8")
        forcing = Forcing()
        forcing.Rain.inputfile = str(path)
        if configured_units:
            read_param_str_forcing(f"rainunits = {configured_units};", forcing)
        prepare_forcing(Param(), forcing)
        return forcing.Rain

    def assert_rain_source(self, rain, expected):
        idx = SimpleNamespace(interior=np.array([0, 1]))
        adv = SimpleNamespace(dh=np.zeros(2))
        add_rain_vec(idx, Param(), SimpleNamespace(totaltime=0), rain,
                     adv, np.array([0., 9999.]), 9999.)
        np.testing.assert_allclose(adv.dh, [expected, 0.], rtol=1e-12, atol=0)

    def test_m_per_second_is_not_divided_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            rain = self.load_rain(Path(tmp)/"rain.txt", "# rainfall (m/s)\n0 0.000002\n3600 0.000002\n")
            self.assert_rain_source(rain, .000002)

    def test_mm_per_hour_is_normalized_at_the_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            rain = self.load_rain(Path(tmp)/"rain.txt", "# rainfall (mm/h)\n0 10\n3600 10\n")
            self.assertAlmostEqual(rain.nowvalue, 10/3600000., places=15)
            self.assert_rain_source(rain, 10/3600000.)
            self.assertAlmostEqual(rain.nowvalue*3600., .01, places=12)

    def test_explicit_config_units_work_without_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            rain = self.load_rain(Path(tmp)/"rain.txt", "0 0.000002\n3600 0.000002\n", "m/s")
            self.assert_rain_source(rain, .000002)

    def test_conflicting_units_fail_before_simulation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "conflict"):
                self.load_rain(Path(tmp)/"rain.txt", "# rainfall (m/s)\n0 .000002\n3600 .000002\n", "mm/h")

    def grid_fixture(self, directory):
        values = np.arange(17*20, dtype=np.float64).reshape(17,20)+10.
        values[0,0] = -3.  # Real negative terrain must remain valid.
        values[8,9] = -9999.
        path = Path(directory)/"dem.asc"
        with path.open("w", encoding="utf-8") as stream:
            stream.write("ncols 20\nnrows 17\nxllcorner 100\nyllcorner 200\ncellsize 30\nNODATA_value -9999\n")
            np.savetxt(stream, values, fmt="%.9g")
        forcing, param = Forcing(), Param()
        forcing.Bathy.append(StaticForcingP(inputfile=str(path), extension="asc"))
        param.minmask = -4.
        param.blkmemwidth = param.blkwidth + 2*param.halowidth
        param.blksize = param.blkmemwidth**2
        param, forcing = read_bathy_data(forcing, param)
        param.outfile = str(Path(directory)/"grid.nc")
        param.outvars = ["zb"]
        return values, param, forcing

    def test_full_grid_dimensions_centers_and_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, param, forcing = self.grid_fixture(tmp)
            init_save_to_netcdf(param, Model())
            with netCDF4.Dataset(param.outfile) as ds:
                self.assertEqual((len(ds.dimensions["y"]),len(ds.dimensions["x"])), (17,20))
                np.testing.assert_array_equal(ds["x"][:],100+(np.arange(20)+.5)*30)
                np.testing.assert_array_equal(ds["y"][:],200+(np.arange(17)+.5)*30)
                self.assertEqual((ds.xmin,ds.xmax,ds.ymin,ds.ymax), (100.,700.,200.,710.))
            self.assertEqual((forcing.Bathy[0].xo,forcing.Bathy[0].yo), (115.,215.))

    def test_mesh_and_writer_preserve_edges_nodata_and_exact_dem(self):
        with tempfile.TemporaryDirectory() as tmp:
            values, param, forcing = self.grid_fixture(tmp)
            model = Model()
            init_mesh(param, forcing, model)
            interpolate_bathy(param, forcing, model.blocks, model.zb)
            setedges(param, model.blocks, model.zb)
            init_save_to_netcdf(param, model)
            loop = Loop()
            loop.totaltime = 0.
            save_to_netcdf(param, loop, model)
            expected = np.flipud(values).copy()
            expected[expected == -9999.] = param.mask
            with netCDF4.Dataset(param.outfile) as ds:
                np.testing.assert_array_equal(ds["zb"][0].filled(np.nan), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
