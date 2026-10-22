from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(r"D:\VTP")
PREREG = ROOT / "V48_SAR_preregistration_20261002.json"
RELEASE = ROOT / "V48_SAR_OBSERVATION_RELEASE_20261002.json"
VALIDATION = ROOT / "V48_SAR_OBSERVATION_VALIDATION_20261002.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise RuntimeError(f"Expected explicit UTC timestamp, got {value}")
    return parsed


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    for path in (PREREG, RELEASE, VALIDATION):
        if not path.is_file():
            raise FileNotFoundError(path)

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))

    if release.get("status") != "V48_SAR_OBSERVATION_FROZEN_PRE_FORMAL_EVALUATION":
        raise RuntimeError(f"Unexpected SAR observation release status: {release.get('status')}")
    if validation.get("status") != "PASS_V48_SAR_OBSERVATION_VALIDATION" or validation.get("failures"):
        raise RuntimeError("SAR observation validation has not passed cleanly")
    if release.get("formal_bg_flood_run") is not False or release.get("formal_sar_evaluation_run") is not False:
        raise RuntimeError("Observation release must remain pre-formal-evaluation")

    source = release["source"]
    processing = release["processing"]
    observation = release["observation"]

    for key in ("tif", "asc", "prj"):
        item = observation[key]
        path = Path(item["path"])
        if not path.is_file() or sha256(path).lower() != item["sha256"].lower():
            raise RuntimeError(f"Observation {key} hash verification failed: {path}")

    release_hash = sha256(RELEASE)
    validation_hash = sha256(VALIDATION)
    start = parse_utc(source["start_datetime_utc"])
    stop = parse_utc(source["end_datetime_utc"])
    if stop <= start:
        raise RuntimeError("Sentinel acquisition stop must be after start")
    midpoint = start + (stop - start) / 2
    ict = timezone(timedelta(hours=7))

    # Preserve the old local raster only as historical evidence. It does not
    # establish provenance for the newly reconstructed V48 observation.
    old_local = prereg.get("local_observation", {})
    if "legacy_unverified_observation" not in prereg.setdefault("source_provenance", {}):
        prereg["source_provenance"]["legacy_unverified_observation"] = {
            "role": "historical V39-V45 observation reference only; exact product lineage, acquisition UTC, and class semantics were not proven for this raster",
            "tif": old_local.get("tif"),
            "asc": old_local.get("asc"),
            "engineering_alignment_raster": old_local.get("engineering_alignment_raster"),
            "product_to_local_observation_lineage_verified": False,
            "acquisition_utc_verified_for_this_local_raster": False,
            "class_semantics_verified_from_product_lineage": False,
        }

    prereg["candidate_observation_product"]["preferred_candidate"] = {
        "product_id": source["stac_item_id"],
        "source_grd_product_id": source["stac_item_id"].removesuffix("_rtc"),
        "provider": source["provider"],
        "platform": source.get("platform"),
        "mode": "IW",
        "product_type": "Sentinel-1 RTC derived from GRD",
        "polarization": ["VV"],
        "orbit_direction": str(source.get("orbit_state", "")).upper(),
        "relative_path": source.get("relative_orbit"),
        "acquisition_start_utc": iso_utc(start),
        "acquisition_stop_utc": iso_utc(stop),
        "acquisition_midpoint_utc": iso_utc(midpoint),
        "acquisition_start_ict": start.astimezone(ict).isoformat(),
        "acquisition_stop_ict": stop.astimezone(ict).isoformat(),
        "acquisition_midpoint_ict": midpoint.astimezone(ict).isoformat(),
        "source_asset_href": source["vv_asset_href"],
        "source_asset_http": source.get("vv_asset_http"),
        "catalog_provenance": "Microsoft Planetary Computer sentinel-1-rtc STAC item pinned in V48_SAR_OBSERVATION_RELEASE_20261002.json",
        "processing_manifest_path": str(RELEASE),
        "processing_manifest_sha256": release_hash,
        "product_to_local_observation_lineage_verified": True,
    }

    prereg["local_observation"] = {
        "tif": {
            **observation["tif"],
            "width": observation["width"],
            "height": observation["height"],
            "crs": observation["crs"],
            "resolution_m": observation["resolution_m"],
            "nodata": observation["nodata"],
            "band_description": "S1_RTC_VV_OTSU_FLOOD_CLASS",
        },
        "asc": observation["asc"],
        "prj": observation["prj"],
        "release_manifest": {"path": str(RELEASE), "sha256": release_hash},
        "validation_manifest": {"path": str(VALIDATION), "sha256": validation_hash},
        "acquisition_start_utc": source["start_datetime_utc"],
        "acquisition_end_utc": source["end_datetime_utc"],
        "acquisition_midpoint_utc": iso_utc(midpoint),
        "class_semantics_required": processing["classification"],
        "class_semantics_verified_from_product_lineage": True,
        "acquisition_utc_verified_for_this_local_raster": True,
        "source_product_to_local_observation_lineage_verified": True,
        "reconstruction_note": "New V48 observation reconstructed directly from the pinned public Sentinel-1 RTC VV asset before formal BG_Flood/SAR evaluation. This does not retroactively prove provenance of the older Otsu TIFF.",
    }

    prereg["source_provenance"]["sar_observation_release"] = {
        "path": str(RELEASE),
        "sha256": release_hash,
    }
    prereg["source_provenance"]["sar_observation_validation"] = {
        "path": str(VALIDATION),
        "sha256": validation_hash,
    }

    removable_prefixes = (
        "Prove exact Sentinel product ID -> local observation TIFF lineage",
        "Verify acquisition UTC for the exact local observation raster",
        "Verify observation class semantics and coverage/NoData semantics",
    )
    prereg["formal_evaluation_blockers"] = [
        item
        for item in prereg.get("formal_evaluation_blockers", [])
        if not item.startswith(removable_prefixes)
    ]
    prereg["formal_evaluation_allowed"] = False
    prereg["status"] = "BLOCKED_PRE_SAR_PREREGISTRATION"
    PREREG.write_text(json.dumps(prereg, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": prereg["status"],
        "preregistration": str(PREREG),
        "preregistration_sha256": sha256(PREREG),
        "observation_tif": observation["tif"],
        "observation_release_sha256": release_hash,
        "observation_validation_sha256": validation_hash,
        "acquisition_midpoint_utc": iso_utc(midpoint),
        "remaining_documented_blockers": prereg["formal_evaluation_blockers"],
        "formal_evaluation_allowed": prereg["formal_evaluation_allowed"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
