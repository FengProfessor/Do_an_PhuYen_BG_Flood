"""Actual evidence tampering must invalidate C.1 despite stored PASS flags."""
import hashlib

import pandas as pd
import pytest

from v49_validate_fixed_water_evidence import (
    review_rows_block_automatic_carving, verify_evidence_sources,
)


@pytest.fixture
def evidence(tmp_path):
    pbf = tmp_path / "snapshot.pbf"
    pbf.write_bytes(b"original OSM snapshot")
    jrc = tmp_path / "occurrence.tif"
    jrc.write_bytes(b"original satellite water evidence")
    md5 = hashlib.md5(pbf.read_bytes()).hexdigest()
    md5_path = tmp_path / "snapshot.md5"
    md5_path.write_text(md5)
    audit = {"geofabrik_md5_match": True, "geofabrik_md5_expected": md5,
             "source_hashes": {"occurrence": hashlib.sha256(jrc.read_bytes()).hexdigest(),
                               "geofabrik_pbf_sha256": hashlib.sha256(pbf.read_bytes()).hexdigest()}}
    return audit, pbf, md5_path, {"occurrence": jrc}


def test_unchanged_live_evidence_passes(evidence):
    assert verify_evidence_sources(*evidence)["pass"]


@pytest.mark.parametrize("tampering", ["jrc", "pbf", "missing_pin"])
def test_stored_success_does_not_hide_tampering(evidence, tampering):
    audit, pbf, md5, jrc = evidence
    if tampering == "jrc":
        jrc["occurrence"].write_bytes(b"modified water observation")
    elif tampering == "pbf":
        pbf.write_bytes(b"modified hydrography")
    else:
        del audit["source_hashes"]["occurrence"]
    assert not verify_evidence_sources(audit, pbf, md5, jrc)["pass"]


def test_resolved_empty_review_queue_is_valid():
    assert review_rows_block_automatic_carving(pd.DataFrame(columns=["blocks_v49e"]))


def test_existing_unresolved_row_must_block():
    assert not review_rows_block_automatic_carving(pd.DataFrame({"blocks_v49e": [True, False]}))
