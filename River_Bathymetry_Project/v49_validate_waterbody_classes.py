"""Independent acceptance validator for V49-C water-body classification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import geopandas as gpd

from v49_classify_waterbodies import (
    CHANNEL_ELIGIBLE_CLASSES,
    DEFAULT_DEM,
    DEFAULT_INVENTORY,
    DEFAULT_OUTPUT_DIR,
    EXPECTED_DEM_SHA256,
    FINAL_CLASSES,
    TREATMENT_BY_CLASS,
)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def validate_classification(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    inventory_path: Path = DEFAULT_INVENTORY,
    dem_path: Path = DEFAULT_DEM,
) -> dict:
    gpkg = output_dir / "V49_waterbody_classification.gpkg"
    audit_path = output_dir / "V49_C_classification_audit.json"
    classified = gpd.read_file(gpkg, layer="classified_objects")
    inventory = gpd.read_file(inventory_path, layer="water_objects")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))

    inventory_ids = set(inventory.object_id.astype(str))
    classified_ids = set(classified.object_id.astype(str))
    missing_ids = sorted(inventory_ids - classified_ids)
    extra_ids = sorted(classified_ids - inventory_ids)
    duplicate_ids = sorted(
        classified.loc[classified.object_id.astype(str).duplicated(), "object_id"].astype(str).tolist()
    )

    required_fields = [
        "final_class",
        "subtype",
        "final_confidence",
        "review_required_final",
        "treatment_code",
        "treatment_rule",
        "evidence_summary",
        "future_channel_geometry_eligible",
    ]
    missing_fields = [field for field in required_fields if field not in classified.columns]
    blank_fields: dict[str, int] = {}
    if not missing_fields:
        for field in ["final_class", "subtype", "final_confidence", "treatment_code", "treatment_rule", "evidence_summary"]:
            values = classified[field].fillna("").astype(str).str.strip()
            blank_fields[field] = int(values.eq("").sum())

    invalid_classes = sorted(set(classified.final_class.astype(str)) - set(FINAL_CLASSES)) if "final_class" in classified else ["MISSING_FIELD"]
    treatment_mismatches: list[str] = []
    channel_eligibility_mismatches: list[str] = []
    if not missing_fields and not invalid_classes:
        for _, row in classified.iterrows():
            object_id = str(row.object_id)
            final_class = str(row.final_class)
            expected_treatment = TREATMENT_BY_CLASS[final_class][0]
            if str(row.treatment_code) != expected_treatment:
                treatment_mismatches.append(object_id)
            expected_eligible = final_class in CHANNEL_ELIGIBLE_CLASSES
            if bool(row.future_channel_geometry_eligible) != expected_eligible:
                channel_eligibility_mismatches.append(object_id)

    unknown = classified[classified.final_class.astype(str) == "UNKNOWN_REVIEW_REQUIRED"] if "final_class" in classified else classified.iloc[0:0]
    unknown_review_fail = sorted(
        unknown.loc[~unknown.review_required_final.astype(bool), "object_id"].astype(str).tolist()
    ) if "review_required_final" in unknown else []
    unknown_treatment_fail = sorted(
        unknown.loc[unknown.treatment_code.astype(str) != "NO_AUTOMATIC_CARVING", "object_id"].astype(str).tolist()
    ) if "treatment_code" in unknown else []

    class_specific_failures: dict[str, list[str]] = {}
    expected = {
        "OCEAN": "EXTERNAL_BATHYMETRY_OR_BOUNDARY",
        "WETLAND_FLOODPLAIN_WATER": "PRESERVE_STORAGE_NO_RIVER_TRENCH",
        "LAKE_RESERVOIR": "STAGE_AREA_VOLUME_OR_BATHYMETRY",
        "ESTUARY_TIDAL_RIVER": "TIDAL_RIVER_WITH_MARINE_BOUNDARY",
    }
    if "final_class" in classified and "treatment_code" in classified:
        for cls, treatment in expected.items():
            subset = classified[classified.final_class.astype(str) == cls]
            bad = subset[subset.treatment_code.astype(str) != treatment]
            class_specific_failures[cls] = sorted(bad.object_id.astype(str).tolist())

    dem_hash_now = sha256_file(dem_path)
    audit_before = str(audit.get("source_hashes", {}).get("dem_sha256_before", ""))
    audit_after = str(audit.get("source_hashes", {}).get("dem_sha256_after", ""))
    dem_unchanged = bool(
        dem_hash_now == EXPECTED_DEM_SHA256 == audit_before == audit_after
        and audit.get("dem_unchanged", False)
        and not audit.get("dem_modified_in_v49_c", True)
    )

    osm_info = audit.get("historical_osm", {})
    osm_provenance_ok = bool(
        osm_info.get("status") == "HISTORICAL_OSM_SNAPSHOT"
        and osm_info.get("snapshot_utc") == "2021-11-25T00:00:00Z"
        and int(osm_info.get("unique_waterway_count", 0)) > 0
    )

    all_documented = bool(
        not missing_fields
        and all(count == 0 for count in blank_fields.values())
        and not invalid_classes
        and not treatment_mismatches
    )
    parent_support_ok = True
    parent_support_error = None
    if "parent_channel_support" in audit:
        try:
            from v49_audit_parent_channel_support import validated_table
            pin = audit["parent_channel_support"]
            manifest = Path(pin["path"])
            if sha256_file(manifest) != pin["sha256"]:
                raise ValueError("Parent-support manifest changed")
            decisions = validated_table(manifest.parent).set_index("object_id")
            if set(decisions.index) != classified_ids:
                raise ValueError("Parent decision object coverage mismatch")
            for _, row in classified.iterrows():
                if str(row.final_class) != str(decisions.loc[row.object_id, "after"]):
                    raise ValueError(f"Classification diverges from source geometry: {row.object_id}")
        except Exception as exc:
            parent_support_ok, parent_support_error = False, str(exc)
    gate_c_pass = bool(
        len(classified) == len(inventory) == 81
        and not missing_ids
        and not extra_ids
        and not duplicate_ids
        and all_documented
        and not channel_eligibility_mismatches
        and not unknown_review_fail
        and not unknown_treatment_fail
        and all(not ids for ids in class_specific_failures.values())
        and dem_unchanged
        and osm_provenance_ok
        and parent_support_ok
    )

    report = {
        "schema_version": "V49-C-validation-1",
        "inventory_object_count": int(len(inventory)),
        "classified_object_count": int(len(classified)),
        "missing_object_ids": missing_ids,
        "extra_object_ids": extra_ids,
        "duplicate_object_ids": duplicate_ids,
        "missing_required_fields": missing_fields,
        "blank_required_field_counts": blank_fields,
        "invalid_classes": invalid_classes,
        "treatment_mismatch_object_ids": treatment_mismatches,
        "channel_eligibility_mismatch_object_ids": channel_eligibility_mismatches,
        "unknown_review_required_failures": unknown_review_fail,
        "unknown_no_carve_failures": unknown_treatment_fail,
        "class_specific_treatment_failures": class_specific_failures,
        "unknown_review_count": int(len(unknown)),
        "all_objects_documented": all_documented,
        "historical_osm_provenance_ok": osm_provenance_ok,
        "parent_channel_support_ok": parent_support_ok,
        "parent_channel_support_error": parent_support_error,
        "dem_expected_sha256": EXPECTED_DEM_SHA256,
        "dem_current_sha256": dem_hash_now,
        "dem_unchanged": dem_unchanged,
        "modified_water_pixel_count_in_v49_c": 0,
        "gate_c_interpretation": (
            "V49-C performs no DEM edits. Gate C passes when every inventory object has a documented class/treatment, "
            "uncertain objects are explicitly no-carve review targets, class safety constraints hold, and the source DEM hash is unchanged."
        ),
        "gate_c_pass": gate_c_pass,
    }
    path = output_dir / "V49_C_validation_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    args = parser.parse_args()
    print(json.dumps(validate_classification(args.output_dir, args.inventory, args.dem), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
