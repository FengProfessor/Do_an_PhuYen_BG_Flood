"""
Cập nhật lực tác động ngoại lực (Mưa, Gió, Sông).
"""

import math
import numpy as np
from .param import Param
from .model import BlockP, AdvanceP
from .utils import calcres, memloc, interptime, distance


def init_rain_istation(param, blocks, rain):
    import numpy as np
    from .utils import memloc, calcres
    if rain.istation is not None:
        return
        
    print("Pre-calculating spatial rain distribution map...", flush=True)
    rain.istation = np.zeros(param.blkmemwidth**2 * param.nblk, dtype=int)
    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):
                idx_cell = memloc(param.halowidth, param.blkmemwidth, ix, iy, ib)
                delta2 = calcres(param.dx, blocks.level[ib])
                cx = param.xo + blocks.xo[ib] + (ix + 0.5) * delta2
                cy = param.yo + blocks.yo[ib] + (iy + 0.5) * delta2
                
                min_d = 1e20
                best_s = 0
                for s_idx, s_coord in enumerate(rain.station_coords):
                    d = (cx - s_coord[0])**2 + (cy - s_coord[1])**2
                    if d < min_d:
                        min_d = d
                        best_s = s_idx
                rain.istation[idx_cell] = best_s


def init_rain_grid_weights(param, blocks, rain):
    """
    Tính trước các chỉ số và trọng số nội suy song tuyến (bilinear) 
    cho từng ô lưới mô phỏng dựa trên lưới mưa GRID.
    """
    import numpy as np
    from .utils import memloc, calcres
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:32648", "EPSG:4326", always_xy=True)
    except ImportError:
        print("WARNING: pyproj not found. Rainfall interpolation might be inaccurate.")
        transformer = None

    if hasattr(rain, 'grid_indices') and rain.grid_indices is not None:
        return

    print("Pre-calculating bilinear rain interpolation weights...", flush=True)
    
    n_cells = param.blkmemwidth**2 * param.nblk
    rain.grid_indices = np.zeros((4, n_cells), dtype=int)
    rain.grid_weights = np.zeros((4, n_cells), dtype=float)

    lons = np.linspace(rain.lon_range[0], rain.lon_range[1], rain.nlon)
    lats = np.linspace(rain.lat_range[0], rain.lat_range[1], rain.nlat)
    dlon = (rain.lon_range[1] - rain.lon_range[0]) / (rain.nlon - 1) if rain.nlon > 1 else 1.0
    dlat = (rain.lat_range[1] - rain.lat_range[0]) / (rain.nlat - 1) if rain.nlat > 1 else 1.0

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        levdx = calcres(param.dx, blocks.level[ib])
        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):
                idx_cell = memloc(param.halowidth, param.blkmemwidth, ix, iy, ib)
                cx = param.xo + blocks.xo[ib] + (ix + 0.5) * levdx
                cy = param.yo + blocks.yo[ib] + (iy + 0.5) * levdx
                
                if transformer:
                    lon, lat = transformer.transform(cx, cy)
                else:
                    # Fallback if no pyproj (assume degrees, though unlikely for UTM model)
                    lon, lat = cx, cy

                # Find bounding box in rain grid
                gi = max(0, min(int((lon - rain.lon_range[0]) / dlon), rain.nlon - 2))
                gj = max(0, min(int((lat - rain.lat_range[0]) / dlat), rain.nlat - 2))

                # Relative positions [0, 1]
                u = (lon - lons[gi]) / dlon
                v = (lat - lats[gj]) / dlat
                u = max(0.0, min(1.0, u))
                v = max(0.0, min(1.0, v))

                # Indices of 4 neighbors
                # Standard BG-Flood GRID order: index = gj * nlon + gi
                i00 = gj * rain.nlon + gi
                i10 = gj * rain.nlon + (gi + 1)
                i01 = (gj + 1) * rain.nlon + gi
                i11 = (gj + 1) * rain.nlon + (gi + 1)

                rain.grid_indices[:, idx_cell] = [i00, i10, i01, i11]
                rain.grid_weights[:, idx_cell] = [(1-u)*(1-v), u*(1-v), (1-u)*v, u*v]



def add_rainforcing_cpu(param: Param, loop, blocks, rain, adv, zb):
    """
    Thêm lượng mưa vào dh sử dụng nội suy Bilinear nếu là dữ liệu Grid,
    hoặc Nearest Neighbor nếu là dữ liệu trạm.
    """
    from .utils import memloc, bilinear_interpolation, interptime
    import pyproj
    from pyproj import Transformer

    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth
    
    # Khởi tạo Transformer để chuyển từ UTM sang Lat/Lon (ngược lại với lúc nạp)
    # Giả định mô hình đang dùng EPSG:32648 (UTM 48N)
    try:
        transformer = Transformer.from_crs("EPSG:32648", "EPSG:4326", always_xy=True)
    except:
        transformer = None

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        levdx = calcres(param.dx, blocks.level[ib])
        
        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):
                i = memloc(halowidth, blkmemwidth, ix, iy, ib)
                
                if zb[i] >= param.mask - 1.0:
                    continue

                if rain.uniform:
                    rainhh = rain.nowvalue
                elif rain.is_grid and transformer:
                    # Tọa độ thực của ô lưới
                    cx = param.xo + blocks.xo[ib] + (ix + 0.5) * levdx
                    cy = param.yo + blocks.yo[ib] + (iy + 0.5) * levdx
                    
                    # Chuyển sang Lat/Lon
                    lon, lat = transformer.transform(cx, cy)
                    
                    # Nội suy không gian trên lưới Grid
                    lons = np.linspace(rain.lon_range[0], rain.lon_range[1], rain.nlon)
                    lats = np.linspace(rain.lat_range[0], rain.lat_range[1], rain.nlat)
                    
                    # Tìm chỉ số ô lưới Grid chứa điểm (lat, lon)
                    # Giả sử lưới đều
                    dlat = (rain.lat_range[1] - rain.lat_range[0]) / (rain.nlat - 1)
                    dlon = (rain.lon_range[1] - rain.lon_range[0]) / (rain.nlon - 1)
                    
                    gi = max(0, min(int((lon - rain.lon_range[0]) / dlon), rain.nlon - 2))
                    gj = max(0, min(int((lat - rain.lat_range[0]) / dlat), rain.nlat - 2))
                    
                    # Lấy 4 điểm xung quanh tham chiếu thời gian
                    step = 1
                    while step < len(rain.unidata) - 1 and rain.unidata[step].time < loop.totaltime:
                        step += 1
                    dt_f = rain.unidata[step].time - rain.unidata[step-1].time
                    t_el = loop.totaltime - rain.unidata[step-1].time
                    
                    # Mưa tại 4 đỉnh (Bilinear)
                    def get_grid_val(s, i_g, j_g):
                        # Trong kịch bản lưới, chúng ta sẽ lưu index = j_g * nlon + i_g
                        idx = j_g * rain.nlon + i_g
                        return rain.multi_val[s][idx]

                    q11_p = get_grid_val(step-1, gi, gj)
                    q21_p = get_grid_val(step-1, gi+1, gj)
                    q12_p = get_grid_val(step-1, gi, gj+1)
                    q22_p = get_grid_val(step-1, gi+1, gj+1)
                    
                    q11_n = get_grid_val(step, gi, gj)
                    q21_n = get_grid_val(step, gi+1, gj)
                    q12_n = get_grid_val(step, gi, gj+1)
                    q22_n = get_grid_val(step, gi+1, gj+1)
                    
                    # Nội suy song tuyến tính tại T-1 và T
                    r1 = bilinear_interpolation(q11_p, q12_p, q21_p, q22_p, 
                                                lons[gi], lons[gi+1], lats[gj], lats[gj+1], lon, lat)
                    r2 = bilinear_interpolation(q11_n, q12_n, q21_n, q22_n, 
                                                lons[gi], lons[gi+1], lats[gj], lats[gj+1], lon, lat)
                    
                    # Nội suy thời gian
                    rainhh = interptime(r2, r1, dt_f, t_el)
                else:
                    # Giữ nguyên logic trạm gần nhất nếu không có GRID
                    if rain.station_coords and rain.multi_val is not None:
                        if rain.istation is None:
                            init_rain_istation(param, blocks, rain)
                        s_idx = rain.istation[i]
                        step = 1
                        while step < len(rain.unidata) - 1 and rain.unidata[step].time < loop.totaltime:
                            step += 1
                        rainhh = interptime(rain.multi_val[step][s_idx], rain.multi_val[step-1][s_idx], 
                                            rain.unidata[step].time - rain.unidata[step-1].time, 
                                            loop.totaltime - rain.unidata[step-1].time)
                    else:
                        rainhh = rain.nowvalue

                adv.dh[i] += rainhh  # prepare_forcing already normalized rainfall to m/s



def add_rain_vec(idx, param, loop, rain, adv, zb_interior, mask_val):
    """Add rainfall to dh. Handles uniform, multi-station, and GRID spatial rain (Vectorized)."""
    from .gpu_backend import xp
    import numpy as np

    valid_mask = zb_interior < mask_val - 1.0

    if rain.uniform and hasattr(rain, 'nowvalue'):
        rain_ms = rain.nowvalue
        adv.dh[idx.interior] = xp.where(valid_mask, adv.dh[idx.interior] + rain_ms, adv.dh[idx.interior])
    
    elif not rain.uniform and getattr(rain, 'is_grid', False) and rain.multi_val is not None:
        # GRID RAIN (Vectorized Bilinear Interpolation)
        if hasattr(rain, 'grid_indices') and rain.grid_indices is not None:
            # Get precomputed indices and weights
            idx00 = xp.asarray(rain.grid_indices[0])
            idx10 = xp.asarray(rain.grid_indices[1])
            idx01 = xp.asarray(rain.grid_indices[2])
            idx11 = xp.asarray(rain.grid_indices[3])
            
            w00 = xp.asarray(rain.grid_weights[0])
            w10 = xp.asarray(rain.grid_weights[1])
            w01 = xp.asarray(rain.grid_weights[2])
            w11 = xp.asarray(rain.grid_weights[3])

            # Find current time step
            if len(rain.unidata) < 2:
                r_interp = xp.asarray(rain.multi_val[0])
            else:
                step = 1
                while step < len(rain.unidata) - 1 and rain.unidata[step].time < loop.totaltime:
                    step += 1
                dt_f = rain.unidata[step].time - rain.unidata[step-1].time
                t_el = loop.totaltime - rain.unidata[step-1].time
                frac = t_el / dt_f if dt_f > 0 else 0.0
                
                r_now = xp.asarray(rain.multi_val[step])
                r_prev = xp.asarray(rain.multi_val[step-1])
                r_interp = r_prev + (r_now - r_prev) * frac

            # Sample values at 4 neighbors and interpolate
            # r_interp is 1D array of size nlat*nlon
            r_vals = r_interp[idx00] * w00 + r_interp[idx10] * w10 + \
                     r_interp[idx01] * w01 + r_interp[idx11] * w11
            
            rain_ms_all = r_vals[idx.interior]
            adv.dh[idx.interior] = xp.where(valid_mask, adv.dh[idx.interior] + rain_ms_all, adv.dh[idx.interior])
        else:
            # Fallback to mean if not initialized (should not happen with flow_gpu fix)
            rain_val = xp.mean(xp.asarray(rain.multi_val[0]))
            rain_ms = rain_val
            adv.dh[idx.interior] = xp.where(valid_mask, adv.dh[idx.interior] + rain_ms, adv.dh[idx.interior])

    elif not rain.uniform and rain.station_coords and rain.multi_val is not None:
        # STATION RAIN (Vectorized)
        if rain.istation is not None:
            istat = xp.asarray(rain.istation)
            step = 1
            while step < len(rain.unidata) - 1 and rain.unidata[step].time < loop.totaltime:
                step += 1
            dt_f = rain.unidata[step].time - rain.unidata[step-1].time
            t_el = loop.totaltime - rain.unidata[step-1].time
            frac = t_el / dt_f if dt_f > 0 else 0.0
            
            r_now = xp.asarray(rain.multi_val[step])
            r_prev = xp.asarray(rain.multi_val[step-1])
            r_interp = r_prev + (r_now - r_prev) * frac
            
            rain_ms_all = r_interp[istat[idx.interior]]
            adv.dh[idx.interior] = xp.where(valid_mask, adv.dh[idx.interior] + rain_ms_all, adv.dh[idx.interior])



def add_windforcing_cpu(param, blocks, uwind, vwind, adv):
    """
    Thêm ứng suất gió vào dhu, dhv.
    """
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth
    rhoairrhowater = 0.00121951  # rho(air)/rho(water)

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):
                i = memloc(halowidth, blkmemwidth, ix, iy, ib)
                delta = calcres(param.dx, blocks.level[ib])

                x = param.xo + blocks.xo[ib] + ix * delta
                y = param.yo + blocks.yo[ib] + iy * delta

                if uwind.uniform:
                    uwindi = uwind.nowvalue
                else:
                    # TODO: interp2BUQ cho spatial wind
                    uwindi = uwind.nowvalue

                if vwind.uniform:
                    vwindi = vwind.nowvalue
                else:
                    vwindi = vwind.nowvalue

                adv.dhu[i] += rhoairrhowater * param.Cd * uwindi * abs(uwindi)
                adv.dhv[i] += rhoairrhowater * param.Cd * vwindi * abs(vwindi)


def add_river_forcing(param, loop, rivers, model):
    """
    Thêm lưu lượng sông vào dh.
    """
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for river in rivers:
        if not river.flow_input:
            continue

        # Nội suy lưu lượng theo thời gian
        bndstep = 0
        while (bndstep < len(river.flow_input) - 1 and
               river.flow_input[bndstep].time - loop.totaltime <= 0.0):
            bndstep += 1

        prev_step = max(bndstep - 1, 0)
        dt_bnd = river.flow_input[bndstep].time - river.flow_input[prev_step].time
        t_elapsed = loop.totaltime - river.flow_input[prev_step].time

        qnow = interptime(
            river.flow_input[bndstep].q,
            river.flow_input[prev_step].q,
            dt_bnd, t_elapsed
        )

        # Inject vào các block chứa sông
        for ibl in range(param.nblk):
            ib = model.blocks.active[ibl]
            for iy in range(param.blkwidth):
                for ix in range(param.blkwidth):
                    i = memloc(halowidth, blkmemwidth, ix, iy, ib)
                    delta = calcres(param.dx, model.blocks.level[ib])

                    x = param.xo + model.blocks.xo[ib] + ix * delta
                    y = param.yo + model.blocks.yo[ib] + iy * delta

                    if (river.xstart <= x <= river.xend and
                            river.ystart <= y <= river.yend):
                        if river.disarea > 0:
                            model.adv.dh[i] += qnow / river.disarea

def apply_infiltration_cpu(il_map, cl_map, evolv, dt: float, h_threshold: float = 0.05, adv_dh=None):
    """
    Áp dụng thấm (Initial + Continuous Loss) trên CPU sử dụng bản đồ không gian.
    Bổ sung h_threshold: Nếu nước sâu hơn ngưỡng này (lòng sông/dòng chảy tập trung), chặn thấm.
    """
    h = evolv.h
    cum = evolv.cum_infilt
    zs = evolv.zs
    
    # 1. Chuyển đổi đơn vị mảng (mm -> m, mm/h -> m/step)
    il_m = il_map / 1000.0
    cl_ms = cl_map / 1000.0 / 3600.0
    cl_step = cl_ms * dt
    
    # 2. Tính lượng thấm tiềm năng
    rem_il = np.maximum(0.0, il_m - cum)
    total_pot = cl_step + rem_il
    
    # CHẶN THẤM: Nếu h > h_threshold, coi như dòng chảy đã bão hòa địa phương, infilt = 0
    infilt_mask = (h < h_threshold).astype(float)
    potential_masked = total_pot * infilt_mask

    actual_infilt = np.minimum(h, potential_masked)

    # 3. Cập nhật cum_infilt - luôn thực hiện
    infilt_to_il = np.maximum(0.0, actual_infilt - cl_step)
    cum += infilt_to_il

    if adv_dh is not None:
        # AN TOAN: Ghi vao sink term cua flux divergence, khong sua h truc tiep
        adv_dh -= actual_infilt / dt
    else:
        h -= actual_infilt
        zs -= actual_infilt


def apply_infiltration_gpu(il_map, cl_map, evolv, dt: float, h_threshold: float = 0.05, adv_dh=None):
    """
    Áp dụng thấm (Initial + Continuous Loss) trên GPU sử dụng bản đồ không gian.
    Bổ sung h_threshold: Nếu nước sâu hơn ngưỡng này, chặn thấm.
    """
    from .gpu_backend import xp
    h = evolv.h
    cum = evolv.cum_infilt
    zs = evolv.zs

    # 1. Chuyển đổi đơn vị mảng (mm -> m, mm/h -> m/step)
    il_m = il_map / 1000.0
    cl_ms = cl_map / 1000.0 / 3600.0
    cl_step = cl_ms * dt

    # 2. Tính lượng thấm tiềm năng
    rem_il = xp.maximum(0.0, il_m - cum)
    total_pot = cl_step + rem_il
    
    # CHẶN THẤM: Nếu h > h_threshold, infilt = 0
    infilt_mask = (h < h_threshold).astype(float)
    potential_masked = total_pot * infilt_mask

    actual_infilt = xp.minimum(h, potential_masked)

    # 3. Cập nhật cum_infilt - luon thuc hien
    infilt_to_il = xp.maximum(0.0, actual_infilt - cl_step)
    cum += infilt_to_il

    if adv_dh is not None:
        # AN TOAN: Ghi vao sink term, tranh bi ghi de trong Corrector step
        adv_dh -= actual_infilt / dt
    else:
        h -= actual_infilt
        zs -= actual_infilt
def add_river_vec(idx, param, loop, rivers, adv, blocks):
    from .gpu_backend import xp
    from .utils import memloc, calcres, interptime
    import numpy as np
    
    for river in rivers:
        if not river.flow_input:
            continue
            
        bndstep = 0
        while (bndstep < len(river.flow_input) - 1 and
               river.flow_input[bndstep].time - loop.totaltime <= 0.0):
            bndstep += 1

        prev_step = max(bndstep - 1, 0)
        dt_bnd = river.flow_input[bndstep].time - river.flow_input[prev_step].time
        t_elapsed = loop.totaltime - river.flow_input[prev_step].time

        qnow = interptime(
            river.flow_input[bndstep].q,
            river.flow_input[prev_step].q,
            dt_bnd, t_elapsed
        )
        
        if not hasattr(river, 'gpu_mask'):
            mask = np.zeros(param.blkmemwidth**2 * param.nblkmem, dtype=bool)
            area = 0.0
            for ibl in range(param.nblk):
                ib = blocks.active[ibl]
                delta = calcres(param.dx, blocks.level[ib])
                xo = param.xo + blocks.xo[ib]
                yo = param.yo + blocks.yo[ib]
                
                for iy in range(param.blkwidth):
                    cy = yo + (iy + 0.5) * delta
                    y_min = min(river.ystart, river.yend)
                    y_max = max(river.ystart, river.yend)
                    if cy + delta/2 < y_min or cy - delta/2 > y_max:
                        continue
                    for ix in range(param.blkwidth):
                        cx = xo + (ix + 0.5) * delta
                        x_min = min(river.xstart, river.xend)
                        x_max = max(river.xstart, river.xend)
                        if cx + delta/2 >= x_min and cx - delta/2 <= x_max:
                            cell_idx = memloc(param.halowidth, param.blkmemwidth, ix, iy, ib)
                            mask[cell_idx] = True
                            area += delta * delta
            
            from .gpu_backend import to_device
            river.gpu_mask = to_device(mask)
            river.disarea = area
            print(f"River initialized: disarea = {river.disarea} m2")
            
        if river.disarea <= 0:
            continue
            
        dh_inc = qnow / river.disarea
        adv.dh[river.gpu_mask] += dh_inc
