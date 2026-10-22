from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(r"D:\VTP")
CONTRACT = ROOT / "V48_BG_Flood_contract_20261002.json"
OUT = ROOT / "V48_BG_Flood_validation_20261002.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    failures = []

    for section in ("config",):
        item = contract[section]
        path = Path(item["path"])
        if not path.is_file() or sha256(path).lower() != item["sha256"].lower():
            failures.append(f"hash mismatch: {path}")

    for section in ("asc", "tif", "prj"):
        item = contract["terrain"][section]
        path = Path(item["path"])
        if not path.is_file() or sha256(path).lower() != item["sha256"].lower():
            failures.append(f"hash mismatch: {path}")

    for group in ("forcing", "engine_semantics"):
        for item in contract[group].values():
            path = Path(item["path"])
            if not path.is_file() or sha256(path).lower() != item["sha256"].lower():
                failures.append(f"hash mismatch: {path}")

    for item in contract["provenance"].values():
        if not isinstance(item, dict) or "path" not in item:
            continue
        path = Path(item["path"])
        if not path.is_file() or sha256(path).lower() != item["sha256"].lower():
            failures.append(f"hash mismatch: {path}")

    asc_path = Path(contract["terrain"]["asc"]["path"])
    with asc_path.open("r", encoding="ascii") as f:
        header = {}
        for _ in range(6):
            key, value = f.readline().split()[:2]
            header[key.lower()] = float(value)
        values = np.loadtxt(f)
    nodata = header["nodata_value"]
    valid = values[values != nodata]
    minmask = float(contract["terrain"]["minmask"])
    valid_masked = int(np.count_nonzero(valid <= minmask))
    if valid_masked != 0:
        failures.append(f"minmask would mask {valid_masked} valid DEM cells")
    nodata_is_masked = bool(nodata <= minmask)
    if not nodata_is_masked:
        failures.append("NoData sentinel is not covered by minmask")

    cfg = Path(contract["config"]["path"]).read_text(encoding="utf-8")
    required_text = [
        "bathy = ../../05-Du-lieu-GIS/PhuYen_DEM_30m_V48_CONDITIONED_CLOSED_LOOP_FROZEN.asc;",
        "minmask = -4.0;",
        "zsinit = 1.0;",
        "zsoffset = 0.0;",
    ]
    for text in required_text:
        if text not in cfg:
            failures.append(f"missing config pin: {text}")

    result = {
        "status": "PASS_V48_BG_FLOOD_CONTRACT_VALIDATION" if not failures else "FAIL_V48_BG_FLOOD_CONTRACT_VALIDATION",
        "contract": str(CONTRACT),
        "contract_sha256": sha256(CONTRACT),
        "bg_flood_run": False,
        "sentinel1_2021_used": False,
        "checks": {
            "valid_dem_cells_masked_by_minmask": valid_masked,
            "nodata_sentinel": nodata,
            "nodata_is_masked": nodata_is_masked,
            "valid_min_m": float(valid.min()),
            "minmask": minmask,
            "zsinit_m": float(contract["initial_state"]["zsinit_m"]),
        },
        "failures": failures,
    }
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
