from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(r"D:\VTP")
RAIN_V23 = ROOT / "Scenarios" / "rain_v23_era5_spatial.txt"
RAIN_V34 = ROOT / "Scenarios" / "rain_v34_era5_x2.txt"
PREP_V34 = ROOT / "BG_Flood_Project" / "BG_Flood" / "prep_v34.py"
CONTRACT = ROOT / "V48_BG_Flood_contract_20261002.json"
PREREG = ROOT / "V48_SAR_preregistration_20261002.json"
EVIDENCE = ROOT / "V48_RUN_EPOCH_EVIDENCE_20261002.json"
PROVENANCE = ROOT / "V48_RUN_EPOCH_PROVENANCE_20261002.json"
RUN_MANIFEST = ROOT / "V48_BG_Flood_RUN_MANIFEST_20261002.json"

GENERATOR_MESSAGE = Path(
    r"C:\Users\CuongHM\.gemini\antigravity\brain\bb357db6-a6f6-4f5e-bc1c-f195409d437d"
    r"\.system_generated\messages\dfbc1279-8a8a-4d50-ae6b-1dbb6bfa1879.json"
)
GENERATOR_TASK_LOG = Path(
    r"C:\Users\CuongHM\.gemini\antigravity\brain\bb357db6-a6f6-4f5e-bc1c-f195409d437d"
    r"\.system_generated\tasks\task-3863.log"
)
EDIT_TRANSCRIPT_AGGREGATE = Path(
    r"C:\Users\CuongHM\.gemini\antigravity\brain\2a14d3b9-0c61-4507-b922-ac4882d9ae0d"
    r"\.system_generated\logs\transcript_full.jsonl"
)
EDIT_TRANSCRIPT = Path(
    r"C:\Users\CuongHM\.gemini\antigravity\brain\2a14d3b9-0c61-4507-b922-ac4882d9ae0d"
    r"\.system_generated\logs\chunks\transcript_full\00000015.jsonl"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_ref(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path), "sha256": sha256(path)}


def read_series(path: Path) -> tuple[list[int], list[float]]:
    times: list[int] = []
    rates: list[float] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) != 2:
            raise RuntimeError(f"Unexpected forcing row in {path}: {raw!r}")
        times.append(int(float(parts[0])))
        rates.append(float(parts[1]))
    return times, rates


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    generator_text = GENERATOR_MESSAGE.read_text(encoding="utf-8")
    generator_log_text = GENERATOR_TASK_LOG.read_text(encoding="utf-8", errors="replace")
    edit_text = EDIT_TRANSCRIPT.read_text(encoding="utf-8", errors="replace")
    prep_text = PREP_V34.read_text(encoding="utf-8")

    require("timezone=Asia/Ho_Chi_Minh" in generator_text, "Generator provenance does not pin Asia/Ho_Chi_Minh")
    require("start_date=2021-11-26" in generator_text, "Generator provenance missing 2021-11-26 start date")
    require("end_date=2021-12-01" in generator_text, "Generator provenance missing 2021-12-01 end date")
    require("rain_v23_era5_spatial.txt" in generator_text, "Generator provenance does not name rain_v23 output")
    require("t_s = i * 3600" in generator_text, "Generator provenance does not define elapsed-hour time axis")
    require("File: D:\\VTP\\Scenarios\\rain_v23_era5_spatial.txt" in generator_log_text, "Task log does not confirm V23 output path")
    require("Tong mua TB: 199.0mm" in generator_log_text, "Task log signature differs from retained V23 generation")

    require("REMOVED: 432000" in edit_text, "September edit provenance does not record removal of the backward timestamp")
    require("t=432000.0 <= prev_t=514800.0" in edit_text, "September edit provenance does not record the exact monotonicity condition")
    require("Lines before: 147 Lines after: 146" in edit_text, "September edit provenance does not record a one-line removal")

    require("rain_v23_era5_spatial.txt" in prep_text, "prep_v34 no longer names V23 rainfall")
    require("rain_v34_era5_x2.txt" in prep_text, "prep_v34 no longer names V34 rainfall")
    require("float(parts[1]) * 2.0" in prep_text, "prep_v34 no longer applies the frozen x2 rainfall scaling")

    v23_t, v23_r = read_series(RAIN_V23)
    v34_t, v34_r = read_series(RAIN_V34)
    expected_t = list(range(0, 144 * 3600, 3600))
    require(v23_t == expected_t, "V23 time axis is not the expected 144 hourly samples from 0 to 514800 s")
    require(v34_t == v23_t, "V34 time axis differs from V23 time axis")
    max_scale_error = max(abs(v34 - 2.0 * v23) for v23, v34 in zip(v23_r, v34_r, strict=True))
    require(max_scale_error <= 5.1e-11, f"V34 rainfall is not V23 x2 within decimal-write tolerance: {max_scale_error}")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    contract_rain = contract["forcing"]["rainfall"]
    require(Path(contract_rain["path"]).resolve() == RAIN_V34.resolve(), "BG_Flood contract does not use frozen V34 rainfall")
    require(contract_rain["sha256"].lower() == sha256(RAIN_V34).lower(), "BG_Flood contract rainfall hash differs from V34")

    local_zone = ZoneInfo("Asia/Ho_Chi_Minh")
    local_epoch = datetime(2021, 11, 26, 0, 0, 0, tzinfo=local_zone)
    utc_epoch = local_epoch.astimezone(timezone.utc)
    local_epoch_iso = local_epoch.isoformat()
    utc_epoch_iso = utc_epoch.isoformat().replace("+00:00", "Z")

    provenance = {
        "status": "PASS_V48_RUN_EPOCH_PROVENANCE",
        "date": "2026-10-02",
        "formal_bg_flood_run_started": False,
        "conclusion": {
            "model_t0_local": local_epoch_iso,
            "model_t0_timezone": "Asia/Ho_Chi_Minh",
            "model_t0_utc": utc_epoch_iso,
            "timezone_verified": True,
            "basis": "The exact retained command that created rain_v23 requested Open-Meteo with timezone=Asia/Ho_Chi_Minh and encoded the returned hourly sequence as elapsed seconds starting at i=0. The only later retained edit removed one backward duplicate terminal timestamp and did not rebase the time axis. rain_v34 preserves the V23 time vector and applies a fixed x2 rate scaling.",
        },
        "generator_provenance": {
            "message": file_ref(GENERATOR_MESSAGE),
            "task_log": file_ref(GENERATOR_TASK_LOG),
            "verified_facts": {
                "api": "Open-Meteo archive API",
                "request_timezone": "Asia/Ho_Chi_Minh",
                "request_start_date": "2021-11-26",
                "request_end_date": "2021-12-01",
                "grid_points": 16,
                "time_encoding": "t_s = i * 3600",
                "output_path": str(RAIN_V23),
                "task_reported_mean_total_mm": 199.0,
            },
        },
        "post_generation_edit_provenance": {
            "transcript": file_ref(EDIT_TRANSCRIPT),
            "source_note": {
                "evidence_selection": "Pinned retained transcript chunk containing all three exact edit markers.",
                "aggregate_log_path": str(EDIT_TRANSCRIPT_AGGREGATE),
                "aggregate_log_hash_validation": False,
                "reason": "The aggregate transcript_full.jsonl is appendable. Hash-validating the retained chunk avoids false integrity failures caused by unrelated later appends while preserving hash-backed evidence for the historical edit.",
                "previous_aggregate_sha256": "10e23eb885e3a5158ff35b380976c5c581191d9ecfa0fab4322ecf44e706f8ad",
            },
            "verified_facts": {
                "edit_time_utc": "2026-09-04T02:52:36Z",
                "removed_row": "432000\\t0.0000000000",
                "reason": "432000 <= previous timestamp 514800",
                "lines_before": 147,
                "lines_after": 146,
                "time_rebase_performed": False,
            },
        },
        "retained_forcing": {
            "rain_v23": {
                **file_ref(RAIN_V23),
                "numeric_rows": len(v23_t),
                "first_elapsed_s": v23_t[0],
                "last_elapsed_s": v23_t[-1],
                "step_s": 3600,
                "strictly_monotonic": True,
            },
            "prep_v34": file_ref(PREP_V34),
            "rain_v34": {
                **file_ref(RAIN_V34),
                "numeric_rows": len(v34_t),
                "first_elapsed_s": v34_t[0],
                "last_elapsed_s": v34_t[-1],
                "step_s": 3600,
                "time_axis_identical_to_v23": True,
                "rate_scaling_from_v23": 2.0,
                "max_rate_scaling_abs_error_m_per_s": max_scale_error,
            },
        },
        "bg_flood_contract": file_ref(CONTRACT),
    }
    PROVENANCE.write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")

    run_manifest = {
        "status": "FROZEN_PRE_FORMAL_BG_FLOOD_RUN",
        "date": "2026-10-02",
        "formal_bg_flood_run_started": False,
        "run_epoch": {
            "local": local_epoch_iso,
            "timezone": "Asia/Ho_Chi_Minh",
            "utc": utc_epoch_iso,
            "timezone_verified": True,
            "provenance": {"path": str(PROVENANCE), "sha256": sha256(PROVENANCE)},
        },
        "bg_flood_contract": file_ref(CONTRACT),
        "rainfall": file_ref(RAIN_V34),
        "run_controls": {
            "endtime_s": contract["parameters"]["endtime_s"],
            "outputtimestep_s": contract["parameters"]["outputtimestep_s"],
            "formal_run_has_not_started": True,
        },
        "model_arms": {
            "V48_BASE_COPERNICUS": {
                "terrain_path": prereg["model_arms"]["V48_BASE_COPERNICUS"]["terrain_reference"],
                "terrain_sha256": prereg["model_arms"]["V48_BASE_COPERNICUS"]["terrain_sha256"],
            },
            "V48_CONDITIONED": {
                "terrain_path": prereg["model_arms"]["V48_CONDITIONED"]["formal_run_terrain_path"],
                "terrain_sha256": prereg["model_arms"]["V48_CONDITIONED"]["formal_run_terrain_sha256"],
            },
        },
    }
    RUN_MANIFEST.write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    evidence = {
        "status": "PASS_V48_RUN_EPOCH_FROZEN",
        "date": "2026-10-02",
        "formal_bg_flood_run_started": False,
        "candidate_model_t0_local": local_epoch_iso,
        "candidate_model_t0_timezone": "Asia/Ho_Chi_Minh",
        "candidate_model_t0_utc": utc_epoch_iso,
        "timezone_verified": True,
        "provenance_manifest": {"path": str(PROVENANCE), "sha256": sha256(PROVENANCE)},
        "frozen_run_manifest": {"path": str(RUN_MANIFEST), "sha256": sha256(RUN_MANIFEST)},
        "finding": "The exact rain_v23 generator requested Asia/Ho_Chi_Minh; the later monotonicity fix removed only a backward duplicate terminal row; rain_v34 preserves the time vector. Therefore model t=0 is frozen as 2021-11-26 00:00 ICT = 2021-11-25 17:00 UTC.",
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")

    prereg["hydrodynamic_contract"].update(
        {
            "run_epoch_local": local_epoch_iso,
            "run_epoch_timezone": "Asia/Ho_Chi_Minh",
            "run_epoch_utc": utc_epoch_iso,
            "run_epoch_timezone_verified": True,
            "run_epoch_provenance": {"path": str(PROVENANCE), "sha256": sha256(PROVENANCE)},
            "frozen_run_manifest": {"path": str(RUN_MANIFEST), "sha256": sha256(RUN_MANIFEST)},
        }
    )
    prereg.setdefault("source_provenance", {})["run_epoch_provenance"] = {
        "path": str(PROVENANCE),
        "sha256": sha256(PROVENANCE),
    }
    prereg["formal_evaluation_blockers"] = [
        item
        for item in prereg.get("formal_evaluation_blockers", [])
        if not item.startswith("Freeze BG_Flood run epoch")
    ]
    prereg["formal_evaluation_allowed"] = len(prereg["formal_evaluation_blockers"]) == 0
    prereg["status"] = "READY_PRE_FORMAL_EVALUATION_PENDING_VALIDATOR" if prereg["formal_evaluation_allowed"] else prereg["status"]
    PREREG.write_text(json.dumps(prereg, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS_V48_RUN_EPOCH_FROZEN",
                "run_epoch_local": local_epoch_iso,
                "run_epoch_utc": utc_epoch_iso,
                "provenance": {"path": str(PROVENANCE), "sha256": sha256(PROVENANCE)},
                "run_manifest": {"path": str(RUN_MANIFEST), "sha256": sha256(RUN_MANIFEST)},
                "evidence": {"path": str(EVIDENCE), "sha256": sha256(EVIDENCE)},
                "preregistration": {"path": str(PREREG), "sha256": sha256(PREREG)},
                "remaining_documented_blockers": prereg["formal_evaluation_blockers"],
                "formal_evaluation_allowed_pending_validator": prereg["formal_evaluation_allowed"],
                "formal_bg_flood_run_started": False,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
