"""
Gradient computation using minmod limiter.
"""

import numpy as np
from .param import Param
from .model import BlockP, EvolvingP, GradientsP
from .utils import calcres, memloc, minmod2


# ============================================================
# MAIN WRAPPER (giống gradientCPU)
# ============================================================

def gradient_cpu(param: Param,
                 blocks: BlockP,
                 evolv: EvolvingP,
                 grad: GradientsP,
                 zb: np.ndarray):
    """
    Tính gradient cho tất cả biến tiến hóa.
    """

    _compute_gradient(param, blocks, evolv.h,  grad.dhdx,  grad.dhdy)
    _compute_gradient(param, blocks, evolv.zs, grad.dzsdx, grad.dzsdy)
    _compute_gradient(param, blocks, evolv.u,  grad.dudx,  grad.dudy)
    _compute_gradient(param, blocks, evolv.v,  grad.dvdx,  grad.dvdy)

    # --- bảo toàn cao độ nếu bật ---
    if param.conserve_elevation:
        _conserve_elevation(param, blocks, evolv, grad)


# ============================================================
# CORE GRADIENT (giống kernel gradient)
# ============================================================

def _compute_gradient(param: Param,
                      blocks: BlockP,
                      a: np.ndarray,
                      dadx: np.ndarray,
                      dady: np.ndarray):

    theta = param.theta
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for ibl in range(param.nblk):

        ib = blocks.active[ibl]
        lev = blocks.level[ib]
        delta = calcres(param.dx, lev)

        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):

                i = memloc(halowidth, blkmemwidth, ix, iy, ib)

                a_l = a[memloc(halowidth, blkmemwidth, ix - 1, iy, ib)]
                a_r = a[memloc(halowidth, blkmemwidth, ix + 1, iy, ib)]
                a_b = a[memloc(halowidth, blkmemwidth, ix, iy - 1, ib)]
                a_t = a[memloc(halowidth, blkmemwidth, ix, iy + 1, ib)]
                a_i = a[i]

                dadx[i] = minmod2(theta, a_l, a_i, a_r) / delta
                dady[i] = minmod2(theta, a_b, a_i, a_t) / delta


# ============================================================
# CONSERVE ELEVATION (giống conserveElevationGradHalo)
# ============================================================

def _conserve_elevation(param: Param,
                        blocks: BlockP,
                        evolv: EvolvingP,
                        grad: GradientsP):
    """
    Đảm bảo:
        zs = zb + h
    nên gradient zs phải phù hợp với gradient h.
    """

    for ibl in range(param.nblk):

        ib = blocks.active[ibl]

        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):

                i = memloc(param, ix, iy, ib)

                grad.dzsdx[i] = grad.dhdx[i]
                grad.dzsdy[i] = grad.dhdy[i]