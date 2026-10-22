import numpy as np

from v49_build_water_inventory import build_ocean_mask, relabel_deterministically
from v49_classify_water_objects import classify_water_object


def test_ocean_mask_does_not_leak_far_up_narrow_river():
    water = np.zeros((60, 80), dtype=bool)
    water[:, 55:] = True
    water[28:31, 10:56] = True

    ocean = build_ocean_mask(
        water,
        core_radius_pixels=4,
        restore_radius_pixels=4,
        east_seed_columns=8,
    )

    assert ocean[:, 70:].all()
    assert not ocean[29, 10]
    assert water[29, 10]


def test_relabel_is_deterministic_top_left_order():
    mask = np.zeros((10, 12), dtype=bool)
    mask[6:8, 1:3] = True
    mask[1:3, 8:10] = True

    labels_a, _ = relabel_deterministically(mask)
    labels_b, _ = relabel_deterministically(mask.copy())

    assert np.array_equal(labels_a, labels_b)
    assert labels_a[1, 8] == 1
    assert labels_a[6, 1] == 2


def test_classifier_keeps_estuary_in_review_queue():
    klass, confidence, review, _ = classify_water_object(
        {
            "distance_to_ocean_m": 120.0,
            "hydrorivers_min_m": 30.0,
            "osm_waterway_min_m": 20.0,
            "hydrorivers_within_90m_fraction": 0.4,
            "osm_within_90m_fraction": 0.5,
            "hydrorivers_feature_count": 2,
        }
    )

    assert klass == "ESTUARY_REVIEW_REQUIRED"
    assert confidence == "MEDIUM"
    assert review is True


def test_classifier_never_invents_lake_or_reservoir_without_evidence():
    klass, _, review, _ = classify_water_object(
        {
            "distance_to_ocean_m": 5000.0,
            "hydrorivers_min_m": 1000.0,
            "osm_waterway_min_m": 1000.0,
            "hydrorivers_within_90m_fraction": 0.0,
            "osm_within_90m_fraction": 0.0,
            "hydrorivers_feature_count": 0,
        }
    )

    assert klass == "OPEN_WATER_REVIEW_REQUIRED"
    assert review is True


def test_large_broad_water_is_not_promoted_to_river_by_one_crossing_line():
    klass, _, review, _ = classify_water_object(
        {
            "area_km2": 40.0,
            "distance_to_ocean_m": 30000.0,
            "hydrorivers_min_m": 0.0,
            "osm_waterway_min_m": 0.0,
            "hydrorivers_within_90m_fraction": 0.14,
            "osm_within_90m_fraction": 0.11,
            "hydrorivers_feature_count": 12,
        }
    )

    assert klass == "OPEN_WATER_REVIEW_REQUIRED"
    assert review is True
