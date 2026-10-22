# V46 — Nghiên cứu bổ sung cho đồ án BG_Flood Phú Yên

**Ngày rà soát:** 30/09/2026  
**Phạm vi:** kiểm tra chuỗi hydrological conditioning V46, các JSON/CSV/manifest và mã tạo V46; đối chiếu các luận điểm chính với bài báo DOI/publisher và tài liệu chính thức của JRC, HydroSHEDS/HydroRIVERS, OpenStreetMap/Overpass. Ghi chú này không thay thế kiểm định mô hình ngập bằng quan trắc.

## 1. Kết luận ngắn

V46 có một chuỗi audit tốt hơn rõ rệt so với V44/V45: Sentinel-1 2021 không được đọc trong các bước tạo candidate/topology/apply; OSM được truy vấn ở trạng thái lịch sử trước ảnh SAR; JRC được gắn nhãn 1984–2020; mọi thay đổi cuối cùng có tọa độ, reason code và hash. Tuy vậy, luận văn chỉ nên gọi V46 là **DEM/routing surface đã được hydrologically conditioned theo các ràng buộc đã nêu**, không nên gọi là “DEM đúng hơn về cao độ vật lý” hay “địa hình thực đã được hiệu chỉnh”. Stream burning/breaching chủ động thay đổi cao độ để cưỡng bức tính liên tục thủy văn; đây là điểm được tài liệu HydroSHEDS và các nghiên cứu conditioning cảnh báo rõ [1–3].

Điểm cần nói chính xác nhất là **V41 sạch theo lineage SAR**, không phải DEM nguyên trạng. `05-Du-lieu-GIS/process_dem.py` tạo V41 từ `PhuYen_DEM_30m_V39_Safe.asc` bằng: cắt cao độ âm về 0, Priority-Flood, sau đó cộng epsilon-slope hướng đông `0.001 m/cell` trên toàn raster hợp lệ. Đối chiếu trực tiếp V39→V41 cho thấy **4.407.900/4.410.000 ô** thay đổi >0,001 m; chênh lệch chỉ tăng cao độ, median **+1,088 m**, cực đại **+31,497 m**. Riêng gradient đông–tây có biên độ tối đa khoảng **2,099 m** trên 2.100 cột. Vì vậy V41 phù hợp làm **base không chứa chỉnh sửa theo SAR-2021**, nhưng không được mô tả là raw DEM/DTM chưa xử lý. Audit trước của dự án cũng chưa chứng nhận độc lập nguồn gốc và vertical datum của DEM 30 m/V41.

## 2. Holdout Sentinel-1 2021: có gì đã chứng minh, có gì chưa

Chuỗi V46 hiện có bằng chứng tốt cho claim hẹp: **raster Sentinel-1 2021 không được dùng trực tiếp để chọn hoặc hạ các ô V46**. `v46_conditioning_dryrun.py`, `v46_build_hydro_evidence.py`, `v46_topology_paths.py` đều ghi invariant không dùng Sentinel; `v46_apply_conditioning.py` chỉ nhận V41 + bảng cut/topology; `V46_final_verification.json` còn kiểm tra reason code không chứa Sentinel và kết quả là `PASS`.

Snapshot OSM dùng trong nhánh lịch sử được cố định tại **2021-11-25T00:00:00Z**, trước ảnh SAR giữ lại ngày **2021-11-30**. Overpass QL xác nhận tham số `[date:"..."]` trả trạng thái cơ sở dữ liệu OSM tại thời điểm quá khứ đó [4]. Manifest cục bộ ghi **99 way** (59 river, 32 stream, 8 canal), timestamp way muộn nhất **2021-06-15T22:12:49Z**, và lưu hash từng tệp OSM.

Tuy nhiên chưa nên viết “toàn bộ V46 hoàn toàn độc lập với mọi thông tin hậu sự kiện”. Seed 55 ô ban đầu đến từ `V46_legacy_current_osm_stable_core_20260930`, tức một mask chọn tọa độ có provenance từ OSM hiện tại; `v46_validate_seed55.py` sau đó chứng minh cả **55/55 ô** này đều nằm trong stable core dựng lại từ OSM lịch sử 25/11/2021. Điều đó chứng minh **historical support** cho 55 ô, nhưng việc chọn đúng subset 55 trong tập lịch sử 407 ô vẫn chịu selection từ nguồn hiện tại. Claim an toàn là: **“55 tọa độ frozen đều được corroborate bởi snapshot OSM lịch sử trước SAR”**. Claim quá mạnh là: **“55 seed được tạo hoàn toàn chỉ từ dữ liệu pre-event/pre-2021”**.

Nếu cần một holdout thời gian chặt nhất cho luận văn, nên tái sinh seed trực tiếp từ các input lịch sử (hoặc chạy topology trên toàn bộ 407 ô historical stable Tier A) và khóa mọi ngưỡng trước khi xem kết quả SAR.

## 3. JRC pre-2021: hợp lệ làm bằng chứng phụ, không phải ground truth

Trang dữ liệu chính thức JRC hiện liệt kê asset `JRC/GSW1_3/*` là **1984–2020**, đúng với mục tiêu “pre-2021” [5]. Bài gốc Pekel et al. mô tả Global Surface Water từ Landsat ở quy mô 30 m [6]. File V46 dùng là `JRC_GSW1_3_occurrence_1984_2020_100E_10N.tif`, SHA256 `64060355...924b7`; manifest ghi temporal coverage 1984–2020. Raster local không có tag temporal nhúng, nên khả năng tái lập phụ thuộc vào URL nguồn + manifest + hash đã lưu.

JRC occurrence chỉ là **tần suất quan sát nước mặt**, không phải bathymetry, mực nước hay bằng chứng rằng một ô DEM cần bị hạ. JRC cũng đã công bố rằng Occurrence ở các bản v1.2–v1.4 có bất nhất ở các năm bổ sung và được tính lại trong v1.5; vì vậy dùng v1.3 như evidence phụ là hợp lý hơn gọi nó là ground truth [5].

Trong 38 ô V46 thực sự được hạ, `jrc_occurrence_buffer_max_pct` là **0% ở 34 ô** và **43% ở 4 ô**. Như vậy không được viết “mọi cut V46 đều được JRC xác nhận”. Gate topology là **JRC ≥25% trong 1 cell _hoặc_ upstream area ≥0,5 km² trong 2 cell**; phần lớn ô áp dụng đã đi qua nhánh flow/upstream-area chứ không phải JRC.

## 4. Stable Tier A và seed 55

Dry-run lịch sử dùng OSM + HydroRIVERS + terrain với ba bề rộng corridor lồng nhau:

| Run | OSM corridor | HydroRIVERS corridor | Candidate | Tier A |
|---|---:|---:|---:|---:|
| strict | 30 m | 60 m | 14.017 ô | **407 ô** |
| base | 60 m | 90 m | 22.946 ô | **1.580 ô** |
| wide | 90 m | 150 m | 36.079 ô | **4.530 ô** |

`V46_stable_core_summary.json` cho stable Tier A intersection = **407 ô = 0,3663 km²**, gồm **151 component** (76 singleton, 75 multi-cell; lớn nhất 28 ô). Nhưng `strict_not_in_base=0` và `base_not_in_wide=0`: ba tập là lồng nhau, nên intersection bằng đúng tập strict. Vì vậy “stable” ở đây chỉ chứng minh ổn định đối với **ba lựa chọn corridor đã thử**; chưa chứng minh robustness với relief threshold, slope/elevation cap, nguồn hydrography khác, thuật toán D8, thời điểm OSM hay các ngưỡng topology.

Seed legacy/current-OSM có **55 ô = 0,0495 km², 24 component**. Khi kiểm lại với historical stable core 407 ô, **55/55** còn support, không thiếu ô nào. Đây là bằng chứng corroboration tốt, nhưng không biến quá trình chọn subset 55 thành một thiết kế hoàn toàn pre-event như đã nêu ở mục 2.

HydroRIVERS phù hợp làm prior ở quy mô mạng chính, không phải centerline chính xác ở từng ô 30 m: tài liệu chính thức cho biết HydroRIVERS được trích từ HydroSHEDS ở **15 arc-second (~500 m tại xích đạo)** và bắt đầu stream khi upstream area >10 km² hoặc mean natural discharge >0,1 m³/s; các dòng nhỏ hơn bị loại vì vị trí ngày càng kém tin cậy [7]. V46 dùng **373 reach** HydroRIVERS giao với miền DEM, nên corridor rộng hơn OSM là có cơ sở phương pháp.

## 5. Topology paths và quyết định cut

`v46_topology_paths.py` xử lý **24 component seed**. Với mỗi component, mã lấy historical OSM way và HydroRIVERS ID, dựng ordered cells theo OSM, tìm cặp anchor upstream/downstream có **direct D8 trace**, kiểm upstream area không giảm downstream và filled elevation không tăng downstream, rồi nội suy tuyến tính một target profile giữa hai anchor. Gate bổ sung là JRC ≥25% hoặc upstream area ≥0,5 km²; cap toàn cục là cut ≤3 m, ≤8 ô/component, path span ≤20 ô và lệch OSM centerline ≤1 cell. Strict auto yêu cầu cut ≤1 m và ≤4 ô/component.

Kết quả topology: **24/24 component có DIRECT_D8_TRACE**; phân loại **1 `AUTO_APPROVE_STRICT`, 15 `REVIEW_APPROVE_BOUNDED`, 8 `REJECT`**. Tổng proposal: 1 strict cell, 37 bounded cells và 17 rejected cells. Tám component bị reject gồm: 1 component lệch >1 cell khỏi historical OSM, 4 component thiếu cả JRC≥25 lẫn upstream-area≥0,5 km², và 3 component cần cut >3 m.

Các path này chứng minh **tính nhất quán thuật toán với D8 + OSM/HydroRIVERS trong các ràng buộc đã đặt**, không chứng minh vị trí cống/cửa xả thật, bathymetry, hay rằng nước ngoài thực địa chắc chắn đi theo đúng path đó. Target profile tuyến tính là construction của thuật toán, không phải mặt cắt đo đạc.

Một điểm provenance cần giữ nguyên khi viết luận văn: không tìm thấy artifact review thủ công riêng cho 15 component `REVIEW_APPROVE_BOUNDED`. `v46_apply_conditioning.py` đưa toàn bộ nhóm này vào output khi chạy cờ `--include-bounded`; summary xác nhận `include_bounded=true`. Vì vậy nên gọi chúng là **“bounded components được đưa vào theo rule/cờ thực thi”** hoặc “bounded-review class đã được áp dụng”, không nên khẳng định “15 component đã được chuyên gia kiểm duyệt thủ công” nếu chưa có biên bản/GIS review độc lập.

## 6. V46 thực tế đã sửa gì

Theo `V46_conditioning_summary.json`, `V46_applied_cells.csv` và đối chiếu raster V41↔V46:

- Base V41 SHA256: `9fb70773a96fc2d52521aa803c3aa08537a5e379d9592754541365ad32e15488`.
- V46 SHA256: `bbfe4be06347d014fefd958aff7af33d518593120e0bfeca4e1e7b9e9f3676ac`.
- **38 ô** được hạ, thuộc **16 component**; diện tích ô thay đổi **0,0342 km²**.
- 1 ô thuộc `AUTO_APPROVE_STRICT`, cut **0,839667 m**.
- 37 ô thuộc 15 `REVIEW_APPROVE_BOUNDED`; cut min **0,735 m**, median **1,186 m**, max **2,9625 m**.
- Trên toàn 38 ô, cut min **0,735000 m**, median **1,160333 m**, max **2,962500 m**.
- Tổng `Σ(cut × 900 m²)` = **49.289,8276 m³**. Đây là **thể tích hạ raster hình học**, không phải thể tích nước lũ, thể tích lòng dẫn thật hay khối lượng đào thi công.
- Grid transform và NoData được giữ; tất cả thay đổi là lowering; raster diff khớp đúng audit rows.
- 17 proposal bị reject không được đưa vào V46.

`V46_final_verification.json` có status **PASS** với toàn bộ check true: base hash, exact historical snapshot, không có way hậu cutoff, JRC pre-2021 theo manifest, seed đúng 55 ô, mọi applied cell nằm trong seed, diff đúng CSV, chỉ lowering, decision hợp lệ, mọi component áp dụng có direct D8 topology, cap 1 m/3 m, reason code đầy đủ, OSM + HydroRIVERS đầy đủ, không có Sentinel trong reason. Kiểm lại hash hiện tại của bốn manifest chính (`conditioning`, `hydro_evidence`, `seed55`, `topology`) cho **0 lỗi hash**.

## 7. Câu nào có thể và không thể viết trong đồ án

| Có thể viết | Không nên viết nếu chưa có bằng chứng bổ sung |
|---|---|
| “V41 được chọn làm base pre-SAR; V46 không kế thừa các sửa đổi SAR-based của V44.” | “V41 là DEM nguyên gốc/chưa xử lý/ground truth địa hình.” |
| “Rasters/scripts V46 không dùng Sentinel-1 2021 trực tiếp trong candidate/topology/apply; SAR được giữ lại cho bước đánh giá sau.” | “Toàn bộ thiết kế V46 hoàn toàn blind với mọi dữ liệu hậu 2021.” Seed 55 vẫn được preselect từ current-OSM rồi mới historical-corroborate. |
| “JRC GSW1.3 1984–2020 là bằng chứng nước mặt lịch sử phụ trợ, pre-2021.” | “JRC xác nhận tất cả 38 cut” hoặc “JRC là bathymetry/ground truth.” |
| “55/55 tọa độ frozen có support trong historical stable Tier A; historical core có 407 ô.” | “55 seed được sinh hoàn toàn từ historical OSM.” |
| “Stable Tier A 407 ô tồn tại qua ba corridor strict/base/wide.” | “407 ô đã chứng minh robust với mọi tham số/phương pháp.” |
| “24/24 component có direct D8 topology theo thuật toán V46; 16 component được áp dụng.” | “D8 path là đường dòng/cống thực địa đã được quan trắc.” |
| “V46 hạ 38 ô, tối đa 2,9625 m, audit/manifest hiện PASS.” | “V46 chính xác hơn về cao độ vật lý” hoặc “đã cải thiện ngập” trước khi chạy validation độc lập. |
| “49.289,83 m³ là tổng thể tích hạ DEM theo hình học lưới.” | “49.289,83 m³ là thể tích lũ/khả năng tiêu thoát/thể tích đào thực tế.” |
| “HydroRIVERS là prior topology quy mô vùng.” | “HydroRIVERS là centerline 30 m chính xác cho mọi sông/kênh Phú Yên.” |

## 8. Cách trình bày V46 trong luận văn

Wording bảo thủ và có thể bảo vệ được trước phản biện:

> V46 được xây dựng từ V41 theo một quy trình hydrological conditioning có audit. V41 được xem là base pre-SAR trong lineage của nghiên cứu, nhưng bản thân V41 đã trải qua tiền xử lý depression filling và epsilon-slope nên không được coi là DEM nguyên trạng. Candidate V46 được giới hạn bởi historical OSM, HydroRIVERS và địa hình/flow dẫn xuất từ V41; JRC GSW 1984–2020 chỉ được dùng như bằng chứng nước mặt bổ trợ. Raster Sentinel-1 2021 không tham gia trực tiếp vào các bước candidate, topology hoặc áp dụng cut và được dành cho đánh giá sau khi V46 đã được tạo. V46 cuối cùng hạ 38 ô trong 16 component, với độ hạ 0,735–2,9625 m và giữ nguyên grid/NoData; các thay đổi này nên được diễn giải như conditioning nhằm cải thiện tính liên tục routing theo các ràng buộc đã đặt, không phải phép đo lại cao độ lòng sông.

Nếu muốn dùng từ **“independent validation”** theo nghĩa mạnh, còn hai việc nên khóa trước: (i) loại selection từ current-OSM bằng cách sinh seed hoàn toàn từ snapshot lịch sử, và (ii) lưu provenance đầy đủ của raster SAR/cảnh Sentinel-1 cùng rule/threshold đã freeze trước khi tính metric SAR. Sau đó mới báo CSI/F1/IoU hay cải thiện ngập như kết quả validation, không dùng các metric đó để quay lại chọn cut/ngưỡng.

## 9. Nguồn sơ cấp/official đã đối chiếu

1. Lindsay, J.B. (2016), *Efficient hybrid breaching-filling sink removal methods for flow path enforcement in digital elevation models*, Hydrological Processes 30(6), 846–857. https://doi.org/10.1002/hyp.10648
2. Lindsay, J.B. (2016), *The practice of DEM stream burning revisited*, Earth Surface Processes and Landforms 41(5), 658–668. https://doi.org/10.1002/esp.3888
3. Callow, J.N., Van Niel, K.P., Boggs, G.S. (2007), *How does modifying a DEM to reflect known hydrology affect subsequent terrain analysis?*, Journal of Hydrology. https://doi.org/10.1016/j.jhydrol.2006.06.020
4. OpenStreetMap Wiki, *Overpass API/Overpass QL — Date (attic data)*. https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL#Date
5. European Commission JRC, *Global Surface Water — Data Access* (trang chính thức; bảng asset xác nhận `GSW1_3` = 1984–2020; truy cập 30/09/2026). https://global-surface-water.appspot.com/download
6. Pekel, J.-F. et al. (2016), *High-resolution mapping of global surface water and its long-term changes*, Nature 540, 418–422. https://doi.org/10.1038/nature20584
7. HydroSHEDS, *HydroRIVERS Technical Documentation v1.0* (Oct 2019) và trang sản phẩm chính thức. https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf ; https://www.hydrosheds.org/products/hydrorivers
8. HydroSHEDS, *HydroSHEDS Technical Documentation v1.4* (Apr 2022), cảnh báo conditioned DEM đã bị thay đổi để suy diễn drainage. https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf
9. Yamazaki, D. et al. (2019), *MERIT Hydro: A High-Resolution Global Hydrography Map Based on Latest Topography Dataset*, Water Resources Research 55, 5053–5073. https://doi.org/10.1029/2019WR024873
10. Chen, Q., Mudd, S.M., Attal, M., Hancock, S. (2024), *Extracting an accurate river network: Stream burning re-revisited*, Remote Sensing of Environment 312, 114333. https://doi.org/10.1016/j.rse.2024.114333
11. Hawker, L. et al. (2024), *Assessing LISFLOOD-FP with the next-generation digital elevation model FABDEM using household survey and remote sensing data in the Central Highlands of Vietnam*, NHESS 24, 539–566. https://doi.org/10.5194/nhess-24-539-2024 — bằng chứng cho tầm quan trọng của lựa chọn DEM trong bối cảnh Việt Nam, không phải bằng chứng trực tiếp rằng V46 tốt hơn ở Phú Yên.

### Bằng chứng cục bộ chính

`V46_Nghien_cuu_hydro_conditioning_nguon_mo_20260930.md`; `05-Du-lieu-GIS/process_dem.py`; `v46_conditioning_dryrun.py`; `v46_build_hydro_evidence.py`; `v46_consolidate_sensitivity.py`; `v46_validate_seed55.py`; `v46_topology_paths.py`; `v46_apply_conditioning.py`; `v46_verify_final.py`; các summary/manifest/CSV trong `V46_stable_core_20260930`, `V46_seed55_historical_validated_20260930`, `V46_topology_20260930`, `V46_audit_20260930`, và `V46_inputs`.
