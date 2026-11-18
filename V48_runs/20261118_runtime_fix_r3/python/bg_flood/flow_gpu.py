"""
Flow GPU — Vectorized solver chạy trên GPU (CuPy) hoặc CPU (NumPy).

Tương đương flow_cpu.py nhưng không dùng vòng for Python.
Tất cả phép tính là array operations → tự động chạy trên GPU nếu có CuPy.

Gồm:
  - fill_halo_vec: halo exchange vectorized
  - gradient_vec: gradient + minmod limiter
  - kurganov_x/y_vec: Kurganov-Petrova flux
  - advection_vec: update dh, dhu, dhv + advance kernel
  - friction_vec: bottom friction
  - flow_gpu: orchestrator predictor-corrector
"""

from .gpu_backend import xp, to_numpy
import math
import warnings
from .updateforcing import apply_infiltration_gpu, add_rain_vec, init_rain_istation, init_rain_grid_weights, add_river_vec
from .boundary import update_bnd


# ================================================================
# HALO FILL (vectorized)
# ================================================================

def fill_halo_vec(idx, var):
    """Fill halo cells using precomputed index arrays."""
    var[idx.halo_left_dst]  = var[idx.halo_left_src]
    var[idx.halo_right_dst] = var[idx.halo_right_src]
    var[idx.halo_bot_dst]   = var[idx.halo_bot_src]
    var[idx.halo_top_dst]   = var[idx.halo_top_src]


def fill_halo_all(idx, evolv, zb):
    """Fill halo for all evolving variables + zb."""
    fill_halo_vec(idx, evolv.zs)
    fill_halo_vec(idx, evolv.h)
    fill_halo_vec(idx, evolv.u)
    fill_halo_vec(idx, evolv.v)
    fill_halo_vec(idx, zb)


def _fill_halo_flux_arr_vec(idx, var):
    """Fill inter-block flux halo cells only (skip physical outer domain boundaries)."""
    if len(idx.flux_halo_left_dst):
        var[idx.flux_halo_left_dst] = var[idx.flux_halo_left_src]
    if len(idx.flux_halo_right_dst):
        var[idx.flux_halo_right_dst] = var[idx.flux_halo_right_src]
    if len(idx.flux_halo_bot_dst):
        var[idx.flux_halo_bot_dst] = var[idx.flux_halo_bot_src]
    if len(idx.flux_halo_top_dst):
        var[idx.flux_halo_top_dst] = var[idx.flux_halo_top_src]


def fill_halo_flux_vec(idx, flux):
    """Fill inter-block halo for all flux arrays."""
    _fill_halo_flux_arr_vec(idx, flux.Fhu)
    _fill_halo_flux_arr_vec(idx, flux.Fhv)
    _fill_halo_flux_arr_vec(idx, flux.Fqux)
    _fill_halo_flux_arr_vec(idx, flux.Fquy)
    _fill_halo_flux_arr_vec(idx, flux.Fqvx)
    _fill_halo_flux_arr_vec(idx, flux.Fqvy)
    _fill_halo_flux_arr_vec(idx, flux.Su)
    _fill_halo_flux_arr_vec(idx, flux.Sv)


# ================================================================
# GRADIENT + MINMOD (vectorized)
# ================================================================

def minmod2_vec(theta, a_left, a_center, a_right):
    """Vectorized minmod2 limiter."""
    d_minus = a_center - a_left
    d_plus  = a_right - a_center
    d_center = 0.5 * (a_right - a_left)
    
    s1 = theta * d_minus
    s2 = d_center
    s3 = theta * d_plus
    
    # minmod3: nếu cùng dấu → min abs, ngược dấu → 0
    pos = (s1 > 0) & (s2 > 0) & (s3 > 0)
    neg = (s1 < 0) & (s2 < 0) & (s3 < 0)
    
    result = xp.zeros_like(a_center)
    result[pos] = xp.minimum(xp.minimum(s1[pos], s2[pos]), s3[pos])
    result[neg] = xp.maximum(xp.maximum(s1[neg], s2[neg]), s3[neg])
    
    return result


def gradient_vec(idx, param, evolv, grad, zb):
    """Vectorized gradient computation for all variables."""
    theta = param.theta
    inv_delta = 1.0 / idx.delta
    
    i = idx.interior
    il = idx.i_left
    ir = idx.i_right
    ib = idx.i_bot
    it = idx.i_top
    
    for (arr, dadx, dady) in [
        (evolv.h,  grad.dhdx,  grad.dhdy),
        (evolv.zs, grad.dzsdx, grad.dzsdy),
        (evolv.u,  grad.dudx,  grad.dudy),
        (evolv.v,  grad.dvdx,  grad.dvdy),
    ]:
        a_c = arr[i]
        dadx[i] = minmod2_vec(theta, arr[il], a_c, arr[ir]) * inv_delta
        dady[i] = minmod2_vec(theta, arr[ib], a_c, arr[it]) * inv_delta


def fill_gradient_halo_vec(idx, forcing, grad):
    """Complete reconstructed states on a uniform grid with wall/outflow boundaries."""
    sides = (("left", forcing.left, "x"), ("right", forcing.right, "x"),
             ("bot", forcing.bot, "y"), ("top", forcing.top, "y"))
    for name, side, _ in sides:
        if len(getattr(idx, f"bnd_{name}_i")) and side.type not in (0, 2):
            raise NotImplementedError("R3 small-test runtime supports wall=0/outflow=2 only")
    # Gradient nội bộ phải thuộc đúng ô láng giềng, giống các giá trị h/zs/u/v.
    for field in ("h", "zs", "u", "v"):
        for axis in ("x", "y"):
            _fill_halo_flux_arr_vec(idx, getattr(grad, f"d{field}d{axis}"))
    for name, side, normal_axis in sides:
        halo = getattr(idx, f"bnd_{name}_i")
        inside = getattr(idx, f"bnd_{name}_inside")
        normal_velocity = "u" if normal_axis == "x" else "v"
        for field in ("h", "zs", "u", "v"):
            # Qua tường: vận tốc pháp tuyến lẻ, các trường còn lại chẵn.
            # Lấy đạo hàm pháp tuyến đổi dấu parity; đạo hàm tiếp tuyến giữ dấu.
            parity = -1. if field == normal_velocity else 1.
            for axis in ("x", "y"):
                derivative = getattr(grad, f"d{field}d{axis}")
                if side.type == 0:
                    sign = -parity if axis == normal_axis else parity
                    derivative[halo] = sign * derivative[inside]
                elif axis == normal_axis:
                    derivative[halo] = 0.
                else:
                    derivative[halo] = derivative[inside]


# ================================================================
# KURGANOV X (vectorized)
# ================================================================

def kurganov_x_vec(idx, param, evolv, grad, flux, dtmax):
    """Vectorized Kurganov flux in X direction."""
    g = param.g
    CFL = param.CFL
    epsi = float(xp.finfo(xp.float64).eps)
    eps = param.eps + epsi
    ga = 0.5 * g
    
    i = idx.kx_i
    il = idx.kx_ileft
    delta = idx.kx_delta
    dx = delta * 0.5
    
    hi = evolv.h[i]
    hn = evolv.h[il]
    
    wet = (hi > eps) | (hn > eps)
    
    # Default dry
    flux.Fhu[i]  = xp.where(wet, flux.Fhu[i], 0.0)
    flux.Fqux[i] = xp.where(wet, flux.Fqux[i], 0.0)
    flux.Su[i]   = xp.where(wet, flux.Su[i], 0.0)
    flux.Fqvx[i] = xp.where(wet, flux.Fqvx[i], 0.0)
    dtmax[i] = xp.where(wet, dtmax[i], dtmax[i])
    
    if not xp.any(wet):
        return
    
    # Only compute for wet faces
    w = wet
    
    zi = evolv.zs[i] - hi
    zn = evolv.zs[il] - hn
    
    dhdx_i  = grad.dhdx[i]
    dhdx_il = grad.dhdx[il]
    dzsdx_i  = grad.dzsdx[i]
    dzsdx_il = grad.dzsdx[il]
    dudx_i  = grad.dudx[i]
    dudx_il = grad.dudx[il]
    dvdx_i  = grad.dvdx[i]
    dvdx_il = grad.dvdx[il]
    
    zl = zi - dx * (dzsdx_i - dhdx_i)
    zr = zn + dx * (dzsdx_il - dhdx_il)
    zlr = xp.maximum(zl, zr)
    
    hl = hi - dx * dhdx_i
    hr = hn + dx * dhdx_il
    up = evolv.u[i] - dx * dudx_i
    um = evolv.u[il] + dx * dudx_il
    
    hp = xp.maximum(0.0, hl + zl - zlr)
    hm = xp.maximum(0.0, hr + zr - zlr)
    
    # Wave speeds
    cp = xp.sqrt(g * hp)
    cm = xp.sqrt(g * hm)
    ap = xp.maximum(xp.maximum(up + cp, um + cm), 0.0)
    am = xp.minimum(xp.minimum(up - cp, um - cm), 0.0)
    
    a_max = xp.maximum(ap, -am)
    
    # Flux
    denom = ap - am
    safe_denom = xp.where(denom != 0, denom, 1.0)
    ad = 1.0 / safe_denom
    
    qm = hm * um
    qp = hp * up
    apm = ap * am
    
    fh = (ap * qm - am * qp + apm * (hp - hm)) * ad
    fu = (ap * (qm * um + ga * hm * hm) - am * (qp * up + ga * hp * hp) + apm * (qp - qm)) * ad
    
    # Transverse flux
    v_bot = evolv.v[il] + dx * dvdx_il
    v_top = evolv.v[i] - dx * dvdx_i
    fv = xp.where(fh > 0, v_bot * fh, v_top * fh)
    
    # Timestep (no CFL here — applied once in flow_gpu)
    dt_local = xp.where(w & (a_max > epsi), delta / a_max, 1.0 / epsi)
    
    # Source terms
    sl = ga * (hp * hp - hl * hl + (hl + hi) * (zi - zl))
    sr = ga * (hm * hm - hr * hr + (hr + hn) * (zn - zr))
    
    # Zero where dry
    fh = xp.where(w, fh, 0.0)
    fu = xp.where(w, fu, 0.0)
    fv = xp.where(w, fv, 0.0)
    sl = xp.where(w, sl, 0.0)
    sr = xp.where(w, sr, 0.0)
    
    flux.Fhu[i]  = fh
    flux.Fqux[i] = fu - sl
    flux.Su[i]   = fu - sr
    flux.Fqvx[i] = fv
    
    dtmax[i] = xp.where(w, xp.minimum(dtmax[i], dt_local), dtmax[i])


# ================================================================
# KURGANOV Y (vectorized)
# ================================================================

def kurganov_y_vec(idx, param, evolv, grad, flux, dtmax):
    """Vectorized Kurganov flux in Y direction."""
    g = param.g
    CFL = param.CFL
    epsi = float(xp.finfo(xp.float64).eps)
    eps = param.eps + epsi
    ga = 0.5 * g
    
    i = idx.ky_i
    ib_idx = idx.ky_ibot
    delta = idx.ky_delta
    dy = delta * 0.5
    
    hi = evolv.h[i]
    hn = evolv.h[ib_idx]
    
    wet = (hi > eps) | (hn > eps)
    
    flux.Fhv[i]  = xp.where(wet, flux.Fhv[i], 0.0)
    flux.Fqvy[i] = xp.where(wet, flux.Fqvy[i], 0.0)
    flux.Sv[i]   = xp.where(wet, flux.Sv[i], 0.0)
    flux.Fquy[i] = xp.where(wet, flux.Fquy[i], 0.0)
    
    if not xp.any(wet):
        return
    
    w = wet
    
    zi = evolv.zs[i] - hi
    zn = evolv.zs[ib_idx] - hn
    
    dhdy_i   = grad.dhdy[i]
    dhdy_ib  = grad.dhdy[ib_idx]
    dzsdy_i  = grad.dzsdy[i]
    dzsdy_ib = grad.dzsdy[ib_idx]
    dvdy_i   = grad.dvdy[i]
    dvdy_ib  = grad.dvdy[ib_idx]
    dudy_i   = grad.dudy[i]
    dudy_ib  = grad.dudy[ib_idx]
    
    zl = zi - dy * (dzsdy_i - dhdy_i)
    zr = zn + dy * (dzsdy_ib - dhdy_ib)
    zlr = xp.maximum(zl, zr)
    
    hl = hi - dy * dhdy_i
    hr = hn + dy * dhdy_ib
    vp = evolv.v[i] - dy * dvdy_i
    vm = evolv.v[ib_idx] + dy * dvdy_ib
    
    hp = xp.maximum(0.0, hl + zl - zlr)
    hm = xp.maximum(0.0, hr + zr - zlr)
    
    cp = xp.sqrt(g * hp)
    cm = xp.sqrt(g * hm)
    ap = xp.maximum(xp.maximum(vp + cp, vm + cm), 0.0)
    am = xp.minimum(xp.minimum(vp - cp, vm - cm), 0.0)
    
    a_max = xp.maximum(ap, -am)
    
    denom = ap - am
    safe_denom = xp.where(denom != 0, denom, 1.0)
    ad = 1.0 / safe_denom
    
    qm = hm * vm
    qp = hp * vp
    apm = ap * am
    
    fh = (ap * qm - am * qp + apm * (hp - hm)) * ad
    fu = (ap * (qm * vm + ga * hm * hm) - am * (qp * vp + ga * hp * hp) + apm * (qp - qm)) * ad
    
    # Transverse
    u_bot = evolv.u[ib_idx] + dy * dudy_ib
    u_top = evolv.u[i] - dy * dudy_i
    fv = xp.where(fh > 0, u_bot * fh, u_top * fh)
    
    dt_local = xp.where(w & (a_max > epsi), delta / a_max, 1.0 / epsi)
    
    sl = ga * (hp * hp - hl * hl + (hl + hi) * (zi - zl))
    sr = ga * (hm * hm - hr * hr + (hr + hn) * (zn - zr))
    
    fh = xp.where(w, fh, 0.0)
    fu = xp.where(w, fu, 0.0)
    fv = xp.where(w, fv, 0.0)
    sl = xp.where(w, sl, 0.0)
    sr = xp.where(w, sr, 0.0)
    
    flux.Fhv[i]  = fh
    flux.Fqvy[i] = fu - sl
    flux.Sv[i]   = fu - sr
    flux.Fquy[i] = fv
    
    dtmax[i] = xp.where(w, xp.minimum(dtmax[i], dt_local), dtmax[i])


# ================================================================
# ADVECTION (vectorized)
# ================================================================

def update_ev_vec(idx, param, evolv, flux, adv):
    """Compute dh, dhu, dhv from flux divergence."""
    i  = idx.interior
    ir = idx.ev_iright
    it = idx.ev_itop
    
    inv_delta = 1.0 / idx.delta
    ga = 0.5 * param.g
    # Coriolis parameter: f = 2 * omega * sin(lat)
    # 2 * omega = 2 * (2 * pi / 86400) = pi / 21600
    lat_rad = param.lat * 3.14159265 / 180.0
    fc = math.sin(lat_rad) * 3.14159265 / 21600.0
    
    hi = evolv.h[i]
    
    adv.dh[i] = -1.0 * (flux.Fhu[ir] - flux.Fhu[i] +
                         flux.Fhv[it] - flux.Fhv[i]) * inv_delta
    
    adv.dhu[i] = (flux.Fqux[i] + flux.Fquy[i] -
                  flux.Su[ir] - flux.Fquy[it]) * inv_delta + fc * hi * evolv.v[i]
    
    adv.dhv[i] = (flux.Fqvy[i] + flux.Fqvx[i] -
                  flux.Sv[it] - flux.Fqvx[ir]) * inv_delta - fc * hi * evolv.u[i]


def adv_kernel_vec(idx, param, dt, zb, evolv, adv, evolv_o):
    """Advance solution by dt with non-negative depth clamping and velocity bounds."""
    i = idx.interior
    eps = param.eps
    
    hold = evolv.h[i]
    ho = hold + dt * adv.dh[i]
    ho = xp.clip(ho, 0.0, 100.0)  # Safeguard: clamp depth [0, 100m]
    
    wet = ho >= 0.001
    
    uo = xp.where(wet, (hold * evolv.u[i] + dt * adv.dhu[i]) / xp.maximum(ho, eps), 0.0)
    vo = xp.where(wet, (hold * evolv.v[i] + dt * adv.dhv[i]) / xp.maximum(ho, eps), 0.0)
    
    # Velocity bounds
    uo = xp.where(wet, xp.clip(uo, -20.0, 20.0), 0.0)
    vo = xp.where(wet, xp.clip(vo, -20.0, 20.0), 0.0)
    
    evolv_o.h[i]  = ho
    evolv_o.u[i]  = uo
    evolv_o.v[i]  = vo
    evolv_o.zs[i] = zb[i] + ho


def cleanup_vec(idx, evolv_o, evolv):
    """Copy solution back with depth clamping and velocity bounds."""
    i = idx.interior
    h_new = xp.clip(evolv_o.h[i], 0.0, 100.0)
    wet = h_new >= 0.001
    evolv.h[i]  = h_new
    evolv.u[i]  = xp.where(wet, xp.clip(evolv_o.u[i], -20.0, 20.0), 0.0)
    evolv.v[i]  = xp.where(wet, xp.clip(evolv_o.v[i], -20.0, 20.0), 0.0)
    evolv.zs[i] = evolv_o.zs[i]


# removed add_rain_vec definition as it is imported from updateforcing.py


# ================================================================
# FRICTION (vectorized)
# ================================================================

def friction_vec(idx, param, dt, cf, evolv):
    """Vectorized bottom friction (semi-implicit).
    
    FIX: Sử dụng h_fric_min = 0.01m thay vì eps (0.0001m) làm ngưỡng
    tối thiểu khi tính ma sát. Khi h < 0.01m, ma sát bị giới hạn để
    không triệt tiêu hoàn toàn vận tốc, cho phép nước nông lan truyền.
    """
    i = idx.interior
    eps = param.eps
    g = param.g
    h_fric_min = 0.01  # Ngưỡng tối thiểu cho tính ma sát (1 cm)
    
    hi = evolv.h[i]
    wet = hi > eps
    
    if not xp.any(wet):
        return
    
    ui = evolv.u[i]
    vi = evolv.v[i]
    normu = xp.sqrt(ui * ui + vi * vi)
    
    cfi = cf[i]
    
    # Sử dụng h_fric (>= 0.01m) cho tính toán ma sát để tránh
    # tb bùng nổ khi h cực nhỏ
    h_fric = xp.maximum(hi, h_fric_min)
    
    if param.frictionmodel == 0:
        # Constant cf
        pass
    elif param.frictionmodel == 1:
        # Smart friction (log-law)
        zo = cfi
        Hbar = h_fric / xp.maximum(zo, 1e-30)
        e_val = math.e
        low = Hbar <= e_val
        cfi_low = 1.0 / xp.maximum(0.46 * Hbar, 1e-30)
        log_Hbar = xp.log(xp.maximum(Hbar, 1.0))
        cfi_high = 1.0 / xp.maximum(2.5 * (log_Hbar - 1.0 + 1.359 / xp.maximum(Hbar, 1e-30)), 1e-30)
        cfi = xp.where(low, cfi_low, cfi_high)
        cfi = cfi * cfi
    elif param.frictionmodel == -1:
        # Manning
        n = cfi
        h13 = h_fric ** (1.0 / 3.0)
        cfi = g * n * n / h13
    
    tb = cfi * normu / h_fric * dt
    
    factor = 1.0 / (1.0 + tb)
    factor = xp.where(wet, factor, 1.0)
    
    evolv.u[i] = ui * factor
    evolv.v[i] = vi * factor



# ================================================================
# FLOW GPU — Main orchestrator (Predictor-Corrector)
# ================================================================

def flow_gpu(param, loop, forcing, model):
    """
    Predictor-Corrector solver — vectorized, runs on GPU if CuPy available.
    Drop-in replacement for flow_cpu().
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        _flow_gpu_inner(param, loop, forcing, model)


def _flow_gpu_inner(param, loop, forcing, model):
    """Inner implementation (wrapped to suppress RuntimeWarnings)."""
    idx = model.block_index
    if idx.hw != 1 or not bool(xp.all(idx.delta == param.dx)):
        raise NotImplementedError("R3 small-test runtime requires a uniform grid and one halo cell")
    
    # ============================================================
    # PREDICTOR STEP
    # ============================================================
    
    # 1. Fill halo
    fill_halo_all(idx, model.evolv, model.zb)

    # 1b. Update physical boundaries for predictor step (after inter-block halo fill)
    update_bnd(param, loop, forcing, model, evolv=model.evolv)
    
    # 2. Reset dtmax
    model.time.dtmax[:] = loop.hugeposval
    
    # 3. Gradient
    gradient_vec(idx, param, model.evolv, model.grad, model.zb)
    fill_gradient_halo_vec(idx, forcing, model.grad)
    
    # 4-5. Kurganov X & Y
    kurganov_x_vec(idx, param, model.evolv, model.grad, model.flux, model.time.dtmax)
    kurganov_y_vec(idx, param, model.evolv, model.grad, model.flux, model.time.dtmax)
    
    # 6. Fill halo flux
    fill_halo_flux_vec(idx, model.flux)
    
    # 7. Timestep (CFL) and Stability Safeguards
    idx = model.block_index
    # Safeguard 1: Non-negative depth clamping
    model.evolv.h[idx.interior] = xp.maximum(model.evolv.h[idx.interior], 0.0)
    h = model.evolv.h[idx.interior]

    # Safeguard 2: Immediate NaN detection in water depth
    nan_mask = xp.isnan(h)
    if xp.any(nan_mask):
        nan_count = int(xp.sum(nan_mask))
        msg = f"CRITICAL NUMERICAL INSTABILITY: Detected {nan_count} NaN values in water depth (h) at t={loop.totaltime:.2f}s! Raising exception."
        print(f"\n[STABILITY ALERT] {msg}", flush=True)
        raise RuntimeError(msg)

    # Wet-dry threshold nâng cao: Tại các ô có h < 0.001m, set u=v=0
    dry_mask = h < 0.001
    model.evolv.u[idx.interior] = xp.where(dry_mask, 0.0, model.evolv.u[idx.interior])
    model.evolv.v[idx.interior] = xp.where(dry_mask, 0.0, model.evolv.v[idx.interior])

    # Chỉ lấy min(dtmax) ở các ô thực sự ướt (h > 0.001) để tránh dt bị ép nhỏ do nước nông
    hmin_dt = 0.001  # Ngưỡng tối ưu cho bài toán mưa
    wet_mask = h > hmin_dt
    dtmax_interior = model.time.dtmax[idx.interior]
    if xp.any(wet_mask):
        dt_candidate = dtmax_interior[wet_mask]
        min_dt_val = float(param.CFL * xp.min(dt_candidate))
        if not math.isfinite(min_dt_val) or min_dt_val <= 0.0:
            msg = f"CRITICAL NUMERICAL INSTABILITY: Non-finite CFL dt ({min_dt_val}) computed from wet cells at t={loop.totaltime:.2f}s!"
            print(f"\n[STABILITY ALERT] {msg}", flush=True)
            min_dt_val = 0.1



        loop.dt = min_dt_val
    else:
        # Nếu không có ô nào ướt, giữ dt lớn để tránh treo
        loop.dt = 1.0

    # Guard against runaway dt in fully-dry starts (common in rain-only cases).
    remaining = max(param.endtime - loop.totaltime, 0.0)
    dt_cap = remaining
    if param.outputtimestep > 0.0:
        dt_cap = min(dt_cap, param.outputtimestep)

    # Use user-defined dt limit from config if available (e.g. dt = 2.0)
    if param.dt > 0.0:
        dt_cap = min(dt_cap, param.dt)

    # CFL limiter toàn cục
    h_max = float(xp.max(h))
    u_arr = model.evolv.u[idx.interior]
    v_arr = model.evolv.v[idx.interior]
    v_max = float(xp.max(xp.sqrt(u_arr**2 + v_arr**2)))
    max_wave_speed = float(math.sqrt(param.g * h_max) + v_max)
    min_dx = float(xp.min(idx.delta))
    if max_wave_speed > 0.0:
        min_stable_dt = min_dx / (2.0 * max_wave_speed)
        dt_cap = min(dt_cap, min_stable_dt)

    dry_domain = bool(xp.max(h) <= param.eps)
    if dry_domain:
        dt_cap = min(dt_cap, 60.0)

    # Safeguard 3: Never expand dt on invalid/non-finite dt, trigger error instead
    if not math.isfinite(loop.dt) or loop.dt <= 0.0:
        msg = f"CRITICAL NUMERICAL INSTABILITY: Invalid timestep dt={loop.dt} at t={loop.totaltime:.2f}s! Raising exception."
        print(f"\n[STABILITY ALERT] {msg}", flush=True)
        raise RuntimeError(msg)
    else:
        loop.dt = min(loop.dt, dt_cap)

    loop.dtmax = loop.dt
    model.time.dt = loop.dt
    
    # 8. Advection (compute dh, dhu, dhv)
    update_ev_vec(idx, param, model.evolv, model.flux, model.adv)
    
    if forcing.Rain.inputfile:
        if not forcing.Rain.uniform:
            if forcing.Rain.is_grid:
                if not hasattr(forcing.Rain, 'grid_indices') or forcing.Rain.grid_indices is None:
                    init_rain_grid_weights(param, model.blocks, forcing.Rain)
            elif forcing.Rain.istation is None:
                init_rain_istation(param, model.blocks, forcing.Rain)
        add_rain_vec(idx, param, loop, forcing.Rain, model.adv, model.zb[idx.interior], param.mask)

    if forcing.rivers:
        add_river_vec(idx, param, loop, forcing.rivers, model.adv, model.blocks)

    # 10. Infiltration (Initial/Continuous Loss)
    if param.il > 0.0 or param.cl > 0.0 or param.ilfile or param.clfile:
        apply_infiltration_gpu(model.il, model.cl, model.evolv, loop.dt * 0.5, adv_dh=model.adv.dh)
    
    # 10. Advance by dt/2
    adv_kernel_vec(idx, param, model.time.dt * 0.5, model.zb,
                   model.evolv, model.adv, model.evolv_o)
    
    # ============================================================
    # CORRECTOR STEP
    # ============================================================
    
    # 11. Fill halo for intermediate (block boundaries)
    fill_halo_all(idx, model.evolv_o, model.zb)
    
    # 11b. Update physical boundaries for intermediate step (IMPORTANT to avoid NaN)
    update_bnd(param, loop, forcing, model, evolv=model.evolv_o)

    # 12. Gradient again
    gradient_vec(idx, param, model.evolv_o, model.grad, model.zb)
    fill_gradient_halo_vec(idx, forcing, model.grad)
    
    # 13-14. Kurganov X & Y again
    kurganov_x_vec(idx, param, model.evolv_o, model.grad, model.flux, model.time.dtmax)
    kurganov_y_vec(idx, param, model.evolv_o, model.grad, model.flux, model.time.dtmax)
    
    # 15. Fill halo flux
    fill_halo_flux_vec(idx, model.flux)
    
    # 16. Advection again
    update_ev_vec(idx, param, model.evolv_o, model.flux, model.adv)
    
    if forcing.Rain.inputfile:
        if not forcing.Rain.uniform:
            if forcing.Rain.is_grid:
                if not hasattr(forcing.Rain, 'grid_indices') or forcing.Rain.grid_indices is None:
                    init_rain_grid_weights(param, model.blocks, forcing.Rain)
            elif forcing.Rain.istation is None:
                init_rain_istation(param, model.blocks, forcing.Rain)
        add_rain_vec(idx, param, loop, forcing.Rain, model.adv, model.zb[idx.interior], param.mask)
    
    if forcing.rivers:
        add_river_vec(idx, param, loop, forcing.rivers, model.adv, model.blocks)

    # 17b. Infiltration again
    if param.il > 0.0 or param.cl > 0.0 or param.ilfile or param.clfile:
        apply_infiltration_gpu(model.il, model.cl, model.evolv_o, loop.dt, adv_dh=model.adv.dh)
    
    # 18. Advance by dt
    adv_kernel_vec(idx, param, model.time.dt, model.zb,
                   model.evolv, model.adv, model.evolv_o)
    
    # 19. Friction
    friction_vec(idx, param, model.time.dt, model.cf, model.evolv_o)
    
    # 20. Cleanup
    cleanup_vec(idx, model.evolv_o, model.evolv)
