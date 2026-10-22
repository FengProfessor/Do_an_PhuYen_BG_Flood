from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(r"D:\VTP")
DESIGN = ROOT / "V47_candidate_sensitivity_design_20261001.json"
OUT_ROOT = ROOT / "V47_candidate_sensitivity_20261001"
SCRIPT = ROOT / "v46_conditioning_dryrun.py"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    fixed = design["fixed_inputs"]
    results = []
    for i, run in enumerate(design["runs"], start=1):
        out = OUT_ROOT / run["run_id"]
        summary = out / "V46_dryrun_summary.json"
        print(f"[{i}/{len(design['runs'])}] {run['run_id']}", flush=True)
        cmd = [
            sys.executable,
            str(SCRIPT),
            "--dem", fixed["dem"],
            "--osm", fixed["osm"],
            "--osm-max-timestamp", fixed["osm_max_timestamp"],
            "--hydrorivers", fixed["hydrorivers"],
            "--out-dir", str(out),
            "--corridor-cells", str(run["corridor_cells"]),
            "--hydro-corridor-cells", str(run["hydro_corridor_cells"]),
            "--relief-threshold-m", str(run["relief_threshold_m"]),
            "--relief-window", str(run["relief_window"]),
            "--max-slope-deg", str(run["max_slope_deg"]),
            "--max-elevation-m", str(run["max_elevation_m"]),
            "--compare-v44", fixed["compare_v44"],
            "--compare-v45", fixed["compare_v45"],
        ]
        subprocess.run(cmd, cwd=ROOT, check=True)
        s = json.loads(summary.read_text(encoding="utf-8"))
        results.append(
            {
                "run_id": run["run_id"],
                "out_dir": str(out),
                "summary_sha256": sha256(summary),
                "candidate_cells": s.get("candidate_cells"),
                "tier_a_cells": s.get("tier_a_cells"),
                "parameters": run,
            }
        )
        print(
            f"  candidate={s.get('candidate_cells')} tierA={s.get('tier_a_cells')}",
            flush=True,
        )

    run_manifest = {
        "status": "PASS",
        "design": str(DESIGN),
        "design_sha256": sha256(DESIGN),
        "algorithm": str(SCRIPT),
        "algorithm_sha256": sha256(SCRIPT),
        "sentinel1_2021_used_for_selection": False,
        "runs": results,
    }
    path = OUT_ROOT / "V47_candidate_sensitivity_run_manifest.json"
    path.write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "manifest": str(path)}, indent=2))


if __name__ == "__main__":
    main()
