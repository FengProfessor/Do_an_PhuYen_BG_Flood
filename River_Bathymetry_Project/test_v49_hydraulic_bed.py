"""Focused V49-E logic tests."""

from __future__ import annotations

import math

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from v49_synthesize_hydraulic_bed import (
    authorized_reach_ids,
    linear_bed_target,
    raised_cosine_weight,
)


def test_raised_cosine_has_center_and_bank_boundary_conditions() -> None:
    assert raised_cosine_weight(0.0, 50.0) == 1.0
    assert raised_cosine_weight(50.0, 50.0) == 0.0
    assert math.isclose(raised_cosine_weight(25.0, 50.0), 0.5, abs_tol=1.0e-12)


def test_linear_bed_target_preserves_v49d_endpoints_without_global_filter() -> None:
    assert linear_bed_target(10.0, 6.0, 0.0) == 10.0
    assert linear_bed_target(10.0, 6.0, 1.0) == 6.0
    assert linear_bed_target(10.0, 6.0, 0.25) == 9.0


def test_authorization_is_strict_intersection_of_d_and_c1() -> None:
    reaches = gpd.GeoDataFrame(
        {
            "reach_id": ["A", "B", "C"],
            "geometry_authorized_for_v49e": [True, True, False],
            "geometry": [
                LineString([(0, 0), (1, 0)]),
                LineString([(0, 1), (1, 1)]),
                LineString([(0, 2), (1, 2)]),
            ],
        },
        geometry="geometry",
        crs="EPSG:32649",
    )
    gate = pd.DataFrame(
        {
            "reach_id": ["A", "B", "C"],
            "c1_authorized_for_v49e": [True, False, True],
        }
    )
    assert authorized_reach_ids(reaches, gate) == ["A"]
