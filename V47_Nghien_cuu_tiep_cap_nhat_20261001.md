# V47 — Cập nhật nghiên cứu BG_Flood Phú Yên

**Ngày:** 01/10/2026  
**Mục tiêu:** tổng hợp phần đã nghiên cứu từ V46/V47 và bổ sung các kiểm định mới trước khi dùng Sentinel-1 2021 làm holdout.  
**Nguyên tắc:** không dùng Sentinel-1 2021 để chọn candidate/cut; không chỉnh DOCX; không sửa DEM trong các phân tích dưới đây.

## 1. Trước khi tiếp tục: đã nghiên cứu được gì?

Từ V46 đã khóa được các điểm sau:

1. V41 không phải raw DEM “sạch” theo nghĩa chưa xử lý; nó đã qua Priority-Flood và epsilon slope. V46 vì vậy phải được diễn giải là **hydrologically conditioned routing/elevation surface**.
2. Sentinel-1 2021 không được dùng trực tiếp trong chuỗi tạo 38 cut V46, nhưng seed 55 cũ từng có selection provenance từ current OSM trước khi được historical OSM corroborate.
3. JRC GSW1.3 1984–2020 phù hợp làm **pre-event auxiliary evidence**, không phải bathymetry, event ground truth hay independent vertical validation.
4. Ba run corridor cũ chỉ chứng minh 407 strict cells được retained khi nới corridor; chưa đủ để gọi cả 407 là robust với mọi tham số.
5. Seed-55 topology có 24/24 component direct D8 trace; 1 strict, 15 bounded, 8 reject. V46 thực tế hạ 38 ô thuộc 16 component, diện tích 0,0342 km²; median cut 1,160333 m; max 2,962500 m; tổng cut-volume raster 49.289,8276 m³.
6. Final verification V46 PASS và các manifest chính đã được kiểm hash. Không có artifact riêng chứng minh 15 bounded component đã được chuyên gia review thủ công.

## 2. Phát hiện mới: provenance raw Copernicus đã mạnh hơn đáng kể

`V47_copernicus_provenance_20261001.json` đã tái tạo raster nền từ bốn object Copernicus DEM GLO-30 công khai:

- 4 tile local khớp kích thước và ETag/MD5 của object nguồn;
- reprojection về EPSG:32649, bilinear, grid 2100×2100, 30 m;
- `PhuYen_DEM_30m.tif` khớp **4.410.000/4.410.000 ô**, max absolute difference = **0,0 m**.

Claim hiện có thể nâng lên:

> Raster nền của project được tái tạo chính xác từ bốn tile Copernicus DEM GLO-30 đã khóa provenance.

Không được suy ra rằng V41/V46 vẫn giữ nguyên absolute vertical accuracy specification của raw Copernicus sau các bước conditioning/edit.

## 3. Phát hiện mới: V41 chứa inherited edits lớn từ V39_Safe

`V47_lineage_audit_20261001.json` tái tạo V41 đúng **4.410.000/4.410.000 ô** từ lineage lưu trong workspace, nhưng đồng thời lộ ra một inherited edit quan trọng:

- V35_fixed → V39_Safe: **22.928 ô** bị hạ đúng **2,5 m**;
- sau Priority-Flood/conditioning, ảnh hưởng counterfactual của nhánh V39_Safe xuất hiện trên **37.776 ô**;
- trong đó **19.417/22.928** ô edit gốc còn để lại ảnh hưởng cuối;
- **3.511** ô edit gốc bị fill xóa hết tác động;
- **18.359 ô ảnh hưởng cuối nằm ngoài mask edit V39_Safe ban đầu** do quá trình filling truyền ảnh hưởng sang vùng lân cận.

Đây là lý do không nên mô tả V41/V46 chỉ dựa trên 38 cut mới. Luận văn phải phân biệt:

> lineage inherited edits trước V41

và

> 38 cut có audit riêng từ V41 → V46.

## 4. V39_Safe hiện vẫn là provenance gap lớn

Các file hiện có chứng minh đặc tính của mask 22.928 ô, nhưng chưa tìm thấy script/lệnh sinh `PhuYen_DEM_30m_V39_Safe.asc` hay vector nguồn của `road_density_30m.tif`.

Suy ngược trực tiếp từ raster cho thấy:

- modified cells: **22.928**;
- elevation gốc: 0,003–24,888 m, mean 4,074 m;
- slope trong mask: mean **1,163°**, max **23,067°**;
- `road_density > 0`: **97,715%**;
- `road_density > 0,05`: chỉ **74,075%**;
- `slope <= 2°`: **81,285%**;
- `slope <= 5°`: **96,114%**.

Không có tổ hợp đơn giản của các threshold đang lưu (`z`, slope, road_density) tái tạo đúng mask 22.928 ô. Các note cũ còn mâu thuẫn giữa `z<=25 m`, `z<=15 m`, slope cap 2° và mô tả “chỉ vùng phẳng”.

Vì vậy wording an toàn hiện tại là:

> V39_Safe là một inherited project DEM edit đã định lượng được numerically nhưng **generation provenance chưa tái lập đầy đủ**.

Không nên viết “22.928 ô đều là đường vùng phẳng được chọn bằng rule X” cho tới khi tìm được generator/source data tương ứng.

## 5. Phát hiện mới: topology trực tiếp từ historical 407-core

Đã bỏ selection dependency của seed 55 và chạy topology trực tiếp từ 407 historical strict Tier-A cells:

- 407 cells → **151 components**;
- **149/151** có direct D8 topology;
- **13 strict**;
- **81 bounded**;
- **57 reject**;
- strict dry-run đề xuất 18 cut cells, 11.438,46 m³;
- `dem_modified=false`;
- `seed_current_osm_used_as_evidence=false`;
- `sentinel1_2021_used=false`.

57 reject cho thấy direct D8 trace không đủ để approve. Reject reason chính:

| Lý do | Component |
|---|---:|
| Không có JRC>=25% hoặc upstream-area>=0,5 km² | 24 |
| Cut depth vượt cap 3 m | 11 |
| Cả cut-depth cap và supplemental-support fail | 8 |
| Cách historical OSM centerline >1 cell | 3 |
| Không có direct D8 topology | 2 |
| Không cần positive cut | 2 |
| Các tổ hợp path-span / modified-cells / cut-depth khác | 7 |

## 6. Phát hiện mới: sensitivity 11 cấu hình làm thay đổi claim “407 stable”

Thiết kế `V47_candidate_sensitivity_design_20261001.json` được khóa trước khi chạy và không dùng Sentinel-1 2021 để selection. 11 cấu hình thay riêng relief threshold/window, slope cap, elevation cap và corridor.

Kết quả:

- baseline: **407 cells / 151 components**;
- sống trong **11/11** cấu hình: **82 cells = 20,15%**;
- sống **>=10/11**: **284 cells = 69,78%**;
- sống **>=9/11**: **390 cells = 95,82%**;
- union qua mọi run: **1.714 cells**.

Hai perturbation làm retention giảm mạnh nhất:

- relief threshold 1,5 m → **233/407 = 57,25%**;
- slope cap 3° → **250/407 = 61,43%**.

Vì vậy 407 phải được gọi là **baseline strict candidate set**. Robustness nên báo bằng survival frequency; `>=9/11` chỉ là design/reporting threshold, không phải xác suất đúng.

## 7. Cross-analysis mới: candidate robustness và topology admissibility là hai bộ lọc khác nhau

`V47_topology_sensitivity_cross_20261001.json` nối 151 component topology với 11-run sensitivity:

- strict: 13 component; **12/13** có toàn bộ ô sống >=9/11;
- bounded: 81 component; **79/81** có toàn bộ ô sống >=9/11;
- reject: 57 component; vẫn có **49/57** có toàn bộ ô sống >=9/11.

Điểm khoa học quan trọng:

> Candidate-stage robustness không đồng nghĩa topology admissibility. Một component có thể rất ổn định với parameter candidate nhưng vẫn phải reject vì thiếu supplemental evidence, cut quá sâu, path quá dài hoặc fail geometry/topology gate.

Ba approved component yếu nhất theo survival >=9/11 là component **1, 88, 92**; chúng nên được xem là sensitivity flags nếu sau này cần review thủ công.

## 8. JRC ablation diagnostic

Trong 94 component strict+bounded của historical-407 dry run:

- có JRC>=25% support: **25**;
- có upstream-area>=0,5 km² support: **87**;
- có cả hai: **18**;
- upstream-area only: **69**;
- JRC only: **7**.

Như vậy nếu chỉ bỏ nhánh JRC khỏi OR-gate nhưng giữ nguyên mọi thứ khác, **87/94 approved component** vẫn có upstream-area support; **7/94** đang phụ thuộc vào JRC để qua supplemental gate. Đây là **gate-ablation diagnostic**, chưa phải full independent JRC holdout vì JRC vẫn có thể đã ảnh hưởng các bước khác nếu pipeline khác dùng nó.

## 9. Phát hiện từ source review: epsilon implementation phải mô tả lại

Nguồn Priority-Flood/flat-resolution cho phép dùng artificial gradient để phục vụ routing, nhưng `05-Du-lieu-GIS/process_dem.py` thực tế cộng:

`0,001 m × (ncols-1-col)`

cho **mọi valid cell**, không chỉ flat cells. Với 2.100 cột, artificial east-west ramp lớn nhất là **2,099 m**.

Do đó không được viết:

> “V41 chỉ thay đổi 0,001 m do epsilon.”

Cách đúng hơn:

> “0,001 m là increment giữa hai cột kề nhau; implementation tạo một deterministic eastward routing ramp tích lũy tối đa 2,099 m trên toàn domain width.”

## 10. Nguồn sơ cấp đã đối chiếu

Memo nguồn: `V47_primary_sources_20261001.md`.

Các nguồn chính gồm:

- Copernicus DEM Product Handbook v5.0 và DOI 10.5270/ESA-c5d3d65;
- Barnes et al. (2014) Priority-Flood, DOI 10.1016/j.cageo.2013.04.024;
- Garbrecht & Martz (1997) flat drainage direction, DOI 10.1016/S0022-1694(96)03138-1;
- Lindsay (2016) constrained breaching/filling, DOI 10.1002/hyp.10648;
- JRC Global Surface Water official guide/data-access + Pekel et al. (2016), DOI 10.1038/nature20584;
- Overpass QL historical `date` + OSM Accuracy/Limitations/Completeness;
- O'Callaghan & Mark (1984) D8 drainage extraction;
- Tarboton (1997) D-infinity / grid-bias discussion, DOI 10.1029/96WR03137.

## 11. Claim mạnh nhất hiện nay

Claim có thể bảo vệ tốt nhất trước hội đồng là:

> BG_Flood sử dụng một hydrologically conditioned routing surface có raw Copernicus provenance được tái tạo exact, dùng historical hydrographic evidence trước sự kiện, áp fail-closed topology/perturbation constraints, và đã lượng hóa candidate sensitivity trước khi dùng Sentinel-1 2021 làm holdout.

Các giới hạn phải nói song song:

- V41/V46 không có independent vertical checkpoints nên chưa claim vertical accuracy tốt hơn;
- V39_Safe inherited edit chưa tái lập đầy đủ generation provenance;
- D8 direct trace là model-specific connectivity;
- JRC/OSM là auxiliary evidence, không phải ground truth;
- 407 là baseline candidate set, không phải 407 truth cells.

## 12. Nghiên cứu tiếp theo nên ưu tiên

1. Tìm hoặc tái tạo **generator/source provenance của V39_Safe và road_density_30m**; đây là khoảng trống lineage lớn nhất hiện tại.
2. Chạy **true source-holdout** ở candidate stage, ưu tiên JRC-held-out và OSM-held-out, thay vì chỉ ablation trong topology gate.
3. Chạy **topology-cap sensitivity** cho max-cut / modified-cells / path-span và báo transition strict↔bounded↔reject.
4. Chạy **before/after routing diagnostics** V41↔candidate conditioned surface, vẫn không dùng SAR để tune.
5. Sau khi khóa config/hash/rule mới mở Sentinel-1 2021 một lần như holdout evaluation.

