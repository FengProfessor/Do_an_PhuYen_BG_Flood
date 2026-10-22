"""Focused tests for V49-G sensitivity construction and frozen comparison rules."""

from __future__ import annotations

import numpy as np
import pandas as pd
from affine import Affine
from shapely.geometry import LineString

from v49_synthesize_hydraulic_bed import synthesize_reach_delta


def _reach() -> pd.Series:
    return pd.Series(
        {
            "reach_id": "R",
            "geometry": LineString([(15.0, 45.0), (75.0, 45.0)]),
            "width_m": 60.0,
            "depth_est_m": 0.4,
            "depth_low_m": 0.2,
            "depth_high_m": 0.7,
            "preliminary_bed_upstream_m": 10.0,
            "preliminary_bed_downstream_m": 9.8,
        }
    )


def test_depth_field_controls_only_lowering_magnitude() -> None:
    dem = np.full((3, 3), 10.0, dtype=np.float32)
    valid = np.ones((3, 3), dtype=bool)
    class_mask = np.ones((3, 3), dtype=bool)
    protected = np.zeros((3, 3), dtype=bool)
    transform = Affine(30.0, 0.0, 0.0, 0.0, -30.0, 90.0)
    reach = _reach()

    low, low_allowed, low_trace = synthesize_reach_delta(
        dem, valid, transform, reach, class_mask, protected, depth_field="depth_low_m"
    )
    central, central_allowed, _ = synthesize_reach_delta(
        dem, valid, transform, reach, class_mask, protected, depth_field="depth_est_m"
    )
    high, high_allowed, high_trace = synthesize_reach_delta(
        dem, valid, transform, reach, class_mask, protected, depth_field="depth_high_m"
    )

    assert np.array_equal(low_allowed, central_allowed)
    assert np.array_equal(central_allowed, high_allowed)
    assert np.all(low <= central + 1.0e-7)
    assert np.all(central <= high + 1.0e-7)
    assert low_trace["selected_depth_field"] == "depth_low_m"
    assert high_trace["selected_depth_field"] == "depth_high_m"
    assert np.isclose(low.max(), 0.2)
    assert np.isclose(high.max(), 0.7)


def test_unknown_depth_field_is_rejected() -> None:
    dem = np.full((3, 3), 10.0, dtype=np.float32)
    try:
        synthesize_reach_delta(
            dem,
            np.ones((3, 3), dtype=bool),
            Affine(30.0, 0.0, 0.0, 0.0, -30.0, 90.0),
            _reach(),
            np.ones((3, 3), dtype=bool),
            np.zeros((3, 3), dtype=bool),
            depth_field="invented_depth",
        )
    except ValueError as exc:
        assert "Unsupported V49-D depth field" in str(exc)
    else:
        raise AssertionError("Unsupported depth field was accepted")
