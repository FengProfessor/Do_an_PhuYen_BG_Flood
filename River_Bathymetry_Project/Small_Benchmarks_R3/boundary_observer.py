"""Read-only face-flux diagnostics, separate from the legacy discrete budget."""
from __future__ import annotations

import json
import math
from pathlib import Path


def install_boundary_observer(output: Path) -> dict:
    from bg_flood import flow_gpu as flow, mainloop
    from bg_flood.gpu_backend import xp

    state = {"schema": "r3-boundary-budget-1", "step_count": 0, "simulated_time_s": 0.,
             "initial_volume_m3": None, "current_volume_m3": None,
             "max_relative_volume_drift": 0., "max_abs_wall_flux_m3_s": 0.,
             "max_abs_internal_flux_mismatch_m3_s": 0., "boundary_depth_change_max_m": 0.,
             "clamp_added_m3": 0., "clamp_removed_m3": 0.,
             "boundary_net_inflow_volume_m3": {n: 0. for n in ("left", "right", "bot", "top")},
             "boundary_max_abs_net_rate_m3_s": {n: 0. for n in ("left", "right", "bot", "top")},
             "all_values_finite": True}
    context = {"stage": 0, "model": None, "param": None, "forcing": None, "rates": {}, "edge_initial": {}}

    def scalar(value):
        number = float(value)
        if not math.isfinite(number):
            state["all_values_finite"] = False
            raise ValueError("Non-finite value in boundary observer")
        return number

    def volume(model):
        idx = model.block_index
        return scalar(xp.sum(model.evolv.h[idx.interior] * idx.delta ** 2, dtype=xp.float64))

    original_update = flow.update_ev_vec

    def update(idx, param, evolv, flux, adv):
        result = original_update(idx, param, evolv, flux, adv)
        context["stage"] += 1
        rates = {}
        for name, field, face, sign in (
            ("left", flux.Fhu, idx.bnd_left_inside, 1.),
            ("right", flux.Fhu, idx.bnd_right_i, -1.),
            ("bot", flux.Fhv, idx.bnd_bot_inside, 1.),
            ("top", flux.Fhv, idx.bnd_top_i, -1.),
        ):
            values = field[face] * param.dx * sign
            rate = scalar(xp.sum(values, dtype=xp.float64))
            rates[name] = rate
            state["boundary_max_abs_net_rate_m3_s"][name] = max(state["boundary_max_abs_net_rate_m3_s"][name], abs(rate))
            if getattr(context["forcing"], name).type == 0 and len(face):
                # Kiểm tra cả từng mặt lẫn tổng cạnh, tránh triệt tiêu hai sai lệch.
                largest = max(abs(rate), scalar(xp.max(xp.abs(values))))
                state["max_abs_wall_flux_m3_s"] = max(state["max_abs_wall_flux_m3_s"], largest)
        divergence = scalar(xp.sum(adv.dh[idx.interior] * idx.delta ** 2, dtype=xp.float64))
        mismatch = abs(divergence - sum(rates.values()))
        state["max_abs_internal_flux_mismatch_m3_s"] = max(state["max_abs_internal_flux_mismatch_m3_s"], mismatch)
        if context["stage"] == 2:
            context["rates"] = rates
        return result

    flow.update_ev_vec = update
    original_advance = flow.adv_kernel_vec

    def advance(idx, param, dt, zb, evolv, adv, evolv_o):
        raw = evolv.h[idx.interior] + dt * adv.dh[idx.interior]
        # Tính cả hai stage để ca luôn ướt không che việc clamp ở Predictor.
        state["clamp_added_m3"] += scalar(xp.sum(xp.maximum(-raw, 0.) * idx.delta ** 2, dtype=xp.float64))
        state["clamp_removed_m3"] += scalar(xp.sum(xp.maximum(raw - 100., 0.) * idx.delta ** 2, dtype=xp.float64))
        result = original_advance(idx, param, dt, zb, evolv, adv, evolv_o)
        if context["stage"] == 2:
            for name, rate in context["rates"].items():
                state["boundary_net_inflow_volume_m3"][name] += dt * rate
        return result

    flow.adv_kernel_vec = advance
    original_flow = mainloop.flow_gpu

    def observed_flow(param, loop, forcing, model):
        context.update(stage=0, model=model, param=param, forcing=forcing, rates={})
        if state["initial_volume_m3"] is None:
            state["initial_volume_m3"] = volume(model)
            for name in ("left", "right", "bot", "top"):
                cells = getattr(model.block_index, f"bnd_{name}_inside")
                context["edge_initial"][name] = model.evolv.h[cells].copy()
        result = original_flow(param, loop, forcing, model)
        if context["stage"] != 2:
            raise RuntimeError("Expected exactly two flux stages in R3 vectorized solver")
        current = volume(model)
        state["current_volume_m3"] = current
        drift = abs(current - state["initial_volume_m3"]) / max(abs(state["initial_volume_m3"]), 1.)
        state["max_relative_volume_drift"] = max(state["max_relative_volume_drift"], drift)
        for name, initial in context["edge_initial"].items():
            cells = getattr(model.block_index, f"bnd_{name}_inside")
            if len(cells):
                change = scalar(xp.max(xp.abs(model.evolv.h[cells] - initial)))
                state["boundary_depth_change_max_m"] = max(state["boundary_depth_change_max_m"], change)
        state["step_count"] += 1
        state["simulated_time_s"] = float(loop.totaltime + loop.dt)
        if state["simulated_time_s"] >= param.endtime:
            output.write_text(json.dumps(state, indent=2, allow_nan=False), encoding="utf-8")
        return result

    mainloop.flow_gpu = observed_flow
    return state
