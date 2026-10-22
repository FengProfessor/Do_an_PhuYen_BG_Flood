"""Regression: Gate-G preparation must reject changed frozen input pins."""

import copy
import json
import shutil
from pathlib import Path

import pytest

from v49_validate_hydraulic_validation import validate_v49_g, verify_frozen_references


ROOT = Path(__file__).resolve().parent / "V49_G_20261013"


@pytest.fixture
def evidence_bundle(tmp_path):
    for name in (
        "V49_G_LOW_terrain_audit.json",
        "V49_G_HIGH_terrain_audit.json",
        "SAR_vs_V48_BASE_frame_33_metrics.json",
    ):
        shutil.copy2(ROOT / name, tmp_path / name)
    manifest = json.loads((ROOT / "V49_G_PREPARATION_MANIFEST.json").read_text(encoding="utf-8"))
    return tmp_path, manifest


@pytest.mark.parametrize("group", ["forcing", "engine_semantics", "terrain", "sentinel1"])
def test_changed_frozen_pin_blocks_preparation(evidence_bundle, group):
    directory, original = evidence_bundle
    manifest = copy.deepcopy(original)
    if group == "sentinel1":
        manifest[group]["sha256"] = "0" * 64
    else:
        key = "LOW" if group == "terrain" else next(iter(manifest[group]))
        manifest[group][key]["sha256"] = "0" * 64
    (directory / "V49_G_PREPARATION_MANIFEST.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    report = validate_v49_g(directory)
    assert report["preparation_pass"] is False, f"changed {group} pin was accepted"
    assert report["gate_g_pass"] is False


@pytest.mark.parametrize("corruption", ["missing_sha", "metadata_only"])
def test_deleted_input_pin_is_not_silently_skipped(evidence_bundle, corruption):
    _, manifest = evidence_bundle
    if corruption == "missing_sha":
        del manifest["sentinel1"]["sha256"]
    else:
        manifest["sentinel1"] = {"description": "source unavailable"}
    assert not verify_frozen_references(manifest)["pass"]
