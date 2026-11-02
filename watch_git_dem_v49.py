"""Watcher script to poll GitHub for newly returned carved/breached DEM files

and automatically trigger the V49 hydraulic simulation pipeline.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RBP = ROOT / "River_Bathymetry_Project"

def run_cmd(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out after 60s"

def check_for_remote_dem() -> dict:
    # 1. Fetch remote origin
    code, stdout, stderr = run_cmd(["git", "fetch", "origin", "main"])
    if code != 0:
        return {"status": "FETCH_FAILED", "error": stderr}

    # 2. Check if remote has commits that local does not have
    code, rev_count, _ = run_cmd(["git", "rev-list", "HEAD..origin/main", "--count"])
    num_new_commits = int(rev_count) if code == 0 and rev_count.isdigit() else 0

    if num_new_commits == 0:
        return {
            "status": "UP_TO_DATE",
            "message": "Origin/main has no new commits. Waiting for new DEM commit from Git...",
            "num_new_commits": 0
        }

    # 3. There are new commits on remote -> Pull
    _, remote_sha, _ = run_cmd(["git", "rev-parse", "origin/main"])
    _, local_sha, _ = run_cmd(["git", "rev-parse", "HEAD"])
    print(f"[WATCHER] {num_new_commits} new remote commit(s) detected ({remote_sha[:8]}). Pulling...")
    code, pull_out, pull_err = run_cmd(["git", "pull", "origin", "main"])
    if code != 0:
        return {"status": "PULL_FAILED", "error": pull_err}

    # 4. Check what files were pulled
    code, changed_files_raw, _ = run_cmd(["git", "diff", "--name-only", local_sha, remote_sha])
    changed_files = [line.strip() for line in changed_files_raw.splitlines() if line.strip()]

    # 5. Check if any carved / breached DEM is among changed files
    dem_exts = [".tif", ".tiff", ".asc", ".dem"]
    dem_keywords = ["dem", "bathy", "carv", "breach", "bed", "hydraulic"]
    dem_matches = [
        f for f in changed_files
        if any(f.lower().endswith(ext) for ext in dem_exts)
        and any(k in f.lower() for k in dem_keywords)
    ]

    result = {
        "status": "NEW_COMMITS_PULLED",
        "pulled_sha": remote_sha,
        "changed_files": changed_files,
        "dem_matches": dem_matches
    }

    if dem_matches:
        result["status"] = "CARVED_DEM_DETECTED"
        print(f"[WATCHER] Carved DEM file detected: {dem_matches}!")
        # Trigger V49 launch
        launch_status = trigger_v49_pipeline(dem_matches)
        result["launch_status"] = launch_status

    return result

def find_dem_candidates() -> list[Path]:
    candidates = []
    search_dirs = [ROOT / "05-Du-lieu-GIS", RBP]
    for d in search_dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix.lower() in [".tif", ".asc"]:
                name = p.name.lower()
                if any(k in name for k in ["carv", "breach", "full_river_bathy", "hydraulic_bed"]):
                    candidates.append(p.relative_to(ROOT))
    return candidates

def trigger_v49_pipeline(dem_files: list[str]) -> dict:
    """Preflight and prepare V49 pipeline with new DEM."""
    v49_script = RBP / "v49_run_hydraulic_validation.py"
    if not v49_script.exists():
        return {"status": "SCRIPT_MISSING", "path": str(v49_script)}

    # Run preflight
    print("[WATCHER] Running V49 preflight...")
    code, out, err = run_cmd([sys.executable, str(v49_script), "--arm", "CENTRAL", "preflight"], cwd=RBP)
    preflight_ok = (code == 0)

    # Run prepare
    print("[WATCHER] Running V49 prepare...")
    p_code, p_out, p_err = run_cmd([sys.executable, str(v49_script), "--arm", "CENTRAL", "prepare"], cwd=RBP)

    return {
        "preflight_exit": code,
        "preflight_ok": preflight_ok,
        "preflight_output": out[:500] if out else err[:500],
        "prepare_exit": p_code,
        "prepare_output": p_out[:500] if p_out else p_err[:500]
    }

if __name__ == "__main__":
    res = check_for_remote_dem()
    print(json.dumps(res, indent=2))
