"""
Điều kiện biên (Vectorized)
"""

import math
from .gpu_backend import xp

def flow_bnd_vec(idx_bnd_i, idx_bnd_inside, side, evolv, param, loop, g):
    """
    Vectorized boundary application for one side.
    """
    if len(idx_bnd_i) == 0:
        return

    # 1. Lấy dữ liệu từ ô bên trong (Inside)
    zs_in = evolv.zs[idx_bnd_inside]
    h_in  = evolv.h[idx_bnd_inside]
    u_in  = evolv.u[idx_bnd_inside]
    v_in  = evolv.v[idx_bnd_inside]

    # Map normal/tangential velocities based on side
    if side.isright == 0: # Top/Bot boundary
        un_in = v_in
        ut_in = u_in
    else: # Left/Right boundary
        un_in = u_in
        ut_in = v_in

    # 2. Xử lý dữ liệu biên theo thời gian (Interpolation)
    # Vì bài toán của bạn đang dùng biên đồng nhất (uniform wlev), ta lấy giá trị đầu tiên
    zsbnd = 0.0
    unbnd = 0.0
    utbnd = ut_in

    if side.on and side.data:
        # Tìm bước thời gian phù hợp (đơn giản hóa cho vectorized)
        # Nếu có nhiều mốc thời gian, ta lấy mốc hiện tại
        if len(side.data) == 1:
            zsbnd = side.data[0].wlevs[0]
        else:
            # Tìm bước k phù hợp
            k = 1
            while k < len(side.data) and side.data[k].time < loop.totaltime:
                k += 1
            k = min(k, len(side.data)-1)
            
            dtb = side.data[k].time - side.data[k-1].time
            tel = loop.totaltime - side.data[k-1].time
            frac = tel / dtb if dtb > 0 else 0.0
            zsbnd = side.data[k-1].wlevs[0] + (side.data[k].wlevs[0] - side.data[k-1].wlevs[0]) * frac

    # 3. Áp dụng loại biên (Type)
    sign = float(side.isright + side.istop)

    if side.type == 0: # Wall (Reflection)
        un_new = xp.zeros_like(un_in)
        ut_new = ut_in
        zs_new = zs_in
        h_new  = h_in
    elif side.type == 2: # Outflow (Free exit)
        un_new = un_in
        ut_new = ut_in
        zs_new = zs_in
        h_new  = h_in
    elif side.type == 1: # Dirichlet (Fixed wlev)
        # Tính hb = mực nước tại biên - độ cao đáy
        zb_at_bnd = zs_in - h_in  # zb = zs - h
        hb = xp.maximum(zsbnd - zb_at_bnd, 0.0)
        un_new = sign * 2.0 * (xp.sqrt(g * h_in) - xp.sqrt(g * hb)) + un_in
        ut_new = xp.zeros_like(ut_in)
        # FIX: Ghi đúng mực nước biên vào ghost cell thay vì copy từ ô bên trong
        zs_new = xp.full_like(zs_in, zsbnd)
        h_new  = hb
    else: # Default Wall
        un_new = xp.zeros_like(un_in)
        ut_new = ut_in
        zs_new = zs_in
        h_new  = h_in

    # 4. Ghi ngược lại vào các ô halo
    if side.isright == 0: # Top/Bot
        evolv.v[idx_bnd_i] = un_new
        evolv.u[idx_bnd_i] = ut_new
    else: # Left/Right
        evolv.u[idx_bnd_i] = un_new
        evolv.v[idx_bnd_i] = ut_new
    
    evolv.zs[idx_bnd_i] = zs_new
    evolv.h[idx_bnd_i]  = h_new

def update_bnd(param, loop, forcing, model, evolv=None):
    """
    Cập nhật điều kiện biên Vectorized.
    Mặc định cập nhật cho model.evolv nếu không chỉ định mảng khác.
    """
    if evolv is None:
        evolv = model.evolv
        
    idx = model.block_index
    g = param.g
    
    # Left
    flow_bnd_vec(idx.bnd_left_i, idx.bnd_left_inside, forcing.left, evolv, param, loop, g)
    # Right
    flow_bnd_vec(idx.bnd_right_i, idx.bnd_right_inside, forcing.right, evolv, param, loop, g)
    # Top
    flow_bnd_vec(idx.bnd_top_i, idx.bnd_top_inside, forcing.top, evolv, param, loop, g)
    # Bot
    flow_bnd_vec(idx.bnd_bot_i, idx.bnd_bot_inside, forcing.bot, evolv, param, loop, g)