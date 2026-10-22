"""Validate V49-A inventory completeness, DEM immutability, and output consistency."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from v49_build_water_inventory import DEFAULT_OUTPUT_DIR, sha256_file


def validate(output_dir: Path) -> dict:
    audit_path = output_dir / "V49_water_coverage_audit.json"
    csv_path = output_dir / "V49_water_object_table.csv"
    gpkg_path = output_dir / "V49_master_water_inventory.gpkg"
    map_path = output_dir / "V49_water_coverage_map.png"
    evidence_path = output_dir / "V49_master_water_evidence.tif"
    ocean_path = output_dir / "V49_ocean_mask.tif"

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    table = pd.read_csv(csv_path)
    spatial = gpd.read_file(gpkg_path, layer="water_objects")
    dem_path = Path(audit["inputs"]["dem"])

    expected_inland = int(
        audit["threshold_audit"][str(audit["config"]["occurrence_threshold"])][
            "qualifying_object_count"
        ]
    )
    inland = table[table["provisional_class"] != "OCEAN"]

    checks = {
        "csv_and_gpkg_row_count_match": len(table) == len(spatial),
        "object_ids_unique": table["object_id"].is_unique,
        "expected_inland_object_count_matches": len(inland) == expected_inland,
        "all_inland_objects_have_class": bool(inland["provisional_class"].notna().all()),
        "all_review_candidates_are_flagged": bool(
            (
                ~inland["provisional_class"].astype(str).str.contains(
                    "REVIEW_REQUIRED|CANDIDATE"
                )
                | inland["review_required"].astype(bool)
            ).all()
        ),
        "ocean_object_present": bool((table["provisional_class"] == "OCEAN").any()),
        "ocean_excluded_from_inland_statistics": bool(
            audit["gate_A"]["ocean_excluded_from_inland_statistics"]
        ),
        "dem_sha256_still_matches": sha256_file(dem_path)
        == audit["dem_integrity"]["sha256_before"],
        "coverage_map_exists": map_path.exists() and map_path.stat().st_size > 0,
        "evidence_raster_exists": evidence_path.exists() and evidence_path.stat().st_size > 0,
        "ocean_mask_exists": ocean_path.exists() and ocean_path.stat().st_size > 0,
    }
    report = {
        "version": "V49-A",
        "checks": checks,
        "pass": bool(all(checks.values())),
    }
    report_path = output_dir / "V49_A_validation_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = validate(args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()

