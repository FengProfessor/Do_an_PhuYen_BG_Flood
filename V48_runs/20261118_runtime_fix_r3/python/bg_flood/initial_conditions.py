"""
Khởi tạo điều kiện ban đầu (Initial Conditions).

Điều phối toàn bộ quy trình khởi tạo:
  interp bathy → setedges(zb) → cf → setedges(cf)
  → initevolv (cold/warm) → CopyArrayBUQ → bndblks
"""

import math
import numpy as np
from .param import Param
from .model import Model, EvolvingP, BlockP
from .forcing import Forcing
from .utils import calcres, bilinear_interpolation, memloc, raster_cell_valid
from .init_evolv import cold_start, warm_start


# ============================================================
# GRID MANIPULATION  (tương đương GridManip.cu)
# ============================================================

def setedges(param: Param, blocks: BlockP, arr: np.ndarray):
    """
    Extend the physical edge cell into ghost halos for a zero-gradient boundary.
    Never overwrite a real cell: doing so changes input DEM and raster values.
    Apply only where the block has no neighboring block on that side.
    """
    blkwidth = param.blkwidth

    for bl in range(param.nblk):
        ib = blocks.active[bl]

        for k in range(param.halowidth):
            # Source is always the closest real cell; destination is halo.
            _setedges_side_lr(param, ib, blocks.LeftBot[ib], blocks.LeftTop[ib],
                              0, -1 - k, arr)
            _setedges_side_lr(param, ib, blocks.RightBot[ib], blocks.RightTop[ib],
                              blkwidth - 1, blkwidth + k, arr)
            _setedges_side_bt(param, ib, blocks.TopLeft[ib], blocks.TopRight[ib],
                              blkwidth - 1, blkwidth + k, arr)
            _setedges_side_bt(param, ib, blocks.BotLeft[ib], blocks.BotRight[ib],
                              0, -1 - k, arr)


def _setedges_side_lr(param, ib, blkA, blkB, iread, iwrite, arr):
    if blkA == ib or blkB == ib:
        jstart = 0 if blkA == ib else param.blkwidth // 2
        jend = param.blkwidth if blkB == ib else param.blkwidth // 2
        for j in range(jstart, jend):
            n = memloc(param.halowidth, param.blkmemwidth, iread, j, ib)
            k = memloc(param.halowidth, param.blkmemwidth, iwrite, j, ib)
            arr[k] = arr[n]


def _setedges_side_bt(param, ib, blkA, blkB, jread, jwrite, arr):
    if blkA == ib or blkB == ib:
        istart = 0 if blkA == ib else param.blkwidth // 2
        iend = param.blkwidth if blkB == ib else param.blkwidth // 2
        for i in range(istart, iend):
            n = memloc(param.halowidth, param.blkmemwidth, i, jread, ib)
            k = memloc(param.halowidth, param.blkmemwidth, i, jwrite, ib)
            arr[k] = arr[n]


def copy_evolv(param: Param, blocks: BlockP, source: EvolvingP, dest: EvolvingP):
    """
    Sao chép biến tiến hóa.
    """
    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        for j in range(param.blkwidth):
            for i in range(param.blkwidth):
                n = memloc(param.halowidth, param.blkmemwidth, i, j, ib)
                dest.h[n] = source.h[n]
                dest.u[n] = source.u[n]
                dest.v[n] = source.v[n]
                dest.zs[n] = source.zs[n]


# ============================================================
# BOUNDARY BLOCK DETECTION  (tương đương Calcbndblks + Findbndblks)
# ============================================================

def find_bnd_blks(param: Param, forcing: Forcing, blocks: BlockP):
    """
    Tìm các block nằm trên mỗi biên.
    """
    left_blks = []
    right_blks = []
    top_blks = []
    bot_blks = []

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        levdx = calcres(param.dx, blocks.level[ib])

        leftxo = blocks.xo[ib]
        rightxo = blocks.xo[ib] + (param.blkwidth - 1) * levdx
        topyo = blocks.yo[ib] + (param.blkwidth - 1) * levdx
        botyo = blocks.yo[ib]

        if (rightxo - (param.xmax - param.xo)) > (-1.0 * levdx):
            right_blks.append(ib)

        if (topyo - (param.ymax - param.yo)) > (-1.0 * levdx):
            top_blks.append(ib)

        if botyo < levdx:
            bot_blks.append(ib)

        if leftxo < levdx:
            left_blks.append(ib)

    forcing.left.blks = np.array(left_blks, dtype=np.int32) if left_blks else np.array([], dtype=np.int32)
    forcing.left.nblk = len(left_blks)
    forcing.right.blks = np.array(right_blks, dtype=np.int32) if right_blks else np.array([], dtype=np.int32)
    forcing.right.nblk = len(right_blks)
    forcing.top.blks = np.array(top_blks, dtype=np.int32) if top_blks else np.array([], dtype=np.int32)
    forcing.top.nblk = len(top_blks)
    forcing.bot.blks = np.array(bot_blks, dtype=np.int32) if bot_blks else np.array([], dtype=np.int32)
    forcing.bot.nblk = len(bot_blks)


# ============================================================
# BATHYMETRY INTERPOLATION
# ============================================================

def interpolate_raster_to_model(param: Param, blocks: BlockP, model_array: np.ndarray, 
                               raster_val: np.ndarray, raster_nx: int, raster_ny: int, 
                               raster_xo: float, raster_yo: float, raster_dx: float, 
                               raster_xmax: float, raster_ymax: float,
                               is_manning: bool = False,
                               preserve_nodata: bool = False):
    """
    Nội suy dữ liệu từ một raster sang lưới tính toán của model.
    Sử dụng bilinear interpolation.
    
    Nếu is_manning=True, sẽ chuyển đổi Manning's n sang hệ số cf nội bộ.
    """
    for ibl in range(param.nblk):
        ib = blocks.active[ibl]
        lev = blocks.level[ib]
        levdx = calcres(param.dx, lev)

        for j in range(-param.halowidth, param.blkwidth + param.halowidth):
            for i in range(-param.halowidth, param.blkwidth + param.halowidth):
                n = memloc(param.halowidth, param.blkmemwidth, i, j, ib)

                x = param.xo + blocks.xo[ib] + i * levdx
                y = param.yo + blocks.yo[ib] + j * levdx

                if preserve_nodata and not raster_cell_valid(
                        x, y, raster_val, raster_nx, raster_ny,
                        raster_xo, raster_yo, raster_dx, param.mask):
                    model_array[n] = param.mask
                    continue

                x = max(min(x, raster_xmax), raster_xo)
                y = max(min(y, raster_ymax), raster_yo)

                cfi = min(max(int(math.floor((x - raster_xo) / raster_dx)), 0), raster_nx - 2)
                cfip = cfi + 1
                x1 = raster_xo + raster_dx * cfi
                x2 = raster_xo + raster_dx * cfip

                cfj = min(max(int(math.floor((y - raster_yo) / raster_dx)), 0), raster_ny - 2)
                cfjp = cfj + 1
                y1 = raster_yo + raster_dx * cfj
                y2 = raster_yo + raster_dx * cfjp

                q11 = raster_val[cfi + cfj * raster_nx]
                q12 = raster_val[cfi + cfjp * raster_nx]
                q21 = raster_val[cfip + cfj * raster_nx]
                q22 = raster_val[cfip + cfjp * raster_nx]

                mask_val = param.mask
                valid_vals = [v for v in [q11, q12, q21, q22] if v < mask_val]
                
                if not valid_vals:
                    val_interp = param.mask
                else:
                    avg_valid = sum(valid_vals) / len(valid_vals)
                    q11_f = q11 if q11 < mask_val else avg_valid
                    q12_f = q12 if q12 < mask_val else avg_valid
                    q21_f = q21 if q21 < mask_val else avg_valid
                    q22_f = q22 if q22 < mask_val else avg_valid
                    
                    val_interp = bilinear_interpolation(q11_f, q12_f, q21_f, q22_f,
                                                        x1, x2, y1, y2, x, y)
                
                if is_manning and val_interp < mask_val:
                    # Chuyển đổi Manning's n sang cf: cf = g * n^2 / h^(1/3)
                    # Tuy nhiên trong BG_Flood bản cũ, cf thường được lưu trực tiếp hoặc 
                    # tính toán động. Ở đây ta lưu Manning's n nếu frictionmodel=-1.
                    model_array[n] = val_interp
                else:
                    model_array[n] = val_interp


def interpolate_bathy(param: Param, forcing: Forcing, blocks: BlockP, zb: np.ndarray):
    """
    Nội suy địa hình tương thích với hàm generic mới.
    """
    if not forcing.Bathy:
        return

    bathy = forcing.Bathy[0]
    interpolate_raster_to_model(param, blocks, zb, 
                                bathy.val, bathy.nx, bathy.ny, 
                                bathy.xo, bathy.yo, bathy.dx, 
                                bathy.xmax, bathy.ymax,
                                preserve_nodata=True)


# ============================================================
# ORCHESTRATOR  (tương đương InitialConditions() trong C++)
# ============================================================

def init_evolv(param: Param, forcing: Forcing, model: Model):
    """
    Khởi tạo điều kiện ban đầu hoàn chỉnh.

    Thứ tự:
      1. Nội suy địa hình (interp2BUQ → zb)
      2. Extend zb into physical ghost halos; preserve physical edge cells
      3. Khởi tạo ma sát (cf)
      4. Extend static raster values into physical ghost halos
      5. initevolv (cold/warm start)
      6. CopyArrayBUQ(evolv → evolv_o)
      7. Calcbndblks + Findbndblks
    """
    print("\nKhởi tạo điều kiện ban đầu...")

    # 1. Nội suy địa hình (zb) từ dữ liệu bathy sang lưới tính toán
    interpolate_bathy(param, forcing, model.blocks, model.zb)

    # 2. Only initialize zb ghost halos. Never overwrite real terrain cells.
    setedges(param, model.blocks, model.zb)

    # 3. Khởi tạo ma sát (cf)
    if param.cfmap:
        from .read_input import read_asc_bathy
        print(f"\tĐọc bản đồ ma sát: {param.cfmap}")
        nx, ny, xo, yo, dx, nodata, data = read_asc_bathy(param.cfmap)
        data[data == nodata] = param.mask
        xmax = xo + (nx - 1) * dx
        ymax = yo + (ny - 1) * dx
        interpolate_raster_to_model(param, model.blocks, model.cf,
                                    data, nx, ny, xo, yo, dx, xmax, ymax,
                                    is_manning=(param.frictionmodel == -1))
    else:
        model.cf[:] = param.cf

    # 3b. Khởi tạo bản đồ thấm (il, cl)
    if param.ilfile:
        from .read_input import read_asc_bathy
        print(f"\tĐọc bản đồ thấm ban đầu (il): {param.ilfile}")
        nx, ny, xo, yo, dx, nodata, data = read_asc_bathy(param.ilfile)
        data[data == nodata] = 0.0
        xmax = xo + (nx - 1) * dx
        ymax = yo + (ny - 1) * dx
        interpolate_raster_to_model(param, model.blocks, model.il,
                                    data, nx, ny, xo, yo, dx, xmax, ymax)
        # Khóa thấm tại lòng sông/biển (zb < 0)
        model.il[model.zb < 0.0] = 0.0
        # Sửa lại các giá trị mask (nếu bị gán param.mask do interpolate) thành 0.0
        model.il[model.il == param.mask] = 0.0
    else:
        model.il[:] = param.il

    if param.clfile:
        from .read_input import read_asc_bathy
        print(f"\tĐọc bản đồ thấm liên tục (cl): {param.clfile}")
        nx, ny, xo, yo, dx, nodata, data = read_asc_bathy(param.clfile)
        data[data == nodata] = 0.0
        xmax = xo + (nx - 1) * dx
        ymax = yo + (ny - 1) * dx
        interpolate_raster_to_model(param, model.blocks, model.cl,
                                    data, nx, ny, xo, yo, dx, xmax, ymax)
        # Khóa thấm tại lòng sông/biển (zb < 0)
        model.cl[model.zb < 0.0] = 0.0
        # Sửa lại các giá trị mask (nếu bị gán param.mask do interpolate) thành 0.0
        model.cl[model.cl == param.mask] = 0.0
    else:
        model.cl[:] = param.cl

    # 4. Initialize physical ghost halos for static rasters.
    setedges(param, model.blocks, model.cf)
    setedges(param, model.blocks, model.il)
    setedges(param, model.blocks, model.cl)

    # 5. initevolv: cold/warm start
    if math.isnan(param.zsinit) and not (param.leftbnd or param.rightbnd or param.topbnd or param.botbnd):
        param.zsinit = 0.0

    if not math.isnan(param.zsinit):
        # print("\tKhởi tạo lạnh (Cold start)")
        cold_start(param, model.blocks, model.zb, model.evolv)
    else:
        # print("\tKhởi tạo ấm (Warm start)")
        warm_start(param, forcing, model.blocks, model.zb, model.evolv)

    # 6. Sao chép evolv → evolv_o (C++: CopyArrayBUQ)
    copy_evolv(param, model.blocks, model.evolv, model.evolv_o)

    # 7. Tính và gán boundary blocks
    find_bnd_blks(param, forcing, model.blocks)

    print("\tHoàn tất khởi tạo điều kiện ban đầu.")
