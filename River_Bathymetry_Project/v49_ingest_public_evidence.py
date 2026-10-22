"""Normalize visually verified official reservoir tables and 2021 flood peaks.

Printed Z/F/W values are retained without adjustment. These are reservoir
storage references, not measured spatial bed elevations. Gauge datum and
station coordinates must be verified before evaluating modeled absolute WSE.
"""
from pathlib import Path
from datetime import datetime, timezone
import json
import numpy as np
import pandas as pd
import fitz
from v49_synthesize_hydraulic_bed import sha256_file

PROJECT = Path(__file__).resolve().parent
SOURCES = PROJECT / "V49_sources_20261013"
OUTPUT = PROJECT / "V49_PUBLIC_EVIDENCE_20261013"
CURVES = {
    "SONG_BA_HA": {
        "page": 45, "object_id": "W20_0028",
        "z": [67.8,70,72.5,75,77.5,80,82.5,85,87.5,90,92.5,95,97.5,100,102.5,105,107.5,110,112.5,115,117.5,120],
        "f": [0,.38,.47,.70,.82,.94,1.19,2.37,3.41,4.98,7.15,10.59,14.80,26.48,39.28,54.66,79.94,99.29,119.92,142.11,170.54,192.52],
        "w": [0,.28,1.34,2.80,4.71,6.91,9.57,13.94,21.13,31.55,46.62,68.65,100.23,151.12,232.79,349.69,516.95,740.56,1014.17,1341.32,1731.60,2185.14],
    },
    "SONG_HINH": {
        "page": 47, "object_id": "W20_0059",
        "z": [185,190,195,200,205,210,215,220],
        "f": [0,1.16,8.75,19.,30.41,43.28,58.69,71.76],
        "w": [0,1.93,24.47,92.28,215.20,399.44,655.49,980.40],
    },
}

SUPPLEMENTARY_SOURCES = {
    "TT25_2015_PhuYen_geographic_names.pdf": "https://vupc.mae.gov.vn/Data/files/25-2015-tt-btnmt.PDF",
    "QD1136_2020_reservoir_inventory.pdf": "https://congbao.daklak.gov.vn/FileCongBao/upload/2001592/convertPDFFile/61e0de92582d7c018305328d.pdf",
    "IWRP_storage_bulletin_20220930.pdf": "https://vanhanhtt.thuyloivietnam.gov.vn/resource/32f93d85-61e5-eddf-54fd-1fede2d4b613/Ban%20tin%20tich%20%20nuoc%20ho%20chua%20vung%20NTB.%20T10.pdf",
    "IWRP_weekly_20211008.pdf": "https://vanhanhtt.thuyloivietnam.gov.vn/resource/32f93d85-61e5-eddf-54fd-1fede2d4b613/Nam%20Trung%20Bo_Ban%20tin%20Tuan_08.10.2021.pdf",
}

VERIFIED_SOURCE_SHA256 = {
    "TT25_2015_PhuYen_geographic_names.pdf": "3785c61a37e0a1fb3448dc5276d73ead76b9e8433e7408431455863ddc75c631",
    "QD878_2018_SongBa.pdf": "618b34beabc213ca495b61330a90e7abecaaa9c2f94178ecc873325efa1b26d2",
    "DakLak_environment_2021_2025_2026.pdf": "c29c63ed68cd1e7e0afd4818f2890cde81f3e9528da93672097e437f2cef4c29",
    "QD1757_2010_ZFW.pdf": "7acbf83a34117efbaa85293e597e65e6ce5b7437bbc3afbe23b82d300d7a524c",
    "IMH_HECRAS_PhuYen_2024.pdf": "3108d28a3941ae654b3239a556dcefbd88bc1be4110a158b18ecf98017ca588f",
    "QD1136_2020_reservoir_inventory.pdf": "2c3c36531b306ea7d43e089e46e6a0a0ea58ae4e7fe028051c4a03a6b7d24205",
    "IWRP_storage_bulletin_20220930.pdf": "0d8d900136daa8e226ea30712e73534983d10031d07d356da35a9ff879fcb7fa",
    "IWRP_weekly_20211008.pdf": "8bab2629b265e57e0f889a44ab3151f6da8470cf7f5f4c661ddb665e6b81172c",
}


def verified_source_sha256(path, expected):
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Published source changed after visual verification: {path}")
    return actual


def published_capacity_references():
    """Identity candidates only: one capacity is not a stage-volume curve."""
    return [
        {"reservoir": name, "locality_as_published": locality, "inventory_object_id_candidate": object_id,
         "useful_volume_million_m3": useful, "total_volume_million_m3": total,
         "dam_crest_elevation_m": crest, "maximum_dam_height_m": height,
         "source_pdf_page_1_based": page, "identity_match_status": "NAME_AND_LOCALITY_CANDIDATE_REQUIRES_FOOTPRINT_CHECK",
         "full_zfw_curve_available": False, "spatial_bathymetry_certified": False}
        for name, locality, object_id, useful, total, crest, height, page in [
            ("Phú Xuân", "Xuân Phước, Đồng Xuân", "W20_0012", 8.59,11.22,39.70,23.8,2),
            ("Đồng Tròn", "An Nghiệp, Tuy An", "W20_0014",18.31,19.55,38.,29.,2),
            ("Suối Vực", "Suối Bạc, Sơn Hòa", "W20_0020",9.94,10.510,91.7,26.59,2),
            ("Đồng Khôn", "Hòa Xuân Tây, Đông Hòa", "W20_0069",2.61,2.716,26.2,16.2,2),
            ("Buôn Đức", "EaTrol, Sông Hinh", "W20_0071",None,4.276,203.8,19.6,2),
            ("Hóc Răm", "Hòa Tân Tây, Tây Hòa", "W20_0064",2.60,2.910,25.8,17.8,3),
        ]
    ]


def catalogue_relative_locations():
    """Original-page transcription of relative map locations, not survey marks."""
    rows = []
    for name, locality, oid, lat, lon, page, kind in [
        ("Sông Ba Hạ", "Suối Trai, Sơn Hòa", "W20_0028", (13,3,56), (108,54,38),67,"RESERVOIR"),
        ("Sông Ba Hạ", "Đức Bình Tây, Sông Hinh", "W20_0028", (13,1,22), (108,53,35),69,"RESERVOIR"),
        ("Sông Hinh", "Đức Bình Đông, Sông Hinh", "W20_0059", (12,55,16), (108,58,16),69,"RESERVOIR"),
        ("Phú Xuân", "Xuân Phước, Đồng Xuân", "W20_0012", (13,17,0), (109,1,46),39,"RESERVOIR"),
        ("Đồng Tròn", "An Nghiệp, Tuy An", "W20_0014", (13,16,5), (109,9,35),96,"RESERVOIR"),
        ("Đồng Khôn", "Hòa Xuân Tây, Đông Hòa", "W20_0069", (12,55,37), (109,19,31),31,"RESERVOIR"),
        ("Hóc Răm", "Hòa Tân Tây, Tây Hòa", "W20_0064", (12,56,20), (109,16,57),82,"RESERVOIR"),
        ("cầu Ngân Sơn", "Chí Thạnh, Tuy An", "W20_0011", (13,19,41), (109,12,27),85,"BRIDGE"),
    ]:
        rows.append({"name_as_published": name, "locality_as_published": locality,
                     "inventory_object_id_candidate": oid, "feature_type": kind,
                     "latitude_dms": " ".join(map(str,lat)), "longitude_dms": " ".join(map(str,lon)),
                     "latitude_vn2000_degrees": lat[0]+lat[1]/60+lat[2]/3600,
                     "longitude_vn2000_degrees": lon[0]+lon[1]/60+lon[2]/3600,
                     "horizontal_crs": "VN-2000 (EPSG:4756), national 1:25000 map catalogue",
                     "location_semantics": "RELATIVE_MAP_FEATURE_CENTRE_NOT_MEASUREMENT_STATION",
                     "object_link_semantics": "SAME_NAME_RIVER_LANDMARK_CONTEXT_ONLY" if kind == "BRIDGE" else "NAME_LOCALITY_RESERVOIR_CANDIDATE",
                     "coordinate_accuracy_m": None, "source_pdf_page_1_based": page,
                     "vertical_datum": "NOT_PROVIDED_BY_GEOGRAPHIC_NAMES_CATALOGUE",
                     "usable_as_gauge_or_survey_location": False,
                     "automatic_geometry_authorization": False})
    return rows


def storage_at_level(curve, elevation_m):
    if not {"z", "f", "w"}.issubset(curve):
        raise ValueError("A complete ZFW table is required; a single capacity is not a curve")
    z, f, w = (np.asarray(curve[key], dtype=float) for key in ("z", "f", "w"))
    if not (2 <= len(z) == len(f) == len(w)) or not all(np.isfinite(a).all() for a in (z,f,w)):
        raise ValueError("Invalid curve rows")
    if any(np.any(np.diff(a) <= 0) for a in (z,f,w)):
        raise ValueError("Storage curve must be strictly increasing")
    if not np.isfinite(elevation_m) or elevation_m < z[0] or elevation_m > z[-1]:
        raise ValueError("Elevation outside the published curve; extrapolation is prohibited")
    return {"elevation_m": float(elevation_m), "surface_area_km2": float(np.interp(elevation_m,z,f)),
            "volume_m3": float(np.interp(elevation_m,z,w) * 1e6), "interpolation": "PIECEWISE_LINEAR_BETWEEN_PUBLISHED_ROWS"}


def build():
    for name, expected in VERIFIED_SOURCE_SHA256.items():
        verified_source_sha256(SOURCES / name, expected)
    OUTPUT.mkdir(exist_ok=True)
    reservoir_pdf = SOURCES / "QD878_2018_SongBa.pdf"
    report_pdf = SOURCES / "DakLak_environment_2021_2025_2026.pdf"
    reference_sha = sha256_file(reservoir_pdf)
    report_sha = sha256_file(report_pdf)
    registry = []
    source_urls = {"QD878_2018_SongBa.pdf": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2018/07/878-qd-ttg.signed.pdf",
                   "DakLak_environment_2021_2025_2026.pdf": "https://vpubnd.daklak.gov.vn/CMS/Content/VanBan/2026/4.2026/1123_QD-UBND%20BC.pdf",
                   "QD1757_2010_ZFW.pdf": "https://congbao.chinhphu.vn/van-ban/quyet-dinh-so-1757-qd-ttg-3387/1435.htm"}
    source_urls["IMH_HECRAS_PhuYen_2024.pdf"] = "https://imh.ac.vn/wp-content/uploads/2024/07/30.bai-6.pdf"
    source_urls.update(SUPPLEMENTARY_SOURCES)
    for name, url in source_urls.items():
        p = SOURCES / name
        registry.append({"path": str(p), "source_url": url, "sha256": sha256_file(p), "bytes": p.stat().st_size,
                         "download_transport": "Windows Invoke-WebRequest with certificate verification"})
    curve_reports = {}
    for name, curve in CURVES.items():
        for z in curve["z"]:
            storage_at_level(curve, z)
        frame = pd.DataFrame({"elevation_m": curve["z"], "surface_area_km2": curve["f"],
                              "volume_million_m3": curve["w"], "volume_m3": np.asarray(curve["w"]) * 1e6})
        frame.to_csv(OUTPUT / f"{name}_published_ZFW.csv", index=False)
        curve_reports[name] = {"published_rows": len(frame), "inventory_object_id": curve["object_id"],
                              "source_path": str(reservoir_pdf), "source_sha256": reference_sha,
                              "source_pdf_page_1_based": curve["page"], "source_url": source_urls[reservoir_pdf.name],
                              "extraction": "Printed numeric table transcribed and visually checked against original PDF; not graph digitization",
                              "reference_status": "VERIFIED_PUBLISHED_STORAGE_CURVE", "vertical_datum_transform_to_model": None,
                              "spatial_bathymetry_certified": False,
                              "limitations": "Engineering reference predates 2021; survey date/sedimentation, full reservoir footprint and vertical datum transformation remain to be established."}
    peak_rows = []
    for station, value, local, page in [
        ("CUNG_SON",38.72,"2021-11-30T19:00:00+07:00",211),
        ("PHU_LAM",4.63,"2021-11-30T23:00:00+07:00",212),
        ("HA_BANG",10.61,"2021-11-30T16:00:00+07:00",212)]:
        peak_rows.append({"station": station, "observation_type": "EVENT_PEAK_REPORTED",
                          "reported_stage_m": value, "time_local": local,
                          "time_utc": datetime.fromisoformat(local).astimezone(timezone.utc).isoformat(),
                          "source_path": str(report_pdf), "source_sha256": report_sha, "pdf_page_1_based": page,
                          "vertical_datum": "UNVERIFIED", "station_coordinate_status": "UNVERIFIED",
                          "usable_as_absolute_model_wse": False, "usable_for_model_timing_after_station_location_verification": True})
    pd.DataFrame(peak_rows).to_csv(OUTPUT / "2021_official_reported_flood_peaks.csv", index=False)
    capacity_pdf = SOURCES / "QD1136_2020_reservoir_inventory.pdf"
    capacity_rows = published_capacity_references()
    for row in capacity_rows:
        row.update(source_path=str(capacity_pdf), source_sha256=sha256_file(capacity_pdf),
                   source_url=source_urls[capacity_pdf.name], reference_year=2020)
        row["total_volume_m3"] = row["total_volume_million_m3"] * 1e6
    pd.DataFrame(capacity_rows).to_csv(OUTPUT / "published_minor_reservoir_capacity_references.csv", index=False)
    catalogue_pdf = SOURCES / "TT25_2015_PhuYen_geographic_names.pdf"
    location_rows = catalogue_relative_locations()
    for row in location_rows:
        row.update(source_path=str(catalogue_pdf), source_sha256=sha256_file(catalogue_pdf),
                   source_url=source_urls[catalogue_pdf.name], reference_year=2015)
    pd.DataFrame(location_rows).to_csv(OUTPUT / "published_relative_geographic_locations.csv", index=False)
    hwm_pdf = SOURCES / "IMH_HECRAS_PhuYen_2024.pdf"
    with fitz.open(hwm_pdf) as paper:
        text = paper[7].get_text()
    block = text.split("Kinh độ\nVĩ độ\n", 1)[1].split("Kết quả mô phỏng", 1)[0]
    tokens = [float(s.replace(",", ".")) for s in block.splitlines() if s.strip()]
    table = np.asarray(tokens).reshape(20, 6)
    if not np.array_equal(table[:, 0], np.arange(1, 21)) or not np.allclose(table[:, 3] - table[:, 4], table[:, 5], atol=.011):
        raise ValueError("Published HWM table extraction failed row/delta consistency")
    hwm = pd.DataFrame({"point_id": table[:, 0].astype(int), "longitude_reported": table[:, 1],
                        "latitude_reported": table[:, 2], "observed_mark_elevation_m": table[:, 3],
                        "coordinate_rounding_degrees": .01, "longitude_half_width_degrees": .005,
                        "latitude_half_width_degrees": .005, "vertical_datum": "UNVERIFIED",
                        "survey_month": "2022-05", "flood_event_start": "2021-11-25", "flood_event_end": "2021-12-05",
                        "source_pdf_page_1_based": 8, "source_sha256": sha256_file(hwm_pdf),
                        "usable_for_exact_30m_point_wse_validation": False})
    hwm.to_csv(OUTPUT / "2021_published_high_water_marks_coarse_coordinates.csv", index=False)
    output_tables = []
    for name in ("SONG_BA_HA_published_ZFW.csv", "SONG_HINH_published_ZFW.csv",
                 "2021_official_reported_flood_peaks.csv", "published_minor_reservoir_capacity_references.csv",
                 "2021_published_high_water_marks_coarse_coordinates.csv", "published_relative_geographic_locations.csv"):
        path = OUTPUT / name
        output_tables.append({"path": str(path), "sha256": sha256_file(path), "row_count": len(pd.read_csv(path))})
    summary = {"schema_version": "V49-public-evidence-1", "sources": registry, "reservoir_curves": curve_reports,
               "output_tables": output_tables,
               "published_reservoir_curve_count": len(curve_reports), "published_curve_rows": 30,
               "official_reported_peak_count": len(peak_rows),
               "minor_reservoir_capacity_reference_count": len(capacity_rows),
               "minor_reservoir_capacity_references": capacity_rows,
               "relative_geographic_location_count": len(location_rows),
               "relative_geographic_location_limitations": "Feature centres from the 2015 VN-2000 1:25000 geographic-name catalogue; not hydrometric stations or survey coordinates. Original PDF pages, not unverified OCR, supply the transcription.",
               "published_high_water_mark_count": len(hwm),
               "high_water_mark_limitations": "Coordinates are rounded to 0.01 degrees (roughly 1 km) and vertical datum is unspecified; do not substitute them for exact 30 m survey points. Event window also extends beyond the frozen 120 h simulation.",
               "observation_conflicts": [
                   {"station": "PHU_LAM", "official_retrospective_peak": "4.63 m at 2021-11-30 23:00 +07",
                    "previous_official_rapid_report": "4.62 m at 2021-12-01 01:00 +07",
                    "action": "Retain separate source claims; resolve 0.01 m / 2 h discrepancy before choosing a single timing target"},
                   {"reservoir": "SONG_BA_HA", "official_2018_reference": "349.70 million m3 total in technical table; ZFW row at 105 m is 349.69 million m3",
                    "owner_website_reference": "394.70 million m3 total",
                    "owner_website_url": "https://beta.sbh.vn/c3/gioi-thieu-c/Linh-vuc-hoat-dong-2-224",
                    "action": "Use the printed 2018 ZFW rows as a versioned reference; do not silently scale to the conflicting summary"},
                   {"reservoir": "SONG_HINH", "official_2018_normal_level_m": 209.,
                    "official_2018_total_volume_m3": 357000000.,
                    "coarse_table_piecewise_linear_volume_at_normal_level_m3": storage_at_level(CURVES["SONG_HINH"], 209.)["volume_m3"],
                    "action": "Retain the published technical value separately; 5 m row spacing makes linear interpolation approximate, not a measured volume at 209 m"},
                   {"reservoir": "HOA_SON", "source_path": str(SOURCES / "IWRP_storage_bulletin_20220930.pdf"),
                    "source_sha256": sha256_file(SOURCES / "IWRP_storage_bulletin_20220930.pdf"),
                    "published_region": "Vạn Ninh, Khánh Hòa",
                    "technical_table_normal_level_m": 27., "operational_table_normal_level_m": 26.5,
                    "technical_table_pdf_page": 5, "operational_table_pdf_page": 6,
                    "action": "Do not merge competing normal levels or force a Phú Yên administrative match"}],
               "external_validation_complete": False, "hydraulic_promotion_ready": False}
    (OUTPUT / "V49_PUBLIC_EVIDENCE_REGISTER.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (SOURCES / "SOURCE_MANIFEST.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("published_reservoir_curve_count", "published_curve_rows", "official_reported_peak_count", "published_high_water_mark_count", "external_validation_complete")}, indent=2))
    return summary


if __name__ == "__main__":
    build()
