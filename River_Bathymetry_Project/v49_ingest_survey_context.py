"""Import inspected Phu Sen survey footprint and collar heights as context.

The seven corners are from signed drawing I-2, PDF page 208. Paired VN-2000
coordinates verify EPSG:9218 versus EPSG:3406 independently. Heights remain
untransformed because no vertical benchmark/datum tie is established.
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from pyproj.transformer import TransformerGroup
from shapely.geometry import Point, Polygon

from v49_classify_waterbodies import sha256_file

PROJECT = Path(__file__).resolve().parent
SOURCES = PROJECT / "V49_sources_R3_20261013"
R3 = PROJECT / "V49_R3_20261013"
OUTPUT = R3 / "SURVEY_CONTEXT"
SOURCE = SOURCES / "Gov_PhuSen_DaRang_sand_EIA_2026.pdf"
SOURCE_SHA = "a1287f66384d07e10ebbf7fe3380974d7041bb23e568a474eb4f342e07404440"
SOURCE_URL = "https://snnmt.daklak.gov.vn/uploads/sonnmt/ccbvmt/0%20.DTM%20Phu%20Sen%20Binh%20An.pdf"
# Printed X is northing, Y is easting; always_xy supplies easting first.
# Main drawing coordinates, not the inconsistent rounded A in narrative p31.
CORNERS = [
    ("1", 1437978.00, 567657.00, 1438213.63, 296502.40),
    ("A", 1437932.48, 567767.88, 1438167.02, 296612.84),
    ("F", 1437745.92, 568100.25, 1437977.18, 296943.41),
    ("3", 1437616.00, 567989.00, 1437848.33, 296830.88),
    ("4", 1437773.00, 567603.00, 1438009.14, 296446.38),
    ("5", 1437832.00, 567664.00, 1438067.55, 296507.96),
    ("6", 1437879.00, 567555.00, 1438115.62, 296399.41),
]
COLLARS = [("LK1", "T.I", 11.71), ("LK2", "T.I", 13.62),
           ("LK3", "T.II", 12.08), ("LK4", "T.II", 11.73), ("LK5", "T.II", 13.39),
           ("LK6", "T.III", 12.16), ("LK7", "T.III", 11.88), ("LK8", "T.III", 11.61),
           ("LK9", "T.IV", 11.62), ("LK10", "T.IV", 11.20), ("LK11", "T.IV", 11.46)]


def calculate():
    if sha256_file(SOURCE) != SOURCE_SHA:
        raise ValueError("Phu Sen primary PDF differs from the inspected version")
    with fitz.open(SOURCE) as pdf:
        if len(pdf) != 219 or "1437932,48" not in pdf[207].get_text() or "LK11" not in pdf[208].get_text():
            raise ValueError("Survey drawing page identity or corner/collar labels failed")
    group = TransformerGroup(9218, 32649, always_xy=True, allow_ballpark=False)
    transforms = [t for t in group.transformers if 0 <= t.accuracy <= 1.]
    if not transforms:
        raise ValueError("Defined VN-2000 to model horizontal transform unavailable")
    model_transform = transforms[0]
    paired_transform = Transformer.from_crs(9218, 3406, always_xy=True, allow_ballpark=False)
    rows = []
    for name, north3, east3, north6, east6 in CORNERS:
        ex, ny = paired_transform.transform(east3, north3)
        x, y = model_transform.transform(east3, north3)
        rows.append(dict(corner=name, vn2000_tm3_northing_m=north3, vn2000_tm3_easting_m=east3,
                         printed_vn2000_utm49_northing_m=north6, printed_vn2000_utm49_easting_m=east6,
                         paired_crs_residual_m=float(np.hypot(ex-east6, ny-north6)),
                         model_easting_m=x, model_northing_m=y, source_pdf_page=208,
                         source_survey_month="2024-01", vertical_datum_verified=False,
                         authorizes_2021_hydraulic_bed=False, geometry=Point(x, y)))
    corners = gpd.GeoDataFrame(rows, geometry="geometry", crs=32649)
    if corners.paired_crs_residual_m.max() > .02:
        raise ValueError("The printed 3-degree and 6-degree coordinates do not verify the CRS")
    polygon = Polygon([(r[2], r[1]) for r in CORNERS])
    model_polygon = Polygon([(r["model_easting_m"], r["model_northing_m"]) for r in rows])
    if not polygon.is_valid or abs(polygon.area - 91419.) > 1.:
        raise ValueError("Closed survey footprint fails printed 9.1419 ha area check")
    objects = gpd.read_file(R3 / "C" / "V49_waterbody_classification.gpkg", layer="classified_objects")
    inland = objects[objects.final_class != "OCEAN"]
    overlaps = inland.geometry.intersection(model_polygon).area
    hits = inland[overlaps > 0].copy()
    hits["overlap_with_survey_m2"] = overlaps[overlaps > 0]
    collars = pd.DataFrame([dict(borehole=name, geological_transect=transect, printed_collar_height_m=height,
                                source_pdf_pages="208|209", source_survey_month="2024-01",
                                height_kind="BOREHOLE_COLLAR_GROUND_HEIGHT_NOT_WATER_DEPTH",
                                vertical_datum="UNVERIFIED", collar_xy_available=False,
                                authorizes_2021_hydraulic_bed=False) for name, transect, height in COLLARS])
    footprint = gpd.GeoDataFrame([dict(survey="Phu Sen 2024 bar survey", area_in_source_crs_m2=float(polygon.area),
                                     printed_area_ha=9.1419, source_survey_month="2024-01", source_pdf_page=208,
                                     vertical_datum_verified=False, bank_to_bank_bathymetry=False,
                                     authorizes_2021_hydraulic_bed=False, geometry=model_polygon)], crs=32649)
    context = dict(horizontal_source_crs="EPSG:9218", alternate_printed_crs="EPSG:3406", model_crs="EPSG:32649",
                   horizontal_transform=model_transform.description, transform_accuracy_m=model_transform.accuracy,
                   maximum_paired_coordinate_residual_m=float(corners.paired_crs_residual_m.max()),
                   footprint_source_area_m2=float(polygon.area),
                   overlap_objects=[dict(object_id=r.object_id, final_class=r.final_class,
                                         overlap_m2=float(r.overlap_with_survey_m2)) for _, r in hits.iterrows()],
                   source_conflicts=["Narrative p31 states 108 degrees 30 for its 6-degree table; signed drawing p208 specifies 111 degrees, verified by paired reprojection.",
                                     "Narrative p31 rounds corner A northing to 1437932.00; drawing p208 gives 1437932.48, which agrees with the paired 6-degree coordinate."],
                   geometry_accepted_reach_count=0, collar_height_count=11, geological_transect_count=4,
                   vertical_datum_verified=False, bank_to_bank_bathymetry=False,
                   usable_for_2021_bed_modification=False)
    return corners, collars, footprint, context


def build():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    corners, collars, footprint, context = calculate()
    csv_paths = []
    for table, name in ((corners.drop(columns="geometry"), "V49_PhuSen_2024_survey_corners.csv"),
                        (collars, "V49_PhuSen_2024_collar_heights.csv")):
        path = OUTPUT / name
        table.to_csv(path, index=False, encoding="utf-8-sig")
        csv_paths.append(dict(path=str(path.resolve()), sha256=sha256_file(path), row_count=len(table)))
    gpkg = OUTPUT / "V49_PhuSen_2024_survey_context.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    corners.to_file(gpkg, layer="survey_boundary_corners", driver="GPKG")
    footprint.to_file(gpkg, layer="survey_footprint", driver="GPKG")
    source_classification = R3 / "C" / "V49_waterbody_classification.gpkg"
    report = dict(schema_version="V49-PhuSen-survey-context-1", **context,
                  source=dict(path=str(SOURCE.resolve()), sha256=SOURCE_SHA, url=SOURCE_URL),
                  classification=dict(path=str(source_classification.resolve()), sha256=sha256_file(source_classification)),
                  tables=csv_paths, spatial_output=dict(path=str(gpkg.resolve()), sha256=sha256_file(gpkg)))
    (OUTPUT / "V49_PhuSen_2024_survey_register.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def validate():
    report = json.loads((OUTPUT / "V49_PhuSen_2024_survey_register.json").read_text(encoding="utf-8"))
    pins = [report["source"], report["classification"], *report["tables"], report["spatial_output"]]
    if not all(sha256_file(Path(p["path"])) == p["sha256"] for p in pins):
        raise ValueError("Survey context source or output checksum mismatch")
    corners, collars, footprint, context = calculate()
    for expected, pin in zip((corners.drop(columns="geometry"), collars), report["tables"]):
        actual = pd.read_csv(pin["path"], dtype={"corner": str})
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-9)
    for layer, expected in (("survey_boundary_corners", corners), ("survey_footprint", footprint)):
        actual = gpd.read_file(report["spatial_output"]["path"], layer=layer)
        if actual.crs != expected.crs or len(actual) != len(expected) or not actual.geometry.geom_equals_exact(expected.geometry, 1e-7).all():
            raise ValueError("Saved survey geometry differs from primary coordinate transcription")
        pd.testing.assert_frame_equal(actual.drop(columns="geometry"), expected.drop(columns="geometry"),
                                      check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-9)
    if any(report.get(k) != v for k, v in context.items()):
        raise ValueError("Survey interpretation differs from primary evidence readback")
    result = dict(source_and_output_sha256_match=True, coordinate_and_height_transcription_readback=True,
                  paired_crs_verified=True, saved_spatial_geometry_verified=True,
                  no_unverified_vertical_or_2021_bed_promotion=True, pass_=True,
                  corner_count=7, collar_count=11, surveyed_bathymetry_accepted_count=0,
                  overlap_objects=context["overlap_objects"])
    (OUTPUT / "V49_PhuSen_2024_survey_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    build()
    print(json.dumps(validate(), indent=2))
