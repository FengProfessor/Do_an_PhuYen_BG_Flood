"""Source/output tampering must not convert bar heights into accepted bathymetry."""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

import v49_ingest_survey_context as survey


@pytest.fixture
def register(tmp_path, monkeypatch):
    monkeypatch.setattr(survey, "OUTPUT", tmp_path)
    report = survey.build()
    return report, tmp_path / "V49_PhuSen_2024_survey_register.json"


def save(path, report):
    path.write_text(json.dumps(report), encoding="utf-8")


def test_forged_collar_authorization_fails_even_after_csv_is_repinned(register):
    report, path = register
    pin = report["tables"][1]
    table = pd.read_csv(pin["path"])
    table.loc[0, "authorizes_2021_hydraulic_bed"] = True
    table.to_csv(pin["path"], index=False)
    pin["sha256"] = survey.sha256_file(Path(pin["path"]))
    save(path, report)
    with pytest.raises(AssertionError):
        survey.validate()


def test_forged_vertical_datum_cannot_pass_context_readback(register):
    report, path = register
    report["vertical_datum_verified"] = True
    save(path, report)
    with pytest.raises(ValueError, match="interpretation"):
        survey.validate()


def test_shifted_survey_geometry_fails_even_after_spatial_file_is_repinned(register):
    report, path = register
    pin = report["spatial_output"]
    corners = gpd.read_file(pin["path"], layer="survey_boundary_corners")
    corners.loc[0, "geometry"] = Point(corners.geometry[0].x + 100, corners.geometry[0].y)
    corners.to_file(pin["path"], layer="survey_boundary_corners", driver="GPKG")
    pin["sha256"] = survey.sha256_file(Path(pin["path"]))
    save(path, report)
    with pytest.raises(ValueError, match="geometry"):
        survey.validate()


def test_spatial_attributes_cannot_claim_verified_datum_after_repinning(register):
    report, path = register
    pin = report["spatial_output"]
    footprint = gpd.read_file(pin["path"], layer="survey_footprint")
    footprint.loc[0, "vertical_datum_verified"] = True
    footprint.to_file(pin["path"], layer="survey_footprint", driver="GPKG")
    pin["sha256"] = survey.sha256_file(Path(pin["path"]))
    save(path, report)
    with pytest.raises(AssertionError):
        survey.validate()
