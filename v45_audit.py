"""Read-only V45 investigation. Writes diagnostics only under V45_audit/.

python v45_audit.py --check-symptom  # fails while most SAR flood in ROI is missed
python v45_audit.py --probes        # exercise current production functions on CPU
python v45_audit.py                # raster, NetCDF, forcing, section diagnostics
"""
from pathlib import Path
from types import SimpleNamespace as NS
import argparse
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'BG_Flood_Project/BG_Flood'
GIS = ROOT / '05-Du-lieu-GIS'
OUT = ROOT / 'V45_audit'


def save(name, value):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(value, indent=2, ensure_ascii=False))


def load_comparison():
    import netCDF4 as nc
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import reproject, Resampling
    with nc.Dataset(BASE / 'results/PhuYen_30m_V44.nc') as ds:
        x, y = np.asarray(ds['x'][:]), np.asarray(ds['y'][:])
        h = np.flipud(ds['h'][33].filled(np.nan))
        z = np.flipud(ds['zb'][33].filled(np.nan))
        stage = np.flipud(ds['zs'][33].filled(np.nan))
        t = float(ds['time'][33])
    transform = from_origin(x[0]-15, y[-1]+15, 30, 30)
    layers = {}
    for key, path, method in [
        ('sar', GIS/'DakLak_PhuYen_FloodExtent_Otsu_20211130_05h36.tif', Resampling.nearest),
        ('water', GIS/'water_density_30m.tif', Resampling.bilinear),
        ('hand', BASE/'Teamwork_Validation/PhuYen_HAND_30m.tif', Resampling.bilinear),
    ]:
        with rasterio.open(path) as src:
            dst = np.full(h.shape, -9999., dtype=np.float32)
            reproject(source=rasterio.band(src, 1), destination=dst,
                      src_transform=src.transform, src_crs=src.crs,
                      src_nodata=src.nodata, dst_transform=transform,
                      dst_crs='EPSG:32649', dst_nodata=-9999., resampling=method)
            layers[key] = dst
    valid = np.isfinite(h) & np.isin(layers['sar'], [0, 1]) & (layers['water'] >= 0) & (layers['water'] <= .5) & (layers['hand'] >= 0)
    # Diagnostic rectangle only; not a delineated basin or left/right bank split.
    roi = (x[None, :] >= 300000) & (x[None, :] <= 325000) & (y[::-1, None] >= 1425000) & (y[::-1, None] <= 1450000)
    return x, y, h, z, stage, t, layers, valid, roi


def metrics(h, sar, mask):
    obs, sim = sar == 1, h > .3
    tp = int(np.sum(obs & sim & mask))
    fn = int(np.sum(obs & ~sim & mask))
    fp = int(np.sum(~obs & sim & mask))
    return dict(tp_cells=tp, fn_cells=fn, fp_cells=fp,
                fn_km2=fn*.0009, recall=tp/max(tp+fn, 1), csi=tp/max(tp+fn+fp, 1))


def symptom():
    x, y, h, z, stage, t, layers, valid, roi = load_comparison()
    m = metrics(h, layers['sar'], valid & roi)
    print(json.dumps(m, indent=2))
    assert m['recall'] >= .5, 'REPRODUCED: majority of SAR flooded cells in downstream diagnostic ROI remain dry (h <= 0.3 m). This is a diagnostic threshold, not V45 acceptance.'


def probes():
    # Select the supported NumPy backend before imports; do not alter production files.
    sys.modules['cupy'] = None
    sys.path.insert(0, str(BASE / 'python'))
    from bg_flood.param import Param
    from bg_flood.model import Model, Loop, BlockP
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

    # Actual rainfall reader -> source function, at maximum of the V44 forcing.
    rain = read_uni_forcing_file(str(ROOT/'Scenarios/rain_v34_era5_x2.txt'))
    peak = max(rain, key=lambda r: r.wspeed)
    m = model()
    add_rain_vec(m.block_index, p, Loop(), NS(uniform=True, nowvalue=peak.wspeed), m.adv,
                 m.zb[m.block_index.interior], p.mask)
    injected = float(m.adv.dh[m.block_index.interior][0])
    results = {'rain': dict(file_peak_m_per_s=peak.wspeed, actual_dh_m_per_s=injected,
                           expected_over_actual=peak.wspeed/injected)}

    # Actual initialization function: same resolution should preserve cell values.
    arr = np.zeros(36)
    raster = np.arange(36, dtype=float).reshape(6, 6)
    interpolate_raster_to_model(p, m.blocks, arr, raster.ravel(), 6, 6, 0., 0., 30., 150., 150.)
    results['same_grid_interpolation'] = dict(expected_first_cell=0., actual_first_cell=float(arr[7]),
                                             meaning='At true ASC first-cell center (15,15), current reader treats corner (0,0) as sample center.')

    # Execute the complete production predictor/corrector on a uniform closed tile.
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
    results['infiltration_one_step'] = dict(initial_h=initial, final_h=float(np.mean(m.evolv.h[i])),
        stored_cumulative_il=float(np.mean(m.evolv.cum_infilt[i])),
        residual_h_plus_cum_minus_initial=float(np.mean(m.evolv.h[i]+m.evolv.cum_infilt[i]))-initial,
        dt=loop.dt, il_mm=30., cl_mm_per_h=0.)

    m = model(1.)
    m.evolv.u[:] = 2.
    update_bnd(p, Loop(), f, m)
    before = float(m.evolv.u[m.block_index.bnd_left_i][0])
    fill_halo_all(m.block_index, m.evolv, m.zb)
    results['wall_predictor_halo'] = dict(after_boundary=before,
        after_predictor_halo_fill=float(m.evolv.u[m.block_index.bnd_left_i][0]))
    results['correctness_checks'] = {
        'rain_units_match_file': bool(np.isclose(injected, peak.wspeed, rtol=1e-9, atol=1e-15)),
        'same_grid_preserves_values': bool(abs(arr[7]) < 1e-9),
        'infiltration_bookkeeping_conserves_water': bool(abs(results['infiltration_one_step']['residual_h_plus_cum_minus_initial']) < 1e-9),
        'wall_boundary_survives_predictor_halo': bool(abs(m.evolv.u[m.block_index.bnd_left_i][0]) < 1e-9),
    }
    save('solver_probes.json', results)


def data_audit():
    import rasterio
    import netCDF4 as nc
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x, y, h, z, stage, t, layers, valid, roi = load_comparison()
    results = {'frame_time_seconds': t, 'whole_domain': metrics(h, layers['sar'], valid),
               'downstream_rectangle': metrics(h, layers['sar'], valid & roi),
               'roi_bounds_utm': [300000,1425000,325000,1450000], 'rasters': {}}
    dems = {}
    for name in ['PhuYen_DEM_30m.asc', 'PhuYen_DEM_30m_V41.asc', 'PhuYen_DEM_30m_V44.asc',
                 'PhuYen_DEM_30m_V45.asc', 'PhuYen_manning_30m_V43.asc', 'il_30m_V36.asc', 'cl_30m_V36.asc']:
        with rasterio.open(GIS/name) as src:
            a = src.read(1)
            vals = a[(a != src.nodata) & np.isfinite(a)]
            results['rasters'][name] = dict(shape=list(a.shape), transform=list(src.transform), crs=str(src.crs),
                nodata=src.nodata, percentiles=np.percentile(vals,[0,5,50,95,100]).tolist(), below_minmask=int(np.sum(vals <= -1)))
            if 'DEM' in name:
                dems[name] = a
    d41, d44, d45 = [dems[f'PhuYen_DEM_30m_{v}.asc'] for v in ('V41','V44','V45')]
    for label, old, new in [('V44_minus_V41',d41,d44),('V45_minus_V44',d44,d45)]:
        diff = new-old
        changed = (np.abs(diff)>.01) & (old != -9999) & (new != -9999)
        r,c = np.where(changed)
        results[label] = dict(cells=int(changed.sum()), area_km2=float(changed.sum()*.0009),
            delta_percentiles=np.percentile(diff[changed],[0,5,50,95,100]).tolist(),
            excavation_m3=float(-diff[changed].sum(dtype=float)*900),
            bounds_centers=[float(270015+c.min()*30),float(1477985-r.max()*30),
                            float(270015+c.max()*30),float(1477985-r.min()*30)])
    # Check actual solver zb against 4-sample average implied by corner/center mismatch.
    average4 = (d44[1:,:-1]+d44[1:,1:]+d44[:-1,:-1]+d44[:-1,1:])/4
    match = np.isfinite(z) & (z < 9999) & (average4 > -100) & roi
    results['solver_zb_vs_average4'] = dict(max_abs_error=float(np.max(np.abs(z[match]-average4[match]))),
        median_abs_error=float(np.median(np.abs(z[match]-average4[match]))))
    col = int(np.argmin(abs(x-314955)))
    sel = (y[::-1] >= 1442000) & (y[::-1] <= 1444000)
    # model north row 0 corresponds to source row 1 in current output geometry
    section = np.column_stack([y[::-1][sel], d41[1:, col][sel],d44[1:,col][sel],d45[1:,col][sel],z[sel,col],h[sel,col],stage[sel,col]])
    OUT.mkdir(exist_ok=True)
    np.savetxt(OUT/'section_x314955.csv',section,delimiter=',',header='y,z41_raw,z44_raw,z45_raw,zb_solver,h_solver,zs_solver',comments='')
    fig,ax=plt.subplots(figsize=(12,5))
    for k,label in [(1,'V41 ASC'),(2,'V44 ASC'),(3,'V45 draft ASC'),(4,'V44 solver zb')]:
        ax.plot(section[:,0],section[:,k],label=label)
    ax.plot(section[:,0],np.where(section[:,5]>.01,section[:,6],np.nan),label='V44 wet-cell water surface',color='blue',lw=2)
    ax.set(xlabel='Northing (m, EPSG:32649)',ylabel='Elevation / water surface (m)',
           title='Diagnostic cross-section x=314955 m; V44 t=102 h')
    ax.legend(ncol=2); ax.grid(alpha=.3); fig.tight_layout();fig.savefig(OUT/'section_x314955.png',dpi=150);plt.close(fig)
    rain=np.loadtxt(ROOT/'Scenarios/rain_v34_era5_x2.txt')
    end=432000
    keep=rain[:,0]<=end
    results['rain_120h'] = dict(file_integral_mm=float(np.trapz(rain[keep,1],rain[keep,0])*1000),
        actual_solver_integral_mm=float(np.trapz(rain[keep,1]/3600000,rain[keep,0])*1000))
    results['rivers']={}
    for name in ['xa_lu_BaHa_Nov2021_V40_sync.txt','xa_lu_BanThach_V43.txt','xa_lu_KyLo_V40_sync.txt','xa_lu_TuyAn_V40_sync.txt']:
        a=np.loadtxt(BASE/name); tt=np.unique(np.r_[0,a[(a[:,0]>0)&(a[:,0]<end),0],end]);qq=np.interp(tt,a[:,0],a[:,1])
        results['rivers'][name]=dict(peak_q=float(a[:,1].max()),peak_hour=float(a[a[:,1].argmax(),0]/3600),
          q_101_6h=float(np.interp(365760,a[:,0],a[:,1])),q_108_6h=float(np.interp(390960,a[:,0],a[:,1])),
          volume_120h_m3=float(np.trapz(qq,tt)))
    with nc.Dataset(BASE/'results/PhuYen_30m_V44.nc') as ds:
        results['netcdf']=dict(shape=list(ds['h'].shape), time_attributes={k:str(ds['time'].getncattr(k)) for k in ds['time'].ncattrs()},
                                x_bounds=[float(x[0]),float(x[-1])],y_bounds=[float(y[0]),float(y[-1])])
    save('data_audit.json',results)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check-symptom',action='store_true');parser.add_argument('--probes',action='store_true')
    args=parser.parse_args()
    if args.check_symptom: symptom()
    elif args.probes: probes()
    else: data_audit()
