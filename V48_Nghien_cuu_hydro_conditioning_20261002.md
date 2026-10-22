# V48 — Nghiên cứu hydrological conditioning từ DEM gốc Copernicus

**Ngày:** 02/10/2026  
**Trạng thái:** nghiên cứu/dry-run hoàn tất; **chưa chỉnh DEM, chưa mở Sentinel-1 2021 để chọn tham số/cut**.

## 1. Kết luận chính

V48 nên được xây lại từ `05-Du-lieu-GIS/PhuYen_DEM_30m.tif`, không kế thừa V39 Safe, V41 hay 38 cut V46. Lý do đã được audit định lượng: V39 Safe hạ 22.928 ô × 2,5 m; sau conditioning, ảnh hưởng counterfactual còn lan tới 37.776 ô. Raw GeoTIFF đã được V47 tái tạo exact từ 4 tile Copernicus GLO-30: 4.410.000/4.410.000 ô, max diff 0 m.

Nghiên cứu V48 đã tái chạy chuỗi pre-SAR từ raw Copernicus: historical OSM 25/11/2021 + HydroRIVERS + terrain candidate sensitivity + routing-only D8/HAND/JRC evidence + topology/cut dry-run. Không bước nào dùng Sentinel-1 2021 để chọn candidate hay cut.

## 2. Base V48 nên khóa thế nào

- Source of truth: `PhuYen_DEM_30m.tif`, SHA-256 `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`.
- Grid: 2100 × 2100, EPSG:32649, 30 m.
- Raw có 760 ô âm; đây là dữ liệu nguồn cần được xử lý bằng rule công khai nếu BG_Flood không chấp nhận cao độ âm, không được sửa ngầm.
- `PhuYen_DEM_30m.asc` chỉ nên là export phục vụ engine: file không mang CRS và khác GeoTIFF tối đa 0.0006104 m do làm tròn text. Không dùng ASC làm mốc provenance số 0.

Tên đề xuất: **`V48_BASE_COPERNICUS` = đúng raw GeoTIFF/hash trên**.

## 3. Routing evidence sinh lại từ raw

`pyflwdir` routing-only fill từ raw cho:

- fill cells: **218,129**;
- max fill depth: **30.047 m**;
- p99 fill depth: **1.273 m**;
- max upstream area: **3107.09 km²**.

Các raster filled/D8/HAND này hiện chỉ là **routing evidence**, không phải V48 conditioned DEM. Max fill ~30 m cho thấy không được đơn giản lấy global depression-filled surface làm địa hình thủy lực cuối.

## 4. Candidate stage từ raw Copernicus

Cùng baseline strict 1/2 của V47, raw Copernicus tạo:

- **815 Tier-A cells / 206 components**;
- tổng candidate Tier A+B: **19,404 cells**;
- V41-based baseline cũ: **407 cells / 151 components**.

Điều này chứng minh inherited conditioning V39→V41 đã thay đổi đáng kể không gian candidate; 407 cells V47 không nên được chuyển thẳng sang V48.

## 5. Sensitivity 11 cấu hình — cùng design V47, đổi duy nhất base DEM

- sống 11/11: **207/815 = 25.40%**;
- sống ≥10/11: **553 = 67.85%**;
- sống ≥9/11: **770 = 94.48%**;
- union mọi cấu hình: **2,900 cells**.

So với V41 branch: 82 cells sống 11/11 và 390 cells sống ≥9/11. Với raw, robust core lớn hơn nhưng vẫn phải qua topology gate; survival không phải xác suất đúng.

## 6. Topology/cut dry-run từ raw D8/HAND

815 cells → 206 components; **203/206** có direct D8 connectivity. Decision:

- **AUTO_APPROVE_STRICT: 47 components**;
- **REVIEW_APPROVE_BOUNDED: 66 components**;
- **REJECT: 93 components**.

Tổng approved under current rules: **113 components**. Reject nhiều nhất do: NO_JRC25_OR_UPSTREAM_AREA_0_5KM2_SUPPORT=40, NO_POSITIVE_CUT_NEEDED=32, CUT_DEPTH_EXCEEDS_GLOBAL_CAP=26, MODIFIED_CELLS_EXCEED_GLOBAL_CAP=14, COMPONENT_GT_1_CELL_FROM_HISTORICAL_OSM_CENTERLINE=5.

Support channels trong 113 approved components:

- JRC≥25%: 30;
- upstream area≥0,5 km²: 107;
- cả hai: 24;
- upstream-only: 83;
- JRC-only: 6.

Nếu áp toàn bộ strict+bounded proposal hiện tại, dry-run có **258 cut cells / 113 components**, median cut **0.991 m**, max **2.966 m**, volume raster **242100.7 m³**. Đây vẫn là proposal, chưa được apply.

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
