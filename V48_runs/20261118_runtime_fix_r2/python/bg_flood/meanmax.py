"""
Tính mean và max của các biến tiến hóa.
"""

from .utils import memloc


def calc_mean_max(param, loop, model):
    """
    Tích lũy mean và cập nhật max.

    """
    if not param.outmean and not param.outmax:
        return

    for ibl in range(param.nblk):
        ib = model.blocks.active[ibl]
        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):
                i = memloc(param.halowidth, param.blkmemwidth, ix, iy, ib)

                if param.outmean:
                    model.evmean.h[i] += model.evolv.h[i]
                    model.evmean.zs[i] += model.evolv.zs[i]
                    model.evmean.u[i] += model.evolv.u[i]
                    model.evmean.v[i] += model.evolv.v[i]

                if param.outmax:
                    model.evmax.h[i] = max(model.evmax.h[i], model.evolv.h[i])
                    model.evmax.zs[i] = max(model.evmax.zs[i], model.evolv.zs[i])
                    model.evmax.u[i] = max(model.evmax.u[i], abs(model.evolv.u[i]))
                    model.evmax.v[i] = max(model.evmax.v[i], abs(model.evolv.v[i]))

    if param.outmean:
        loop.nstep += 1


def reset_mean_max(param, loop, model):
    """
    Reset mean/max arrays sau khi xuất.
    """
    if not param.outmean and not param.outmax:
        return

    # Chỉ reset khi vừa xuất (nextoutputtime vừa tăng)
    if loop.nextoutputtime - loop.totaltime > loop.dt * 1e-5:
        return

    for ibl in range(param.nblk):
        ib = model.blocks.active[ibl]
        for iy in range(param.blkwidth):
            for ix in range(param.blkwidth):
                i = memloc(param.halowidth, param.blkmemwidth, ix, iy, ib)

                if param.outmean:
                    model.evmean.h[i] = 0.0
                    model.evmean.zs[i] = 0.0
                    model.evmean.u[i] = 0.0
                    model.evmean.v[i] = 0.0

                if param.outmax:
                    model.evmax.h[i] = 0.0
                    model.evmax.zs[i] = 0.0
                    model.evmax.u[i] = 0.0
                    model.evmax.v[i] = 0.0

    if param.outmean:
        loop.nstep = 0
