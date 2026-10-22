from v49_classify_waterbodies import ClassificationConfig, TREATMENT_BY_CLASS, choose_class, treatment_for_class


CFG = ClassificationConfig()


def base_evidence(**overrides):
    data = {
        "object_id": "W20_TEST",
        "provisional_class": "REVIEW_REQUIRED",
        "area_km2": 0.2,
        "distance_to_ocean_m": 10000.0,
        "worldcover_water_fraction": 0.5,
        "worldcover_wetland_fraction": 0.0,
        "shape_elongation": 3.0,
        "graph_length_m": 0.0,
        "graph_major_reach_count": 0,
        "osm_river_m": 0.0,
        "osm_stream_m": 0.0,
        "osm_canal_m": 0.0,
        "osm_tidal_channel_m": 0.0,
        "osm_names": "",
    }
    data.update(overrides)
    return data


def test_ocean_is_always_marine_treatment():
    final_class, _, confidence, review, _ = choose_class(
        base_evidence(object_id="OCEAN_0001", provisional_class="OCEAN", graph_length_m=50000), CFG
    )
    assert final_class == "OCEAN"
    assert confidence == "HIGH"
    assert review is False
    assert treatment_for_class(final_class)[0] == "EXTERNAL_BATHYMETRY_OR_BOUNDARY"


def test_coastal_supported_channel_becomes_estuary():
    final_class, _, _, review, _ = choose_class(
        base_evidence(distance_to_ocean_m=100, graph_length_m=1200, osm_river_m=800), CFG
    )
    assert final_class == "ESTUARY_TIDAL_RIVER"
    assert review is False


def test_song_hinh_style_broad_named_water_becomes_lake_reservoir():
    final_class, _, confidence, review, _ = choose_class(
        base_evidence(
            area_km2=42.8,
            distance_to_ocean_m=37000,
            worldcover_water_fraction=0.65,
            shape_elongation=2.2,
            graph_length_m=18000,
            osm_river_m=24000,
            osm_names="Hồ Sông Hinh",
        ),
        CFG,
    )
    assert final_class == "LAKE_RESERVOIR"
    assert confidence == "HIGH"
    assert review is False


def test_wetland_requires_strong_wetland_and_weak_channel_support():
    final_class, _, _, review, _ = choose_class(
        base_evidence(worldcover_water_fraction=0.1, worldcover_wetland_fraction=0.35, graph_length_m=0), CFG
    )
    assert final_class == "WETLAND_FLOODPLAIN_WATER"
    assert review is False
    assert treatment_for_class(final_class)[0] == "PRESERVE_STORAGE_NO_RIVER_TRENCH"


def test_direct_dominant_osm_canal_on_linear_object_becomes_canal():
    final_class, _, _, review, _ = choose_class(
        base_evidence(area_km2=0.08, shape_elongation=8, osm_canal_m=900, osm_river_m=20), CFG
    )
    assert final_class == "CANAL"
    assert review is False


def test_canal_crossing_broad_water_does_not_override_natural_or_storage_context():
    final_class, _, _, _, _ = choose_class(
        base_evidence(
            area_km2=6.0,
            distance_to_ocean_m=10000,
            worldcover_water_fraction=0.85,
            shape_elongation=2.0,
            graph_length_m=1200,
            osm_canal_m=300,
            osm_river_m=2000,
        ),
        CFG,
    )
    assert final_class != "CANAL"


def test_broad_near_coastal_ambiguous_water_is_review_no_carve():
    final_class, subtype, _, review, _ = choose_class(
        base_evidence(
            area_km2=4.5,
            distance_to_ocean_m=2400,
            graph_length_m=5000,
            osm_river_m=6000,
            worldcover_water_fraction=0.8,
        ),
        CFG,
    )
    assert final_class == "UNKNOWN_REVIEW_REQUIRED"
    assert subtype == "COASTAL_RIVER_LAGOON_AMBIGUOUS"
    assert review is True
    assert treatment_for_class(final_class)[0] == "NO_AUTOMATIC_CARVING"


def test_osm_only_low_confidence_candidate_stays_review_required():
    final_class, subtype, _, review, _ = choose_class(
        base_evidence(
            provisional_class="OSM_WATERWAY_CANDIDATE",
            hydrorivers_feature_count=0,
            graph_length_m=0,
            osm_river_m=700,
            shape_elongation=3.0,
        ),
        CFG,
    )
    assert final_class == "UNKNOWN_REVIEW_REQUIRED"
    assert subtype == "OSM_ONLY_WATERWAY_AMBIGUOUS"
    assert review is True


def test_mixed_wetland_and_channel_evidence_stays_review_required():
    final_class, subtype, _, review, _ = choose_class(
        base_evidence(
            area_km2=0.5,
            worldcover_water_fraction=0.26,
            worldcover_wetland_fraction=0.10,
            graph_length_m=1300,
            shape_elongation=1.1,
        ),
        CFG,
    )
    assert final_class == "UNKNOWN_REVIEW_REQUIRED"
    assert subtype == "MIXED_WETLAND_CHANNEL_AMBIGUOUS"
    assert review is True


def test_unsupported_open_water_is_unknown_no_carve():
    final_class, _, _, review, _ = choose_class(
        base_evidence(area_km2=1.3, distance_to_ocean_m=1500, worldcover_water_fraction=0.98), CFG
    )
    assert final_class == "UNKNOWN_REVIEW_REQUIRED"
    assert review is True
    assert treatment_for_class(final_class)[0] == "NO_AUTOMATIC_CARVING"


def test_every_registered_class_has_a_nonempty_treatment():
    assert TREATMENT_BY_CLASS
    for final_class, (code, rule) in TREATMENT_BY_CLASS.items():
        assert final_class
        assert code
        assert rule
