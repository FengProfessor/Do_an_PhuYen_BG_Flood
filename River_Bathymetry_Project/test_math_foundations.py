"""
Verification & Adversarial Stress Tests for River Bathymetry Mathematical Foundations
Document under challenge: River_Bathymetry_Methodology.md
Tested by: Challenger M1 Math (teamwork_preview_challenger)
Date: 2026-10-09
"""

import sys
import numpy as np
import pytest

def phi_cos(xi):
    return np.cos(np.pi * xi / 2.0) ** 2

def phi_hermite(xi):
    return (1.0 - xi) ** 2 * (1.0 + 2.0 * xi)

def phi_quintic(xi):
    return 1.0 - (10.0 * xi**3 - 15.0 * xi**4 + 6.0 * xi**5)

def z_parabolic(x, W, d_max, z_bank):
    return z_bank - d_max * (1.0 - (2.0 * x / W) ** 2)

def run_carve_down_filter(z_raw, ds, epsilon):
    """
    Carve-Down Monotonic Filter implementation:
    z_k = min(z_raw_k, z_{k-1} - epsilon * ds)
    """
    N = len(z_raw)
    z_filtered = np.zeros(N, dtype=np.float64)
    z_filtered[0] = z_raw[0]
    for k in range(1, N):
        max_allowed = z_filtered[k-1] - epsilon * ds[k-1]
        z_filtered[k] = min(z_raw[k], max_allowed)
    return z_filtered

def count_sinks(z_profile):
    """
    Count local depressions and uphill flow steps:
    1. Uphill steps: z[k+1] > z[k]
    2. Strict interior sinks: z[k] < z[k-1] and z[k] < z[k+1]
    """
    uphill_steps = int(np.sum(np.diff(z_profile) > 0))
    interior_sinks = 0
    for i in range(1, len(z_profile) - 1):
        if z_profile[i] < z_profile[i-1] and z_profile[i] < z_profile[i+1]:
            interior_sinks += 1
    return uphill_steps, interior_sinks


def test_raised_cosine_transition():
    """
    Verify Raised Cosine Transition (Section 5.3):
    Phi(0) == 1.0, Phi(1) == 0.0, Phi'(0) == 0, Phi'(1) == 0, C_shape == 0.50.
    """
    val_0 = phi_cos(0.0)
    val_1 = phi_cos(1.0)
    assert np.isclose(val_0, 1.0)
    assert np.isclose(val_1, 0.0)

    h = 1e-7
    dphi_dxi_1 = (phi_cos(1.0) - phi_cos(1.0 - h)) / h
    assert np.isclose(dphi_dxi_1, 0.0, atol=1e-5)

    dphi_dxi_0 = (phi_cos(h) - phi_cos(0.0)) / h
    assert np.isclose(dphi_dxi_0, 0.0, atol=1e-5)

    xi_grid = np.linspace(0.0, 1.0, 10001)
    vals = phi_cos(xi_grid)
    diffs = np.diff(vals)
    assert np.all(diffs <= 1e-12)

    area = np.trapezoid(vals, xi_grid) if hasattr(np, 'trapezoid') else np.trapz(vals, xi_grid)
    assert np.isclose(area, 0.50, atol=1e-4)


def test_cubic_hermite_transition():
    """
    Verify Cubic Hermite Transition (Section 5.3):
    Phi(0) == 1.0, Phi(1) == 0.0, Phi'(0) == 0, Phi'(1) == 0, C_shape == 0.50.
    """
    val_0 = phi_hermite(0.0)
    val_1 = phi_hermite(1.0)
    assert np.isclose(val_0, 1.0)
    assert np.isclose(val_1, 0.0)

    h = 1e-7
    dphi_dxi_1 = (phi_hermite(1.0) - phi_hermite(1.0 - h)) / h
    assert np.isclose(dphi_dxi_1, 0.0, atol=1e-5)

    dphi_dxi_0 = (phi_hermite(h) - phi_hermite(0.0)) / h
    assert np.isclose(dphi_dxi_0, 0.0, atol=1e-5)

    xi_grid = np.linspace(0.0, 1.0, 10001)
    vals = phi_hermite(xi_grid)
    diffs = np.diff(vals)
    assert np.all(diffs <= 1e-12)

    area = np.trapezoid(vals, xi_grid) if hasattr(np, 'trapezoid') else np.trapz(vals, xi_grid)
    assert np.isclose(area, 0.50, atol=1e-4)


def test_quintic_hermite_transition_c2():
    """
    Verify Quintic Hermite Transition (Section 5.3):
    Phi(0) == 1.0, Phi(1) == 0.0, C1 and C2 tangency at both boundaries.
    """
    val_0 = phi_quintic(0.0)
    val_1 = phi_quintic(1.0)
    assert np.isclose(val_0, 1.0)
    assert np.isclose(val_1, 0.0)

    h = 1e-5
    dphi_1 = (phi_quintic(1.0) - phi_quintic(1.0 - h)) / h
    dphi_0 = (phi_quintic(h) - phi_quintic(0.0)) / h
    assert np.isclose(dphi_1, 0.0, atol=1e-4)
    assert np.isclose(dphi_0, 0.0, atol=1e-4)

    d2phi_1 = (phi_quintic(1.0) - 2.0 * phi_quintic(1.0 - h) + phi_quintic(1.0 - 2*h)) / (h**2)
    d2phi_0 = (phi_quintic(2*h) - 2.0 * phi_quintic(h) + phi_quintic(0.0)) / (h**2)
    assert np.isclose(d2phi_1, 0.0, atol=1e-3)
    assert np.isclose(d2phi_0, 0.0, atol=1e-3)


def test_parabolic_cross_section():
    """
    Verify Parabolic Cross Section:
    z(0) = z_bank - d_max, z(+-W/2) = z_bank.
    """
    W = 450.0
    d_max = 3.5
    z_bank = 8.0

    val_center = z_parabolic(0.0, W, d_max, z_bank)
    val_left_bank = z_parabolic(-W / 2.0, W, d_max, z_bank)
    val_right_bank = z_parabolic(W / 2.0, W, d_max, z_bank)

    assert np.isclose(val_center, z_bank - d_max)
    assert np.isclose(val_left_bank, z_bank)
    assert np.isclose(val_right_bank, z_bank)

    x_grid = np.linspace(-W / 2.0, W / 2.0, 10001)
    depth_grid = z_bank - z_parabolic(x_grid, W, d_max, z_bank)
    num_area = np.trapezoid(depth_grid, x_grid) if hasattr(np, 'trapezoid') else np.trapz(depth_grid, x_grid)
    theo_area = (2.0 / 3.0) * W * d_max
    assert np.isclose(num_area, theo_area, rtol=1e-4)


def test_anti_sink_monotonic_filter():
    """
    Verify Anti-Sink Monotonic Bed Filter:
    - dz/ds <= -epsilon everywhere.
    - Sink count == 0.
    """
    np.random.seed(42)
    L = 70000.0
    N_points = 2334
    s = np.linspace(0, L, N_points)
    ds = np.diff(s)

    base_slope = 20.0 / L
    z_smooth = 20.0 - base_slope * s

    noise = np.random.normal(0, 1.5, N_points)
    bumps = np.zeros(N_points)
    bumps[300:350] += 5.0
    bumps[700:720] += 8.0
    bumps[1200:1280] += 4.0
    bumps[1600:1650] += 6.0
    bumps[2000:2030] += 3.5

    sinks = np.zeros(N_points)
    sinks[500:520] -= 4.0
    sinks[900:940] -= 6.0
    sinks[1400:1430] -= 5.0
    sinks[1800:1820] -= 3.0

    z_raw = z_smooth + noise + bumps + sinks

    raw_uphill, raw_sinks = count_sinks(z_raw)
    assert raw_uphill > 0
    assert raw_sinks > 0

    epsilon = 2.0e-4
    z_filtered = run_carve_down_filter(z_raw, ds, epsilon)

    slope_diff = np.diff(z_filtered) / ds
    assert np.all(slope_diff <= -epsilon + 1e-12)

    filtered_uphill, filtered_sinks = count_sinks(z_filtered)
    assert filtered_uphill == 0
    assert filtered_sinks == 0
    assert np.all(z_filtered <= z_raw + 1e-12)


def test_adversarial_anti_sink_extreme_stress():
    """
    Adversarial Stress Test for Anti-Sink Filter:
    - Massive 20m high vertical barrier (wall)
    - Consecutive alternating 10m spikes and pits
    - Extremely long flat plateau (zero slope in raw)
    Verify that filter strictly enforces downhill gradient without numeric collapse.
    """
    N = 5000
    ds = np.full(N - 1, 15.0)  # 15m grid spacing
    z_raw = np.zeros(N)
    z_raw[0] = 50.0

    z_raw[1:1000] = 50.0
    z_raw[1000:1500] = 80.0
    for i in range(1500, 3000):
        z_raw[i] = 40.0 + (15.0 if i % 2 == 0 else -15.0)
    z_raw[3000:3500] = -20.0
    z_raw[3500:4000] = 30.0
    z_raw[4000:5000] = -10.0

    epsilon = 2.0e-4
    z_filtered = run_carve_down_filter(z_raw, ds, epsilon)

    slope_diff = np.diff(z_filtered) / ds
    assert np.all(slope_diff <= -epsilon + 1e-12)
    filtered_uphill, filtered_sinks = count_sinks(z_filtered)
    assert filtered_uphill == 0
    assert filtered_sinks == 0
    assert np.all(z_filtered <= z_raw + 1e-12)


def test_leopold_maddock_and_manning():
    """
    Verify Leopold & Maddock Closure (Section 2.1) & Manning in-bank conveyance (Section 2.3).
    """
    b, f, m = 0.50, 0.40, 0.10
    assert np.isclose(b + f + m, 1.00)

    W = 450.0
    d_max = 3.5
    S_0 = 0.000287
    n = 0.030

    A = (2.0 / 3.0) * W * d_max
    P = W
    R_h = A / P
    Q_in_bank = (1.0 / n) * A * (R_h ** (2.0 / 3.0)) * (S_0 ** 0.5)
    assert np.isclose(Q_in_bank, 1043.10, atol=1.0)


def test_2d_floodplain_preservation_and_tangency():
    """
    Test 2D Synthetic River Patch:
    Verify Section 5.4 Outer Domain Invariance:
    - Delta z == 0.0 everywhere outside river mask
    - Continuous gradient across the river boundary
    """
    ny, nx = 100, 100
    y_coords, x_coords = np.mgrid[0:ny, 0:nx]
    channel_center = 50.0
    half_width = 10.0

    dist_from_center = np.abs(y_coords - channel_center)
    river_mask = dist_from_center <= half_width

    xi = dist_from_center / half_width
    xi_channel = np.where(river_mask, xi, 1.0)

    d_max = 3.5
    phi = np.where(river_mask, phi_cos(xi_channel), 0.0)
    delta_z = d_max * phi

    outer_delta_z = delta_z[~river_mask]
    assert np.all(outer_delta_z == 0.0), "Outer domain modified!"

    boundary_cells = river_mask & (dist_from_center >= half_width - 1.0)
    max_boundary_delta_z = np.max(delta_z[boundary_cells])
    assert max_boundary_delta_z < 0.15, f"Boundary jump too large: {max_boundary_delta_z}"

    exact_bank = phi_cos(1.0) * d_max
    assert np.isclose(exact_bank, 0.0)


def print_summary():
    print("=" * 70)
    print("ALL VERIFICATION AND ADVERSARIAL STRESS TESTS FINISHED.")
    print("=" * 70)

if __name__ == "__main__":
    test_raised_cosine_transition()
    test_cubic_hermite_transition()
    test_quintic_hermite_transition_c2()
    test_parabolic_cross_section()
    test_anti_sink_monotonic_filter()
    test_adversarial_anti_sink_extreme_stress()
    test_leopold_maddock_and_manning()
    test_2d_floodplain_preservation_and_tangency()
    print_summary()
