"""
BlockIndex — Precompute tất cả chỉ số (index arrays) cho vectorized/GPU solver.

Thay vì mỗi timestep lặp for-for-for qua (block, iy, ix),
ta tính trước tất cả chỉ số 1 lần duy nhất khi init mesh.

Mảng index nằm trên GPU nếu CuPy khả dụng.
"""

import numpy as np
from .gpu_backend import xp, to_device


class BlockIndex:
    """Chứa tất cả precomputed index arrays."""
    pass


def build_block_index(param, blocks):
    """
    Xây dựng tất cả index arrays cần thiết cho solver.
    
    Parameters
    ----------
    param : Param
    blocks : BlockP
    
    Returns
    -------
    BlockIndex
    """
    idx = BlockIndex()
    
    nblk = param.nblk
    bw = param.blkwidth       # 16
    hw = param.halowidth       # 1
    bmw = param.blkmemwidth    # 18
    bs = param.blksize         # 324
    
    active = blocks.active[:nblk]  # (nblk,) — block IDs
    
    # ============================================================
    # 1. INTERIOR indices: tất cả ô (ix, iy) trong tất cả block
    #    i = (hw + iy) * bmw + (hw + ix) + ib * bs
    # ============================================================
    ix_arr = np.arange(bw)          # 0..15
    iy_arr = np.arange(bw)          # 0..15
    
    # Meshgrid cho 1 block: (bw*bw,) pairs of (ix, iy)
    ixg, iyg = np.meshgrid(ix_arr, iy_arr, indexing='ij')  # (bw, bw)
    ixf = ixg.ravel()  # (256,)
    iyf = iyg.ravel()  # (256,)
    
    # Local offset trong 1 block
    local_offset = (hw + iyf) * bmw + (hw + ixf)  # (256,)
    
    # Block offsets
    blk_offsets = active * bs  # (nblk,)
    
    # Broadcast: (nblk, 256)
    interior = blk_offsets[:, None] + local_offset[None, :]  # (nblk, bw*bw)
    idx.interior = to_device(interior.ravel().astype(np.int64))
    
    # Lưu shape info
    idx.nblk = nblk
    idx.ncells = nblk * bw * bw
    idx.bw = bw
    idx.hw = hw
    idx.bmw = bmw
    idx.bs = bs
    
    # ============================================================
    # 2. LEFT/RIGHT/BOT/TOP neighbours: i ± 1, i ± bmw
    # ============================================================
    idx.i_left  = to_device((interior - 1).ravel().astype(np.int64))
    idx.i_right = to_device((interior + 1).ravel().astype(np.int64))
    idx.i_bot   = to_device((interior - bmw).ravel().astype(np.int64))
    idx.i_top   = to_device((interior + bmw).ravel().astype(np.int64))
    
    # ============================================================
    # 3. DELTA per cell (cho multi-level support)
    # ============================================================
    levels = blocks.level[active]  # (nblk,)
    delta_per_blk = param.dx / (2.0 ** levels)  # (nblk,)
    delta_interior = np.repeat(delta_per_blk, bw * bw)  # (ncells,)
    idx.delta = to_device(delta_interior)
    
    # ============================================================
    # 4. KURGANOV X indices: ix in [0, bw+hw), iy in [0, bw)
    #    i(ix, iy) and ileft = i(ix-1, iy)
    # ============================================================
    kx_ix = np.arange(bw + hw)     # 0..16
    kx_iy = np.arange(bw)          # 0..15
    kxg, kyg = np.meshgrid(kx_ix, kx_iy, indexing='ij')
    kxf = kxg.ravel()  # (17*16,)
    kyf = kyg.ravel()
    
    kx_local = (hw + kyf) * bmw + (hw + kxf)
    kx_local_left = (hw + kyf) * bmw + (hw + kxf - 1)
    
    kx_i = blk_offsets[:, None] + kx_local[None, :]
    kx_ileft = blk_offsets[:, None] + kx_local_left[None, :]
    
    idx.kx_i     = to_device(kx_i.ravel().astype(np.int64))
    idx.kx_ileft = to_device(kx_ileft.ravel().astype(np.int64))
    idx.kx_n = nblk * (bw + hw) * bw
    idx.kx_delta = to_device(np.repeat(delta_per_blk, (bw + hw) * bw))
    
    # ============================================================
    # 5. KURGANOV Y indices: ix in [0, bw), iy in [0, bw+hw)
    # ============================================================
    ky_ix = np.arange(bw)
    ky_iy = np.arange(bw + hw)
    kygx, kygy = np.meshgrid(ky_ix, ky_iy, indexing='ij')
    kyfx = kygx.ravel()
    kyfy = kygy.ravel()
    
    ky_local = (hw + kyfy) * bmw + (hw + kyfx)
    ky_local_bot = (hw + kyfy - 1) * bmw + (hw + kyfx)
    
    ky_i = blk_offsets[:, None] + ky_local[None, :]
    ky_ibot = blk_offsets[:, None] + ky_local_bot[None, :]
    
    idx.ky_i    = to_device(ky_i.ravel().astype(np.int64))
    idx.ky_ibot = to_device(ky_ibot.ravel().astype(np.int64))
    idx.ky_n = nblk * bw * (bw + hw)
    idx.ky_delta = to_device(np.repeat(delta_per_blk, bw * (bw + hw)))
    
    # ============================================================
    # 6. ADVECTION indices: i, iright=i+1, itop=i+bmw
    # ============================================================
    idx.ev_iright = to_device((interior + 1).ravel().astype(np.int64))
    idx.ev_itop   = to_device((interior + bmw).ravel().astype(np.int64))
    
    # ============================================================
    # 7. HALO indices: precompute src/dst for all 4 sides
    # ============================================================
    _build_halo_indices(idx, param, blocks, active, blk_offsets)
    
    # ============================================================
    # 8. Physical Boundary indices (Domain edges)
    # ============================================================
    _build_boundary_indices(idx, param, blocks)

    return idx


def _build_halo_indices(idx, param, blocks, active, blk_offsets):
    """Precompute halo exchange indices for all blocks."""
    bw = param.blkwidth
    hw = param.halowidth
    bmw = param.blkmemwidth
    bs = param.blksize
    nblk = len(active)
    
    # Cho mỗi side, mỗi block có bw * hw halo cells
    n_per_side = nblk * bw * hw
    
    # Preallocate
    left_dst = np.empty(n_per_side, dtype=np.int64)
    left_src = np.empty(n_per_side, dtype=np.int64)
    right_dst = np.empty(n_per_side, dtype=np.int64)
    right_src = np.empty(n_per_side, dtype=np.int64)
    bot_dst = np.empty(n_per_side, dtype=np.int64)
    bot_src = np.empty(n_per_side, dtype=np.int64)
    top_dst = np.empty(n_per_side, dtype=np.int64)
    top_src = np.empty(n_per_side, dtype=np.int64)

    # Inter-block-only flux halo indices (exclude physical outer domain edges)
    flux_left_dst = []
    flux_left_src = []
    flux_right_dst = []
    flux_right_src = []
    flux_bot_dst = []
    flux_bot_src = []
    flux_top_dst = []
    flux_top_src = []
    
    ptr = 0
    for ibl in range(nblk):
        ib = active[ibl]
        base = ib * bs
        
        LB = blocks.LeftBot[ib]
        RB = blocks.RightBot[ib]
        BL = blocks.BotLeft[ib]
        TL = blocks.TopLeft[ib]
        
        for iy in range(bw):
            for k in range(hw):
                p = ptr + iy * hw + k
                
                # LEFT: dst = (-1-k, iy), src from LB or self
                left_dst[p] = base + (hw + iy) * bmw + (hw - 1 - k)
                if LB != ib:
                    left_src[p] = LB * bs + (hw + iy) * bmw + (hw + bw - 1 - k)
                    flux_left_dst.append(left_dst[p])
                    flux_left_src.append(left_src[p])
                else:
                    left_src[p] = base + (hw + iy) * bmw + hw  # zero gradient
                
                # RIGHT: dst = (bw+k, iy), src from RB or self
                right_dst[p] = base + (hw + iy) * bmw + (hw + bw + k)
                if RB != ib:
                    right_src[p] = RB * bs + (hw + iy) * bmw + (hw + k)
                    flux_right_dst.append(right_dst[p])
                    flux_right_src.append(right_src[p])
                else:
                    right_src[p] = base + (hw + iy) * bmw + (hw + bw - 1)
        
        for ix in range(bw):
            for k in range(hw):
                p = ptr + ix * hw + k
                
                # BOTTOM: dst = (ix, -1-k), src from BL or self
                bot_dst[p] = base + (hw - 1 - k) * bmw + (hw + ix)
                if BL != ib:
                    bot_src[p] = BL * bs + (hw + bw - 1 - k) * bmw + (hw + ix)
                    flux_bot_dst.append(bot_dst[p])
                    flux_bot_src.append(bot_src[p])
                else:
                    bot_src[p] = base + hw * bmw + (hw + ix)
                
                # TOP: dst = (ix, bw+k), src from TL or self
                top_dst[p] = base + (hw + bw + k) * bmw + (hw + ix)
                if TL != ib:
                    top_src[p] = TL * bs + (hw + k) * bmw + (hw + ix)
                    flux_top_dst.append(top_dst[p])
                    flux_top_src.append(top_src[p])
                else:
                    top_src[p] = base + (hw + bw - 1) * bmw + (hw + ix)
        
        ptr += bw * hw
    
    idx.halo_left_dst  = to_device(left_dst)
    idx.halo_left_src  = to_device(left_src)
    idx.halo_right_dst = to_device(right_dst)
    idx.halo_right_src = to_device(right_src)
    idx.halo_bot_dst   = to_device(bot_dst)
    idx.halo_bot_src   = to_device(bot_src)
    idx.halo_top_dst   = to_device(top_dst)
    idx.halo_top_src   = to_device(top_src)

    idx.flux_halo_left_dst  = to_device(np.array(flux_left_dst, dtype=np.int64))
    idx.flux_halo_left_src  = to_device(np.array(flux_left_src, dtype=np.int64))
    idx.flux_halo_right_dst = to_device(np.array(flux_right_dst, dtype=np.int64))
    idx.flux_halo_right_src = to_device(np.array(flux_right_src, dtype=np.int64))
    idx.flux_halo_bot_dst   = to_device(np.array(flux_bot_dst, dtype=np.int64))
    idx.flux_halo_bot_src   = to_device(np.array(flux_bot_src, dtype=np.int64))
    idx.flux_halo_top_dst   = to_device(np.array(flux_top_dst, dtype=np.int64))
    idx.flux_halo_top_src   = to_device(np.array(flux_top_src, dtype=np.int64))


def _build_boundary_indices(idx, param, blocks):
    """Precompute indices for cells on the physical domain boundaries."""
    bw = param.blkwidth
    hw = param.halowidth
    bmw = param.blkmemwidth
    bs = param.blksize
    
    # Chúng ta cần xác định block nào nằm ở biên thực sự (không có hàng xóm)
    # và lưu chỉ số của các ô biên đó.
    
    def get_side_indices(side_name):
        bnd_i = []       # Chỉ số ô halo (đích)
        bnd_inside = []  # Chỉ số ô nội miền sát biên (nguồn)
        bnd_blk = []     # ID của block chứa biên này
        
        # Lấy danh sách block active
        active = blocks.active[blocks.active >= 0]
        
        for ib in active:
            is_edge = False
            if side_name == "left" and blocks.LeftBot[ib] == ib: is_edge = True
            elif side_name == "right" and blocks.RightBot[ib] == ib: is_edge = True
            elif side_name == "top" and blocks.TopLeft[ib] == ib: is_edge = True
            elif side_name == "bot" and blocks.BotLeft[ib] == ib: is_edge = True
            
            if not is_edge: continue
            
            base = ib * bs
            for t in range(bw):
                if side_name == "left":
                    ix, iy = 0, t
                    ix_in, iy_in = 1, t
                elif side_name == "right":
                    ix, iy = bw - 1, t
                    ix_in, iy_in = bw - 2, t
                elif side_name == "top":
                    ix, iy = t, bw - 1
                    ix_in, iy_in = t, bw - 2
                else: # bot
                    ix, iy = t, 0
                    ix_in, iy_in = t, 1
                
                # Ô biên thực (trong interior)
                idx_edge = base + (hw + iy) * bmw + (hw + ix)
                # Ô ngay sát bên trong
                idx_inside = base + (hw + iy_in) * bmw + (hw + ix_in)
                # Ô halo tương ứng (để áp dụng điều kiện biên vào halo)
                if side_name == "left":   idx_halo = base + (hw + iy) * bmw + (hw - 1)
                elif side_name == "right": idx_halo = base + (hw + iy) * bmw + (hw + bw)
                elif side_name == "top":   idx_halo = base + (hw + bw) * bmw + (hw + ix)
                else:                     idx_halo = base + (hw - 1) * bmw + (hw + ix)
                
                bnd_i.append(idx_halo)
                bnd_inside.append(idx_edge)
                bnd_blk.append(ib)
                
        return (to_device(np.array(bnd_i, dtype=np.int64)), 
                to_device(np.array(bnd_inside, dtype=np.int64)),
                np.array(bnd_blk, dtype=np.int32))

    idx.bnd_left_i, idx.bnd_left_inside, idx.bnd_left_blk = get_side_indices("left")
    idx.bnd_right_i, idx.bnd_right_inside, idx.bnd_right_blk = get_side_indices("right")
    idx.bnd_top_i, idx.bnd_top_inside, idx.bnd_top_blk = get_side_indices("top")
    idx.bnd_bot_i, idx.bnd_bot_inside, idx.bnd_bot_blk = get_side_indices("bot")
