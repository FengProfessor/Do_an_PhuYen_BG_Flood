from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(r"D:\VTP")
GIS = ROOT / "05-Du-lieu-GIS"
RESEARCH = ROOT / "V48_research_20261002"
AUDIT = ROOT / "V48_audit_20261002"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    selection = load(RESEARCH / "final_selection/V48_final_selection_summary.json")
    holdout = load(RESEARCH / "source_holdout/V48_source_holdout_summary.json")
    caps = load(RESEARCH / "topology_cap_sensitivity/V48_topology_cap_sensitivity_summary.json")
    sensitivity = load(RESEARCH / "candidate_sensitivity/V48_candidate_sensitivity_summary.json")
    conditioning = load(AUDIT / "V48_conditioning_summary.json")
    verification = load(AUDIT / "V48_final_verification.json")

    frozen = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.tif"
    frozen_asc = GIS / "PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.asc"
    base = GIS / "PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif"

    release = {
        "status": "V48_CONDITIONED_FROZEN_PRE_SAR_RELEASE",
        "date": "2026-10-02",
        "release_role": "Frozen hydrodynamic model terrain input; Sentinel-1 remains held out for subsequent validation.",
        "base": {"path": str(base), "sha256": sha256(base)},
        "frozen": {
            "tif": str(frozen),
            "tif_sha256": sha256(frozen),
            "asc": str(frozen_asc),
            "asc_sha256": sha256(frozen_asc),
        },
        "selection": selection["counts"],
        "cut_statistics": selection["cut_statistics"],
        "candidate_sensitivity": sensitivity["cross_run"],
        "topology_cap_sensitivity": {
            "configurations": caps["cross_run"]["configurations"],
            "stable_strict_components_all_runs": caps["cross_run"]["stable_strict_components_all_runs"],
        },
        "source_holdout": {
            "jrc_changed_decision_components": holdout["jrc_topology_holdout"]["changed_decision_components"],
            "jrc_strict_retained": holdout["jrc_topology_holdout"]["strict_retained"],
            "jrc_bounded_retained": holdout["jrc_topology_holdout"]["bounded_retained"],
            "osm_holdout_scope": "candidate-stage diagnostic only; historical OSM geometry remains a topology construction input",
        },
        "conditioning_invariants": conditioning["invariants"],
        "verification": verification["checks"],
        "scientific_freeze": {
            "sentinel1_2021_used_for_conditioning": False,
            "global_priority_flood_applied_to_final_dem": False,
            "epsilon_ramp_applied_to_final_dem": False,
            "negative_elevations_clipped": False,
            "rule_after_freeze": "Do not tune or alter V48_CONDITIONED_FROZEN using Sentinel-1 2021 results. Any SAR-informed change must be a separate exploratory branch/version.",
        },
        "audit_files": {
            "selection": str(RESEARCH / "final_selection/V48_final_selection_summary.json"),
            "conditioning": str(AUDIT / "V48_conditioning_summary.json"),
            "verification": str(AUDIT / "V48_final_verification.json"),
            "applied_cells": str(AUDIT / "V48_applied_cells.csv"),
            "manifest": str(AUDIT / "V48_conditioning_manifest.json"),
        },
    }
    release_path = AUDIT / "V48_FINAL_RELEASE_20261002.json"
    release_path.write_text(json.dumps(release, indent=2, ensure_ascii=False), encoding="utf-8")

    report = f"""# V48 — DEM chuẩn đã khóa trước Sentinel-1

**Ngày khóa:** 02/10/2026  
**Trạng thái:** `V48_CONDITIONED_FROZEN_PRE_SAR_RELEASE`

## Kết quả cuối

- Base chính thức: `PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif`, byte-identical với `PhuYen_DEM_30m.tif` gốc Copernicus.
- DEM dùng cho mô hình: `PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.tif`.
- Bản ASC cho BG_Flood: `PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.asc`.
- Final conditioning: **{selection['counts']['final_components']} components / {selection['counts']['final_cut_cells']} cells**.
- Cut depth: min **{selection['cut_statistics']['min_m']:.3f} m**, median **{selection['cut_statistics']['median_m']:.3f} m**, max **{selection['cut_statistics']['max_m']:.3f} m**.
- Cut volume raster: **{selection['cut_statistics']['volume_m3']:.1f} m³**.

## Rule chọn cuối

Một component chỉ được vào V48 nếu đồng thời:

1. baseline topology class = `AUTO_APPROVE_STRICT`;
2. vẫn strict trong cả **7/7 topology-cap configurations**;
3. vẫn strict khi **JRC bị hold out hoàn toàn khỏi topology gate**;
4. mọi Tier-A candidate cell của component sống **>=9/11 candidate sensitivity configurations**;
5. không dùng Sentinel-1 2021 trong candidate, topology, threshold hay cut selection.

Từ 47 strict baseline, giao cuối còn **{selection['counts']['final_components']} components**.

## Các phép biến đổi không có trong V48 frozen

- Không global Priority-Flood trên DEM cuối.
- Không epsilon eastward ramp.
- Không clip các cao độ âm của Copernicus.
- Không kế thừa V39 Safe, V41, V44, V45 hoặc 38 cut V46.
- Không tune theo CSI/Recall/Precision của Sentinel-1.

## Verification

Independent verifier: **{verification['status']}**.

- Changed mask exact: `{verification['checks']['changed_mask_exact']}` ({verification['checks']['changed_cells']}/{verification['checks']['expected_cells']} cells).
- Grid/CRS/nodata preserved: `{verification['checks']['grid_metadata_preserved']}`.
- All changes lowering: `{verification['checks']['all_changes_lowering']}`.
- Max final cut: **{verification['checks']['max_cut_m']:.3f} m**.
- All frozen cell values match selected proposals: `{verification['checks']['all_frozen_values_match_selected_proposals']}`.
- ASC vs frozen GeoTIFF max abs diff: **{verification['checks']['asc_vs_frozen_max_abs_diff_m']:.6f} m**.

## SHA-256 khóa release

- Base: `{sha256(base)}`
- Frozen GeoTIFF: `{sha256(frozen)}`
- Frozen ASC: `{sha256(frozen_asc)}`

## Quy tắc sau freeze

Sentinel-1 2021 từ đây chỉ được dùng để **validation**. Không sửa lại `V48_CONDITIONED_FROZEN` dựa trên kết quả SAR. Nếu cần thử chỉnh theo SAR, phải tạo một nhánh exploratory/version khác để không phá independent validation.
"""
    report_path = ROOT / "V48_FINAL_DEM_REPORT_20261002.md"
    report_path.write_text(report, encoding="utf-8")

    print(json.dumps({
        "status": release["status"],
        "release_json": str(release_path),
        "release_json_sha256": sha256(release_path),
        "report": str(report_path),
        "report_sha256": sha256(report_path),
        "frozen_tif": str(frozen),
        "frozen_tif_sha256": sha256(frozen),
        "frozen_asc": str(frozen_asc),
        "frozen_asc_sha256": sha256(frozen_asc),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
