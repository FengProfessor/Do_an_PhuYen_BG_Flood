from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(r"D:\VTP")
PREREG = ROOT / "V48_SAR_preregistration_20261002.json"
CONTRACT = ROOT / "V48_BG_Flood_contract_20261002.json"
RELEASE = ROOT / "V48_CLOSED_LOOP_FROZEN_RELEASE_20261002.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    for path in (PREREG, CONTRACT, RELEASE):
        if not path.is_file():
            raise FileNotFoundError(path)

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    release = json.loads(RELEASE.read_text(encoding="utf-8"))
    if release.get("status") != "V48_CLOSED_LOOP_FROZEN_PRE_SAR_RELEASE":
        raise RuntimeError(f"Unexpected release status: {release.get('status')}")

    frozen = release["frozen"]
    terrain_path = Path(frozen["tif"])
    if not terrain_path.is_file() or sha256(terrain_path) != frozen["tif_sha256"]:
        raise RuntimeError("Formal conditioned terrain hash verification failed")

    conditioned = prereg["model_arms"]["V48_CONDITIONED"]
    conditioned["formal_run_terrain_path"] = str(terrain_path)
    conditioned["formal_run_terrain_sha256"] = frozen["tif_sha256"]
    conditioned["status"] = "FROZEN_CLOSED_LOOP_PRE_SAR"
    conditioned["closed_loop_release_manifest"] = {
        "path": str(RELEASE),
        "sha256": sha256(RELEASE),
    }

    prereg["hydrodynamic_contract"]["path"] = str(CONTRACT)
    prereg["hydrodynamic_contract"]["sha256"] = sha256(CONTRACT)

    blockers = prereg.get("formal_evaluation_blockers", [])
    prereg["formal_evaluation_blockers"] = [
        item for item in blockers
        if not item.startswith("Reissue and freeze the eventual closed-loop conditioned V48 terrain")
    ]
    prereg["formal_evaluation_allowed"] = False
    PREREG.write_text(json.dumps(prereg, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "preregistration": str(PREREG),
        "preregistration_sha256": sha256(PREREG),
        "formal_run_terrain_path": str(terrain_path),
        "formal_run_terrain_sha256": frozen["tif_sha256"],
        "contract_sha256": sha256(CONTRACT),
        "remaining_documented_blockers": prereg["formal_evaluation_blockers"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
