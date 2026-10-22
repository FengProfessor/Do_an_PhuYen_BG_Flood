from pathlib import Path

import geopandas as gpd
import networkx as nx
from shapely.geometry import LineString, Point, box

from v49_build_hydrograph import (
    HydrographConfig,
    _terminal_type,
    assign_reach_ids,
    orient_reach_geometry,
    split_at_dong_cam,
)


def test_orientation_uses_next_down_geometry_not_dem_slope():
    current = LineString([(10, 0), (0, 0)])
    downstream = LineString([(10, 0), (20, 0)])
    oriented, reversed_flag, method, native_score, reversed_score = orient_reach_geometry(
        current, downstream, []
    )

    assert reversed_flag is True
    assert method == "GRAPH_NEIGHBOUR"
    assert oriented.coords[0] == (0.0, 0.0)
    assert oriented.coords[-1] == (10.0, 0.0)
    assert reversed_score < native_score


def test_reach_ids_are_stable_and_native_based():
    records = [
        {"HYRIV_ID": 123, "geometry": LineString([(0, 0), (1, 0)])},
        {"HYRIV_ID": 456, "geometry": LineString([(1, 0), (2, 0)]), "forced_reach_id": "HR_456_U"},
    ]
    out = assign_reach_ids(records)
    assert out[0]["reach_id"] == "HR_123"
    assert out[1]["reach_id"] == "HR_456_U"


def test_terminal_classification_prefers_endorheic_then_ocean_then_boundary():
    cfg = HydrographConfig(ocean_outlet_tolerance_m=10, terminal_boundary_tolerance_m=2)
    domain = box(0, 0, 100, 100)
    ocean = Point(50, 50).buffer(1)

    terminal, _ = _terminal_type(
        {"ENDORHEIC": 1, "NEXT_DOWN": 0}, Point(50, 50), domain, ocean, None, set(), cfg
    )
    assert terminal == "ENDORHEIC"

    terminal, _ = _terminal_type(
        {"ENDORHEIC": 0, "NEXT_DOWN": 0}, Point(55, 50), domain, ocean, None, set(), cfg
    )
    assert terminal == "OCEAN_OUTLET"

    terminal, _ = _terminal_type(
        {"ENDORHEIC": 0, "NEXT_DOWN": 999}, Point(100, 20), domain, None, None, set(), cfg
    )
    assert terminal == "DOMAIN_EXIT"


def test_source_terminal_inside_persistent_water_is_explicit_review_target():
    cfg = HydrographConfig(evidence_buffer_m=10)
    domain = box(0, 0, 100, 100)
    water = Point(50, 50).buffer(5)
    terminal, _ = _terminal_type(
        {"ENDORHEIC": 0, "NEXT_DOWN": 0}, Point(52, 50), domain, None, water, set(), cfg
    )
    assert terminal == "WATERBODY_TERMINAL_REVIEW"


def test_dong_cam_is_split_into_explicit_structure_node():
    records = [
        {
            "HYRIV_ID": 10,
            "NEXT_DOWN": 11,
            "native_part_count": 1,
            "native_part_index": 1,
            "geometry": LineString([(0, 0), (100, 0)]),
        }
    ]
    out, structure, issues = split_at_dong_cam(records, Point(52, 4), max_snap_m=10)
    out = assign_reach_ids(out)

    assert len(out) == 2
    assert out[0]["reach_id"] == "HR_10_U"
    assert out[1]["reach_id"] == "HR_10_D"
    assert out[0]["to_structure"] is True
    assert out[1]["from_structure"] is True
    assert structure["structure_id"] == "STRUCT_DONG_CAM"
    assert structure["geometry"].distance(Point(52, 0)) < 1e-9
    assert issues[0]["issue_type"] == "STRUCTURE_SNAP"


def test_cycle_detection_fixture_is_effective():
    graph = nx.DiGraph()
    graph.add_edges_from([("A", "B"), ("B", "C")])
    assert list(nx.simple_cycles(graph)) == []
    graph.add_edge("C", "A")
    assert len(list(nx.simple_cycles(graph))) == 1
