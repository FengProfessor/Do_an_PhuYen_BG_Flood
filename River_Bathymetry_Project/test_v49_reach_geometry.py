"""Focused scientific/logic tests for V49-D reach geometry."""

from __future__ import annotations

import math

from shapely.geometry import LineString, Polygon

from v49_estimate_reach_geometry import (
    GeometryConfig,
    authorization_decision,
    confluence_state,
    depth_uncertainty,
    hydromt_powerlaw_depth,
    manning_rectangular_depth,
    manning_rectangular_discharge,
    width_from_cross_section,
)


def test_manning_inverse_reproduces_target_discharge() -> None:
    q = 120.0
    width = 80.0
    slope = 0.0008
    n = 0.035
    depth = manning_rectangular_depth(q, width, slope, n)
    assert 0.0 < depth < 20.0
    reconstructed = manning_rectangular_discharge(width, depth, slope, n)
    assert math.isclose(reconstructed, q, rel_tol=1.0e-8)


def test_hydromt_powerlaw_documented_default() -> None:
    q = 100.0
    expected = 0.27 * q**0.30
    assert math.isclose(hydromt_powerlaw_depth(q), expected, rel_tol=1.0e-12)
    assert math.isnan(hydromt_powerlaw_depth(0.0))


def test_persistent_water_cross_section_recovers_rectangle_width() -> None:
    line = LineString([(0.0, -500.0), (0.0, 500.0)])
    water = Polygon([(-50.0, -600.0), (50.0, -600.0), (50.0, 600.0), (-50.0, 600.0)])
    width, endpoints = width_from_cross_section(line, water, 0.5, GeometryConfig())
    assert math.isclose(width, 100.0, abs_tol=1.0e-6)
    assert endpoints is not None


def test_uncertainty_is_wider_than_minimum_for_proxy_methods() -> None:
    cfg = GeometryConfig()
    low, high, quality = depth_uncertainty(2.0, "MANNING_RECTANGULAR_QMEAN_PROXY", cfg)
    assert quality == "HIGH"
    assert low <= 0.70 * 2.0
    assert high >= 1.30 * 2.0
    low2, high2, quality2 = depth_uncertainty(2.0, "POWERLAW_HYDROMT_QMEAN_PROXY", cfg)
    assert quality2 == "VERY_HIGH"
    assert low2 < low
    assert high2 > high


def test_tidal_and_unverified_canal_are_never_auto_authorized() -> None:
    tidal = authorization_decision(
        "HYDRORIVERS", ["ESTUARY_TIDAL_RIVER"], 200.0, 2.0, "POWERLAW_HYDROMT_QMEAN_TIDAL_PRIOR_ONLY", False,
        "DIRECT_MEDIUM"
    )
    assert tidal[0] is False
    assert "TIDAL" in tidal[1]
    canal = authorization_decision(
        "LEGACY_CANAL_CANDIDATE", ["RIVER_STREAM"], 30.0, 1.0, "POWERLAW_HYDROMT_QMEAN_PROXY", False,
        "DIRECT_MEDIUM"
    )
    assert canal[0] is False
    assert "NO_ACCEPTED_CANAL" in canal[1]


def test_name_only_depth_is_not_needed_for_authorization() -> None:
    authorized, reason = authorization_decision(
        "HYDRORIVERS", ["RIVER_STREAM"], 120.0, 2.5, "MANNING_RECTANGULAR_QMEAN_PROXY", False,
        "DIRECT_MEDIUM"
    )
    assert authorized is True
    assert "traceable" in reason


def test_indirect_area_length_width_is_review_only() -> None:
    authorized, reason = authorization_decision(
        "HYDRORIVERS", ["RIVER_STREAM"], 400.0, 1.0, "POWERLAW_HYDROMT_QMEAN_PROXY", False,
        "INDIRECT_VERY_LOW"
    )
    assert authorized is False
    assert "WIDTH_EVIDENCE" in reason


def test_confluence_inversion_requires_explanation_or_review() -> None:
    state, _ = confluence_state(1.2, True, False, False, 0.75)
    assert state == "REVIEW_REQUIRED_BED_INVERSION"
    state2, explanation2 = confluence_state(1.2, True, False, True, 0.75)
    assert state2 == "CONTROL_EXCEPTION_STRUCTURE"
    assert explanation2
    state3, explanation3 = confluence_state(1.2, False, True, False, 0.75)
    assert state3 == "CONTROL_CONTEXT_TIDAL_REVIEW"
    assert explanation3


def test_reach_with_downstream_bed_rise_is_held_before_synthesis() -> None:
    authorized, reason = authorization_decision(
        "HYDRORIVERS", ["RIVER_STREAM"], 120., 2.5, "MANNING_RECTANGULAR_QMEAN_PROXY", False,
        "DIRECT_MEDIUM", preliminary_bed_upstream_m=100., preliminary_bed_downstream_m=102.089)
    assert not authorized and "BED_RISE" in reason


def test_unresolved_bed_endpoints_are_not_automatic_inputs() -> None:
    authorized, reason = authorization_decision(
        "HYDRORIVERS", ["RIVER_STREAM"], 120., 2.5, "MANNING_RECTANGULAR_QMEAN_PROXY", False,
        "DIRECT_MEDIUM", preliminary_bed_upstream_m=float("nan"), preliminary_bed_downstream_m=100.)
    assert not authorized and "UNRESOLVED" in reason
