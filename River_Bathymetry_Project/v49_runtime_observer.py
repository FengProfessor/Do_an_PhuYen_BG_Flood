"""Read-only instrumentation of the frozen solver's discrete water budget.

Hooks call the original routines exactly once and never alter model arrays.
The budget distinguishes boundary resets, numerical flux divergence, rain,
river sources, infiltration, and the residual from clamping/rounding.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def install_budget_observer(output: Path):
    from bg_flood import flow_gpu as flow
    from bg_flood import mainloop
    from bg_flood.gpu_backend import xp

    state = {
        "schema_version": "V49-discrete-budget-1",
        "interpretation": "Observed discrete numerical budget; not an external hydraulic validation",
        "step_count": 0,
        "simulated_time_s": 0.0,
        "initial_volume_m3": None,
        "current_volume_m3": None,
        "boundary_reset_volume_m3": 0.0,
        "flux_divergence_volume_m3": 0.0,
        "rain_volume_m3": 0.0,
        "river_volume_m3": 0.0,
        "infiltration_volume_m3": 0.0,
        "clamp_added_volume_m3": 0.0,
        "clamp_removed_volume_m3": 0.0,
        "accumulated_signed_update_residual_m3": 0.0,
        "accumulated_absolute_update_residual_m3": 0.0,
        "component_rate_mismatch_max_m3_s": 0.0,
        "corrector_negative_raw_depth_cell_steps": 0,
        "corrector_depth_above_100m_cell_steps": 0,
        "hydraulic_promotion_ready": False,
    }
    context = {"stage": 0, "model": None, "rates": {}, "last_write": 0.0}

    def volume(model):
        index = model.block_index
        return float(xp.sum(model.evolv.h[index.interior] * index.delta**2, dtype=xp.float64))

    def rate(adv):
        index = context["model"].block_index
        return float(xp.sum(adv.dh[index.interior] * index.delta**2, dtype=xp.float64))

    original_boundary = mainloop.update_bnd

    def boundary(param, loop, forcing, model, *args, **kwargs):
        before = volume(model)
        if state["initial_volume_m3"] is None:
            state["initial_volume_m3"] = before
        result = original_boundary(param, loop, forcing, model, *args, **kwargs)
        state["boundary_reset_volume_m3"] += volume(model) - before
        return result

    mainloop.update_bnd = boundary
    original_update = flow.update_ev_vec

    def update(index, param, evolv, flux, adv):
        result = original_update(index, param, evolv, flux, adv)
        context["stage"] += 1
        if context["stage"] == 2:
            context["rates"] = {"flux_divergence": rate(adv), "rain": 0.0, "river": 0.0, "infiltration": 0.0}
        return result

    flow.update_ev_vec = update

    def wrap_source(original, component, locate_adv):
        def source(*args, **kwargs):
            observing = context["stage"] == 2
            adv = locate_adv(args, kwargs) if observing else None
            before = rate(adv) if observing else 0.0
            result = original(*args, **kwargs)
            if observing:
                context["rates"][component] += rate(adv) - before
            return result
        return source

    flow.add_rain_vec = wrap_source(flow.add_rain_vec, "rain", lambda args, kw: args[4])
    flow.add_river_vec = wrap_source(flow.add_river_vec, "river", lambda args, kw: args[4])

    original_infiltration = flow.apply_infiltration_gpu

    def infiltration(*args, **kwargs):
        observing = context["stage"] == 2
        model = context["model"]
        before = rate(model.adv) if observing else 0.0
        result = original_infiltration(*args, **kwargs)
        if observing:
            context["rates"]["infiltration"] += rate(model.adv) - before
        return result

    flow.apply_infiltration_gpu = infiltration
    original_advance = flow.adv_kernel_vec

    def advance(index, param, dt, zb, evolv, adv, evolv_o):
        observing = context["stage"] == 2
        if observing:
            cells = index.interior
            areas = index.delta**2
            before = float(xp.sum(evolv.h[cells] * areas, dtype=xp.float64))
            total_rate = rate(adv)
            raw = evolv.h[cells] + dt * adv.dh[cells]
            state["corrector_negative_raw_depth_cell_steps"] += int(xp.sum(raw < 0.0))
            state["corrector_depth_above_100m_cell_steps"] += int(xp.sum(raw > 100.0))
            state["clamp_added_volume_m3"] += float(xp.sum(xp.maximum(-raw, 0.0) * areas, dtype=xp.float64))
            state["clamp_removed_volume_m3"] += float(xp.sum(xp.maximum(raw - 100.0, 0.0) * areas, dtype=xp.float64))
        result = original_advance(index, param, dt, zb, evolv, adv, evolv_o)
        if observing:
            after = float(xp.sum(evolv_o.h[index.interior] * index.delta**2, dtype=xp.float64))
            residual = after - before - dt * total_rate
            state["accumulated_signed_update_residual_m3"] += residual
            state["accumulated_absolute_update_residual_m3"] += abs(residual)
            mismatch = abs(total_rate - sum(context["rates"].values()))
            state["component_rate_mismatch_max_m3_s"] = max(state["component_rate_mismatch_max_m3_s"], mismatch)
            for name, value in context["rates"].items():
                state[f"{name}_volume_m3"] += dt * value
        return result

    flow.adv_kernel_vec = advance
    original_flow = mainloop.flow_gpu

    def observed_flow(param, loop, forcing, model):
        context.update(stage=0, model=model, rates={})
        result = original_flow(param, loop, forcing, model)
        state["step_count"] += 1
        state["simulated_time_s"] = float(loop.totaltime + loop.dt)
        state["current_volume_m3"] = volume(model)
        source_total = sum(state[f"{name}_volume_m3"] for name in ("boundary_reset", "flux_divergence", "rain", "river", "infiltration"))
        state["unexplained_closure_residual_m3"] = (
            state["current_volume_m3"] - state["initial_volume_m3"] - source_total
            - state["accumulated_signed_update_residual_m3"]
        )
        now = time.monotonic()
        if now - context["last_write"] >= 60.0 or state["simulated_time_s"] >= param.endtime:
            atomic_json(output, state)
            context["last_write"] = now
        return result

    mainloop.flow_gpu = observed_flow
    return state
