"""Read back the seven primary sources obtained in the R3 research pass."""
import json
from pathlib import Path

import fitz

from v49_classify_waterbodies import sha256_file

PROJECT = Path(__file__).resolve().parent
SOURCES = PROJECT / "V49_sources_R3_20261013"
FILES = [
    ("Gov_PhuSen_DaRang_sand_EIA_2026.pdf", "a1287f66384d07e10ebbf7fe3380974d7041bb23e568a474eb4f342e07404440", 219,
     "https://snnmt.daklak.gov.vn/uploads/sonnmt/ccbvmt/0%20.DTM%20Phu%20Sen%20Binh%20An.pdf"),
    ("Gov_SonHoa_Ba_sand_EIA_2026.rar", "8995e49d57a61770e67f94f404b78a9d75684a6b7462488b28cd9b468f5ac4cd", None,
     "https://drive.google.com/file/d/1GALFlawuQxrntwYQx6Hq8X_ptd7MMLrL/view?usp=sharing"),
    ("Gov_SonHoa_Ba_sand_EIA_2026.pdf", "96ff57c726e17f82578ee631d071ea675e739076b8826d04a614085c1766c748", 173,
     "https://drive.google.com/file/d/1GALFlawuQxrntwYQx6Hq8X_ptd7MMLrL/view?usp=sharing"),
    ("VNU_KyLo_flood_2021.pdf", "4c423a5e52be639eec1f6a91f00d47659584a751743787c25cc98831afb575f6", 10,
     "https://js.vnu.edu.vn/EES/article/download/4695/4078"),
    ("VNJHM_CungSon_coordinate_Bayes_2021.pdf", "2d62ea1beb47bbfd704a593e07bdba2ab01a93f6fc2a4e8cf08d905c5e3833e9", 13,
     "http://tapchikttv.vn/article-file-download/1791"),
    ("VNJHM_HaBang_survey_2021.pdf", "3fa16c49ccbe6e892d09c32dee172806b1f11e2eb1cfd959415fb0350ccdb3ad", 9,
     "http://tapchikttv.vn/article-file-download/1780"),
    ("NCHMF_hydro_station_map_20261013.html", "1f6fe3ab2666c6c21723a8d2f23891ac8196ecea743dfb9a4b998e1ca64e221f", None,
     "https://www.nchmf.gov.vn/kttv/vi-VN/1/index.html"),
]


def audit():
    checks = []
    for name, expected, pages, url in FILES:
        path = SOURCES / name
        actual = sha256_file(path) if path.is_file() else None
        actual_pages = None
        if pages is not None and actual == expected:
            with fitz.open(path) as pdf:
                actual_pages = len(pdf)
        checks.append(dict(path=str(path.resolve()), source_url=url, expected_sha256=expected,
                           actual_sha256=actual, expected_pdf_pages=pages, actual_pdf_pages=actual_pages,
                           pass_=actual == expected and actual_pages == pages))
    report = dict(schema_version="V49-R3-primary-research-readback-1", sources=checks,
                  source_count=len(checks), pass_=all(c["pass_"] for c in checks))
    report["2021_hourly_samples_obtained"] = 0
    output = PROJECT / "V49_R3_20261013" / "V49_R3_PRIMARY_RESEARCH_REGISTER.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
