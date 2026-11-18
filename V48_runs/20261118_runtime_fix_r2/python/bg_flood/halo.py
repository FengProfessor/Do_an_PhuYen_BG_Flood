"""
Halo fill 
"""

import numpy as np
from .param import Param
from .model import BlockP, EvolvingP, FluxP
from .utils import memloc


def fill_halo_var(param: Param, blocks: BlockP, var: np.ndarray):
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth
    bw = param.blkwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]

        # =====================================================
        # LEFT
        # =====================================================
        LB = blocks.LeftBot[ib]

        for iy in range(bw):
            for k in range(halowidth):

                dst = memloc(halowidth, blkmemwidth,
                             -1 - k, iy, ib)

                if LB != ib:
                    src = memloc(halowidth, blkmemwidth,
                                 bw - 1 - k, iy, LB)
                else:
                    # zero gradient
                    src = memloc(halowidth, blkmemwidth,
                                 0, iy, ib)

                var[dst] = var[src]

        # =====================================================
        # RIGHT
        # =====================================================
        RB = blocks.RightBot[ib]

        for iy in range(bw):
            for k in range(halowidth):

                dst = memloc(halowidth, blkmemwidth,
                             bw + k, iy, ib)

                if RB != ib:
                    src = memloc(halowidth, blkmemwidth,
                                 k, iy, RB)
                else:
                    src = memloc(halowidth, blkmemwidth,
                                 bw - 1, iy, ib)

                var[dst] = var[src]

        # =====================================================
        # BOTTOM
        # =====================================================
        BL = blocks.BotLeft[ib]

        for ix in range(bw):
            for k in range(halowidth):

                dst = memloc(halowidth, blkmemwidth,
                             ix, -1 - k, ib)

                if BL != ib:
                    src = memloc(halowidth, blkmemwidth,
                                 ix, bw - 1 - k, BL)
                else:
                    src = memloc(halowidth, blkmemwidth,
                                 ix, 0, ib)

                var[dst] = var[src]

        # =====================================================
        # TOP
        # =====================================================
        TL = blocks.TopLeft[ib]

        for ix in range(bw):
            for k in range(halowidth):

                dst = memloc(halowidth, blkmemwidth,
                             ix, bw + k, ib)

                if TL != ib:
                    src = memloc(halowidth, blkmemwidth,
                                 ix, k, TL)
                else:
                    src = memloc(halowidth, blkmemwidth,
                                 ix, bw - 1, ib)

                var[dst] = var[src]


# =====================================================
# WRAPPERS
# =====================================================

def fill_halo(param: Param, blocks: BlockP,
              evolv: EvolvingP, zb: np.ndarray):

    fill_halo_var(param, blocks, evolv.zs)
    fill_halo_var(param, blocks, evolv.h)
    fill_halo_var(param, blocks, evolv.u)
    fill_halo_var(param, blocks, evolv.v)
    fill_halo_var(param, blocks, zb)


def fill_halo_flux_var(param: Param, blocks: BlockP, var: np.ndarray):
    """Fill inter-block flux halo cells only (skip physical outer domain boundaries)."""
    halowidth = param.halowidth
    blkmemwidth = param.blkmemwidth
    bw = param.blkwidth

    for ibl in range(param.nblk):
        ib = blocks.active[ibl]

        LB = blocks.LeftBot[ib]
        if LB != ib:
            for iy in range(bw):
                for k in range(halowidth):
                    dst = memloc(halowidth, blkmemwidth, -1 - k, iy, ib)
                    src = memloc(halowidth, blkmemwidth, bw - 1 - k, iy, LB)
                    var[dst] = var[src]

        RB = blocks.RightBot[ib]
        if RB != ib:
            for iy in range(bw):
                for k in range(halowidth):
                    dst = memloc(halowidth, blkmemwidth, bw + k, iy, ib)
                    src = memloc(halowidth, blkmemwidth, k, iy, RB)
                    var[dst] = var[src]

        BL = blocks.BotLeft[ib]
        if BL != ib:
            for ix in range(bw):
                for k in range(halowidth):
                    dst = memloc(halowidth, blkmemwidth, ix, -1 - k, ib)
                    src = memloc(halowidth, blkmemwidth, ix, bw - 1 - k, BL)
                    var[dst] = var[src]

        TL = blocks.TopLeft[ib]
        if TL != ib:
            for ix in range(bw):
                for k in range(halowidth):
                    dst = memloc(halowidth, blkmemwidth, ix, bw + k, ib)
                    src = memloc(halowidth, blkmemwidth, ix, k, TL)
                    var[dst] = var[src]


def fill_halo_flux(param: Param, blocks: BlockP,
                   flux: FluxP):

    fill_halo_flux_var(param, blocks, flux.Fhu)
    fill_halo_flux_var(param, blocks, flux.Fhv)
    fill_halo_flux_var(param, blocks, flux.Fqux)
    fill_halo_flux_var(param, blocks, flux.Fquy)
    fill_halo_flux_var(param, blocks, flux.Fqvx)
    fill_halo_flux_var(param, blocks, flux.Fqvy)
    fill_halo_flux_var(param, blocks, flux.Su)
    fill_halo_flux_var(param, blocks, flux.Sv)