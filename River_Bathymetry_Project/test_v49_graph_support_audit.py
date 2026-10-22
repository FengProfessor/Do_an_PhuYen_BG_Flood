import geopandas as gpd
import pytest
from shapely.geometry import LineString, box

from v49_graph_support_audit import audit_object_graph_support


def fixtures():
    objects = gpd.GeoDataFrame({"object_id": ["river", "unknown", "reservoir"],
                               "final_class": ["RIVER_STREAM", "UNKNOWN_REVIEW_REQUIRED", "LAKE_RESERVOIR"],
                               "current_osm_channel_m": [300.,200.,0.]},
                              geometry=[box(0,0,30,30),box(0,200,30,230),box(0,400,30,430)], crs=32649)
    reaches = gpd.GeoDataFrame({"reach_id": ["existing"]}, geometry=[LineString([(80,0),(80,30)])],crs=32649)
    return objects, reaches


def test_existing_coarse_graph_is_alignment_issue_not_new_missing_branch():
    objects, reaches = fixtures()
    rows = audit_object_graph_support(objects, reaches).set_index("object_id")
    assert rows.loc["river", "graph_30m_reach_count"] == 0
    assert rows.loc["river", "graph_90m_reach_ids"] == "existing"
    assert rows.loc["river", "support_state"] == "COARSE_GRAPH_ALIGNMENT_REVIEW"
    assert rows.loc["unknown", "support_state"] == "NO_GRAPH_WITHIN_90M_REVIEW"
    assert rows.loc["reservoir", "support_state"] == "NO_CHANNEL_GRAPH_GAP_IDENTIFIED"
    assert not rows.automatic_graph_or_carving_authorization.any()


def test_graph_support_rejects_crs_mismatch():
    objects, reaches = fixtures()
    with pytest.raises(ValueError, match="same projected CRS"):
        audit_object_graph_support(objects, reaches.to_crs(4326))
