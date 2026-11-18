"""Check release integrity, deliberate code drift rejection, and legacy pins."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VTP = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    command = [sys.executable, "-X", "utf8", "-B", str(ROOT/"launch_formal.py"), "--check"]
    before = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert before.returncode == 0, before.stdout + before.stderr
    target = ROOT/"python/bg_flood/read_forcing.py"
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\n# Intentional transient release-guard test.\n")
        rejected = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
        assert rejected.returncode != 0, rejected.stdout + rejected.stderr
        assert "Release hash mismatch" in rejected.stderr and str(target) in rejected.stderr
    finally:
        target.write_bytes(original)
    after = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert after.returncode == 0, after.stdout + after.stderr
    assert target.read_bytes() == original
    checked = set()

    def walk(value):
        if isinstance(value, dict):
            if "path" in value and "sha256" in value:
                assert sha(value["path"]) == value["sha256"], value["path"]
                checked.add(value["path"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for name in ("V48_BG_Flood_contract_20261002.json", "V48_BG_Flood_RUN_MANIFEST_20261002.json",
                 "V48_SAR_preregistration_20261002.json", "V48_FORMAL_RUN_PAIR_PREP_20261002.json"):
        walk(json.loads((VTP/name).read_text(encoding="utf-8")))
    runtime = json.loads((ROOT/"V48_RUNTIME_MANIFEST_R1.json").read_text(encoding="utf-8"))
    walk(runtime["previous_preregistration"])
    walk(runtime["previous_pair"])
    changed = {item["module"]: item for item in runtime["changed_modules"]}
    for relative, item in runtime["all_python_files"].items():
        legacy = VTP/"BG_Flood_Project/BG_Flood/python"/relative
        expected = changed[relative]["previous"]["sha256"] if relative in changed else item["sha256"]
        assert sha(legacy) == expected, legacy
        checked.add(str(legacy))
    patch = []
    for item in runtime["changed_modules"]:
        previous = Path(item["previous"]["path"])
        fixed = Path(item["fixed"]["path"])
        relative = item["module"].replace("\\", "/")
        patch.extend(difflib.unified_diff(previous.read_text(encoding="utf-8").splitlines(True),
                                          fixed.read_text(encoding="utf-8").splitlines(True),
                                          fromfile="legacy/python/"+relative,
                                          tofile="runtime_r1/python/"+relative))
    (ROOT/"runtime_fixes.patch").write_text("".join(patch), encoding="utf-8")
    result = {
        "status": "PASS_RELEASE_GUARD_AND_LEGACY_PINS",
        "check_before_drift": "PASS", "intentional_read_forcing_drift": "REJECTED",
        "source_restored_byte_for_byte": True, "check_after_restore": "PASS",
        "legacy_pinned_files_verified": len(checked), "legacy_python_files_verified": len(runtime["all_python_files"]),
        "formal_simulation_started": False,
    }
    (ROOT/"results/release_guard_verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
