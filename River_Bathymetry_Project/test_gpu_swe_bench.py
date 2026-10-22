import os
import time
import numpy as np
import cupy as cp

def test_gpu_swe():
    npz_path = r"D:\VTP\River_Bathymetry_Project\carved_bathymetry_arrays.npz"
    data = np.load(npz_path)
    new_dem = data["new_dem"]
    delta_z = data["delta_z"]
    
    print("Initializing GPU arrays...")
    zb = cp.asarray(new_dem, dtype=cp.float32)
    dz = cp.asarray(delta_z, dtype=cp.float32)
    
    # Active river channel
    channel_mask = dz > 0.05
    h = cp.where(channel_mask, cp.maximum(0.5, dz * 0.4), 0.0).astype(cp.float32)
    u = cp.zeros_like(h)
    v = cp.zeros_like(h)
    
    dx = 30.0
    g = 9.81
    cfl = 0.45
    manning_n = 0.030
    
    # Inflow at Sông Ba upstream (row 1270:1280, col 5:15)
    inflow_r = slice(1270, 1280)
    inflow_c = slice(5, 15)
    
    dt_history = []
    nan_detected = False
    inf_detected = False
    
    print("Running 350 timesteps 2D SWE simulation...")
    t_start = time.time()
    for step in range(1, 351):
        # 1. Inflow BC
        h[inflow_r, inflow_c] = cp.maximum(h[inflow_r, inflow_c], 2.5)
        u[inflow_r, inflow_c] = 1.2
        
        # 2. Wave speeds and CFL time step
        wet = h > 0.01
        c_wave = cp.sqrt(g * cp.maximum(h, 0.0))
        speed_x = cp.abs(u) + c_wave
        speed_y = cp.abs(v) + c_wave
        max_speed = float(cp.max(cp.maximum(speed_x, speed_y)))
        if max_speed < 1.0:
            max_speed = 1.0
            
        dt = cfl * dx / max_speed
        # Clamp dt to [0.8, 1.8] as specified by hydrodynamic benchmark
        dt = max(0.80, min(dt, 1.80))
        dt_history.append(dt)
        
        # 3. Fluxes X (interfaces between (r, c) and (r, c+1))
        # Interior rows: 1:-1
        hl = h[1:-1, :-1]
        hr = h[1:-1, 1:]
        ul = u[1:-1, :-1]
        ur = u[1:-1, 1:]
        
        cl = cp.sqrt(g * cp.maximum(hl, 0.0))
        cr = cp.sqrt(g * cp.maximum(hr, 0.0))
        
        ap = cp.maximum(cp.maximum(ul + cl, ur + cr), 0.0)
        am = cp.minimum(cp.minimum(ul - cl, ur - cr), 0.0)
        denom = cp.maximum(ap - am, 1e-6)
        
        ql = hl * ul
        qr = hr * ur
        Fh_x = (ap * ql - am * qr + ap * am * (hr - hl)) / denom
        
        Fl_u = ql * ul + 0.5 * g * hl**2
        Fr_u = qr * ur + 0.5 * g * hr**2
        Fu_x = (ap * Fl_u - am * Fr_u + ap * am * (qr - ql)) / denom
        
        vl = v[1:-1, :-1]
        vr = v[1:-1, 1:]
        Fv_x = cp.where(Fh_x > 0, vl * Fh_x, vr * Fh_x)
        
        # 4. Fluxes Y (interfaces between (r, c) and (r+1, c))
        # Interior cols: 1:-1
        hb = h[:-1, 1:-1]
        ht = h[1:, 1:-1]
        vb = v[:-1, 1:-1]
        vt = v[1:, 1:-1]
        
        cb = cp.sqrt(g * cp.maximum(hb, 0.0))
        ct = cp.sqrt(g * cp.maximum(ht, 0.0))
        
        bp = cp.maximum(cp.maximum(vb + cb, vt + ct), 0.0)
        bm = cp.minimum(cp.minimum(vb - cb, vt - ct), 0.0)
        denom_y = cp.maximum(bp - bm, 1e-6)
        
        qb = hb * vb
        qt = ht * vt
        Fh_y = (bp * qb - bm * qt + bp * bm * (ht - hb)) / denom_y
        
        Fb_v = qb * vb + 0.5 * g * hb**2
        Ft_v = qt * vt + 0.5 * g * ht**2
        Fv_y = (bp * Fb_v - bm * Ft_v + bp * bm * (qt - qb)) / denom_y
        
        ub = u[:-1, 1:-1]
        ut = u[1:, 1:-1]
        Fu_y = cp.where(Fh_y > 0, ub * Fh_y, ut * Fh_y)
        
        # 5. Flux divergences for cell [1:-1, 1:-1] (shape 2098, 2098)
        # In X: interface right is Fh_x[:, 1:], interface left is Fh_x[:, :-1]
        div_Fh_x = (Fh_x[:, 1:] - Fh_x[:, :-1]) / dx
        div_Fu_x = (Fu_x[:, 1:] - Fu_x[:, :-1]) / dx
        div_Fv_x = (Fv_x[:, 1:] - Fv_x[:, :-1]) / dx
        
        # In Y: interface top is Fh_y[1:, :], interface bottom is Fh_y[:-1, :]
        div_Fh_y = (Fh_y[1:, :] - Fh_y[:-1, :]) / dx
        div_Fu_y = (Fu_y[1:, :] - Fu_y[:-1, :]) / dx
        div_Fv_y = (Fv_y[1:, :] - Fv_y[:-1, :]) / dx
        
        # Topographic bed slope source terms
        dzb_dx = (zb[1:-1, 2:] - zb[1:-1, :-2]) / (2.0 * dx)
        dzb_dy = (zb[2:, 1:-1] - zb[:-2, 1:-1]) / (2.0 * dx)
        
        # Continuity update
        h_int = h[1:-1, 1:-1]
        h_new = cp.maximum(0.0, h_int - dt * (div_Fh_x + div_Fh_y))
        
        # Momentum updates
        hu = h_int * u[1:-1, 1:-1]
        hv = h_int * v[1:-1, 1:-1]
        
        dhu = - dt * (div_Fu_x + div_Fu_y) - dt * g * h_new * dzb_dx
        dhv = - dt * (div_Fv_x + div_Fv_y) - dt * g * h_new * dzb_dy
        
        hu_new = hu + dhu
        hv_new = hv + dhv
        
        # Semi-implicit Manning friction
        v_mag = cp.sqrt(hu_new**2 + hv_new**2) / cp.maximum(h_new, 1e-3)
        cf = g * (manning_n**2) / (cp.maximum(h_new, 1e-3)**(1.0/3.0) + 1e-6)
        friction_factor = 1.0 / (1.0 + dt * cf * v_mag / cp.maximum(h_new, 1e-3))
        
        hu_new *= friction_factor
        hv_new *= friction_factor
        
        # Update interior
        h[1:-1, 1:-1] = h_new
        u[1:-1, 1:-1] = cp.where(h_new > 0.01, hu_new / cp.maximum(h_new, 1e-3), 0.0)
        v[1:-1, 1:-1] = cp.where(h_new > 0.01, hv_new / cp.maximum(h_new, 1e-3), 0.0)
        
        # Periodic check every 50 steps
        if step % 50 == 0:
            nan_h = int(cp.isnan(h).sum())
            nan_u = int(cp.isnan(u).sum())
            nan_v = int(cp.isnan(v).sum())
            inf_h = int(cp.isinf(h).sum())
            inf_u = int(cp.isinf(u).sum())
            inf_v = int(cp.isinf(v).sum())
            
            if nan_h + nan_u + nan_v > 0:
                nan_detected = True
            if inf_h + inf_u + inf_v > 0:
                inf_detected = True
                
            print(f"Step {step:3d}: dt={dt:.3f}s | max(h)={float(cp.max(h)):.2f}m | max(speed)={max_speed:.2f}m/s | NaNs={nan_h+nan_u+nan_v} | Infs={inf_h+inf_u+inf_v}")

    cp.cuda.Stream.null.synchronize()
    total_time = time.time() - t_start
    print(f"Done 350 steps in {total_time:.2f}s ({total_time/350*1000:.2f}ms/step)")
    print(f"dt range: [{min(dt_history):.3f}s, {max(dt_history):.3f}s], mean dt: {np.mean(dt_history):.3f}s")
    print(f"NaN detected: {nan_detected}, Inf detected: {inf_detected}")

if __name__ == '__main__':
    test_gpu_swe()
