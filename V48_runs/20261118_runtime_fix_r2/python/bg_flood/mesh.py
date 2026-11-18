"""
Khởi tạo lưới (mesh) và các block.
"""

import math
import numpy as np
from .param import Param
from .forcing import Forcing
from .model import Model, BlockP
from .utils import calcres, memloc, raster_cell_valid
from .block_index import build_block_index, BlockIndex
from .gpu_backend import xp, is_gpu, to_device


def calc_init_nblk(param: Param, forcing: Forcing) -> int:
    """
    Tính số block ban đầu dựa trên lưới và địa hình.
    """
    nblk = 0
    levdx = calcres(param.dx, param.initlevel)
    maxnbx = math.ceil(param.nx / param.blkwidth)
    maxnby = math.ceil(param.ny / param.blkwidth)

    bathy = forcing.Bathy[0]

    for nblky in range(maxnby):
        for nblkx in range(maxnbx):
            nmask = 0
            for j in range(param.blkwidth):
                for i in range(param.blkwidth):
                    x = param.xo + (float(i) + param.blkwidth * nblkx) * levdx + 0.5 * levdx
                    y = param.yo + (float(j) + param.blkwidth * nblky) * levdx + 0.5 * levdx

                    if not raster_cell_valid(
                            x, y, bathy.val, bathy.nx, bathy.ny,
                            bathy.xo, bathy.yo, bathy.dx, param.mask):
                        nmask += 1

            if nmask < param.blkwidth * param.blkwidth:
                nblk += 1

    return nblk


def init_block_xoyo(param: Param, forcing: Forcing, blocks: BlockP):
    """
    Khởi tạo tọa độ gốc (xo, yo) và trạng thái active cho mỗi block.
    """
    blkid = 0
    levdx = calcres(param.dx, param.initlevel)
    maxnbx = math.ceil(param.nx / param.blkwidth)
    maxnby = math.ceil(param.ny / param.blkwidth)

    bathy = forcing.Bathy[0]

    for nblky in range(maxnby):
        for nblkx in range(maxnbx):
            nmask = 0
            for j in range(param.blkwidth):
                for i in range(param.blkwidth):
                    x = param.xo + (float(i) + param.blkwidth * nblkx) * levdx + 0.5 * levdx
                    y = param.yo + (float(j) + param.blkwidth * nblky) * levdx + 0.5 * levdx

                    if not raster_cell_valid(
                            x, y, bathy.val, bathy.nx, bathy.ny,
                            bathy.xo, bathy.yo, bathy.dx, param.mask):
                        nmask += 1

            if nmask < param.blkwidth * param.blkwidth:
                blocks.xo[blkid] = nblkx * param.blkwidth * levdx + 0.5 * levdx
                blocks.yo[blkid] = nblky * param.blkwidth * levdx + 0.5 * levdx
                blocks.active[blkid] = blkid
                blkid += 1


def init_block_neighbours(param: Param, forcing: Forcing, blocks: BlockP):
    """
    Khởi tạo các hàng xóm cho mỗi block.
    """
    levdx = calcres(param.dx, param.initlevel)
    eps_dist = np.finfo(np.float64).eps * 10.0

    # M?c d?nh: tr? v? chnh n (bin wall)
    coord_dict = {}
    for iblk in range(param.nblk):
        ib2 = blocks.active[iblk]
        x_round = round(blocks.xo[ib2], 1)
        y_round = round(blocks.yo[ib2], 1)
        coord_dict[(x_round, y_round)] = ib2

    for ibl in range(param.nblk):
        bl = blocks.active[ibl]

        leftxo = blocks.xo[bl] - param.blkwidth * levdx
        leftyo = blocks.yo[bl]

        rightxo = blocks.xo[bl] + param.blkwidth * levdx
        rightyo = blocks.yo[bl]

        topxo = blocks.xo[bl]
        topyo = blocks.yo[bl] + param.blkwidth * levdx

        botxo = blocks.xo[bl]
        botyo = blocks.yo[bl] - param.blkwidth * levdx

        # Mặc định: trỏ về chính nó (biên wall)
        blocks.LeftBot[bl] = bl
        blocks.LeftTop[bl] = bl
        blocks.RightBot[bl] = bl
        blocks.RightTop[bl] = bl
        blocks.TopLeft[bl] = bl
        blocks.TopRight[bl] = bl
        blocks.BotLeft[bl] = bl
        blocks.BotRight[bl] = bl

        def get_ib2(x, y):
            xr = round(x, 1)
            yr = round(y, 1)
            return coord_dict.get((xr, yr), bl)

        ib2_left = get_ib2(leftxo, leftyo)
        if ib2_left != bl:
            blocks.LeftBot[bl] = ib2_left
            blocks.LeftTop[bl] = ib2_left
            
        ib2_right = get_ib2(rightxo, rightyo)
        if ib2_right != bl:
            blocks.RightBot[bl] = ib2_right
            blocks.RightTop[bl] = ib2_right
            
        ib2_top = get_ib2(topxo, topyo)
        if ib2_top != bl:
            blocks.TopLeft[bl] = ib2_top
            blocks.TopRight[bl] = ib2_top
            
        ib2_bot = get_ib2(botxo, botyo)
        if ib2_bot != bl:
            blocks.BotLeft[bl] = ib2_bot
            blocks.BotRight[bl] = ib2_bot


def init_mesh(param: Param, forcing: Forcing, model: Model):
    """
    Khởi tạo lưới hoàn chỉnh.
    """
    print("\nKhởi tạo lưới...")

    # Tính số block ban đầu
    nblk = calc_init_nblk(param, forcing)
    param.nblk = nblk
    param.nblkmem = int(math.ceil(nblk * param.membuffer))

    print(f"\tSố block ban đầu: {nblk}; Sẽ cấp phát {param.nblkmem} block trong bộ nhớ.")

    # Cấp phát bộ nhớ
    model.allocate(param.nblkmem, param.blksize)

    # Khởi tạo level
    for ib in range(param.nblkmem):
        model.blocks.active[ib] = -1
        model.blocks.level[ib] = param.initlevel

    # Khởi tạo tọa độ block
    print("\tKhởi tạo vị trí và lân cận của các blocks...")
    init_block_xoyo(param, forcing, model.blocks)

    # Khởi tạo hàng xóm
    init_block_neighbours(param, forcing, model.blocks)

    # Xây dựng chỉ số vector hóa (cho GPU/vectorized solver)
    print("\tXây dựng chỉ số vector hóa (block index)...")
    model.block_index = build_block_index(param, model.blocks)

    print("\tHoàn tất khởi tạo lưới.")


def transfer_to_gpu(model):
    """Chuyển tất cả numpy arrays trong model thành cupy arrays."""
    if not is_gpu:
        return
    print("\tChuyển dữ liệu lên GPU...")
    for ev in [model.evolv, model.evolv_o]:
        ev.zs = to_device(ev.zs)
        ev.h  = to_device(ev.h)
        ev.u  = to_device(ev.u)
        ev.v  = to_device(ev.v)
        ev.cum_infilt = to_device(ev.cum_infilt)
    for g in [model.grad]:
        g.dzsdx = to_device(g.dzsdx); g.dzsdy = to_device(g.dzsdy)
        g.dhdx  = to_device(g.dhdx);  g.dhdy  = to_device(g.dhdy)
        g.dudx  = to_device(g.dudx);  g.dudy  = to_device(g.dudy)
        g.dvdx  = to_device(g.dvdx);  g.dvdy  = to_device(g.dvdy)
    f = model.flux
    f.Su = to_device(f.Su); f.Sv = to_device(f.Sv)
    f.Fqux = to_device(f.Fqux); f.Fquy = to_device(f.Fquy)
    f.Fqvx = to_device(f.Fqvx); f.Fqvy = to_device(f.Fqvy)
    f.Fhu = to_device(f.Fhu); f.Fhv = to_device(f.Fhv)
    a = model.adv
    a.dh = to_device(a.dh); a.dhu = to_device(a.dhu); a.dhv = to_device(a.dhv)
    model.time.dtmax = to_device(model.time.dtmax)
    model.zb = to_device(model.zb)
    model.cf = to_device(model.cf)
    model.il = to_device(model.il)
    model.cl = to_device(model.cl)

    # Update OutputVarMap references
    model.OutputVarMap = {
        'zs': model.evolv.zs,
        'h': model.evolv.h,
        'u': model.evolv.u,
        'v': model.evolv.v,
        'zb': model.zb,
        'cum_infilt': model.evolv.cum_infilt,
        'il': model.il,
        'cl': model.cl,
        'cf': model.cf
    }
