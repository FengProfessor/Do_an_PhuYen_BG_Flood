"""Exercise the selected runtime's real flux operators on tiny uniform fixtures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def run_checks(source: Path, device: str) -> dict:
    source = source.resolve()
    if (source / "python/run_bgflood.py").exists():
        source = source / "python"
    sys.path.insert(0, str(source))
    if device == "cpu":
        sys.modules["cupy"] = None
    else:
        import cupy
        cupy.cuda.Device(0).use()
    import numpy as np
    from types import SimpleNamespace
    from bg_flood import flow_gpu as flow
    from bg_flood.block_index import build_block_index
    from bg_flood.boundary import update_bnd
    from bg_flood.forcing import Forcing
    from bg_flood.gpu_backend import xp, is_gpu
    from bg_flood.model import AdvanceP, BlockP, EvolvingP, FluxP, GradientsP, Loop
    from bg_flood.param import Param
    if not Path(flow.__file__).resolve().is_relative_to(source):
        raise RuntimeError("Wrong runtime imported by operator checks")
    if bool(is_gpu) != (device == "cuda"):
        raise RuntimeError("Requested backend is not active")
    has_patch = hasattr(flow, "fill_gradient_halo_vec")
    rows = []
    for blocks_axis in (1, 2):
        for axis, mode in (("x", "uniform"), ("x", "increasing"), ("x", "decreasing"),
                           ("y", "increasing"), ("y", "decreasing"), ("x", "depth_slope")):
            param = Param()
            param.nblk = param.nblkmem = blocks_axis ** 2
            param.dx = 30.
            param.blkmemwidth, param.blksize = 18, 324
            blocks = BlockP()
            blocks.allocate(param.nblk)
            blocks.active[:] = np.arange(param.nblk)
            for ib in range(param.nblk):
                bx, by = ib % blocks_axis, ib // blocks_axis
                for n, neighbor in (("LeftBot", ib - 1 if bx else ib),
                                    ("RightBot", ib + 1 if bx < blocks_axis - 1 else ib),
                                    ("BotLeft", ib - blocks_axis if by else ib),
                                    ("TopLeft", ib + blocks_axis if by < blocks_axis - 1 else ib)):
                    getattr(blocks, n)[ib] = neighbor
            idx = build_block_index(param, blocks)
            forcing = Forcing()
            for side in (forcing.left, forcing.right, forcing.top, forcing.bot):
                side.type = 0
            evolv, grad, flux, adv = EvolvingP(), GradientsP(), FluxP(), AdvanceP()
            for item in (evolv, grad, flux, adv):
                item.allocate(324 * param.nblk)
                if is_gpu:
                    for key, value in vars(item).items():
                        if isinstance(value, np.ndarray):
                            setattr(item, key, xp.asarray(value))
            bed = xp.zeros(324 * param.nblk)
            ib = idx.interior // 324
            ix = idx.interior % 18 - 1 + (ib % blocks_axis) * 16
            iy = (idx.interior % 324) // 18 - 1 + (ib // blocks_axis) * 16
            coordinate = ix if axis == "x" else iy
            evolv.h[idx.interior] = 2. + (.001 * ix + .002 * iy if mode == "depth_slope" else 0.)
            evolv.zs[idx.interior] = evolv.h[idx.interior]
            velocity = evolv.u if axis == "x" else evolv.v
            velocity[idx.interior] = .1 if mode == "uniform" else (-.01 if mode == "decreasing" else .01) * (coordinate + .5)
            model = SimpleNamespace(block_index=idx, evolv=evolv, zb=bed)
            flow.fill_halo_all(idx, evolv, bed)
            update_bnd(param, Loop(), forcing, model)
            flow.gradient_vec(idx, param, evolv, grad, bed)
            if has_patch:
                flow.fill_gradient_halo_vec(idx, forcing, grad)
            dtmax = xp.full(324 * param.nblk, 1e30)
            flow.kurganov_x_vec(idx, param, evolv, grad, flux, dtmax)
            flow.kurganov_y_vec(idx, param, evolv, grad, flux, dtmax)
            flow.fill_halo_flux_vec(idx, flux)
            flow.update_ev_vec(idx, param, evolv, flux, adv)
            faces = (flux.Fhu[idx.bnd_left_inside], -flux.Fhu[idx.bnd_right_i],
                     flux.Fhv[idx.bnd_bot_inside], -flux.Fhv[idx.bnd_top_i])
            edge_rates = [float(xp.sum(a, dtype=xp.float64) * 30.) for a in faces]
            maximum = max(max(abs(n) for n in edge_rates), max(float(xp.max(xp.abs(a))) * 30. for a in faces))
            net = float(xp.sum(adv.dh[idx.interior], dtype=xp.float64) * 900.)
            pressure = float(xp.max(xp.abs(flux.Fqux[idx.bnd_left_inside])))
            checks = {"wall_mass_flux_zero": maximum <= 1e-10,
                      "interfaces_cancel": abs(net - sum(edge_rates)) <= 1e-8,
                      "wall_momentum_not_erased": pressure > 1.}
            rows.append({"shape": [16 * blocks_axis] * 2, "axis": axis, "mode": mode,
                         "wall_max_abs_m3_s": maximum, "net_dV_dt_m3_s": net,
                         "interface_mismatch_m3_s": net - sum(edge_rates), "checks": checks,
                         "status": "PASS" if all(checks.values()) else "FAIL"})
    return {"status": "PASS" if has_patch and all(r["status"] == "PASS" for r in rows) else "FAIL",
            "runtime": str(source), "device": device, "gradient_halo_api": has_patch,
            "meaning": "Instantaneous real-runtime operators, not full-time simulations or field validation",
            "cases": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run_checks(args.runtime, args.device)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(f"[R3] Operator checks: {result['status']}; {args.out}")
    raise SystemExit(0 if result["status"] == "PASS" else 2)
