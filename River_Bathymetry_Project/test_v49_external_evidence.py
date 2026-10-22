import json
import netCDF4
import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer
import v49_evaluate_external_evidence as external


def fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(external,"EVIDENCE",tmp_path)
    table=tmp_path/"2021_published_high_water_marks_coarse_coordinates.csv"
    pd.DataFrame([dict(point_id=1,longitude_reported=109.25,latitude_reported=12.97,observed_mark_elevation_m=9.13)]).to_csv(table,index=False)
    external.preregister()
    path=tmp_path/"model.nc"
    x,y=Transformer.from_crs(4326,32649,always_xy=True).transform(109.25,12.97)
    with netCDF4.Dataset(path,"w") as dataset:
        for name,count in [("time",2),("x",2),("y",2)]:dataset.createDimension(name,count)
        dataset.createVariable("time","f8",("time",))[:]=[0,10800]
        dataset.createVariable("x","f8",("x",))[:]=[x-15,x+15]
        dataset.createVariable("y","f8",("y",))[:]=[y-15,y+15]
        h=dataset.createVariable("h","f4",("time","y","x"))
        h[:]=np.array([[[.5,0],[0,0]],[[0,0],[0,0]]])
    return path,table


def test_coarse_hwm_uses_available_period_max_without_claiming_exact_wse(tmp_path,monkeypatch):
    path,_=fixture(tmp_path,monkeypatch)
    report=external.evaluate_coarse_high_water_marks(path)
    assert report["rows"][0]["cells_ever_wet"]==1
    assert report["rows"][0]["valid_envelope_cells"]==4
    assert not report["rows"][0]["absolute_wse_error_computed"]
    assert not report["hydraulic_promotion_ready"]


def test_changed_hwm_evidence_cannot_be_evaluated_with_old_registration(tmp_path,monkeypatch):
    path,table=fixture(tmp_path,monkeypatch)
    table.write_text(table.read_text()+"\n",encoding="utf-8")
    with pytest.raises(ValueError,match="checksum"):
        external.evaluate_coarse_high_water_marks(path)
