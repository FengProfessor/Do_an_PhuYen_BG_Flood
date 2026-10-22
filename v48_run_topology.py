from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(r"D:\VTP")


def main() -> None:
    cmd = [
        sys.executable,
        str(ROOT / "v47_topology_paths.py"),
        "--dem", str(ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m.tif"),
        "--core", str(ROOT / "V48_research_20261002/topology_raw815/V48_baseline815_core.tif"),
        "--core-manifest", str(ROOT / "V48_research_20261002/topology_raw815/V48_baseline815_core_manifest.json"),
        "--strict-csv", str(ROOT / "V48_research_20261002/candidate_baseline_strict_1_2/V46_obstruction_candidates.csv"),
        "--osm-dir", str(ROOT / "V46_inputs/osm_historical_20211125"),
        "--hydro-dir", str(ROOT / "V48_research_20261002/hydro_evidence_raw"),
        "--out-dir", str(ROOT / "V48_research_20261002/topology_raw815/result"),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
