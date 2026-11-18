import numpy as np
import os
from time import perf_counter
from .param import Param
from .model import Model, Loop
from .utils import calcres, memloc

# Bien toan cuc giu file NetCDF mo
_nc_dataset = None


def _fixed_grid_output_indices(param, model, nx_out, ny_out, levdx):
    """Map active block interiors to output pixels once per frame.

    The R1 full-grid run has one level with cell centers aligned to the
    output raster. For mixed levels, overlapping or misaligned blocks, use
    the original per-cell writer to preserve its assignment semantics.
    """
    active = np.asarray(model.blocks.active[:param.nblk], dtype=np.int64)
    if not len(active):
        empty = np.empty(0, dtype=np.int64)
        return empty, empty

    levels = np.asarray(model.blocks.level[active])
    if np.any(levels != param.initlevel):
        return None

    origin_x = (np.asarray(model.blocks.xo[active]) - 0.5 * levdx) / levdx
    origin_y = (np.asarray(model.blocks.yo[active]) - 0.5 * levdx) / levdx
    x_round = np.rint(origin_x)
    y_round = np.rint(origin_y)
    if (np.any(np.abs(origin_x - x_round) > 1e-7)
            or np.any(np.abs(origin_y - y_round) > 1e-7)):
        return None

    offsets = np.arange(param.blkwidth, dtype=np.int64)
    ix, iy = np.meshgrid(offsets, offsets, indexing='xy')
    ix = ix.ravel()
    iy = iy.ravel()
    gi = x_round.astype(np.int64)[:, None] + ix[None, :]
    gj = y_round.astype(np.int64)[:, None] + iy[None, :]
    inside = ((gi >= 0) & (gi < nx_out) & (gj >= 0) & (gj < ny_out)).ravel()
    local = ((iy + param.halowidth) * param.blkmemwidth
             + ix + param.halowidth)
    source = (active[:, None] * param.blksize + local[None, :]).ravel()[inside]
    destination = (gj * nx_out + gi).ravel()[inside]

    # Repeated destinations require the scalar writer's ordered assignments.
    ordered = np.sort(destination)
    if np.any(ordered[1:] == ordered[:-1]):
        return None
    return source, destination


def init_save_to_netcdf(param: Param, model: Model):
    try:
        import netCDF4 as nc4
    except ImportError:
        return

    outfile = param.outfile
    if os.path.exists(outfile):
        base, ext = os.path.splitext(outfile)
        count = 1
        while os.path.exists(outfile):
            outfile = f"{base}_{count}{ext}"
            count += 1
        param.outfile = outfile

    ds = nc4.Dataset(outfile, 'w', format='NETCDF4')

    ds.setncattr('maxlevel', param.maxlevel)
    ds.setncattr('minlevel', param.minlevel)
    ds.setncattr('xmin', param.xo)
    ds.setncattr('xmax', param.xo + param.nx * param.dx)
    ds.setncattr('ymin', param.yo)
    ds.setncattr('ymax', param.yo + param.ny * param.dx)

    ds.createDimension('time', None)
    time_var = ds.createVariable('time', 'f4', ('time',))
    time_var.units = 's'
    time_var.long_name = 'elapsed time since simulation start'

    levdx = calcres(param.dx, param.initlevel)
    nx_out = param.nx
    ny_out = param.ny

    ds.createDimension('x', nx_out)
    ds.createDimension('y', ny_out)

    x_var = ds.createVariable('x', 'f8', ('x',))
    y_var = ds.createVariable('y', 'f8', ('y',))
    x_var.units = 'm'
    y_var.units = 'm'
    x_var[:] = param.xo + (np.arange(nx_out) + 0.5) * levdx
    y_var[:] = param.yo + (np.arange(ny_out) + 0.5) * levdx

    crs_var = ds.createVariable('spatial_ref', 'i4')
    crs_var.spatial_ref = "EPSG:32649"
    crs_var.epsg_code = "EPSG:32649"
    crs_var.grid_mapping_name = "transverse_mercator"

    for varname in param.outvars:
        var = ds.createVariable(varname, 'f4', ('time', 'y', 'x'), zlib=True, fill_value=-9999.0)
        var.grid_mapping = 'spatial_ref'
        var.units = 'm/s' if varname in ('u', 'v') else 'm'

    ds.sync()
    ds.close() # Close immediately after init!


def save_to_netcdf(param: Param, loop: Loop, model: Model):
    frame_started = perf_counter()
    try:
        import netCDF4 as nc4
        import matplotlib.pyplot as plt
    except ImportError:
        return

    if not os.path.exists(param.outfile):
        init_save_to_netcdf(param, model)

    ds = nc4.Dataset(param.outfile, 'a')

    time_var = ds.variables['time']
    step = len(time_var)
    time_var[step] = loop.totaltime

    nx_out = ds.dimensions['x'].size
    ny_out = ds.dimensions['y'].size
    levdx = calcres(param.dx, param.initlevel)

    # Dictionary luu tam data de ve
    vars_2d = {}
    from .gpu_backend import to_numpy
    terrain = to_numpy(model.zb)
    raster_indices = _fixed_grid_output_indices(param, model, nx_out, ny_out, levdx)
    if raster_indices is not None:
        source, destination = raster_indices
        fluid = terrain[source] < param.mask - 1.0
        fluid_source = source[fluid]
        fluid_destination = destination[fluid]

    for varname in param.outvars:
        if varname not in ds.variables:
            continue

        data_2d = np.full((ny_out, nx_out), np.nan, dtype=np.float32)

        if varname in model.OutputVarMap:
            var_data = model.OutputVarMap[varname]
            try:
                from .gpu_backend import to_numpy
                var_data = to_numpy(var_data)
            except ImportError:
                pass
        else:
            continue

        if raster_indices is not None:
            # zb retains the terrain sentinel; other variables skip masked
            # cells, matching the original per-cell writer.
            indices = (source, destination) if varname == 'zb' else (fluid_source, fluid_destination)
            data_2d.reshape(-1)[indices[1]] = var_data[indices[0]]
        else:
            levdx_cache = {}
            for ibl in range(param.nblk):
                ib = model.blocks.active[ibl]
                lev = model.blocks.level[ib]

                if lev not in levdx_cache:
                    levdx_cache[lev] = calcres(param.dx, lev)
                blk_levdx = levdx_cache[lev]

                xo_base = param.xo + model.blocks.xo[ib]
                yo_base = param.yo + model.blocks.yo[ib]

                for iy in range(param.blkwidth):
                    for ix in range(param.blkwidth):
                        n = memloc(param.halowidth, param.blkmemwidth, ix, iy, ib)
                        if varname != 'zb' and terrain[n] >= param.mask - 1.0:
                            continue
                        x = xo_base + ix * blk_levdx
                        y = yo_base + iy * blk_levdx

                        gi = int(round((x - param.xo - 0.5 * levdx) / levdx))
                        gj = int(round((y - param.yo - 0.5 * levdx) / levdx))

                        if 0 <= gi < nx_out and 0 <= gj < ny_out:
                            data_2d[gj, gi] = var_data[n]

        ds.variables[varname][step, :, :] = data_2d
        vars_2d[varname] = data_2d

    ds.sync()
    ds.close() # Close immediately so Windows releases lock!

    # Render a PNG for realtime viewing
    if 'h' in vars_2d:
        h_filled = np.nan_to_num(vars_2d['h'], nan=0.0)
        plt.figure(figsize=(10,8))
        plt.imshow(h_filled, cmap='Blues', vmin=0.3, vmax=5, origin='lower')
        plt.colorbar(label='Water Depth (m)')
        plt.title(f"Realtime Preview - Step {step} (t={loop.totaltime}s)")
        out_png = param.outfile.replace('.nc', f'_frame_{step}.png')
        plt.savefig(out_png, dpi=100)
        plt.close()

    print(f"NetCDF frame t={loop.totaltime:.3f}s saved in "
          f"{perf_counter() - frame_started:.2f}s "
          f"({'vectorized' if raster_indices is not None else 'scalar'})", flush=True)


def close_netcdf():
    pass

