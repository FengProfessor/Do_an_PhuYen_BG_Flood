"""
Advection kernel - cập nhật các biến tiến hóa.
"""

import numpy as np
import math
from .param import Param
from .model import BlockP, EvolvingP, FluxP, AdvanceP
from .utils import calcres, memloc

PI = 3.14159265


def update_ev_cpu(param: Param, blocks: BlockP, evolv: EvolvingP,
                  flux: FluxP, adv: AdvanceP):
    """
    Tính các đại lượng gia tăng (dh, dhu, dhv) từ flux.
    """
    g = param.g
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        delta = calcres(param.dx, blocks.level[ib])

        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):
                # Coriolis parameter: f = 2 * omega * sin(lat)
                # 2 * omega = pi / 21600
                lat_rad = param.lat * PI / 180.0
                fc = math.sin(lat_rad) * PI / 21600.0

                i = memloc(halowidth, blkmemwidth, ix, iy, ib)
                iright = memloc(halowidth, blkmemwidth, ix + 1, iy, ib)
                itop = memloc(halowidth, blkmemwidth, ix, iy + 1, ib)

                cm = 1.0
                fmu = 1.0
                fmv = 1.0

                hi = evolv.h[i]
                uui = evolv.u[i]
                vvi = evolv.v[i]

                cmdinv = 1.0 / (cm * delta)
                ga = 0.5 * g

                adv.dh[i] = -1.0 * (flux.Fhu[iright] - flux.Fhu[i] +
                                     flux.Fhv[itop] - flux.Fhv[i]) * cmdinv

                dmdl = 0.0  # (fmu - fmu) / (cm * delta) = 0 nếu không dùng spherical
                dmdt = 0.0
                fG = vvi * dmdl - uui * dmdt

                adv.dhu[i] = (flux.Fqux[i] + flux.Fquy[i] -
                              flux.Su[iright] - flux.Fquy[itop]) * cmdinv + fc * hi * vvi

                adv.dhv[i] = (flux.Fqvy[i] + flux.Fqvx[i] -
                              flux.Sv[itop] - flux.Fqvx[iright]) * cmdinv - fc * hi * uui

                adv.dhu[i] += hi * (ga * hi * dmdl + fG * vvi)
                adv.dhv[i] += hi * (ga * hi * dmdt - fG * uui)


def adv_kernel_cpu(param: Param, blocks: BlockP, dt: float, zb: np.ndarray,
                   evolv: EvolvingP, adv: AdvanceP, evolv_o: EvolvingP):
    """
    Cập nhật biến tiến hóa theo bước thời gian dt.
    """
    eps = param.eps
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]

        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):
                i = memloc(halowidth, blkmemwidth, ix, iy, ib)

                hold = evolv.h[i]
                ho = hold + dt * adv.dh[i]

                if ho > eps:
                    uo = (hold * evolv.u[i] + dt * adv.dhu[i]) / ho
                    vo = (hold * evolv.v[i] + dt * adv.dhv[i]) / ho
                else:
                    ho = max(ho, 0.0)
                    uo = 0.0
                    vo = 0.0

                evolv_o.h[i] = ho
                evolv_o.u[i] = uo
                evolv_o.v[i] = vo
                evolv_o.zs[i] = zb[i] + ho


def cleanup_cpu(param: Param, blocks: BlockP, evolv_o: EvolvingP, evolv: EvolvingP):
    """
    Sao chép biến đã cập nhật về biến chính.
    """
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):
                i = memloc(halowidth, blkmemwidth, ix, iy, ib)
                evolv.h[i] = evolv_o.h[i]
                evolv.u[i] = evolv_o.u[i]
                evolv.v[i] = evolv_o.v[i]
                evolv.zs[i] = evolv_o.zs[i]
