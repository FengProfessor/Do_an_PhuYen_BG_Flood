"""Independent structural validator for V49-B graph deliverables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd


PROJECT_DIR = Path(r"D:\VTP\River_Bathymetry_Project")
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "V49_B_20261012"


def validate_hydrograph(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict:
    gpkg = output_dir / "V49_hydrograph.gpkg"
    reaches = gpd.read_file(gpkg, layer="reaches")
    nodes = gpd.read_file(gpkg, layer="nodes")
    structures = gpd.read_file(gpkg, layer="structures")
    audit = json.loads((output_dir / "V49_graph_audit.json").read_text(encoding="utf-8"))

    node_ids = set(nodes.node_id.astype(str))
    from_missing = sorted(set(reaches.from_node.astype(str)) - node_ids)
    to_missing = sorted(set(reaches.to_node.astype(str)) - node_ids)
    duplicate_reaches = sorted(reaches.loc[reaches.reach_id.duplicated(), "reach_id"].astype(str).tolist())
    duplicate_nodes = sorted(nodes.loc[nodes.node_id.duplicated(), "node_id"].astype(str).tolist())

    graph = nx.DiGraph()
    for _, row in reaches.iterrows():
        graph.add_edge(str(row.from_node), str(row.to_node), reach_id=str(row.reach_id))
    cycles = list(nx.simple_cycles(graph))

    terminal_rows = reaches[reaches.next_reach_id.fillna("").astype(str).eq("")]
    missing_terminal_type = terminal_rows[terminal_rows.terminal_type.fillna("").astype(str).eq("")]
    dong_cam = structures[structures.structure_id.astype(str) == "STRUCT_DONG_CAM"]
    dong_cam_node = nodes[nodes.node_id.astype(str) == "STRUCT_DONG_CAM"]

    topology_pass = (
        not from_missing
        and not to_missing
        and not duplicate_reaches
        and not duplicate_nodes
        and not cycles
        and missing_terminal_type.empty
        and len(dong_cam) == 1
        and len(dong_cam_node) == 1
        and int(audit.get("orphan_major_reach_count", -1)) == 0
        and int(audit.get("unresolved_terminal_count", -1)) == 0
        and int(audit.get("endpoint_gap_over_120m_count", -1)) == 0
        and bool(audit.get("dem_unchanged", False))
    )

    report = {
        "schema_version": "V49-B-validation-1",
        "reach_count": int(len(reaches)),
        "node_count": int(len(nodes)),
        "structure_count": int(len(structures)),
        "duplicate_reach_ids": duplicate_reaches,
        "duplicate_node_ids": duplicate_nodes,
        "missing_from_nodes": from_missing,
        "missing_to_nodes": to_missing,
        "directed_cycle_count": int(len(cycles)),
        "terminal_without_type_count": int(len(missing_terminal_type)),
        "dong_cam_structure_count": int(len(dong_cam)),
        "dong_cam_node_count": int(len(dong_cam_node)),
        "orphan_major_reach_count": int(audit.get("orphan_major_reach_count", -1)),
        "unresolved_terminal_count": int(audit.get("unresolved_terminal_count", -1)),
        "endpoint_gap_over_120m_count": int(audit.get("endpoint_gap_over_120m_count", -1)),
        "dem_unchanged": bool(audit.get("dem_unchanged", False)),
        "topology_validation_pass": bool(topology_pass),
        "bed_elevation_ordering_gate": audit.get("bed_elevation_ordering_gate"),
        "gate_b_pass": bool(topology_pass and audit.get("gate_b_pass", False)),
        "gate_b_note": audit.get("gate_b_reason"),
    }
    path = output_dir / "V49_B_validation_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(validate_hydrograph(args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
