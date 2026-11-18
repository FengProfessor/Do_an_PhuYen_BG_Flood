
"""
Thực hiện giải hệ phương trình nước nông 2D (Shallow Water Equations)
bằng sơ đồ Kurganov-Petrova với phương pháp Predictor-Corrector.
"""
import math
import numpy as np
from .halo import fill_halo, fill_halo_flux
from .gradients import gradient_cpu
from .kurganov import update_kurg_x_cpu, update_kurg_y_cpu
from .advection import update_ev_cpu, adv_kernel_cpu, cleanup_cpu
from .friction import bottom_friction_cpu
from .updateforcing import (
    add_rainforcing_cpu,
    add_windforcing_cpu,
    add_river_forcing,
    apply_infiltration_cpu
)
from .utils import memloc


# ============================================================
# Khởi tạo lại mảng dtmax (Reset bước thời gian cực đại)
# ============================================================

def init_array_buq(param, blocks, value, arr):
    """
    Gán giá trị ban đầu cho mảng dtmax

    """

    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]

        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):

                i = memloc(halowidth, blkmemwidth, ix, iy, ib)
                arr[i] = value


# ============================================================
# Tính bước thời gian theo điều kiện CFL
# ============================================================

def calc_timestep_cpu(param, loop, blocks, time_obj):
    """
    Tìm bước thời gian nhỏ nhất trong toàn miền tính toán

    """

    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    dtmin = loop.hugeposval

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]

        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):

                i = memloc(halowidth, blkmemwidth, ix, iy, ib)

                if time_obj.dtmax[i] < dtmin:
                    dtmin = time_obj.dtmax[i]

    return dtmin


# ============================================================
# Hàm chính giải bài toán dòng chảy
# ============================================================

def flow_cpu(param, loop, forcing, model):

    # ========================================================
    # BƯỚC DỰ BÁO (Predictor Step)
    # ========================================================

    # 1. Điền giá trị halo phục vụ tái cấu trúc gradient
    fill_halo(param, model.blocks, model.evolv, model.zb)

    # 2. Khởi tạo lại dtmax
    init_array_buq(param,
                   model.blocks,
                   loop.hugeposval,
                   model.time.dtmax)

    # 3. Tính gradient bằng limiter (minmod)
    gradient_cpu(param,
                 model.blocks,
                 model.evolv,
                 model.grad,
                 model.zb)

    # 4. Tái cấu trúc thông lượng theo phương X
    update_kurg_x_cpu(param,
                      model.blocks,
                      model.evolv,
                      model.grad,
                      model.flux,
                      model.time.dtmax,
                      model.zb)

    # 5. Tái cấu trúc thông lượng theo phương Y
    update_kurg_y_cpu(param,
                      model.blocks,
                      model.evolv,
                      model.grad,
                      model.flux,
                      model.time.dtmax,
                      model.zb)

    # 6. Điền halo cho thông lượng (fine → coarse)
    fill_halo_flux(param,
                   model.blocks,
                   model.flux)

    # 7. Tính bước thời gian theo CFL
    loop.dt = float(
        calc_timestep_cpu(param,
                          loop,
                          model.blocks,
                          model.time)
    )
# Guard against runaway dt in fully-dry starts (common in rain-only cases).
    remaining = max(param.endtime - loop.totaltime, 0.0)
    dt_cap = remaining
    if param.outputtimestep > 0.0:
        dt_cap = min(dt_cap, param.outputtimestep)

    # Use user-defined dt limit from config if available (e.g. dt = 2.0)
    if param.dt > 0.0:
        dt_cap = min(dt_cap, param.dt)


    dry_domain = np.max(model.evolv.h[model.block_index.interior]) <= param.eps
    if dry_domain:
        dt_cap = min(dt_cap, 60.0)


    if not math.isfinite(loop.dt) or loop.dt <= 0.0:
        loop.dt = dt_cap if dt_cap > 0.0 else 0.0
    else:
        loop.dt = min(loop.dt, dt_cap)


    loop.dtmax = loop.dt
    model.time.dt = loop.dt

    # 8. Tính các đại lượng gia tăng (dh, dhu, dhv)
    update_ev_cpu(param,
                  model.blocks,
                  model.evolv,
                  model.flux,
                  model.adv)

    # 9. Bổ sung các tác động ngoại lực:
    if forcing.Rain.inputfile:
        add_rainforcing_cpu(param, loop,
                            model.blocks,
                            forcing.Rain,
                            model.adv,
                            model.zb)

    # 10. Infiltration
    if param.il > 0.0 or param.cl > 0.0 or param.ilfile or param.clfile:
        apply_infiltration_cpu(model.il, model.cl, model.evolv, loop.dt * 0.5)

    if forcing.UWind.inputfile:
        add_windforcing_cpu(param,
                            model.blocks,
                            forcing.UWind,
                            forcing.VWind,
                            model.adv)

    if len(forcing.rivers) > 0:
        add_river_forcing(param,
                          loop,
                          forcing.rivers,
                          model)

    # 10. Cập nhật nghiệm tại nửa bước thời gian (dt/2)
    adv_kernel_cpu(param,
                   model.blocks,
                   model.time.dt * 0.5,
                   model.zb,
                   model.evolv,
                   model.adv,
                   model.evolv_o)

    # ========================================================
    # BƯỚC HIỆU CHỈNH (Corrector Step)
    # ========================================================

    # 11. Điền lại halo cho nghiệm trung gian
    fill_halo(param,
              model.blocks,
              model.evolv_o,
              model.zb)

    # 12. Tính lại gradient
    gradient_cpu(param,
                 model.blocks,
                 model.evolv_o,
                 model.grad,
                 model.zb)

    # 13. Tính lại thông lượng theo phương X
    update_kurg_x_cpu(param,
                      model.blocks,
                      model.evolv_o,
                      model.grad,
                      model.flux,
                      model.time.dtmax,
                      model.zb)

    # 14. Tính lại thông lượng theo phương Y
    update_kurg_y_cpu(param,
                      model.blocks,
                      model.evolv_o,
                      model.grad,
                      model.flux,
                      model.time.dtmax,
                      model.zb)

    # 15. Điền halo cho thông lượng
    fill_halo_flux(param,
                   model.blocks,
                   model.flux)

    # 16. Tính lại gia tăng
    update_ev_cpu(param,
                  model.blocks,
                  model.evolv_o,
                  model.flux,
                  model.adv)

    # 17. Bổ sung ngoại lực lần hai
    if forcing.Rain.inputfile:
        add_rainforcing_cpu(param, loop,
                            model.blocks,
                            forcing.Rain,
                            model.adv,
                            model.zb)

    # 10. Infiltration
    if param.il > 0.0 or param.cl > 0.0 or param.ilfile or param.clfile:
        apply_infiltration_cpu(model.il, model.cl, model.evolv, loop.dt)

    if forcing.UWind.inputfile:
        add_windforcing_cpu(param,
                            model.blocks,
                            forcing.UWind,
                            forcing.VWind,
                            model.adv)

    if len(forcing.rivers) > 0:
        add_river_forcing(param,
                          loop,
                          forcing.rivers,
                          model)

    # 18. Cập nhật nghiệm tại bước thời gian đầy đủ (dt)
    adv_kernel_cpu(param,
                   model.blocks,
                   model.time.dt,
                   model.zb,
                   model.evolv,
                   model.adv,
                   model.evolv_o)

    # 19. Bổ sung ma sát đáy (Bottom friction)
    bottom_friction_cpu(param,
                        model.blocks,
                        model.time.dt,
                        model.cf,
                        model.evolv_o)

    # 20. Sao chép nghiệm mới về biến chính
    cleanup_cpu(param,
                model.blocks,
                model.evolv_o,
                model.evolv)
