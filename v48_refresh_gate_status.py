from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(r"D:\VTP")
DIRECT = ROOT / "V48_closed_loop_direct_20261002" / "V48_closed_loop_direct_summary.json"
RELEASE = ROOT / "V48_CLOSED_LOOP_FROZEN_RELEASE_20261002.json"
CONTRACT = ROOT / "V48_BG_Flood_contract_20261002.json"
CONTRACT_VALIDATION = ROOT / "V48_BG_Flood_validation_20261002.json"
PREREG = ROOT / "V48_SAR_preregistration_20261002.json"
PREREG_VALIDATION = ROOT / "V48_SAR_preregistration_validation_20261002.json"
RUN_EPOCH = ROOT / "V48_RUN_EPOCH_EVIDENCE_20261002.json"
BLOCKERS = ROOT / "V48_SAR_PROVENANCE_BLOCKERS_20261002.md"
OUT = ROOT / "V48_REMEDIATION_GATE_STATUS_20261002.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    required = [DIRECT, RELEASE, CONTRACT, CONTRACT_VALIDATION, PREREG, PREREG_VALIDATION, RUN_EPOCH, BLOCKERS]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing V48 gate artifact(s): {missing}")

    direct = load(DIRECT)
    release = load(RELEASE)
    contract = load(CONTRACT)
    contract_validation = load(CONTRACT_VALIDATION)
    prereg_validation = load(PREREG_VALIDATION)
    run_epoch = load(RUN_EPOCH)

    blockers = prereg_validation.get("formal_evaluation_blockers", [])
    failures = prereg_validation.get("integrity_failures", [])
    ready = prereg_validation.get("status") == "READY_FOR_FORMAL_EVALUATION" and not blockers and not failures

    result = {
        "date": "2026-10-02",
        "overall_status": "READY_FOR_FORMAL_EVALUATION" if ready else "FORMAL_SAR_EVALUATION_BLOCKED",
        "formal_bg_flood_run": False,
        "formal_sar_evaluation_run": False,
        "gates": {
            "closed_loop_topology": {
                "status": "PASS_FROZEN_CLOSED_LOOP_RELEASE",
                "direct_summary": str(DIRECT),
                "direct_summary_sha256": sha256(DIRECT),
                "release_manifest": str(RELEASE),
                "release_manifest_sha256": sha256(RELEASE),
                "final_strict_components": direct["convergence"]["final_strict_components"],
                "iterations_with_new_cuts": direct["convergence"]["iterations_with_new_cuts"],
                "final_changed_cells_vs_base": direct["convergence"]["final_changed_cells_vs_base"],
                "final_max_cumulative_cut_m": direct["convergence"]["final_max_cumulative_cut_m"],
                "frozen_tif": release["frozen"]["tif"],
                "frozen_tif_sha256": release["frozen"]["tif_sha256"],
                "sentinel1_2021_used_for_conditioning": False,
            },
            "bg_flood_contract": {
                "status": contract_validation["status"],
                "contract": str(CONTRACT),
                "contract_sha256": sha256(CONTRACT),
                "validation": str(CONTRACT_VALIDATION),
                "validation_sha256": sha256(CONTRACT_VALIDATION),
                "terrain_tif_sha256": contract["terrain"]["tif"]["sha256"],
                "minmask": contract["terrain"]["minmask"],
                "zsinit_m": contract["initial_state"]["zsinit_m"],
                "bg_flood_run": False,
            },
            "run_epoch": {
                "status": run_epoch["status"],
                "evidence": str(RUN_EPOCH),
                "evidence_sha256": sha256(RUN_EPOCH),
                "timezone_verified": run_epoch["timezone_verified"],
                "run_epoch_utc": run_epoch["candidate_model_t0_utc"],
            },
            "sar_preregistration": {
                "status": prereg_validation["status"],
                "preregistration": str(PREREG),
                "preregistration_sha256": sha256(PREREG),
                "validation": str(PREREG_VALIDATION),
                "validation_sha256": sha256(PREREG_VALIDATION),
                "integrity_failures": failures,
                "formal_evaluation_blockers": blockers,
                "formal_evaluation_allowed": ready,
                "blocker_notes": str(BLOCKERS),
                "blocker_notes_sha256": sha256(BLOCKERS),
            },
        },
        "next_release_condition": "Do not start the formal BG_Flood -> Sentinel-1 one-shot evaluation until the SAR preregistration validator reports READY_FOR_FORMAL_EVALUATION with zero integrity failures and zero blockers.",
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
