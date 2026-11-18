"""Verify both actual V48 DEMs through the mesh/interpolation/NetCDF code."""
from datetime import datetime, timezone, timedelta
import gc
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys

import netCDF4
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
VTP = ROOT.parents[1]
sys.modules["cupy"] = None
sys.path.insert(0,str(ROOT/"python"))
from bg_flood.initial_conditions import interpolate_bathy, setedges
from bg_flood.mesh import calc_init_nblk, init_block_xoyo, init_block_neighbours
from bg_flood.model import Model, Loop
from bg_flood.read_forcing import prepare_forcing
from bg_flood.read_input import read_param_file, read_bathy_data
from bg_flood.updateforcing import add_rain_vec
from bg_flood.write_output import init_save_to_netcdf, save_to_netcdf


def check_arm(arm):
    print(f"[{arm}] Reading actual frozen config and DEM...",flush=True)
    config = ROOT/f"BG_param_PhuYen_30m_V48_FORMAL_{arm}_R1.txt"
    param, forcing = read_param_file(str(config))
    param, forcing = read_bathy_data(forcing,param)
    prepare_forcing(param,forcing)
    assert (param.nx,param.ny,param.dx)==(2100,2100,30.)
    assert (param.xo,param.xmax,param.yo,param.ymax)==(270000.,333000.,1415000.,1478000.)
    rain_path = VTP/"Scenarios/rain_v34_era5_x2.txt"
    raw = np.loadtxt(rain_path)
    np.testing.assert_array_equal([row.time for row in forcing.Rain.unidata],raw[:,0])
    np.testing.assert_array_equal([row.wspeed for row in forcing.Rain.unidata],raw[:,1])
    assert len(raw)==144 and forcing.Rain.units=="m/s" and forcing.Rain.uniform
    for record in forcing.Rain.unidata:
        forcing.Rain.nowvalue=record.wspeed
        adv = SimpleNamespace(dh=np.zeros(2))
        add_rain_vec(SimpleNamespace(interior=np.array([0,1])),param,SimpleNamespace(totaltime=record.time),
                     forcing.Rain,adv,np.array([0.,9999.]),param.mask)
        np.testing.assert_array_equal(adv.dh,[record.wspeed,0.])
    print(f"[{arm}] All 144 rainfall rates enter the source term unchanged in SI.",flush=True)
    model=Model()
    param.nblk=calc_init_nblk(param,forcing)
    param.nblkmem=math.ceil(param.nblk*param.membuffer)
    model.blocks.allocate(param.nblkmem)
    model.blocks.active[:]=-1
    model.blocks.level[:]=param.initlevel
    init_block_xoyo(param,forcing,model.blocks)
    init_block_neighbours(param,forcing,model.blocks)
    model.zb=np.full(param.nblkmem*param.blksize,param.mask,dtype=np.float64)
    model.OutputVarMap={"zb":model.zb}
    print(f"[{arm}] Checking interpolation and real edge cells on {param.nblk} active blocks...",flush=True)
    interpolate_bathy(param,forcing,model.blocks,model.zb)
    setedges(param,model.blocks,model.zb)
    # Initialization probe writes zb only. It is not a formal flood run.
    param.outvars=["zb"]
    param.outfile=str(ROOT/f"results/V48_{arm}_GRID_INPUT_PROBE.nc")
    assert not Path(param.outfile).exists(), "Refusing to overwrite a prior probe"
    init_save_to_netcdf(param,model)
    loop=Loop()
    loop.totaltime=0.
    save_to_netcdf(param,loop,model)
    tif=VTP/"05-Du-lieu-GIS"/("PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif" if arm=="BASE" else "PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.tif")
    with rasterio.open(tif) as source:
        expected=np.flipud(source.read(1))
    with netCDF4.Dataset(param.outfile) as ds:
        assert (len(ds.dimensions["x"]),len(ds.dimensions["y"]))==(2100,2100)
        np.testing.assert_array_equal(ds["x"][:],270000+(np.arange(2100)+.5)*30)
        np.testing.assert_array_equal(ds["y"][:],1415000+(np.arange(2100)+.5)*30)
        terrain=np.asarray(ds["zb"][0])
        np.testing.assert_array_equal(terrain,expected)
        assert (ds.xmin,ds.xmax,ds.ymin,ds.ymax)==(270000.,333000.,1415000.,1478000.)
    result={"config":str(config),"probe":param.outfile,"shape":[2100,2100],
            "cells_exactly_matching_frozen_tif":int(np.count_nonzero(terrain==expected)),
            "max_abs_zb_difference_m":float(np.max(np.abs(terrain-expected))),
            "negative_terrain_cells_preserved":int(np.count_nonzero(terrain<0)),
            "rain_records_verified":len(raw),"rain_source_unit":"m/s",
            "north_row_and_east_column_preserved":True}
    print(f"[{arm}] PASS: all 4,410,000 terrain samples match the frozen GeoTIFF exactly.",flush=True)
    del model, forcing, param
    gc.collect()
    return result,terrain


def main():
    base,base_zb=check_arm("BASE")
    cond,cond_zb=check_arm("CONDITIONED")
    delta=cond_zb.astype(np.float64)-base_zb.astype(np.float64)
    changed=delta!=0
    assert int(changed.sum())==66
    assert np.all(delta[changed]<0)
    result={"status":"PASS_V48_RUNTIME_INPUT_FIXES",
            "captured_at":datetime.now(timezone(timedelta(hours=7))).isoformat(),
            "scope":"Real frozen rainfall and terrain initialization/output; no formal flood/SAR run",
            "backend":"CPU NumPy", "base":base,"conditioned":cond,
            "pair_changed_cells":int(changed.sum()),"pair_max_lowering_m":float(-delta.min())}
    (ROOT/"results/formal_input_verification.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2),flush=True)


if __name__=="__main__":
    main()
