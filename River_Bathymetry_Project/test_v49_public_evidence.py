import pytest
from v49_ingest_public_evidence import CURVES, storage_at_level, published_capacity_references
from v49_ingest_public_evidence import verified_source_sha256
import hashlib
import json
from v49_validate_hydraulic_validation import inspect_published_evidence


def test_published_sbh_normal_level_and_volume_units():
    result = storage_at_level(CURVES["SONG_BA_HA"], 105.)
    assert result["surface_area_km2"] == 54.66
    assert result["volume_m3"] == 349690000.


def test_storage_outside_source_table_cannot_be_invented():
    with pytest.raises(ValueError, match="extrapolation"):
        storage_at_level(CURVES["SONG_HINH"], 230.)


def test_corrupt_nonmonotonic_curve_is_rejected():
    curve = dict(z=[0.,1.,2.],f=[0.,1.,2.],w=[0.,2.,1.])
    with pytest.raises(ValueError, match="increasing"):
        storage_at_level(curve, 1.)


def test_single_capacity_cannot_supply_unobserved_storage_levels():
    reference = published_capacity_references()[0]
    with pytest.raises(ValueError, match="single capacity"):
        storage_at_level(reference, 36.5)


def test_one_zfw_row_cannot_be_interpolated_as_a_curve():
    with pytest.raises(ValueError, match="Invalid curve rows"):
        storage_at_level(dict(z=[0.],f=[0.],w=[0.]), 0.)


def test_modified_pdf_cannot_reuse_visually_verified_transcription(tmp_path):
    source = tmp_path / "reference.pdf"
    source.write_bytes(b"visually verified source")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    source.write_bytes(b"changed source")
    with pytest.raises(ValueError, match="changed after visual verification"):
        verified_source_sha256(source, expected)


@pytest.mark.parametrize("corruption", ["table_content", "reported_row_count"])
def test_published_evidence_registry_rechecks_table_bytes_and_rows(tmp_path, corruption):
    table = tmp_path / "observations.csv"
    table.write_text("station,stage_m\nPHU_LAM,4.63\n", encoding="utf-8")
    ref = {"path": str(table), "sha256": hashlib.sha256(table.read_bytes()).hexdigest(), "row_count": 1}
    if corruption == "table_content":
        table.write_text("station,stage_m\nPHU_LAM,999\n", encoding="utf-8")
    else:
        ref["row_count"] = 2
    register = tmp_path / "register.json"
    register.write_text(json.dumps({"output_tables": [ref]}), encoding="utf-8")
    result = inspect_published_evidence(register)
    assert not result["available"]
    assert not result["qualifies_for_exact_wse_acceptance"]
