import sys
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
import json

ROOT = Path('D:/VTP')
BASE = ROOT / 'V45_runs/20260928_engine_r1'
sys.modules['cupy'] = None
sys.path.insert(0, str(BASE / 'python'))

from bg_flood.param import Param
from bg_flood.model import Model, Loop
from bg_flood.forcing import Forcing
from bg_flood.block_index import build_block_index
from bg_flood.flow_gpu import flow_gpu, fill_halo_all
from bg_flood.boundary import update_bnd
from bg_flood.initial_conditions import interpolate_raster_to_model
from bg_flood.updateforcing import add_rain_vec
from bg_flood.read_forcing import read_uni_forcing_file

p = Param(nx=4, ny=4, dx=30., xo=0., yo=0., xmax=120., ymax=120.,
          blkwidth=4, halowidth=1, blkmemwidth=6, blksize=36, nblk=1, nblkmem=1,
          endtime=10., dt=1.)
p.rainunits = 'm/s'

def model(depth=.02):
    m = Model()
    m.allocate(1, 36)
    m.blocks.active[0] = 0
    m.blocks.xo[0] = m.blocks.yo[0] = 15.
    m.block_index = build_block_index(p, m.blocks)
    for ev in (m.evolv, m.evolv_o):
        ev.h[:] = depth
        ev.zs[:] = depth
    m.cf[:] = 0
    return m

# Test rain units
rain = read_uni_forcing_file(str(ROOT/'Scenarios/rain_v34_era5_x2.txt'))
peak = max(rain, key=lambda r: r.wspeed)
m = model()
add_rain_vec(m.block_index, p, Loop(), NS(uniform=True, nowvalue=peak.wspeed), m.adv,
             m.zb[m.block_index.interior], p.mask)
injected = float(m.adv.dh[m.block_index.interior][0])

# Test same grid
arr = np.zeros(36)
raster = np.arange(36, dtype=float).reshape(6, 6)
interpolate_raster_to_model(p, m.blocks, arr, raster.ravel(), 6, 6, 0., 0., 30., 150., 150.)

# Test infiltration
p.il = 30.
m = model()
m.il[:] = 30.
f = Forcing()
for side in (f.left, f.right, f.top, f.bot):
    side.type = 0
loop = Loop()
i = m.block_index.interior
update_bnd(p, loop, f, m)
initial = float(np.mean(m.evolv.h[i]))
flow_gpu(p, loop, f, m)

# Test wall boundary
m = model(1.)
m.evolv.u[:] = 2.
update_bnd(p, Loop(), f, m)
before = float(m.evolv.u[m.block_index.bnd_left_i][0])
fill_halo_all(m.block_index, m.evolv, m.zb)

results = {
    'rain': dict(file_peak_m_per_s=peak.wspeed, actual_dh_m_per_s=injected, expected_over_actual=peak.wspeed/injected if injected else None),
    'same_grid_interpolation': dict(expected_first_cell=0., actual_first_cell=float(arr[7])),
    'infiltration_one_step': dict(residual=float(np.mean(m.evolv.h[i]+m.evolv.cum_infilt[i]))-initial),
    'wall_predictor_halo': dict(after_boundary=before, after_halo=float(m.evolv.u[m.block_index.bnd_left_i][0])),
    'correctness_checks': {
        'rain_units_match_file': bool(np.isclose(injected, peak.wspeed, rtol=1e-9, atol=1e-15)),
        'same_grid_preserves_values': bool(abs(arr[7]) < 1e-9),
        'infiltration_bookkeeping_conserves_water': bool(abs(float(np.mean(m.evolv.h[i]+m.evolv.cum_infilt[i]))-initial) < 1e-9),
        'wall_boundary_survives_predictor_halo': bool(abs(m.evolv.u[m.block_index.bnd_left_i][0]) < 1e-9),
    }
}
print(json.dumps(results, indent=2))
