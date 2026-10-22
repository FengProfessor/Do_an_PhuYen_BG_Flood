from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


ROOT = Path(r"D:\VTP")
V48 = ROOT / "V48_research_20261002"
BASE_DIR = V48 / "candidate_baseline_strict_1_2"
HYDRO = V48 / "hydro_evidence_raw"
OUT = V48 / "source_holdout"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(BASE_DIR / "V46_obstruction_candidates.csv")
    osm_selected = df[df.distance_to_osm_m <= 30.0].copy()
    hydro_selected = df[df.distance_to_hydrorivers_m <= 60.0].copy()
    osm_confirmed_by_hydro = osm_selected.distance_to_hydrorivers_m <= 60.0
    hydro_confirmed_by_osm = hydro_selected.distance_to_osm_m <= 30.0

    candidate_holdout = {
        "status": "PASS",
        "method": "Apply the frozen terrain rules and one hydrography source for selection; evaluate proximity to the other source only after the selected set is fixed.",
        "osm_selected_hydrorivers_held_out": {
            "selected_cells": int(len(osm_selected)),
            "heldout_hydrorivers_confirmed_cells": int(osm_confirmed_by_hydro.sum()),
            "heldout_hydrorivers_confirmed_pct": float(100.0 * osm_confirmed_by_hydro.mean()),
        },
        "hydrorivers_selected_osm_held_out": {
            "selected_cells": int(len(hydro_selected)),
            "heldout_osm_confirmed_cells": int(hydro_confirmed_by_osm.sum()),
            "heldout_osm_confirmed_pct": float(100.0 * hydro_confirmed_by_osm.mean()),
        },
        "note": "This is a candidate-stage source holdout. The current topology algorithm still uses historical OSM geometry to construct cut profiles, so OSM is not held out from the topology stage.",
    }

    # True JRC holdout for topology: preserve D8/HAND/upstream-area, replace JRC
    # occurrence with zero so it cannot make any component pass the supplemental OR gate.
    hydro_holdout = OUT / "hydro_jrc_heldout"
    hydro_holdout.mkdir(parents=True, exist_ok=True)
    names = [
        "V46_V41_D8.tif",
        "V46_V41_upstream_area_km2.tif",
        "V46_V41_HAND_drain_1km2.tif",
        "V46_V41_HAND_drain_10km2.tif",
        "V46_V41_filled_for_routing_only.tif",
        "V46_V41_fill_depth_m.tif",
    ]
    for name in names:
        shutil.copy2(HYDRO / name, hydro_holdout / name)
    src_jrc = HYDRO / "V46_JRC_GSW1_3_occurrence_1984_2020.tif"
    dst_jrc = hydro_holdout / src_jrc.name
    with rasterio.open(src_jrc) as src:
        profile = src.profile.copy()
        arr = np.zeros(src.shape, dtype=np.uint8)
    profile.update(dtype="uint8", nodata=255, count=1, compress="deflate")
    with rasterio.open(dst_jrc, "w", **profile) as dst:
        dst.write(arr, 1)
        dst.update_tags(JRC_HELD_OUT="true", PURPOSE="V48 topology source-holdout; zero occurrence cannot satisfy JRC>=25 gate")

    topo_out = OUT / "topology_jrc_heldout"
    cmd = [
        sys.executable,
        str(ROOT / "v47_topology_paths.py"),
        "--dem", str(ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m.tif"),
        "--core", str(V48 / "topology_raw815/V48_baseline815_core.tif"),
        "--core-manifest", str(V48 / "topology_raw815/V48_baseline815_core_manifest.json"),
        "--strict-csv", str(BASE_DIR / "V46_obstruction_candidates.csv"),
        "--osm-dir", str(ROOT / "V46_inputs/osm_historical_20211125"),
        "--hydro-dir", str(hydro_holdout),
        "--out-dir", str(topo_out),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)

    base = pd.read_csv(V48 / "topology_raw815/result/V46_topology_components.csv").set_index("component_id")
    held = pd.read_csv(topo_out / "V46_topology_components.csv").set_index("component_id")
    transitions = pd.DataFrame({"component_id": base.index.astype(int), "decision_with_jrc": base.decision.values, "decision_jrc_heldout": held.loc[base.index, "decision"].values})
    transitions["same_decision"] = transitions.decision_with_jrc == transitions.decision_jrc_heldout
    transitions_path = OUT / "V48_jrc_holdout_transitions.csv"
    transitions.to_csv(transitions_path, index=False)

    summary = {
        "status": "PASS",
        "sentinel1_2021_used": False,
        "candidate_source_holdout": candidate_holdout,
        "jrc_topology_holdout": {
            "method": "JRC occurrence replaced by zero before topology; upstream-area/D8/HAND remain available.",
            "baseline_decision_counts": base.decision.value_counts().to_dict(),
            "heldout_decision_counts": held.decision.value_counts().to_dict(),
            "same_decision_components": int(transitions.same_decision.sum()),
            "changed_decision_components": int((~transitions.same_decision).sum()),
            "strict_retained": int(((transitions.decision_with_jrc == "AUTO_APPROVE_STRICT") & (transitions.decision_jrc_heldout == "AUTO_APPROVE_STRICT")).sum()),
            "bounded_retained": int(((transitions.decision_with_jrc == "REVIEW_APPROVE_BOUNDED") & (transitions.decision_jrc_heldout == "REVIEW_APPROVE_BOUNDED")).sum()),
            "transitions_csv": str(transitions_path),
        },
        "provenance": {
            "base_candidate_csv_sha256": sha256(BASE_DIR / "V46_obstruction_candidates.csv"),
            "source_jrc_sha256": sha256(src_jrc),
            "heldout_jrc_sha256": sha256(dst_jrc),
            "topology_script_sha256": sha256(ROOT / "v47_topology_paths.py"),
        },
    }
    out_path = OUT / "V48_source_holdout_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
