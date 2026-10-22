"""Corroborate river fragments against the same connected OSM parent component.

Parent support can establish a mapped feature type. It cannot fill local graph
gaps, establish 2021 persistence, or authorize any bathymetric modification.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from v49_reconcile_water_evidence import number, reconciled_class, sha256_file

PROJECT = Path(__file__).resolve().parent
R2 = PROJECT / "V49_R2_20261013"
R3 = PROJECT / "V49_R3_20261013"
GRAPH = PROJECT / "V49_B_20261012" / "V49_hydrograph.gpkg"


def same_component_support(geometry, polygons, graph):
    if polygons.crs != graph.crs or not graph.crs.is_projected:
        raise ValueError("Parent and graph require the same projected CRS")
    best = {"parent_osm_id": "", "parent_component_index": -1,
            "parent_overlap_fraction": 0., "same_component_graph_m": 0.,
            "parent_component_area_m2": 0., "parent_name": ""}
    if geometry.is_empty or geometry.area <= 0:
        return best
    hits = polygons[polygons.water.fillna("").eq("river") & polygons.geometry.intersects(geometry)]
    candidates = []
    for _, parent in hits.iterrows():
        parts = list(parent.geometry.geoms) if parent.geometry.geom_type == "MultiPolygon" else [parent.geometry]
        for index, part in enumerate(parts):
            overlap = float(part.intersection(geometry).area / geometry.area)
            if overlap <= 0:
                continue
            # No buffering, no credit from a disconnected member of a relation.
            reaches = graph[graph.geometry.intersects(part)]
            length = float(reaches.geometry.intersection(part).length.sum())
            relation = parent.get("osm_id")
            way = parent.get("osm_way_id")
            identity = "relation/" + str(relation) if pd.notna(relation) else "way/" + str(way)
            candidates.append(dict(parent_osm_id=identity, parent_component_index=index,
                                   parent_overlap_fraction=overlap, same_component_graph_m=length,
                                   parent_component_area_m2=float(part.area), parent_name=str(parent.get("name") or "")))
    if candidates:
        # Largest true object overlap; deterministic source-id tie break.
        best = sorted(candidates, key=lambda x: (-x["parent_overlap_fraction"], x["parent_osm_id"], x["parent_component_index"]))[0]
    return best


def fragment_class(row, support):
    prior = str(row["final_class"])
    if prior != "UNKNOWN_REVIEW_REQUIRED":
        return prior, "Previously reconciled type retained."
    if (support["parent_overlap_fraction"] < .60 or support["same_component_graph_m"] < 300.
            or not support["parent_osm_id"]):
        return prior, "No sufficient overlap and HydroRIVERS support within the same connected river polygon."
    proof = dict(row)
    proof.update(current_osm_polygon_dominant_type="river",
                 current_osm_polygon_overlap_fraction=support["parent_overlap_fraction"],
                 current_osm_channel_m=0., graph_length_m=support["same_component_graph_m"])
    cls, reason = reconciled_class(proof)
    if cls == prior:
        return cls, "Mapped parent support lacks independent JRC water corroboration."
    return cls, (reason + f" Same connected parent {support['parent_osm_id']} component "
                 f"{support['parent_component_index']} intersects {support['same_component_graph_m']:.1f} m "
                 "of HydroRIVERS. This is type evidence only; local graph support and geometry gates are unchanged.")


def calculate(classification_path, evidence_path, graph_path):
    classified = gpd.read_file(classification_path, layer="classified_objects")
    evidence = gpd.read_file(evidence_path, layer="audited_water_objects").set_index("object_id")
    polygons = gpd.read_file(evidence_path, layer="geofabrik_current_water_polygons")
    graph = gpd.read_file(graph_path, layer="reaches")
    if classified.crs != polygons.crs:
        raise ValueError("Objects and parents require the same CRS")
    rows = []
    for _, item in classified.iterrows():
        proof = evidence.loc[item.object_id].to_dict()
        proof["final_class"] = item.final_class
        support = same_component_support(item.geometry, polygons, graph)
        after, reason = fragment_class(proof, support)
        rows.append(dict(object_id=item.object_id, before=item.final_class, after=after,
                         changed=after != item.final_class, reason=reason, **support,
                         local_graph_m=number(proof, "graph_length_m"),
                         local_osm_channel_m=number(proof, "current_osm_channel_m"),
                         authorizes_geometry=False, verifies_2021_persistence=False))
    return pd.DataFrame(rows)


def build():
    output = R3 / "PARENT_SUPPORT"
    output.mkdir(parents=True, exist_ok=True)
    classification = R2 / "C" / "V49_waterbody_classification.gpkg"
    evidence = R2 / "C1" / "V49_C1_fixed_water_evidence.gpkg"
    inputs = {name: {"path": str(path.resolve()), "sha256": sha256_file(path)} for name, path in
              (("classification", classification), ("evidence", evidence), ("graph", GRAPH))}
    table = calculate(classification, evidence, GRAPH)
    csv = output / "V49_parent_channel_support.csv"
    table.to_csv(csv, index=False, encoding="utf-8-sig")
    report = dict(schema_version="V49-connected-parent-support-1", inputs=inputs,
                  minimum_same_component_graph_m=300., minimum_object_overlap=.60,
                  changed_object_ids=table.loc[table.changed, "object_id"].tolist(),
                  object_count=len(table), source_osm_epoch="2026-10-11",
                  authorizes_geometry=False, verifies_2021_persistence=False,
                  output={"path": str(csv.resolve()), "sha256": sha256_file(csv)})
    (output / "V49_parent_channel_support.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(table[table.changed].to_string(index=False))
    return report


def validated_table(output=R3 / "PARENT_SUPPORT"):
    report = json.loads((output / "V49_parent_channel_support.json").read_text(encoding="utf-8"))
    pins = [*report["inputs"].values(), report["output"]]
    if not all(Path(pin["path"]).is_file() and sha256_file(Path(pin["path"])) == pin["sha256"] for pin in pins):
        raise ValueError("Parent support source/output checksum mismatch")
    if report.get("authorizes_geometry") is not False or report.get("verifies_2021_persistence") is not False:
        raise ValueError("Parent evidence cannot authorize geometry or persistence")
    inputs = report["inputs"]
    actual = calculate(*(Path(inputs[key]["path"]) for key in ("classification", "evidence", "graph")))
    recorded = pd.read_csv(report["output"]["path"]).fillna("")
    pd.testing.assert_frame_equal(recorded, actual.fillna(""), check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-9)
    if report["changed_object_ids"] != actual.loc[actual.changed, "object_id"].tolist():
        raise ValueError("Changed-object index disagrees with recomputed source geometry")
    return actual


if __name__ == "__main__":
    build()
