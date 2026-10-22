"""Focused logic tests for V49-C.1 fixed-water evidence decisions."""

from __future__ import annotations

from v49_fixed_water_evidence_audit import decide_fixed_water_status, parse_other_tags


def base(**overrides):
    e = {
        "final_class": "RIVER_STREAM",
        "jrc_occurrence_p50": 70.0,
        "jrc_recurrence_p50": 95.0,
        "jrc_2024_permanent_fraction": 0.5,
        "jrc_2024_seasonal_fraction": 0.2,
        "graph_length_m": 1000.0,
        "current_osm_channel_m": 500.0,
        "current_osm_intermittent": False,
        "current_osm_polygon_dominant_type": "river",
        "current_osm_polygon_overlap_fraction": 0.5,
    }
    e.update(overrides)
    return e


def test_strong_jrc_plus_channel_support_is_persistent():
    status, _ = decide_fixed_water_status(base())
    assert status == "CONFIRMED_PERSISTENT"


def test_jrc_absence_alone_does_not_claim_no_river():
    status, _ = decide_fixed_water_status(base(
        jrc_occurrence_p50=5.0,
        jrc_recurrence_p50=5.0,
        jrc_2024_permanent_fraction=0.0,
        current_osm_channel_m=800.0,
        graph_length_m=1200.0,
    ))
    assert status == "INSUFFICIENT_EVIDENCE"


def test_high_recurrence_recent_permanent_plus_topology_can_confirm_without_osm():
    status, _ = decide_fixed_water_status(base(
        jrc_occurrence_p50=40.0,
        jrc_recurrence_p50=100.0,
        jrc_2024_permanent_fraction=0.72,
        jrc_2024_seasonal_fraction=0.26,
        current_osm_channel_m=0.0,
        graph_length_m=420.0,
    ))
    assert status == "CONFIRMED_PERSISTENT"


def test_intermittent_with_weak_jrc_is_seasonal_dynamic():
    status, _ = decide_fixed_water_status(base(
        jrc_occurrence_p50=35.0,
        jrc_recurrence_p50=90.0,
        jrc_2024_permanent_fraction=0.05,
        current_osm_intermittent=True,
    ))
    assert status == "SEASONAL_DYNAMIC"


def test_reservoir_overlap_blocks_river_auto_treatment():
    status, _ = decide_fixed_water_status(base(
        current_osm_polygon_dominant_type="reservoir",
        current_osm_polygon_overlap_fraction=0.8,
    ))
    assert status == "CONFLICT_REVIEW_REQUIRED"


def test_unknown_with_strong_evidence_stays_review_required():
    status, _ = decide_fixed_water_status(base(final_class="UNKNOWN_REVIEW_REQUIRED"))
    assert status == "CONFLICT_REVIEW_REQUIRED"


def test_estuary_requires_tidal_review():
    status, _ = decide_fixed_water_status(base(final_class="ESTUARY_TIDAL_RIVER"))
    assert status == "CONFLICT_REVIEW_REQUIRED"


def test_parse_geofabrik_other_tags():
    tags = parse_other_tags('"water"=>"reservoir","intermittent"=>"yes"')
    assert tags == {"water": "reservoir", "intermittent": "yes"}
