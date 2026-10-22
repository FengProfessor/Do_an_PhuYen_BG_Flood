"""Audit actual 2021 monthly water observations without inferring daily WSE.

FTP VER5-0 is the archive published in 2022, corresponding to GSW v1.4.
It is not the corrected v1.5 2016-2021 YearlyHistory/Seasonality release.
No-data is retained explicitly, never counted as dry water surface.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from shapely.geometry import box

from v49_classify_waterbodies import sha256_file

PROJECT = Path(__file__).resolve().parent
SOURCES = PROJECT / "V49_sources_R3_20261013"
R3 = PROJECT / "V49_R3_20261013"
DOC = "https://developers.google.com/earth-engine/datasets/catalog/JRC_GSW1_4_MonthlyHistory"
RELEASE_NOTES = "https://global-surface-water.appspot.com/download"


def source_url(month):
    return ("https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GSWE/MonthlyHistory/VER5-0/tiles/2021/"
            f"2021_{month:02d}/0000240000-0001120000.tif")


def monthly_counts(values):
    values = np.asarray(values)
    if values.dtype.kind not in "ui" or not np.isin(values, (0, 1, 2)).all():
        raise ValueError("MonthlyHistory requires literal integer codes 0=no observations, 1=dry, 2=water")
    total = int(values.size)
    noobs, dry, wet = (int((values == code).sum()) for code in (0, 1, 2))
    observed = dry + wet
    return dict(object_native_cells=total, no_observation_cells=noobs, dry_observed_cells=dry,
                water_observed_cells=wet, observed_cells=observed,
                observation_fraction=observed / total if total else None,
                water_fraction_of_object=wet / total if total else None,
                water_fraction_of_observed=wet / observed if observed else None)


def annual_counts(monthly):
    monthly = np.asarray(monthly)
    if monthly.ndim != 2 or monthly.shape[0] != 12:
        raise ValueError("All twelve months must use the exact same native object pixel mask")
    monthly_counts(monthly.ravel())
    observed = (monthly > 0).sum(axis=0)
    wet = (monthly == 2).sum(axis=0)
    dry = (monthly == 1).sum(axis=0)
    return dict(never_observed_cells=int((observed == 0).sum()),
                observed_all_12_months_cells=int((observed == 12).sum()),
                observed_water_all_12_months_cells=int((wet == 12).sum()),
                observed_water_at_least_once_cells=int((wet > 0).sum()),
                observed_dry_at_least_once_cells=int((dry > 0).sum()),
                both_water_and_dry_observed_cells=int(((wet > 0) & (dry > 0)).sum()),
                median_observed_months=float(np.median(observed)) if observed.size else None,
                median_water_observed_months=float(np.median(wet)) if wet.size else None,
                monthly_history_establishes_daily_event_shoreline=False,
                authorizes_bathymetry=False)


def source_paths():
    return [SOURCES / f"JRC_monthly_2021_{month:02d}_100E_20N_FTP_VER5_0.tif" for month in range(1, 13)]


def calculate(classification_path):
    objects = gpd.read_file(classification_path, layer="classified_objects").to_crs(4326)
    datasets = []
    try:
        for path in source_paths():
            ds = rasterio.open(path)
            datasets.append(ds)
            if (ds.crs.to_epsg() != 4326 or ds.shape != (40000, 40000) or ds.count != 1
                    or ds.dtypes != ("uint8",) or ds.descriptions != ("water",)
                    or tuple(ds.bounds) != (100., 10., 110., 20.) or ds.transform != datasets[0].transform):
                raise ValueError(f"Unexpected primary tile or monthly grid: {path}")
        monthly_rows, annual_rows = [], []
        base = datasets[0]
        for _, obj in objects.iterrows():
            if not obj.geometry.covered_by(box(*base.bounds)):
                raise ValueError(f"Object outside downloaded tile: {obj.object_id}")
            raw = from_bounds(*obj.geometry.bounds, transform=base.transform)
            left, top = int(np.floor(raw.col_off)), int(np.floor(raw.row_off))
            right, bottom = int(np.ceil(raw.col_off + raw.width)), int(np.ceil(raw.row_off + raw.height))
            window = Window(left, top, right-left, bottom-top)
            mask = geometry_mask([obj.geometry.__geo_interface__], out_shape=(bottom-top, right-left),
                                 transform=base.window_transform(window), invert=True, all_touched=False)
            arrays = []
            for month, ds in enumerate(datasets, 1):
                values = ds.read(1, window=window)[mask]
                arrays.append(values)
                monthly_rows.append(dict(object_id=obj.object_id, final_class=obj.final_class,
                                         year=2021, month=month, **monthly_counts(values)))
            annual_rows.append(dict(object_id=obj.object_id, final_class=obj.final_class,
                                    object_native_cells=int(mask.sum()), **annual_counts(np.stack(arrays))))
        return pd.DataFrame(monthly_rows), pd.DataFrame(annual_rows)
    finally:
        for ds in datasets:
            ds.close()


def build():
    output = R3 / "WATER_HISTORY_2021"
    output.mkdir(parents=True, exist_ok=True)
    classified = R3 / "C" / "V49_waterbody_classification.gpkg"
    pins = [{"year": 2021, "month": month, "url": source_url(month), "path": str(path.resolve()),
             "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for month, path in enumerate(source_paths(), 1)]
    monthly, annual = calculate(classified)
    outputs = []
    for table, name in ((monthly, "V49_2021_monthly_water_observations.csv"),
                        (annual, "V49_2021_annual_observation_coverage.csv"),
                        (monthly[monthly.month == 11], "V49_2021_November_water_observations.csv")):
        path = output / name
        table.to_csv(path, index=False, encoding="utf-8-sig")
        outputs.append(dict(path=str(path.resolve()), sha256=sha256_file(path), row_count=len(table)))
    november = monthly[(monthly.month == 11) & (monthly.final_class != "OCEAN")]
    report = dict(schema_version="V49-2021-monthly-history-audit-1", generated_at_utc=datetime.now(timezone.utc).isoformat(),
                  dataset="GSW v1.4 MonthlyHistory 2021; JRC FTP archive VER5-0, 2022 publication",
                  sources=pins, classification={"path": str(classified.resolve()), "sha256": sha256_file(classified)},
                  outputs=outputs, native_grid_no_resampling=True, object_mask="native pixel centers; all_touched=False",
                  no_observation_code=0, dry_code=1, water_code=2,
                  november_inland_object_count=len(november),
                  november_inland_objects_with_zero_observation=november.loc[november.observed_cells == 0, "object_id"].tolist(),
                  november_inland_objects_with_water_observation=november.loc[november.water_observed_cells > 0, "object_id"].tolist(),
                  daily_event_shoreline_available=False, field_bathymetry_available=False,
                  authorizes_geometry=False, changes_frozen_G_inputs=False,
                  citations=[DOC, RELEASE_NOTES, "https://doi.org/10.1038/nature20584"],
                  limitations=["Monthly water detection is not a daily November 2021 flood extent or water level.",
                               "Zero denotes absent usable observation, not observed dry land.",
                               "Old yearly Seasonality/YearlyHistory products are not used: JRC reports a corrected 2016-2021 release.",
                               "Current object footprints and archive observations may differ in shoreline and geolocation."])
    manifest = output / "V49_2021_WATER_HISTORY_REGISTER.json"
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def validate(output=R3 / "WATER_HISTORY_2021"):
    report = json.loads((output / "V49_2021_WATER_HISTORY_REGISTER.json").read_text(encoding="utf-8"))
    pins = [*report["sources"], report["classification"], *report["outputs"]]
    checksum_ok = all(Path(pin["path"]).is_file() and sha256_file(Path(pin["path"])) == pin["sha256"] for pin in pins)
    if not checksum_ok or [pin["month"] for pin in report["sources"]] != list(range(1, 13)):
        raise ValueError("2021 monthly source or output integrity failure")
    for month, pin in enumerate(report["sources"], 1):
        if pin["url"] != source_url(month) or Path(pin["path"]).resolve() != source_paths()[month-1].resolve():
            raise ValueError("Monthly source provenance mismatch")
    monthly, annual = calculate(Path(report["classification"]["path"]))
    actual_tables = [monthly, annual, monthly[monthly.month == 11]]
    for expected, pin in zip(actual_tables, report["outputs"]):
        recorded = pd.read_csv(pin["path"])
        pd.testing.assert_frame_equal(recorded.reset_index(drop=True), expected.reset_index(drop=True), check_dtype=False,
                                      check_exact=False, rtol=1e-12, atol=1e-9)
        if len(recorded) != pin["row_count"]:
            raise ValueError("Observation row count mismatch")
    checks = dict(source_and_output_checksums=True, source_geometry_readback=True, complete_12_months=True,
                  no_observation_is_not_dry=bool((monthly.observed_cells + monthly.no_observation_cells == monthly.object_native_cells).all()),
                  source_period_is_2021=bool(monthly.year.eq(2021).all()),
                  no_geometry_or_daily_WSE_promotion=all(report.get(key) is False for key in
                      ("authorizes_geometry", "daily_event_shoreline_available", "field_bathymetry_available", "changes_frozen_G_inputs")))
    result = dict(checks=checks, pass_=all(checks.values()), monthly_rows=len(monthly), object_count=len(annual))
    (output / "V49_2021_water_history_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    build()
    print(json.dumps(validate(), indent=2))
