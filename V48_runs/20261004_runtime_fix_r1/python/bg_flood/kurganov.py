"""
Thuật toán Kurganov-Petrova cho phương trình nước nông.

Dựa trên: Kurganov, A., Petrova, G. (2007).
"A second-order well-balanced positivity preserving central-upwind scheme
for the Saint-Venant system."
"""

import numpy as np
import math
from .param import Param
from .model import BlockP, EvolvingP, GradientsP, FluxP
from .utils import calcres, memloc, sq


def kurg_solver(g, delta, epsi, CFL, cm, fm, hp, hm, up, um):
    """
    Bộ giải Riemann gần đúng Kurganov.
    
    Trả về: (dt, fh, fu)
    """
    cp = math.sqrt(g * hp)
    cmo = math.sqrt(g * hm)

    ap = max(max(up + cp, um + cmo), 0.0)
    am = min(min(up - cp, um - cmo), 0.0)

    if ap - am == 0:
        return 1.0 / epsi, 0.0, 0.0

    ad = 1.0 / (ap - am)

    qm = hm * um
    qp = hp * up

    hm2 = hm * hm
    hp2 = hp * hp
    a = max(ap, -am)
    ga = g * 0.5
    apm = ap * am
    dlt = delta * cm / fm

    if a > epsi:
        fh = (ap * qm - am * qp + apm * (hp - hm)) * ad
        fu = (ap * (qm * um + ga * hm2) - am * (qp * up + ga * hp2) + apm * (qp - qm)) * ad
        dt = CFL * dlt / a
    else:
        fh = 0.0
        fu = 0.0
        dt = 1.0 / epsi

    return dt, fh, fu


def update_kurg_x_cpu(param: Param, blocks: BlockP, evolv: EvolvingP,
                      grad: GradientsP, flux: FluxP, dtmax: np.ndarray, zb: np.ndarray):
    """
    Tính flux theo hướng X (Kurganov scheme).
    """
    g = param.g
    CFL = param.CFL
    epsi = np.finfo(np.float64).eps
    eps = param.eps + epsi
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        lev = blocks.level[ib]
        delta = calcres(param.dx, lev)

        # Hàng xóm cho source term
        RB = blocks.RightBot[ib]
        levRB = blocks.level[RB]
        LBRB = blocks.LeftBot[RB]
        LB = blocks.LeftBot[ib]
        levLB = blocks.level[LB]
        RBLB = blocks.RightBot[LB]

        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth + halowidth):
                i = memloc(halowidth, blkmemwidth, ix, iy, ib)
                ileft = memloc(halowidth, blkmemwidth, ix - 1, iy, ib)

                dhdxi = grad.dhdx[i]
                dhdxmin = grad.dhdx[ileft]
                cm = 1.0
                fmu = 1.0

                hi = evolv.h[i]
                hn = evolv.h[ileft]

                if hi > eps or hn > eps:
                    dx = delta * 0.5
                    zi = evolv.zs[i] - hi
                    zl = zi - dx * (grad.dzsdx[i] - dhdxi)
                    zn = evolv.zs[ileft] - hn
                    zr = zn + dx * (grad.dzsdx[ileft] - dhdxmin)
                    zlr = max(zl, zr)

                    hl = hi - dx * dhdxi
                    up_val = evolv.u[i] - dx * grad.dudx[i]
                    hp = max(0.0, hl + zl - zlr)

                    hr = hn + dx * dhdxmin
                    um_val = evolv.u[ileft] + dx * grad.dudx[ileft]
                    hm = max(0.0, hr + zr - zlr)

                    ga = g * 0.5

                    dt, fh, fu = kurg_solver(g, delta, epsi, CFL, cm, fmu, hp, hm, up_val, um_val)

                    if dt < dtmax[i]:
                        dtmax[i] = dt
                    else:
                        dtmax[i] = 1.0 / epsi

                    if fh > 0.0:
                        fv = (evolv.v[ileft] + dx * grad.dvdx[ileft]) * fh
                    else:
                        fv = (evolv.v[i] - dx * grad.dvdx[i]) * fh

                    # Topographic source term (fine/coarse)
                    hi_src = hi
                    zi_src = zi
                    hn_src = hn
                    zn_src = zn

                    if ix == param.blkwidth and levRB < lev:
                        jj = int(iy * 0.5) if LBRB == ib else int(iy * 0.5) + param.blkwidth // 2
                        iright = memloc(halowidth, blkmemwidth, 0, jj, RB)
                        hi_src = evolv.h[iright]
                        zi_src = zb[iright]

                    if ix == 0 and levLB < lev:
                        jj = int(iy * 0.5) if RBLB == ib else int(iy * 0.5) + param.blkwidth // 2
                        ilc = memloc(halowidth, blkmemwidth, param.blkwidth - 1, jj, LB)
                        hn_src = evolv.h[ilc]
                        zn_src = zb[ilc]

                    sl = ga * (sq(hp) - sq(hl) + (hl + hi_src) * (zi_src - zl))
                    sr = ga * (sq(hm) - sq(hr) + (hr + hn_src) * (zn_src - zr))

                    flux.Fhu[i] = fmu * fh
                    flux.Fqux[i] = fmu * (fu - sl)
                    flux.Su[i] = fmu * (fu - sr)
                    flux.Fqvx[i] = fmu * fv
                else:
                    dtmax[i] = 1.0 / epsi
                    flux.Fhu[i] = 0.0
                    flux.Fqux[i] = 0.0
                    flux.Su[i] = 0.0
                    flux.Fqvx[i] = 0.0


def update_kurg_y_cpu(param: Param, blocks: BlockP, evolv: EvolvingP,
                      grad: GradientsP, flux: FluxP, dtmax: np.ndarray, zb: np.ndarray):
    """
    Tính flux theo hướng Y (Kurganov scheme).
    """
    g = param.g
    CFL = param.CFL
    epsi = np.finfo(np.float64).eps
    eps = param.eps + epsi
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        lev = blocks.level[ib]
        delta = calcres(param.dx, lev)

        # Hàng xóm cho source term
        TL = blocks.TopLeft[ib]
        levTL = blocks.level[TL]
        BLTL = blocks.BotLeft[TL]
        BL = blocks.BotLeft[ib]
        levBL = blocks.level[BL]
        TLBL = blocks.TopLeft[BL]

        for iy in range(param.blkwidth + halowidth):
            for ix in range(param.blkwidth):
                i = memloc(halowidth, blkmemwidth, ix, iy, ib)
                ibot = memloc(halowidth, blkmemwidth, ix, iy - 1, ib)

                dhdyi = grad.dhdy[i]
                dhdymin = grad.dhdy[ibot]
                cm = 1.0
                fmv = 1.0

                hi = evolv.h[i]
                hn = evolv.h[ibot]

                if hi > eps or hn > eps:
                    dx = delta * 0.5
                    zi = evolv.zs[i] - hi
                    zl = zi - dx * (grad.dzsdy[i] - dhdyi)
                    zn = evolv.zs[ibot] - hn
                    zr = zn + dx * (grad.dzsdy[ibot] - dhdymin)
                    zlr = max(zl, zr)

                    hl = hi - dx * dhdyi
                    up_val = evolv.v[i] - dx * grad.dvdy[i]
                    hp = max(0.0, hl + zl - zlr)

                    hr = hn + dx * dhdymin
                    um_val = evolv.v[ibot] + dx * grad.dvdy[ibot]
                    hm = max(0.0, hr + zr - zlr)

                    ga = g * 0.5

                    dt, fh, fu = kurg_solver(g, delta, epsi, CFL, cm, fmv, hp, hm, up_val, um_val)

                    if dt < dtmax[i]:
                        dtmax[i] = dt

                    if fh > 0.0:
                        fv = (evolv.u[ibot] + dx * grad.dudy[ibot]) * fh
                    else:
                        fv = (evolv.u[i] - dx * grad.dudy[i]) * fh

                    # Topographic source term
                    hi_src = hi
                    zi_src = zi
                    hn_src = hn
                    zn_src = zn

                    if iy == param.blkwidth and levTL < lev:
                        ii = int(ix * 0.5) if BLTL == ib else int(ix * 0.5) + param.blkwidth // 2
                        itop = memloc(halowidth, blkmemwidth, ii, 0, TL)
                        hi_src = evolv.h[itop]
                        zi_src = zb[itop]

                    if iy == 0 and levBL < lev:
                        ii = int(ix * 0.5) if TLBL == ib else int(ix * 0.5) + param.blkwidth // 2
                        ibc = memloc(halowidth, blkmemwidth, ii, param.blkwidth - 1, BL)
                        hn_src = evolv.h[ibc]
                        zn_src = zb[ibc]

                    sl = ga * (sq(hp) - sq(hl) + (hl + hi_src) * (zi_src - zl))
                    sr = ga * (sq(hm) - sq(hr) + (hr + hn_src) * (zn_src - zr))

                    flux.Fhv[i] = fmv * fh
                    flux.Fqvy[i] = fmv * (fu - sl)
                    flux.Sv[i] = fmv * (fu - sr)
                    # Transverse flux (U-momentum carried by V-direction): Fquy only
                    flux.Fquy[i] = fmv * fv
                else:
                    flux.Fhv[i] = 0.0
                    flux.Fqvy[i] = 0.0
                    flux.Sv[i] = 0.0
                    flux.Fquy[i] = 0.0
