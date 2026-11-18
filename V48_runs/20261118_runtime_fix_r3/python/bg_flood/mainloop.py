"""
vòng lặp chính của mô hình .
"""

import time
import numpy as np
from .gpu_backend import xp, is_gpu
from .utils import memloc
from .halo import fill_halo_var
from .flow_gpu import flow_gpu, fill_halo_vec
from .boundary import update_bnd
from .forcing_update import update_forcing
from .deform import deform_step
from .meanmax import calc_mean_max, reset_mean_max
from .write_output import (
    init_save_to_netcdf,
    save_to_netcdf,
    close_netcdf,
)


# ==========================================================
# INIT LOOP 
# ==========================================================

def init_loop(param, model):
    loop = model.loop

    loop.atmpuni = param.Paref
    loop.totaltime = param.totaltime
    loop.nextoutputtime = param.totaltime + param.outputtimestep

    loop.hugeposval = np.finfo(float).max
    loop.hugenegval = -loop.hugeposval
    loop.epsilon = np.finfo(float).eps

    # Chuẩn bị output
    init_save_to_netcdf(param, model)

    # Khởi tạo TS buffer
    loop.TSAllout = [[] for _ in param.TSnodesout]
    loop.nTSsteps = 0
    loop.nstepout = 0

    # Tính dt ban đầu đúng như C++
    calc_init_dt(param, model)
    loop.dt = calc_global_dt(param, model)

    return loop


# ==========================================================
# INIT DT
# ==========================================================

def calc_init_dt(param, model):
    idx = model.block_index
    i = idx.interior
    h = xp.maximum(model.evolv.h[i], param.eps)
    model.time.dtmax[i] = idx.delta / xp.sqrt(param.g * h)


def calc_global_dt(param, model):
    return float(param.CFL * xp.min(model.time.dtmax))


# ==========================================================
# MAP OUTPUT 
# ==========================================================

def map_output(param, loop, model):
    loop.nstepout += 1

    if (
        loop.totaltime >= loop.nextoutputtime - loop.dt * 1e-5
        and param.outputtimestep > 0.0
    ):
        # Tối ưu: Comment out print để giảm I/O overhead
        # print(
        #     f"\nOutput map at t={loop.totaltime:.4f} s "
        #     f"| mean dt = {param.outputtimestep / loop.nstepout:.6e}"
        # )

        save_to_netcdf(param, loop, model)

        loop.nextoutputtime = min(
            loop.nextoutputtime + param.outputtimestep,
            param.endtime,
        )

        loop.nstepout = 0


# ==========================================================
# POINT OUTPUT 
# ==========================================================

def point_output_step(param, loop, model):
    from .gpu_backend import to_numpy
    if not param.TSnodesout:
        return

    # Fetch only once per step for all nodes
    zs_cpu = to_numpy(model.evolv.zs)
    h_cpu  = to_numpy(model.evolv.h)
    u_cpu  = to_numpy(model.evolv.u)
    v_cpu  = to_numpy(model.evolv.v)

    bmw = param.blkmemwidth
    hw = param.halowidth
    bs = bmw * bmw

    for o, node in enumerate(param.TSnodesout):
        # Index calculation (should be precomputed for even more speed)
        i = (hw + node.j) * bmw + (hw + node.i) + node.block * bs

        loop.TSAllout[o].append({
            "time": loop.totaltime,
            "zs": zs_cpu[i],
            "h":  h_cpu[i],
            "u":  u_cpu[i],
            "v":  v_cpu[i],
        })

    loop.nTSsteps += 1


def flush_ts_output(param, loop):
    for o, node in enumerate(param.TSnodesout):
        with open(node.outname, "a") as f:
            for row in loop.TSAllout[o]:
                f.write(
                    f"{row['time']}\t"
                    f"{row['zs']:.6f}\t"
                    f"{row['h']:.6f}\t"
                    f"{row['u']:.6f}\t"
                    f"{row['v']:.6f}\n"
                )

        loop.TSAllout[o].clear()

    loop.nTSsteps = 0


# ==========================================================
# MAIN LOOP 
# ==========================================================

def main_loop(param, forcing, model):

    print("\nInitialising model main loop...")
    loop = init_loop(param, model)

    # fill halo zb – chỉ một lần (giống C++)
    fill_halo_vec(model.block_index, model.zb)

    if is_gpu:
        print("Model Running... [GPU mode]")
    else:
        print("Model Running... [CPU vectorized mode]")

    start_time = time.time()
    step_count = 0
    print_interval = 1  # In progress mỗi bước để theo dõi

    while loop.totaltime < param.endtime:

        # 1️⃣ Boundary update
        update_bnd(param, loop, forcing, model)

        # 2️⃣ Forcing update
        update_forcing(param, loop, forcing)

        # 3️⃣ Core engine (GPU or vectorized CPU)
        flow_gpu(param, loop, forcing, model)

        # dt đã được flow_cpu cập nhật
        loop.totaltime += loop.dt

        # 4️⃣ Deformation step (sau khi tăng time)
        deform_step(param, loop, forcing, model)

        # 5️⃣ Mean / Max
        calc_mean_max(param, loop, model)

        # 6️⃣ Point output
        if param.TSnodesout:
            point_output_step(param, loop, model)

            # flush nếu đầy
            if (
                loop.nTSsteps + 1
            ) * len(param.TSnodesout) * 4 > param.maxTSstorage \
            or param.endtime - loop.totaltime <= loop.dt * 1e-5:

                flush_ts_output(param, loop)

        # 7️⃣ Map output
        map_output(param, loop, model)

        # 8️⃣ Reset mean/max
        reset_mean_max(param, loop, model)

        # Chỉ in progress mỗi N bước để giảm I/O
        step_count += 1
        if step_count % print_interval == 0 or param.endtime - loop.totaltime <= loop.dt * 1e-5:
            elapsed = time.time() - start_time
            progress = loop.totaltime / param.endtime * 100
            print(
                f"t = {loop.totaltime:.2f}/{param.endtime:.0f}s ({progress:.1f}%) | dt = {loop.dt:.3e} | elapsed = {elapsed:.1f}s",
                flush=True
            )

    print("\n\nSimulation completed.")
    print(f"Runtime: {time.time() - start_time:.2f} s")

    close_netcdf()
    return loop