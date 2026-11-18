"""Issue a new runtime release without changing the 2026-10-02 artifacts."""
from contextlib import redirect_stdout
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
VTP = ROOT.parents[1]
LEGACY = VTP / "BG_Flood_Project/BG_Flood"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for part in iter(lambda: source.read(4*1024*1024), b""):
            h.update(part)
    return h.hexdigest()


def ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(name, data):
    path = ROOT / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return path


def entries(text):
    result = {}
    for raw in text.splitlines():
        line = raw.split("#",1)[0].strip()
        if "=" in line:
            k,v = line.split("=",1)
            result.setdefault(k.strip().lower(),[]).append(v.strip().rstrip(";").strip())
    return result


def prepare_configs():
    for arm in ("BASE","CONDITIONED"):
        original = LEGACY / f"BG_param_PhuYen_30m_V48_FORMAL_{arm}.txt"
        lines = []
        for raw in original.read_text(encoding="utf-8").splitlines():
            if raw.startswith("# Frozen 2026-10-02"):
                raw = "# Runtime fix release 2026-10-04 R1; preserve the original 2026-10-02 inputs."
            if raw.strip().startswith("outfile ="):
                raw = f"outfile = results/V48_FORMAL_{arm}_R1.nc;"
            lines.append(raw)
            if raw.strip().startswith("rainfile ="):
                lines.append("rainunits = m/s;")
        text = "\n".join(lines)+"\n"
        path = ROOT / f"BG_param_PhuYen_30m_V48_FORMAL_{arm}_R1.txt"
        previous, current = entries(original.read_text(encoding="utf-8")), entries(text)
        changed = {k for k in previous.keys() | current.keys() if previous.get(k) != current.get(k)}
        assert changed == {"rainunits","outfile"}, changed
        path.write_text(text, encoding="utf-8")
    for name in ("xa_lu_BaHa_Nov2021_V40_sync.txt", "xa_lu_BanThach_V43.txt",
                 "xa_lu_KyLo_V40_sync.txt", "xa_lu_TuyAn_V40_sync.txt"):
        shutil.copyfile(LEGACY/name, ROOT/name)
        assert sha(LEGACY/name) == sha(ROOT/name)
    base = entries((ROOT/"BG_param_PhuYen_30m_V48_FORMAL_BASE_R1.txt").read_text(encoding="utf-8"))
    cond = entries((ROOT/"BG_param_PhuYen_30m_V48_FORMAL_CONDITIONED_R1.txt").read_text(encoding="utf-8"))
    assert {k for k in base.keys() | cond.keys() if base.get(k)!=cond.get(k)} == {"bathy","outfile"}


def validator(filename, contract=None, prereg=None, out=None):
    path = VTP/filename
    spec = importlib.util.spec_from_file_location("v48_release_"+path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if contract:
        module.CONTRACT = contract
    if prereg:
        module.PREREG = prereg
    module.OUT = out
    with redirect_stdout(io.StringIO()):
        module.main()
    return read(out)


def main():
    prepare_configs()
    if "--configs-only" in sys.argv:
        print("Prepared BASE/CONDITIONED R1 configs; only rainunits/outfile changed.")
        return
    evidence_path = ROOT/"results/formal_input_verification.json"
    evidence = read(evidence_path)
    assert evidence["status"] == "PASS_V48_RUNTIME_INPUT_FIXES"
    assert read(ROOT/"results/cpu_solver_smoke.json")["status"] == "PASS"
    source_contract = VTP/"V48_BG_Flood_contract_20261002.json"
    source_prereg = VTP/"V48_SAR_preregistration_20261002.json"
    source_run = VTP/"V48_BG_Flood_RUN_MANIFEST_20261002.json"
    source_pair = VTP/"V48_FORMAL_RUN_PAIR_PREP_20261002.json"
    now = datetime.now(timezone(timedelta(hours=7))).isoformat()
    code = {str(path.relative_to(ROOT/"python")): ref(path)
            for path in sorted((ROOT/"python").rglob("*.py"))}
    changes = []
    for relative, item in code.items():
        prior = LEGACY/"python"/relative
        if sha(prior) != item["sha256"]:
            changes.append({"module": relative, "previous": ref(prior), "fixed": item})
    runtime = {
        "status":"FROZEN_V48_RUNTIME_FIX_R1", "created_at":now,
        "runtime_id":"20261004_runtime_fix_r1", "cwd":str(ROOT),
        "base_engine":"Original V48 Python runtime with only rainfall-unit and grid-contract fixes",
        "interpreter":ref(sys.executable), "python_version":sys.version,
        "packages":{name:importlib.metadata.version(name) for name in
                    ("numpy","netCDF4","rasterio","matplotlib","pyproj","cupy")},
        "all_python_files":code, "changed_modules":changes,
        "test_scripts":{str(path.relative_to(ROOT)):ref(path) for path in sorted((ROOT/"tests").glob("*.py"))},
        "regressions":ref(ROOT/"results/regressions_after_fix.txt"),
        "formal_input_verification":ref(evidence_path),
        "cpu_solver_smoke":ref(ROOT/"results/cpu_solver_smoke.json"),
        "previous_preregistration":ref(source_prereg),
        "previous_pair":ref(source_pair),
        "test_backend":"CPU NumPy; no GPU simulation run by this release preparation",
        "formal_execution_backend":"GPU required and checked by launch_formal.py",
        "release_tools":{name:ref(ROOT/name) for name in ("launch_formal.py","prepare_release.py")},
        "configs":{arm:ref(ROOT/f"BG_param_PhuYen_30m_V48_FORMAL_{arm}_R1.txt") for arm in ("BASE","CONDITIONED")},
    }
    runtime_path = write("V48_RUNTIME_MANIFEST_R1.json",runtime)
    contract = read(source_contract)
    contract.update(date="2026-10-04", config=ref(ROOT/"BG_param_PhuYen_30m_V48_FORMAL_CONDITIONED_R1.txt"))
    contract["runtime_release"] = ref(runtime_path)
    contract["engine_semantics"] = code
    for name, item in contract["forcing"].items():
        previous = Path(item["path"])
        if previous.parent == LEGACY:
            contract["forcing"][name] = ref(ROOT/previous.name)
    contract["provenance"]["previous_contract"] = ref(source_contract)
    contract["parameters"]["rainunits"] = "m/s"
    contract["release_gate"].update(
        formal_bg_flood_run_allowed=True,
        reason="Runtime R1 fixes verified; launch requires matching release hashes and READY_FOR_FORMAL_EVALUATION from the R1 preregistration validation. No formal run has been started.")
    contract["grid_semantics"] = {"raster_coordinates":"cell centers", "model_bounds":"outer edges",
                                  "output_ncols":2100, "output_nrows":2100,
                                  "terrain_samples_preserved_without_half_cell_interpolation":True}
    contract_path = write("V48_BG_Flood_contract_R1.json",contract)
    validation_path = ROOT/"V48_BG_Flood_validation_R1.json"
    validation = validator("v48_bg_flood_validate.py",contract=contract_path,out=validation_path)
    assert validation["status"] == "PASS_V48_BG_FLOOD_CONTRACT_VALIDATION"
    run = read(source_run)
    run.update(date="2026-10-04", bg_flood_contract=ref(contract_path))
    run["runtime_release"] = ref(runtime_path)
    run["previous_run_manifest"] = ref(source_run)
    run_path = write("V48_BG_Flood_RUN_MANIFEST_R1.json",run)
    prereg = read(source_prereg)
    prereg["date"] = "2026-10-04"
    prereg["runtime_revision"] = {"reason":"Fix rainfall SI normalization and DEM/grid/output coordinates before completed formal runs",
                                   "previous_preregistration":ref(source_prereg), "runtime_manifest":ref(runtime_path),
                                   "scientific_inputs_and_evaluation_rules_changed":False}
    prereg["hydrodynamic_contract"].update(ref(contract_path))
    prereg["hydrodynamic_contract"]["frozen_run_manifest"] = ref(run_path)
    prereg_path = write("V48_SAR_preregistration_R1.json",prereg)
    prereg_validation_path = ROOT/"V48_SAR_preregistration_validation_R1.json"
    prereg_validation = validator("v48_sar_preregistration_validate.py",prereg=prereg_path,out=prereg_validation_path)
    assert prereg_validation["status"] == "READY_FOR_FORMAL_EVALUATION"
    pair = read(source_pair)
    pair.update(date="2026-10-04", status="READY_TO_START_FORMAL_BG_FLOOD_PAIR_RUNTIME_R1",
                preregistration=ref(prereg_path),preregistration_validation=ref(prereg_validation_path),
                contract=ref(contract_path),frozen_run_manifest=ref(run_path),runtime_manifest=ref(runtime_path))
    pair.pop("gate",None)
    shared = entries((ROOT/"BG_param_PhuYen_30m_V48_FORMAL_BASE_R1.txt").read_text(encoding="utf-8"))
    for k in ("bathy","outfile"):
        shared.pop(k)
    pair["shared_config_normalized_sha256"] = hashlib.sha256(json.dumps(shared,sort_keys=True).encode()).hexdigest()
    pair["cwd"] = str(ROOT)
    pair["previous_pair"] = ref(source_pair)
    pair["gate"] = {"runtime_verification":ref(evidence_path), "contract_validation":ref(validation_path),
                    "preregistration_validation":ref(prereg_validation_path)}
    for name, arm in (("base","BASE"),("conditioned","CONDITIONED")):
        config = ROOT/f"BG_param_PhuYen_30m_V48_FORMAL_{arm}_R1.txt"
        pair[name]["config"] = ref(config)
        pair[name]["planned_output"] = str(ROOT/f"results/V48_FORMAL_{arm}_R1.nc")
        pair[name]["argv"] = [str(Path(sys.executable).resolve()),"-X","utf8","-u",str(ROOT/"python/run_bgflood.py"),str(config)]
        pair[name]["cwd"] = str(ROOT)
        pair[name]["command"] = f'& "{sys.executable}" -X utf8 "{ROOT / "launch_formal.py"}" --arm {arm}'
    write("V48_FORMAL_RUN_PAIR_R1.json",pair)
    print(json.dumps({"status":pair["status"],"changed_modules":[v["module"] for v in changes],
                      "contract":validation["status"],"preregistration":prereg_validation["status"]},indent=2))


if __name__ == "__main__":
    main()
