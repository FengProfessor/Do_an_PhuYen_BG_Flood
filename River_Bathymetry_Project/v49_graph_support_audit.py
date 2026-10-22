"""Distinguish mapped-network gaps from coarse graph/polygon misalignment."""
import pandas as pd

CHANNEL_CLASSES = {"RIVER_STREAM", "CANAL", "ESTUARY_TIDAL_RIVER"}


def audit_object_graph_support(objects, reaches):
    if objects.crs != reaches.crs or objects.crs is None or not objects.crs.is_projected:
        raise ValueError("Graph support requires the same projected CRS")
    rows = []
    for _, obj in objects.iterrows():
        if obj.final_class == "OCEAN":
            continue
        associations = {}
        for buffer_m in (30, 90):
            region = obj.geometry.buffer(buffer_m)
            nearby = reaches[reaches.geometry.intersects(region)]
            ids = sorted(str(r.reach_id) for _, r in nearby.iterrows()
                         if r.geometry.intersection(region).length > 0)
            associations[buffer_m] = ids
        channel_m = float(obj.get("current_osm_channel_m", 0) or 0)
        flow_expected = obj.final_class in CHANNEL_CLASSES or channel_m >= 150
        if flow_expected and not associations[90]:
            state = "NO_GRAPH_WITHIN_90M_REVIEW"
        elif flow_expected and not associations[30]:
            state = "COARSE_GRAPH_ALIGNMENT_REVIEW"
        else:
            state = "NO_CHANNEL_GRAPH_GAP_IDENTIFIED"
        rows.append({"object_id": obj.object_id, "final_class": obj.final_class,
                     "channel_graph_relevant": bool(flow_expected), "support_state": state,
                     "graph_30m_reach_count": len(associations[30]), "graph_90m_reach_count": len(associations[90]),
                     "graph_30m_reach_ids": " | ".join(associations[30]),
                     "graph_90m_reach_ids": " | ".join(associations[90]),
                     "automatic_graph_or_carving_authorization": False})
    return pd.DataFrame(rows)
