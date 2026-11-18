"""Verify the issued release before starting an explicitly selected V48 arm."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as source:
        for data in iter(lambda:source.read(4*1024*1024),b""):
            h.update(data)
    return h.hexdigest()


def verify_ref(item):
    path=Path(item["path"])
    if not path.is_file() or digest(path)!=item["sha256"]:
        raise RuntimeError(f"Release hash mismatch: {path}")


def check():
    pair=json.loads((ROOT/"V48_FORMAL_RUN_PAIR_R1.json").read_text(encoding="utf-8"))
    for key in ("runtime_manifest","contract","frozen_run_manifest","preregistration","preregistration_validation"):
        verify_ref(pair[key])
    runtime=json.loads(Path(pair["runtime_manifest"]["path"]).read_text(encoding="utf-8"))
    if Path(sys.executable).resolve()!=Path(runtime["interpreter"]["path"]):
        raise RuntimeError("Use the frozen interpreter from the runtime manifest")
    verify_ref(runtime["interpreter"])
    for name,expected in runtime["packages"].items():
        if importlib.metadata.version(name)!=expected:
            raise RuntimeError(f"Dependency drift: {name}")
    for group in ("all_python_files","release_tools","configs","test_scripts"):
        for item in runtime[group].values():
            verify_ref(item)
    for key in ("formal_input_verification","cpu_solver_smoke","regressions"):
        verify_ref(runtime[key])
    for item in pair["gate"].values():
        verify_ref(item)
    prereg_result=json.loads(Path(pair["preregistration_validation"]["path"]).read_text(encoding="utf-8"))
    if prereg_result["status"]!="READY_FOR_FORMAL_EVALUATION":
        raise RuntimeError("Preregistration is not ready")
    contract=json.loads(Path(pair["contract"]["path"]).read_text(encoding="utf-8"))
    for group in ("forcing","engine_semantics"):
        for item in contract[group].values():
            verify_ref(item)
    for arm in ("base","conditioned"):
        verify_ref(pair[arm]["config"])
        verify_ref(pair[arm]["terrain_tif"])
        terrain=pair[arm].get("terrain_asc") or pair[arm]["terrain_ascii_materialization"]["asc"]
        verify_ref(terrain)
    # Recheck every hash pin in preregistration, including observation and masks.
    def walk(value):
        if isinstance(value,dict):
            if "path" in value and "sha256" in value:
                verify_ref(value)
            for child in value.values():
                walk(child)
        elif isinstance(value,list):
            for child in value:
                walk(child)
    walk(json.loads(Path(pair["preregistration"]["path"]).read_text(encoding="utf-8")))
    print("PASS: runtime, dependencies, inputs, configs, tests and preregistration hashes match.",flush=True)
    return pair


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm",choices=("BASE","CONDITIONED"))
    parser.add_argument("--check",action="store_true",help="Check hashes only; no GPU allocation or simulation")
    args=parser.parse_args()
    pair=check()
    if args.check or args.arm is None:
        return
    arm=pair["base" if args.arm=="BASE" else "conditioned"]
    output=Path(arm["planned_output"])
    log_path=ROOT/f"results/V48_FORMAL_{args.arm}_R1.log"
    if output.exists() or log_path.exists():
        raise FileExistsError("Refusing to overwrite an existing formal run; issue a new run ID")
    import cupy
    if cupy.cuda.runtime.getDeviceCount()<1:
        raise RuntimeError("A working CUDA GPU is required for the formal run")
    cupy.cuda.Device(0).compute_capability  # Match the engine's backend selection check.
    # The user starts this command explicitly; release preparation only uses --check.
    with log_path.open("x",encoding="utf-8") as log:
        done=subprocess.run(arm["argv"],cwd=arm["cwd"],stdout=log,stderr=subprocess.STDOUT)
    if done.returncode:
        raise RuntimeError(f"Formal run failed (exit {done.returncode}); see {log_path}")
    print(f"Completed {args.arm}: {output}")


if __name__=="__main__":
    main()
