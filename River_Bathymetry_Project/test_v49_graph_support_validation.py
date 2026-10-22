import pandas as pd
import pytest
from v49_synthesize_hydraulic_bed import sha256_file
from v49_validate_science_qaqc import validate_graph_support_table


@pytest.mark.parametrize("corruption", ["bytes", "alignment_as_gap", "automatic_authorization"])
def test_graph_review_cannot_accept_modified_table_or_duplicate_aligned_edge(tmp_path, corruption):
    path = tmp_path / "support.csv"
    table = pd.DataFrame([dict(object_id="river", channel_graph_relevant=True,
        graph_30m_reach_count=0, graph_90m_reach_count=1, graph_30m_reach_ids="",
        graph_90m_reach_ids="existing", support_state="COARSE_GRAPH_ALIGNMENT_REVIEW",
        automatic_graph_or_carving_authorization=False)])
    table.to_csv(path, index=False)
    topology = dict(object_graph_support_table_sha256=sha256_file(path),
        linear_water_object_without_graph_support_count=0,
        current_channel_or_candidate_objects_without_graph_90m_ids=[],
        coarse_graph_alignment_review_object_ids=["river"])
    assert validate_graph_support_table(path, topology, 1)
    if corruption == "alignment_as_gap":
        table.loc[0, "support_state"] = "NO_GRAPH_WITHIN_90M_REVIEW"
    elif corruption == "automatic_authorization":
        table.loc[0, "automatic_graph_or_carving_authorization"] = True
    else:
        table.loc[0, "graph_90m_reach_ids"] = "changed"
    table.to_csv(path, index=False)
    if corruption != "bytes":
        topology["object_graph_support_table_sha256"] = sha256_file(path)
    assert not validate_graph_support_table(path, topology, 1)
