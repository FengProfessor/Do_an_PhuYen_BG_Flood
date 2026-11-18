"""
Khởi tạo biến tiến hóa (Init Evolving Variables).

Chứa cold_start() và warm_start().
"""

import math
import numpy as np
from .param import Param
from .model import EvolvingP, BlockP
from .forcing import Forcing
from .utils import calcres, memloc, interptime


def cold_start(param: Param, blocks: BlockP, zb: np.ndarray, evolv: EvolvingP):
    """
    Khởi tạo lạnh: đặt mực nước ban đầu từ zsinit.
    """
    zz_init = 0.0 if math.isnan(param.zsinit) else param.zsinit
    zz_offset = 0.0 if math.isnan(param.zsoffset) else param.zsoffset

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        for j in range(param.blkwidth):
            for i in range(param.blkwidth):
                n = memloc(param.halowidth, param.blkmemwidth, i, j, ib)
                evolv.u[n] = 0.0
                evolv.v[n] = 0.0
                # Đảm bảo zs không bị kéo lên theo zb nếu zb là "núi ảo" nodata 
                # (mặc dù đã xử lý trong interpolate_bathy, đây là lớp bảo vệ thứ 2)
                if zb[n] >= param.mask - 1.0:
                    evolv.zs[n] = zb[n]
                    evolv.h[n] = 0.0
                else:
                    evolv.zs[n] = max(zz_init + zz_offset, zb[n])
                    evolv.h[n] = max(evolv.zs[n] - zb[n], 0.0)


def _get_bnd_zs_at_time(side_data, totaltime):
    """
    Nội suy mực nước biên tại thời điểm totaltime từ chuỗi thời gian biên.
    """
    if not side_data or len(side_data) < 2:
        if side_data and side_data[0].wlevs:
            return side_data[0].wlevs
        return [0.0]

    sl_step = 1
    while sl_step < len(side_data) - 1 and side_data[sl_step].time < totaltime:
        sl_step += 1

    zsbndvec = []
    for k in range(len(side_data[sl_step].wlevs)):
        dt_bnd = side_data[sl_step].time - side_data[sl_step - 1].time
        t_elapsed = totaltime - side_data[sl_step - 1].time
        zsbndvec.append(interptime(
            side_data[sl_step].wlevs[k],
            side_data[sl_step - 1].wlevs[k],
            dt_bnd, t_elapsed
        ))
    return zsbndvec


def _interp_bnd_spatial(zsbndvec, frac):
    """Nội suy không gian trên biên (nếu có nhiều node biên)."""
    if len(zsbndvec) == 1:
        return zsbndvec[0]
    iprev = min(max(int(math.floor(frac * (len(zsbndvec) - 1))), 0), len(zsbndvec) - 2)
    inext = iprev + 1
    return interptime(zsbndvec[inext], zsbndvec[iprev], 1.0,
                      frac * (len(zsbndvec) - 1) - iprev)


def warm_start(param: Param, forcing: Forcing, blocks: BlockP, zb: np.ndarray, evolv: EvolvingP):
    """
    Khởi tạo ấm: nội suy mực nước từ điều kiện biên bằng nghịch đảo khoảng cách.
  
    """
    totaltime = param.totaltime

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        for j in range(param.blkwidth):
            for i in range(param.blkwidth):
                n = memloc(param.halowidth, param.blkmemwidth, i, j, ib)
                levdx = calcres(param.dx, blocks.level[ib])
                xi = param.xo + blocks.xo[ib] + i * levdx
                yi = param.yo + blocks.yo[ib] + j * levdx

                disttop = max((param.ymax - yi) / levdx, 0.1)
                distbot = max((yi - param.yo) / levdx, 0.1)
                distleft = max((xi - param.xo) / levdx, 0.1)
                distright = max((param.xmax - xi) / levdx, 0.1)

                # Tỷ lệ vị trí (dùng cho nội suy không gian trên biên)
                jj = (yi - param.yo) / (param.ymax - param.yo) if param.ymax > param.yo else 0.0
                ii = (xi - param.xo) / (param.xmax - param.xo) if param.xmax > param.xo else 0.0

                zsleft = 0.0
                zsright = 0.0
                zstop = 0.0
                zsbot = 0.0
                lefthere = 0.0
                righthere = 0.0
                tophere = 0.0
                bothere = 0.0

                if forcing.left.on and forcing.left.data:
                    lefthere = 1.0
                    zsbndvec = _get_bnd_zs_at_time(forcing.left.data, totaltime)
                    zsleft = _interp_bnd_spatial(zsbndvec, jj)

                if forcing.right.on and forcing.right.data:
                    righthere = 1.0
                    zsbndvec = _get_bnd_zs_at_time(forcing.right.data, totaltime)
                    zsright = _interp_bnd_spatial(zsbndvec, jj)

                if forcing.bot.on and forcing.bot.data:
                    bothere = 1.0
                    zsbndvec = _get_bnd_zs_at_time(forcing.bot.data, totaltime)
                    zsbot = _interp_bnd_spatial(zsbndvec, ii)

                if forcing.top.on and forcing.top.data:
                    tophere = 1.0
                    zsbndvec = _get_bnd_zs_at_time(forcing.top.data, totaltime)
                    zstop = _interp_bnd_spatial(zsbndvec, ii)

                # Nội suy nghịch đảo khoảng cách (giống C++)
                numerator = ((zsleft / distleft) * lefthere +
                             (zsright / distright) * righthere +
                             (zstop / disttop) * tophere +
                             (zsbot / distbot) * bothere)
                denominator = ((1.0 / distleft) * lefthere +
                               (1.0 / distright) * righthere +
                               (1.0 / disttop) * tophere +
                               (1.0 / distbot) * bothere)

                zsbnd = numerator / denominator if denominator > 0 else 0.0

                evolv.u[n] = 0.0
                evolv.v[n] = 0.0
                evolv.zs[n] = max(zsbnd, zb[n])
                evolv.h[n] = max(evolv.zs[n] - zb[n], 0.0)
