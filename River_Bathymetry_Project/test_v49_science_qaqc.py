"""Focused tests for V49-F aggregation rules."""

from __future__ import annotations

import pandas as pd

from v49_science_qaqc import (
    build_coverage_by_class,
    build_major_persistent_omissions,
    classify_geometry_source,
)


def test_coverage_distinguishes_object_representation_from_modified_footprint() -> None:
    classification = pd.DataFrame(
        {
            "object_id": ["A", "B"],
            "final_class": ["RIVER_STREAM", "RIVER_STREAM"],
            "area_km2": [2.0, 3.0],
        }
    )
    c1 = pd.DataFrame(
        {
            "object_id": ["A", "B"],
            "fixed_water_status": ["CONFIRMED_PERSISTENT", "CONFIRMED_PERSISTENT"],
        }
    )
    e = pd.DataFrame(
        {
            "water_class": ["RIVER_STREAM"],
            "modified_area_m2": [10_000.0],
            "v49c_object_ids": ["A"],
        }
    )
    row = build_coverage_by_class(classification, c1, e).iloc[0]
    assert row.v49e_represented_object_count_pct == 50.0
    assert row.v49e_represented_object_area_pct == 40.0
    assert row.v49e_actual_modified_area_km2 == 0.01


def test_major_omission_rule_is_explicit_and_does_not_treat_ocean_as_inland_omission() -> None:
    c1 = pd.DataFrame(
        {
            "object_id": ["A", "B", "O"],
            "final_class": ["RIVER_STREAM", "RIVER_STREAM", "OCEAN"],
            "area_km2": [1.2, 0.2, 100.0],
            "graph_major_reach_count": [0, 1, 4],
            "fixed_water_status": ["CONFIRMED_PERSISTENT"] * 3,
            "treatment_code": ["R", "R", "M"],
            "future_channel_geometry_eligible": [True, True, False],
            "decision_reason": ["x", "y", "z"],
        }
    )
    omissions = build_major_persistent_omissions(c1, {"A"})
    assert omissions.object_id.tolist() == ["B"]


def test_geometry_source_categories_do_not_upgrade_empirical_fallback() -> None:
    assert classify_geometry_source("MANNING_RECTANGULAR_QMEAN_PROXY") == "HYDRAULIC_INVERSION"
    assert classify_geometry_source("POWERLAW_HYDROMT_QMEAN_PROXY") == "EMPIRICAL_FALLBACK"
    assert (
        classify_geometry_source("POWERLAW_HYDROMT_QMEAN_PROXY_MANNING_REJECTED")
        == "EMPIRICAL_FALLBACK"
    )
    assert classify_geometry_source("UNRESOLVED_LEGACY_CANAL") == "UNRESOLVED"
