"""Evidence decisions must distinguish water type from water persistence."""

from v49_fixed_water_evidence_audit import decide_fixed_water_status
from v49_reconcile_water_evidence import reconciled_class


def evidence(**overrides):
    row = dict(final_class="RIVER_STREAM", current_osm_polygon_dominant_type="reservoir",
               current_osm_polygon_overlap_fraction=0.98, jrc_occurrence_p50=40.,
               jrc_recurrence_p50=96., jrc_2024_permanent_fraction=0.02,
               jrc_2024_seasonal_fraction=0.94, current_osm_channel_m=500., graph_length_m=1200.)
    row.update(overrides)
    return row


def test_reservoir_type_is_corrected_without_claiming_permanent_water():
    row = evidence()
    cls, reason = reconciled_class(row)
    assert cls == "LAKE_RESERVOIR" and reason
    row["final_class"] = cls
    assert decide_fixed_water_status(row)[0] == "SEASONAL_DYNAMIC"


def test_semantic_lake_tag_without_temporal_evidence_does_not_prove_persistence():
    row = evidence(final_class="LAKE_RESERVOIR", jrc_occurrence_p50=0.,
                   jrc_recurrence_p50=0., jrc_2024_permanent_fraction=0., jrc_2024_seasonal_fraction=0.)
    assert decide_fixed_water_status(row)[0] == "INSUFFICIENT_EVIDENCE"


def test_ocean_and_weak_overlaps_are_not_reclassified():
    assert reconciled_class(evidence(final_class="OCEAN"))[0] == "OCEAN"
    assert reconciled_class(evidence(current_osm_polygon_overlap_fraction=0.3))[0] == "RIVER_STREAM"


def test_unknown_channel_needs_polygon_and_linear_support():
    row = evidence(final_class="UNKNOWN_REVIEW_REQUIRED", current_osm_polygon_dominant_type="river")
    assert reconciled_class(row)[0] == "RIVER_STREAM"
    row.update(current_osm_channel_m=0., graph_length_m=0.)
    assert reconciled_class(row)[0] == "UNKNOWN_REVIEW_REQUIRED"


def test_low_coastal_channel_is_held_for_tidal_regime_assessment():
    row = evidence(final_class="UNKNOWN_REVIEW_REQUIRED", current_osm_polygon_dominant_type="river",
                   distance_to_ocean_m=2384., dem_mean_m=.65)
    cls, reason = reconciled_class(row)
    assert cls == "ESTUARY_TIDAL_RIVER" and "not assumed verified" in reason
