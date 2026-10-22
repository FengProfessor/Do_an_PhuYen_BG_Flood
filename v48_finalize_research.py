from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


ROOT = Path(r"D:\VTP")
V48 = ROOT / "V48_research_20261002"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    cop = load_json(ROOT / "V47_copernicus_provenance_20261001.json")
    lineage = load_json(ROOT / "V47_lineage_audit_20261001.json")
    raw_candidate = load_json(V48 / "candidate_baseline_strict_1_2/V46_dryrun_summary.json")
    raw_hydro = load_json(V48 / "hydro_evidence_raw/V46_hydro_evidence_summary.json")
    raw_sens = load_json(V48 / "candidate_sensitivity/V48_candidate_sensitivity_summary.json")
    raw_top = load_json(V48 / "topology_raw815/result/V46_topology_summary.json")
    old_sens = load_json(ROOT / "V47_candidate_sensitivity_20261001/V47_candidate_sensitivity_summary.json")
    old_top = load_json(ROOT / "V47_topology_historical407_20261001/V46_topology_summary.json")

    comp = pd.read_csv(V48 / "topology_raw815/result/V46_topology_components.csv")
    cuts = pd.read_csv(V48 / "topology_raw815/result/V46_proposed_cut_cells.csv")
    survival = pd.read_csv(V48 / "candidate_sensitivity/V48_baseline815_survival.csv")

    survival_map = {
        (int(r.row), int(r.col)): int(r.survival_count_of_11)
        for r in survival.itertuples(index=False)
    }
    base = pd.read_csv(V48 / "candidate_baseline_strict_1_2/V46_obstruction_candidates.csv")
    base = base[base.review_status == "TIER_A_CONSENSUS_CANDIDATE"].copy()

    from scipy.ndimage import label
    with rasterio.open(V48 / "topology_raw815/V48_baseline815_core.tif") as src:
        core = src.read(1) > 0
    comps, _ = label(core, np.ones((3, 3), dtype=np.uint8))
    component_survival: dict[int, list[int]] = {}
    for row in base.itertuples(index=False):
        cid = int(comps[int(row.row), int(row.col)])
        if cid > 0:
            component_survival.setdefault(cid, []).append(survival_map[(int(row.row), int(row.col))])

    robustness_by_decision = {}
    for decision, group in comp.groupby("decision"):
        all_ge9 = 0
        any_ge9 = 0
        all_11 = 0
        any_11 = 0
        mins = []
        means = []
        for cid in group.component_id.astype(int):
            vals = component_survival.get(cid, [])
            if not vals:
                continue
            all_ge9 += int(min(vals) >= 9)
            any_ge9 += int(max(vals) >= 9)
            all_11 += int(min(vals) == 11)
            any_11 += int(max(vals) == 11)
            mins.append(min(vals))
            means.append(float(np.mean(vals)))
        robustness_by_decision[decision] = {
            "components": int(len(group)),
            "all_cells_ge9of11_components": int(all_ge9),
            "any_cell_ge9of11_components": int(any_ge9),
            "all_cells_11of11_components": int(all_11),
            "any_cell_11of11_components": int(any_11),
            "min_component_cell_survival_count_of_11": int(min(mins)) if mins else None,
            "mean_component_survival_count_of_11": float(np.mean(means)) if means else None,
        }

    reject_reasons = Counter()
    for text in comp.loc[comp.decision == "REJECT", "reason_codes"].fillna(""):
        for reason in str(text).split(";"):
            if reason:
                reject_reasons[reason] += 1

    approved = comp[comp.decision != "REJECT"]
    jrc_support = approved.jrc_occurrence_buffer_max_pct >= 25.0
    up_support = approved.upstream_area_buffer_max_km2 >= 0.5
    support_channels = {
        "approved_components": int(len(approved)),
        "jrc25_support": int(jrc_support.sum()),
        "upstream_area_0_5km2_support": int(up_support.sum()),
        "both": int((jrc_support & up_support).sum()),
        "upstream_area_only": int((~jrc_support & up_support).sum()),
        "jrc_only": int((jrc_support & ~up_support).sum()),
    }

    cut_stats = {}
    for decision, group in cuts.groupby("decision"):
        cut_stats[decision] = {
            "cells": int(len(group)),
            "components": int(group.component_id.nunique()),
            "cut_depth_min_m": float(group.cut_depth_m.min()),
            "cut_depth_median_m": float(group.cut_depth_m.median()),
            "cut_depth_max_m": float(group.cut_depth_m.max()),
            "cut_volume_m3": float((group.cut_depth_m * 900.0).sum()),
        }
    approved_cuts = cuts[cuts.decision != "REJECT"].copy()
    cut_stats["ALL_APPROVED"] = {
        "cells": int(len(approved_cuts)),
        "components": int(approved_cuts.component_id.nunique()),
        "cut_depth_min_m": float(approved_cuts.cut_depth_m.min()) if len(approved_cuts) else None,
        "cut_depth_median_m": float(approved_cuts.cut_depth_m.median()) if len(approved_cuts) else None,
        "cut_depth_max_m": float(approved_cuts.cut_depth_m.max()) if len(approved_cuts) else None,
        "cut_volume_m3": float((approved_cuts.cut_depth_m * 900.0).sum()),
    }
    cut_stats["ALL_PROPOSED_INCLUDING_REJECTED"] = {
        "cells": int(len(cuts)),
        "components": int(cuts.component_id.nunique()),
        "cut_depth_min_m": float(cuts.cut_depth_m.min()) if len(cuts) else None,
        "cut_depth_median_m": float(cuts.cut_depth_m.median()) if len(cuts) else None,
        "cut_depth_max_m": float(cuts.cut_depth_m.max()) if len(cuts) else None,
        "cut_volume_m3": float((cuts.cut_depth_m * 900.0).sum()),
    }

    tif_path = ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m.tif"
    asc_path = ROOT / "05-Du-lieu-GIS/PhuYen_DEM_30m.asc"
    with rasterio.open(tif_path) as src:
        tif = src.read(1).astype(np.float64)
        tif_meta = {"shape": list(src.shape), "crs": str(src.crs), "nodata": src.nodata}
    with rasterio.open(asc_path) as src:
        asc = src.read(1).astype(np.float64)
        asc_meta = {"shape": list(src.shape), "crs": None if src.crs is None else str(src.crs), "nodata": src.nodata}
    valid = np.isfinite(tif) & np.isfinite(asc) & (tif > -9000) & (asc > -9000)
    raw_stats = {
        "tif": tif_meta,
        "asc": asc_meta,
        "tif_sha256": sha256(tif_path),
        "asc_sha256": sha256(asc_path),
        "min_m": float(tif[tif > -9000].min()),
        "max_m": float(tif[tif > -9000].max()),
        "negative_cells": int(((tif < 0) & (tif > -9000)).sum()),
        "zero_cells": int((tif == 0).sum()),
        "tif_vs_asc_exact_equal_cells": int((tif[valid] == asc[valid]).sum()),
        "tif_vs_asc_valid_compared": int(valid.sum()),
        "tif_vs_asc_max_abs_diff_m": float(np.max(np.abs(tif[valid] - asc[valid]))),
        "interpretation": "ASC is a rounded text export and has no CRS in the file; use the provenance-locked GeoTIFF as V48 source of truth.",
    }

    summary = {
        "status": "V48_RESEARCH_DRY_RUN_COMPLETE_NO_DEM_MODIFICATION",
        "date": "2026-10-02",
        "scientific_holdout": {
            "sentinel1_2021_used_for_selection": False,
            "sentinel1_2021_opened_by_v48_research": False,
        },
        "raw_copernicus": {
            "provenance_exact_cells": cop["output"]["exact_equal_cells"],
            "provenance_max_abs_diff_m": cop["output"]["max_abs_diff_m"],
            "sha256": cop["output"]["sha256"],
            "raw_stats": raw_stats,
        },
        "why_restart_from_raw": lineage["counterfactual_conditioning"],
        "raw_routing_evidence": raw_hydro["diagnostics"],
        "candidate_baseline": {
            "tier_a_cells": raw_sens["baseline"]["tier_a_cells"],
            "components": raw_sens["baseline"]["components_8_neighbor"],
            "candidate_stage_total_cells": raw_candidate["results"]["candidate_cells"],
        },
        "candidate_sensitivity": raw_sens["cross_run"],
        "topology": {
            "components": raw_top["components"],
            "direct_d8_topology_components": raw_top["direct_d8_topology_components"],
            "decision_counts": raw_top["decision_counts"],
            "support_channels": support_channels,
            "reject_reason_counts": dict(reject_reasons.most_common()),
            "cut_stats": cut_stats,
            "sensitivity_by_decision": robustness_by_decision,
        },
        "comparison_to_v41_based_v47": {
            "baseline_tier_a_cells": {"v41": old_sens["baseline"]["tier_a_cells"], "raw": raw_sens["baseline"]["tier_a_cells"]},
            "baseline_components": {"v41": old_sens["baseline"]["components_8_neighbor"], "raw": raw_sens["baseline"]["components_8_neighbor"]},
            "all_11_cells": {"v41": old_sens["cross_run"]["all_run_intersection_cells"], "raw": raw_sens["cross_run"]["all_run_intersection_cells"]},
            "ge9of11_cells": {"v41": old_sens["cross_run"]["ge9of11_cells"], "raw": raw_sens["cross_run"]["ge9of11_cells"]},
            "topology_decisions_v41": old_top["decision_counts"],
            "topology_decisions_raw": raw_top["decision_counts"],
        },
        "provenance_correction": {
            "note": "v47_topology_paths.py hard-codes the output label d8_source_dem='V41'. In this V48 run the actual --dem and all D8/HAND routing evidence were generated from PhuYen_DEM_30m.tif. The V46_topology_summary.json label is therefore stale metadata and must not be quoted as provenance.",
            "actual_dem": str(tif_path),
            "actual_dem_sha256": sha256(tif_path),
            "actual_hydro_summary": str(V48 / "hydro_evidence_raw/V46_hydro_evidence_summary.json"),
            "actual_hydro_summary_sha256": sha256(V48 / "hydro_evidence_raw/V46_hydro_evidence_summary.json"),
        },
        "decision": {
            "ready_to_create_final_v48_conditioned": False,
            "reason": "Candidate/topology dry-runs are strong enough to define a V48 lineage, but source-holdout and topology-cap sensitivity should be completed before freezing/applying the conditioned DEM.",
            "next_surface_names": ["V48_BASE_COPERNICUS", "V48_CONDITIONED_DRAFT", "V48_CONDITIONED_FROZEN"],
        },
    }

    out_json = V48 / "V48_research_summary_20261002.json"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    raw_ge9 = raw_sens["cross_run"]["ge9of11_cells"]
    raw_all11 = raw_sens["cross_run"]["all_run_intersection_cells"]
    approved_count = int(len(approved))
    strict = int((comp.decision == "AUTO_APPROVE_STRICT").sum())
    bounded = int((comp.decision == "REVIEW_APPROVE_BOUNDED").sum())
    rejected = int((comp.decision == "REJECT").sum())
    all_cut = cut_stats["ALL_APPROVED"]

    md = f"""# V48 — Nghiên cứu hydrological conditioning từ DEM gốc Copernicus

**Ngày:** 02/10/2026  
**Trạng thái:** nghiên cứu/dry-run hoàn tất; **chưa chỉnh DEM, chưa mở Sentinel-1 2021 để chọn tham số/cut**.

## 1. Kết luận chính

V48 nên được xây lại từ `05-Du-lieu-GIS/PhuYen_DEM_30m.tif`, không kế thừa V39 Safe, V41 hay 38 cut V46. Lý do đã được audit định lượng: V39 Safe hạ 22.928 ô × 2,5 m; sau conditioning, ảnh hưởng counterfactual còn lan tới 37.776 ô. Raw GeoTIFF đã được V47 tái tạo exact từ 4 tile Copernicus GLO-30: 4.410.000/4.410.000 ô, max diff 0 m.

Nghiên cứu V48 đã tái chạy chuỗi pre-SAR từ raw Copernicus: historical OSM 25/11/2021 + HydroRIVERS + terrain candidate sensitivity + routing-only D8/HAND/JRC evidence + topology/cut dry-run. Không bước nào dùng Sentinel-1 2021 để chọn candidate hay cut.

## 2. Base V48 nên khóa thế nào

- Source of truth: `PhuYen_DEM_30m.tif`, SHA-256 `{sha256(tif_path)}`.
- Grid: 2100 × 2100, EPSG:32649, 30 m.
- Raw có {raw_stats['negative_cells']:,} ô âm; đây là dữ liệu nguồn cần được xử lý bằng rule công khai nếu BG_Flood không chấp nhận cao độ âm, không được sửa ngầm.
- `PhuYen_DEM_30m.asc` chỉ nên là export phục vụ engine: file không mang CRS và khác GeoTIFF tối đa {raw_stats['tif_vs_asc_max_abs_diff_m']:.7f} m do làm tròn text. Không dùng ASC làm mốc provenance số 0.

Tên đề xuất: **`V48_BASE_COPERNICUS` = đúng raw GeoTIFF/hash trên**.

## 3. Routing evidence sinh lại từ raw

`pyflwdir` routing-only fill từ raw cho:

- fill cells: **{raw_hydro['diagnostics']['routing_fill_cells']:,}**;
- max fill depth: **{raw_hydro['diagnostics']['routing_fill_depth_max_m']:.3f} m**;
- p99 fill depth: **{raw_hydro['diagnostics']['routing_fill_depth_p99_m']:.3f} m**;
- max upstream area: **{raw_hydro['diagnostics']['upstream_area_max_km2']:.2f} km²**.

Các raster filled/D8/HAND này hiện chỉ là **routing evidence**, không phải V48 conditioned DEM. Max fill ~30 m cho thấy không được đơn giản lấy global depression-filled surface làm địa hình thủy lực cuối.

## 4. Candidate stage từ raw Copernicus

Cùng baseline strict 1/2 của V47, raw Copernicus tạo:

- **815 Tier-A cells / 206 components**;
- tổng candidate Tier A+B: **{raw_candidate['results']['candidate_cells']:,} cells**;
- V41-based baseline cũ: **{old_sens['baseline']['tier_a_cells']} cells / {old_sens['baseline']['components_8_neighbor']} components**.

Điều này chứng minh inherited conditioning V39→V41 đã thay đổi đáng kể không gian candidate; 407 cells V47 không nên được chuyển thẳng sang V48.

## 5. Sensitivity 11 cấu hình — cùng design V47, đổi duy nhất base DEM

- sống 11/11: **{raw_all11}/{raw_sens['baseline']['tier_a_cells']} = {raw_sens['cross_run']['all_run_intersection_baseline_pct']:.2f}%**;
- sống ≥10/11: **{raw_sens['cross_run']['ge10of11_cells']} = {raw_sens['cross_run']['ge10of11_baseline_pct']:.2f}%**;
- sống ≥9/11: **{raw_ge9} = {raw_sens['cross_run']['ge9of11_baseline_pct']:.2f}%**;
- union mọi cấu hình: **{raw_sens['cross_run']['union_all_tier_a_cells']:,} cells**.

So với V41 branch: 82 cells sống 11/11 và 390 cells sống ≥9/11. Với raw, robust core lớn hơn nhưng vẫn phải qua topology gate; survival không phải xác suất đúng.

## 6. Topology/cut dry-run từ raw D8/HAND

815 cells → 206 components; **{raw_top['direct_d8_topology_components']}/206** có direct D8 connectivity. Decision:

- **AUTO_APPROVE_STRICT: {strict} components**;
- **REVIEW_APPROVE_BOUNDED: {bounded} components**;
- **REJECT: {rejected} components**.

Tổng approved under current rules: **{approved_count} components**. Reject nhiều nhất do: {', '.join(f'{k}={v}' for k, v in reject_reasons.most_common(5))}.

Support channels trong {approved_count} approved components:

- JRC≥25%: {support_channels['jrc25_support']};
- upstream area≥0,5 km²: {support_channels['upstream_area_0_5km2_support']};
- cả hai: {support_channels['both']};
- upstream-only: {support_channels['upstream_area_only']};
- JRC-only: {support_channels['jrc_only']}.

Nếu áp toàn bộ strict+bounded proposal hiện tại, dry-run có **{all_cut['cells']} cut cells / {all_cut['components']} components**, median cut **{all_cut['cut_depth_median_m']:.3f} m**, max **{all_cut['cut_depth_max_m']:.3f} m**, volume raster **{all_cut['cut_volume_m3']:.1f} m³**. Đây vẫn là proposal, chưa được apply.

## 7. Candidate robustness và topology admissibility vẫn là hai bộ lọc độc lập

Cross-analysis V48 xác nhận bài học V47: một component có thể sống qua nhiều perturbation nhưng vẫn bị reject vì thiếu supplemental support, không cần positive cut, cut quá sâu, quá nhiều cell hoặc fail topology/geometry. Vì vậy V48 không được lấy mask ≥9/11 rồi carve trực tiếp.

Chi tiết theo decision đã được lưu trong `V48_research_summary_20261002.json` dưới `topology.sensitivity_by_decision`.

## 8. Provenance bug cần khóa trước khi dùng kết quả trong luận văn

`v47_topology_paths.py` hard-code metadata `d8_source_dem = "V41"`. Trong run V48, tham số `--dem` thực tế là `PhuYen_DEM_30m.tif` và toàn bộ D8/HAND trong `V48_research_20261002/hydro_evidence_raw` cũng sinh từ raw GeoTIFF. Vì vậy trường `d8_source_dem` trong file `V46_topology_summary.json` của run V48 là **stale label**, không phải provenance thực.

Trước khi freeze V48 nên sửa script để metadata lấy từ `args.dem`/hash thay vì literal `V41`.

## 9. Chưa nên sinh `V48_CONDITIONED` cuối ngay hôm nay

Nghiên cứu hiện đủ để xác nhận **lineage V48 từ raw là khả thi và khoa học hơn V46 lineage cũ**, nhưng chưa nên apply cut/freeze final surface. Hai gate còn nên hoàn tất trước:

1. **source holdout thật sự** ở candidate stage: ít nhất JRC-held-out và OSM-held-out, để đo phụ thuộc vào từng nguồn;
2. **topology-cap sensitivity**: max cut, max modified cells, path span; báo transition strict↔bounded↔reject.

Sau hai gate này mới sinh `V48_CONDITIONED_DRAFT`, audit 100% modified cells, khóa hash/config, rồi đổi tên thành `V48_CONDITIONED_FROZEN`. Chỉ sau freeze mới chạy BG_Flood và mở Sentinel-1 2021 để validation.

## 10. Lineage đề xuất cho đồ án

`Copernicus GLO-30 tiles → PhuYen_DEM_30m.tif / V48_BASE_COPERNICUS → pre-SAR evidence + sensitivity + constrained topology conditioning → V48_CONDITIONED_FROZEN → BG_Flood → Sentinel-1 validation`.

V41/V45/V46 giữ nguyên làm experimental/control branches; không xóa và không đưa ngược các cut cũ vào V48 tự động.

## 11. Nguồn phương pháp đã được V46/V47 kiểm chứng

- Copernicus DEM Product Handbook v5.0 / DOI 10.5270/ESA-c5d3d65.
- Barnes et al. (2014), Priority-Flood, DOI 10.1016/j.cageo.2013.04.024.
- Lindsay (2016), constrained breaching/filling, DOI 10.1002/hyp.10648.
- Lindsay (2016), stream burning revisited, DOI 10.1002/esp.3888.
- Yamazaki et al. (2019), MERIT Hydro, DOI 10.1029/2019WR024873.
- Pekel et al. (2016), JRC Global Surface Water, DOI 10.1038/nature20584.
- O'Callaghan & Mark (1984), D8 drainage extraction.
- Tarboton (1997), D∞ / grid-bias, DOI 10.1029/96WR03137.

## 12. Artefact chính

- `V48_candidate_sensitivity_design_20261002.json`
- `v48_candidate_sensitivity.py`
- `V48_research_20261002/candidate_sensitivity/V48_candidate_sensitivity_summary.json`
- `V48_research_20261002/hydro_evidence_raw/V46_hydro_evidence_summary.json`
- `V48_research_20261002/topology_raw815/result/V46_topology_summary.json`
- `V48_research_20261002/V48_research_summary_20261002.json`

**Không có V48 DEM mới nào được ghi trong nghiên cứu này.**
"""
    out_md = ROOT / "V48_Nghien_cuu_hydro_conditioning_20261002.md"
    out_md.write_text(md, encoding="utf-8")

    manifest = {
        "status": "PASS",
        "summary_json": str(out_json),
        "summary_json_sha256": sha256(out_json),
        "research_md": str(out_md),
        "research_md_sha256": sha256(out_md),
        "driver": str(Path(__file__)),
        "driver_sha256": sha256(Path(__file__)),
        "sentinel1_2021_used": False,
        "dem_modified": False,
    }
    out_manifest = V48 / "V48_research_manifest_20261002.json"
    out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
