"""
Friction module Ma sát đáy trong mô hình nước nông 2D.

Bao gồm:
    - Ma sát tuyến tính (cf cố định)
    - Smart friction (log-law)
    - Manning friction
    - Xia & Lang (2018) friction scheme
"""

import numpy as np
import math
from .param import Param
from .model import BlockP, EvolvingP
from .utils import memloc


# ============================================================
# SMART FRICTION (log-law formulation)
# ============================================================

def smart_friction(h: float, zo: float) -> float:
    """
    Smart friction formulation theo BG_Flood.

    zo: độ nhám đáy (roughness length)
    h : chiều sâu nước

    cf được tính theo công thức log-law:
        cf = [1 / (2.5 (ln(H/zo) - 1 + 1.359/H))]^2
    """
    if h <= 0.0:
        return 0.0

    Hbar = h / zo
    e = math.e

    if Hbar <= e:
        cfi = 1.0 / (0.46 * Hbar)
    else:
        cfi = 1.0 / (2.5 * (math.log(Hbar) - 1.0 + 1.359 / Hbar))

    return cfi * cfi


# ============================================================
# MANNING FRICTION
# ============================================================

def manning_friction(g: float, h: float, n: float) -> float:
    """
    Manning friction:
        cf = g * n^2 / h^(1/3)
    """
    if h <= 0.0:
        return 0.0

    return g * n * n / (h ** (1.0 / 3.0))


# ============================================================
# BOTTOM FRICTION (Semi-Implicit scheme)
# ============================================================

def bottom_friction_cpu(param: Param,
                        blocks: BlockP,
                        dt: float,
                        cf: np.ndarray,
                        evolv: EvolvingP):
    """
    Áp dụng ma sát đáy theo dạng bán ẩn (semi-implicit).

    Phương trình:
        du/dt = -cf |U| / h * u

    Nghiệm rời rạc:
        u_new = u / (1 + cf |U| dt / h)
    """

    eps = param.eps
    g = param.g
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]

        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):

                i = memloc(halowidth, blkmemwidth, ix, iy, ib)

                hi = evolv.h[i]
                if hi <= eps:
                    continue

                ui = evolv.u[i]
                vi = evolv.v[i]

                normu = math.sqrt(ui * ui + vi * vi)

                # --- Chọn mô hình ma sát ---
                if param.frictionmodel == 0:
                    cfi = cf[i]

                elif param.frictionmodel == 1:
                    cfi = smart_friction(hi, cf[i])

                elif param.frictionmodel == -1:
                    cfi = manning_friction(g, hi, cf[i])

                else:
                    cfi = cf[i]

                tb = cfi * normu / hi * dt

                evolv.u[i] = ui / (1.0 + tb)
                evolv.v[i] = vi / (1.0 + tb)


# ============================================================
# XIA & LANG (2018) FRICTION SCHEME
# ============================================================

def xia_friction_cpu(param: Param,
                     blocks: BlockP,
                     dt: float,
                     cf: np.ndarray,
                     evolv: EvolvingP,
                     evolv_o: EvolvingP):
    """
    Ma sát đáy theo Xia & Lang (2018)
    https://doi.org/10.1016/j.advwatres.2018.05.004

    Chính xác hơn khi dòng chảy mạnh.
    """

    eps = param.eps
    g = param.g
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]

        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):

                i = memloc(halowidth, blkmemwidth, ix, iy, ib)

                ho = evolv.h[i]
                hi = evolv_o.h[i]

                if hi <= eps:
                    continue

                ui = evolv_o.u[i]
                vi = evolv_o.v[i]
                normu = math.sqrt(ui * ui + vi * vi)

                # --- Chọn mô hình ma sát ---
                if param.frictionmodel == 0:
                    cfi = cf[i]

                elif param.frictionmodel == 1:
                    cfi = smart_friction(hi, cf[i])

                elif param.frictionmodel == -1:
                    cfi = manning_friction(g, hi, cf[i])

                else:
                    cfi = cf[i]

                tb = cfi * normu * hi / (ho * ho) * dt

                if tb >= 1e-10:
                    factor = math.sqrt(1.0 + 4.0 * tb)

                    evolv_o.u[i] = (
                        ui - ui * factor
                    ) / (-2.0 * tb)

                    evolv_o.v[i] = (
                        vi - vi * factor
                    ) / (-2.0 * tb)