from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(r"D:\VTP")
PREREG = ROOT / "V48_SAR_preregistration_20261002.json"
OUT = ROOT / "V48_SAR_preregistration_validation_20261002.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_file(item: dict, failures: list[str]) -> None:
    path = Path(item["path"])
    if not path.is_file():
        failures.append(f"missing file: {path}")
        return
    expected = item.get("sha256")
    if expected and sha256(path).lower() != expected.lower():
        failures.append(f"hash mismatch: {path}")


def main() -> None:
    p = json.loads(PREREG.read_text(encoding="utf-8"))
    failures: list[str] = []

    check_file(p["local_observation"]["tif"], failures)
    check_file(p["local_observation"]["asc"], failures)
    if p["local_observation"].get("prj"):
        check_file(p["local_observation"]["prj"], failures)
    if p["local_observation"].get("release_manifest"):
        check_file(p["local_observation"]["release_manifest"], failures)
    if p["local_observation"].get("validation_manifest"):
        check_file(p["local_observation"]["validation_manifest"], failures)
    check_file(p["evaluation_design"]["permanent_water_mask"], failures)
    check_file(p["evaluation_design"]["hand_validity_mask"], failures)
    check_file(p["terrain_selection_provenance"]["closed_loop_summary"], failures)
    check_file(p["source_provenance"]["scene_research"], failures)
    check_file(p["source_provenance"]["historical_evaluator"], failures)
    if p["source_provenance"].get("sar_observation_release"):
        check_file(p["source_provenance"]["sar_observation_release"], failures)
    if p["source_provenance"].get("sar_observation_validation"):
        check_file(p["source_provenance"]["sar_observation_validation"], failures)

    observation_validation = p["local_observation"].get("validation_manifest")
    if observation_validation:
        validation_path = Path(observation_validation["path"])
        if validation_path.is_file():
            observation_validation_doc = json.loads(validation_path.read_text(encoding="utf-8"))
            if observation_validation_doc.get("status") != "PASS_V48_SAR_OBSERVATION_VALIDATION":
                failures.append("SAR observation validation manifest is not PASS")
            if observation_validation_doc.get("failures"):
                failures.append("SAR observation validation manifest contains failures")

    contract = p["hydrodynamic_contract"]
    contract_path = Path(contract["path"])
    if not contract_path.is_file() or sha256(contract_path).lower() != contract["sha256"].lower():
        failures.append(f"hash mismatch: {contract_path}")

    run_epoch_provenance = contract.get("run_epoch_provenance")
    frozen_run_manifest = contract.get("frozen_run_manifest")
    if run_epoch_provenance:
        check_file(run_epoch_provenance, failures)
    if frozen_run_manifest:
        check_file(frozen_run_manifest, failures)

    if run_epoch_provenance and Path(run_epoch_provenance["path"]).is_file():
        run_prov_doc = json.loads(Path(run_epoch_provenance["path"]).read_text(encoding="utf-8"))
        if run_prov_doc.get("status") != "PASS_V48_RUN_EPOCH_PROVENANCE":
            failures.append("run epoch provenance manifest is not PASS")
        conclusion = run_prov_doc.get("conclusion", {})
        if conclusion.get("timezone_verified") is not True:
            failures.append("run epoch provenance does not verify timezone")
        if conclusion.get("model_t0_utc") != contract.get("run_epoch_utc"):
            failures.append("run epoch UTC differs between provenance and preregistration")
        if conclusion.get("model_t0_local") != contract.get("run_epoch_local"):
            failures.append("run epoch local time differs between provenance and preregistration")
        if conclusion.get("model_t0_timezone") != contract.get("run_epoch_timezone"):
            failures.append("run epoch timezone differs between provenance and preregistration")
        for ref in (
            run_prov_doc.get("generator_provenance", {}).get("message"),
            run_prov_doc.get("generator_provenance", {}).get("task_log"),
            run_prov_doc.get("post_generation_edit_provenance", {}).get("transcript"),
            run_prov_doc.get("retained_forcing", {}).get("rain_v23"),
            run_prov_doc.get("retained_forcing", {}).get("prep_v34"),
            run_prov_doc.get("retained_forcing", {}).get("rain_v34"),
        ):
            if ref:
                check_file(ref, failures)

    if frozen_run_manifest and Path(frozen_run_manifest["path"]).is_file():
        run_manifest_doc = json.loads(Path(frozen_run_manifest["path"]).read_text(encoding="utf-8"))
        if run_manifest_doc.get("status") != "FROZEN_PRE_FORMAL_BG_FLOOD_RUN":
            failures.append("BG_Flood run manifest is not frozen pre-formal-run")
        if run_manifest_doc.get("formal_bg_flood_run_started") is not False:
            failures.append("BG_Flood run manifest must remain pre-run at preregistration validation")
        manifest_epoch = run_manifest_doc.get("run_epoch", {})
        if manifest_epoch.get("utc") != contract.get("run_epoch_utc"):
            failures.append("run epoch UTC differs between run manifest and preregistration")
        if manifest_epoch.get("local") != contract.get("run_epoch_local"):
            failures.append("run epoch local time differs between run manifest and preregistration")
        if manifest_epoch.get("timezone") != contract.get("run_epoch_timezone"):
            failures.append("run epoch timezone differs between run manifest and preregistration")
        if manifest_epoch.get("timezone_verified") is not True:
            failures.append("run manifest does not record verified run epoch timezone")
        if run_manifest_doc.get("bg_flood_contract", {}).get("sha256", "").lower() != contract.get("sha256", "").lower():
            failures.append("run manifest BG_Flood contract hash differs from preregistration")

    base_path = Path(p["model_arms"]["V48_BASE_COPERNICUS"]["terrain_reference"])
    if not base_path.is_file() or sha256(base_path).lower() != p["model_arms"]["V48_BASE_COPERNICUS"]["terrain_sha256"].lower():
        failures.append(f"hash mismatch: {base_path}")

    blocked_reasons: list[str] = []
    candidate = p["candidate_observation_product"]["preferred_candidate"]
    if not candidate["product_to_local_observation_lineage_verified"]:
        blocked_reasons.append("product_to_local_observation_lineage_unverified")
    if not p["local_observation"]["acquisition_utc_verified_for_this_local_raster"]:
        blocked_reasons.append("local_observation_acquisition_utc_unverified")
    if not p["local_observation"]["class_semantics_verified_from_product_lineage"]:
        blocked_reasons.append("local_observation_class_semantics_unverified")
    if not p["hydrodynamic_contract"]["run_epoch_timezone_verified"] or not p["hydrodynamic_contract"]["run_epoch_utc"]:
        blocked_reasons.append("bg_flood_run_epoch_unfrozen")
    conditioned = p["model_arms"]["V48_CONDITIONED"]
    if not conditioned["formal_run_terrain_path"] or not conditioned["formal_run_terrain_sha256"]:
        blocked_reasons.append("final_closed_loop_conditioned_terrain_unfrozen")
    else:
        conditioned_path = Path(conditioned["formal_run_terrain_path"])
        if not conditioned_path.is_file():
            failures.append(f"missing file: {conditioned_path}")
        elif sha256(conditioned_path).lower() != conditioned["formal_run_terrain_sha256"].lower():
            failures.append(f"hash mismatch: {conditioned_path}")
        release = conditioned.get("closed_loop_release_manifest")
        if release:
            check_file(release, failures)

    if p["evaluation_design"]["wet_depth_threshold_m"] != 0.3:
        failures.append("wet-depth threshold drifted from preregistered 0.30 m")
    if p["frame_selection_rule"]["maximum_allowed_offset_s"] != 5400:
        failures.append("frame-offset limit drifted from 5400 s")
    if p["formal_evaluation_allowed"] and (blocked_reasons or failures):
        failures.append("formal_evaluation_allowed must remain false while blockers exist")

    result = {
        "status": "BLOCKED_AS_PREREGISTERED" if blocked_reasons and not failures else ("FAIL_PREREGISTRATION_INTEGRITY" if failures else "READY_FOR_FORMAL_EVALUATION"),
        "preregistration": str(PREREG),
        "preregistration_sha256": sha256(PREREG),
        "integrity_failures": failures,
        "formal_evaluation_blockers": blocked_reasons,
        "formal_evaluation_allowed": not failures and not blocked_reasons,
        "sentinel_evaluation_run": False,
        "bg_flood_run_started": False
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if failures:
        raise SystemExit(1)
    if blocked_reasons:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
