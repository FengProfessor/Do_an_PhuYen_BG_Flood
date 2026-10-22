import geopandas as gpd
from shapely.geometry import LineString, MultiPolygon, box

from v49_audit_parent_channel_support import fragment_class, same_component_support


def sources(parts, lines):
    parents = gpd.GeoDataFrame({"water": ["river"], "osm_id": ["123"], "osm_way_id": [None]},
                              geometry=[MultiPolygon(parts)], crs=32649)
    graph = gpd.GeoDataFrame(geometry=lines, crs=32649)
    return parents, graph


def proof(**extra):
    row = dict(final_class="UNKNOWN_REVIEW_REQUIRED", jrc_occurrence_p50=45.,
               jrc_recurrence_p50=85., current_osm_channel_m=0., graph_length_m=0.)
    row.update(extra)
    return row


def test_remote_disconnected_member_cannot_classify_river_fragment():
    parents, graph = sources([box(0, 0, 1000, 1000), box(10000, 0, 11000, 1000)],
                             [LineString([(10010, 500), (10990, 500)])])
    support = same_component_support(box(10, 10, 100, 100), parents, graph)
    assert support["parent_overlap_fraction"] == 1.
    assert support["same_component_graph_m"] == 0.
    assert fragment_class(proof(), support)[0] == "UNKNOWN_REVIEW_REQUIRED"


def test_connected_parent_supports_type_without_local_graph_or_carving():
    parents, graph = sources([box(0, 0, 1000, 1000)], [LineString([(10, 500), (990, 500)])])
    support = same_component_support(box(10, 10, 100, 100), parents, graph)
    assert support["same_component_graph_m"] == 980.
    assert fragment_class(proof(), support)[0] == "RIVER_STREAM"
    assert fragment_class(proof(jrc_occurrence_p50=0., jrc_recurrence_p50=0.), support)[0] == "UNKNOWN_REVIEW_REQUIRED"


def test_parent_graph_with_only_minor_object_overlap_stays_held():
    parents, graph = sources([box(0, 0, 1000, 1000)], [LineString([(10, 500), (990, 500)])])
    support = same_component_support(box(900, 0, 1200, 200), parents, graph)
    assert support["parent_overlap_fraction"] < .6
    assert fragment_class(proof(), support)[0] == "UNKNOWN_REVIEW_REQUIRED"
