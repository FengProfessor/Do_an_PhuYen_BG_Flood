# V47 — Nghiên cứu tiếp: khoảng trống bằng chứng quan trọng cho BG_Flood Phú Yên

**Ngày:** 01/10/2026  
**Phạm vi:** đọc lại `V46_Nghien_cuu_bo_sung_cho_do_an_20260930.md`, note nguồn mở V46, các summary/manifest/script V46 liên quan; đối chiếu với nguồn sơ cấp/official/DOI.  
**Mục tiêu:** xác định những claim nào V46 đã đủ mạnh, claim nào còn yếu, và các kiểm định tiếp theo có thể thực hiện bằng dữ liệu hiện có mà **không dùng Sentinel-1 2021 để chọn chỉnh sửa DEM**.  
**Không thực hiện:** không chỉnh DOCX; không dùng kết quả SAR-2021 để chọn threshold/cut/corridor.

## 1. Kết luận ưu tiên

Năm khoảng trống bằng chứng quan trọng nhất, theo thứ tự ưu tiên:

1. **Hydrological conditioning chưa phải vertical validation.** V46 có bằng chứng tốt rằng các chỉnh sửa phục vụ routing được giới hạn và audit được, nhưng chưa có checkpoint cao độ độc lập để chứng minh cao độ vật lý chính xác hơn. HydroSHEDS còn cảnh báo rõ rằng conditioned DEM đã bị thay đổi và có thể không còn đúng cho ứng dụng ngoài suy diễn drainage direction [S1].
2. **OSM/JRC là bằng chứng pre-event nhưng không phải independent validation của chính V46 hiện tại.** OSM lịch sử và JRC đều tham gia candidate/topology; riêng seed 55 còn được preselect từ current OSM rồi mới historical-corroborate. Chúng hỗ trợ provenance và plausibility, không tạo một tập validation độc lập cho 38 ô đã cut.
3. **`REVIEW_APPROVE_BOUNDED` là nhãn thuật toán, không phải xác nhận thực địa hay expert review.** Về khoa học, “bounded” chỉ có nghĩa thay đổi bị giới hạn bởi cap đã định và qua các gate topology/evidence. Đây là risk-control/admissibility class, không phải bằng chứng rằng cao độ mới là đúng.
4. **“407 ô stable” hiện là claim hẹp hơn tên gọi gợi ý.** Ba sensitivity run chỉ thay corridor; các tập Tier A lồng nhau `strict ⊂ base ⊂ wide`, nên intersection 407 ô bằng đúng tập strict 407 ô. Đây là **retention khi nới corridor**, chưa phải robustness với relief, slope, elevation cap, topology, JRC/flow gate hay D8.
5. **Kiểm định tiếp theo mạnh nhất có thể làm ngay là pre-SAR robustness + source holdout + routing diagnostics**, đồng thời sinh topology trực tiếp từ historical core 407 thay vì seed 55 current-OSM-derived. Sau khi khóa toàn bộ rule/hash mới được mở Sentinel-1 2021 để đánh giá cuối.

## 2. Hydrological conditioning và vertical accuracy: cách diễn giải hợp lệ

### 2.1 Claim mạnh có thể bảo vệ

Hydrological conditioning là **biến đổi có chủ đích lên trường cao độ/routing surface nhằm tạo hoặc cải thiện tính liên tục thủy văn**, ví dụ filling hoặc breaching. Lindsay mô tả filling là nâng cao độ trong depression và breaching là carve qua blockage; constrained/selective breaching dùng các giới hạn độ sâu/chiều dài để giảm tác động [S2]. HydroSHEDS gọi riêng một lớp “hydrologically conditioned elevation” và cảnh báo rằng quá trình conditioning đã thay đổi DEM, có thể làm lớp đó không phù hợp cho mục đích ngoài dẫn xuất drainage direction [S1].

Do đó wording hợp lệ cho V46 là:

> **“V46 là routing/elevation surface đã được hydrologically conditioned theo các ràng buộc topology và magnitude đã khóa.”**

Hoặc, nếu muốn sát hơn với thực tế code:

> **“V46 là bản V41 có 38 ô được hạ có kiểm soát để cải thiện tính liên tục routing theo historical hydrography, D8 topology và các constraint đã định.”**

Không có cơ sở hiện tại để đổi nghĩa thành “đã đo lại địa hình” hoặc “cao độ đúng hơn về vật lý”.

### 2.2 Vertical accuracy phải dựa trên reference/checkpoint độc lập

ASPRS/USGS định nghĩa đánh giá vertical accuracy bằng so sánh bề mặt cuối với các checkpoint/reference độc lập; USGS còn yêu cầu checkpoint là một tập độc lập chỉ dùng để đánh giá accuracy, không dùng làm control/calibration [S3, S4]. Điểm này trực tiếp phân biệt hai câu hỏi:

- **Routing question:** sau conditioning, đường thoát nước/topology có hợp lý hơn không?
- **Vertical accuracy question:** cao độ raster có gần cao độ thật tại vị trí độc lập hơn không?

V46 có bằng chứng mạnh hơn cho câu hỏi thứ nhất. Với dữ liệu hiện có, câu hỏi thứ hai **chưa được kiểm định theo nghĩa positional/vertical accuracy chuẩn**.

### 2.3 Copernicus GLO-30: chỉ được dùng thông số nhà sản xuất nếu lineage được khóa

Tài liệu nội bộ cũ gọi DEM nền là **Copernicus DEM GLO-30**; kho dữ liệu cũ cũng có thư mục raw/clip/filter/bound Copernicus. Product Handbook chính thức của Copernicus DEM v5.0 ghi:

- vertical reference: **EGM2008 (EPSG:3855)**;
- GLO-30 grid spacing: 1 arc-second;
- absolute vertical accuracy: **<4 m LE90**;
- relative vertical accuracy: **<2 m** ở slope ≤20%, **<4 m** ở slope >20%;
- các trị số accuracy là thống kê toàn cầu/arithmetic mean và **local deviations can occur** [S5].

Đây là metadata sản phẩm gốc, không tự động trở thành accuracy của V41/V46. Lý do:

- `process_dem.py` cắt giá trị âm về 0, Priority-Flood rồi cộng eastward epsilon gradient `0.001 m/cell` trên raster hợp lệ.
- Audit V46 đã đo V39→V41 thay đổi >0,001 m ở 4.407.900/4.410.000 ô, median khoảng +1,088 m và cực đại +31,497 m.
- V46 sau đó hạ thêm 38 ô, tối đa 2,9625 m.

Vì vậy **không nên lấy LE90 <4 m của raw Copernicus để chứng minh 38 cut là “nằm trong sai số nên đúng”**. Accuracy spec của source không phải tolerance cho phép chỉnh tùy ý, và cũng không chứng minh post-processed product vẫn giữ cùng error distribution.

### 2.4 Khoảng trống cần đóng nếu luận văn muốn nói về vertical accuracy

**Mức mạnh cao nhất:** có survey/GNSS/RTK/benchmark cao độ độc lập với toàn bộ chuỗi tạo V41/V46, đồng nhất vertical datum, rồi tính residual cho V41 và V46 trên checkpoint không dùng để chọn cut.

**Mức trung bình với dữ liệu hiện có:** so sánh chéo với ALOS 12,5 m/SRTM 30 m hoặc DEM độc lập sẵn có. Kết quả chỉ được gọi là **cross-DEM agreement/disagreement**, không phải vertical accuracy vì các DEM khác cũng có error và datum riêng.

**Việc cần làm ngay dù chưa có checkpoint:** tạo một provenance manifest từ raw Copernicus tile → clip/resample → `PhuYen_DEM_30m.asc` → V39 → V41 → V46, lưu hash, resampling, CRS, vertical datum/geoid và mọi transform. Nếu không tái lập được đoạn raw→V39, luận văn chỉ nên nói **“project lineage identifies the source as Copernicus GLO-30”**, không nói đã xác minh đầy đủ nguồn/datum của raster hiện hành.

### 2.5 Nên/không nên viết

**Nên viết:**

> “Hydrological conditioning thay đổi elevation surface để hỗ trợ routing. Các thay đổi V46 vì vậy được diễn giải như flow-enforcement edits có ràng buộc, không phải phép đo lại cao độ thực địa.”

**Không nên viết:**

> “V46 có vertical accuracy tốt hơn V41.”

> “Cut tối đa 2,96 m nhỏ hơn sai số Copernicus nên hợp lệ.”

Hai câu trên cần checkpoint độc lập và chain datum/provenance chặt hơn.

## 3. OSM/JRC pre-event: bằng chứng gì là độc lập, giới hạn gì khi dùng làm validation

### 3.1 OSM historical snapshot: temporal pre-event là claim mạnh

Overpass QL `date` truy vấn trạng thái OSM database tại timestamp quá khứ [S6]. Artifact V46 khóa snapshot `2021-11-25T00:00:00Z`, trước ảnh Sentinel-1 giữ lại ngày 30/11/2021; manifest còn ghi way timestamp muộn nhất 15/06/2021. Vì vậy claim sau là mạnh:

> **“Historical OSM evidence dùng trong V46 tồn tại trong database OSM trước ảnh SAR validation ngày 30/11/2021.”**

Điều này bảo vệ V46 khỏi leakage trực tiếp từ chính ảnh SAR-2021 qua OSM snapshot đó.

### 3.2 Nhưng OSM không phải ground truth hình học/topology

OSM là volunteered/collaborative mapping. Tài liệu OSM tự nêu accuracy/completeness thay đổi theo khu vực, lỗi có thể đến từ source imagery/georeferencing, thiếu coverage, tagging, temporal staleness hoặc mapping error [S7, S8]. Vì vậy:

- OSM centerline support là **map evidence**;
- khoảng cách 1 cell tới OSM là **algorithmic proximity criterion**;
- nó không chứng minh centerline chính xác ±30 m tại Phú Yên;
- nó không chứng minh có cống/cầu/bathymetry tại cell bị cut.

### 3.3 Seed 55: historical corroboration tốt nhưng chưa phải historical selection

Chuỗi hiện tại:

`current OSM legacy stable core -> chọn/freeze 55 tọa độ -> kiểm 55/55 có trong historical stable Tier A`.

Do đó hai claim phải tách:

- **Mạnh:** `55/55` tọa độ frozen đều được historical OSM/HydroRIVERS/Terrain corroborate trước SAR.
- **Yếu/quá mạnh:** “55 seed được sinh độc lập hoàn toàn từ pre-event data.”

Để đạt claim mạnh thứ hai, cần chạy topology trực tiếp từ **historical 407-cell core** (hoặc seed được sinh hoàn toàn từ historical inputs) và khóa rule trước khi xem SAR.

### 3.4 JRC GSW1.3: pre-event nhưng không phải event truth, và phiên bản 1.3 có cảnh báo hiện nay

V46 dùng `JRC_GSW1_3_occurrence_1984_2020`, nên temporal coverage nằm trước sự kiện 2021. JRC Global Surface Water mô tả occurrence là tần suất/độ thường xuyên quan sát **open surface water visible from space** qua chuỗi Landsat; FAQ cũng nhấn mạnh số valid observations là thông tin cần xem khi diễn giải metric [S9, S10]. Pekel et al. là bài gốc của sản phẩm [S11].

Điểm mới rất quan trọng từ trang JRC hiện hành: JRC ghi rõ **Occurrence của versions 1.2–1.4 có inconsistency/error đối với các năm bổ sung**, và v1.5 đã recompute để khôi phục consistency [S9]. V46 dùng v1.3, nên:

- v1.3 vẫn có thể dùng như **historical corroborating evidence**;
- không nên nâng thành “ground truth”;
- nếu sau này kiểm tra lại bằng occurrence corrected, phải coi đó là **robustness check/version sensitivity**, không quay lại điều chỉnh cut sau khi đã nhìn SAR.

### 3.5 JRC hiện cũng không độc lập với topology decision của 38 cut

`v46_topology_paths.py` dùng gate:

`JRC occurrence >=25% within 1 cell OR D8 upstream area >=0.5 km² within 2 cells`.

Vì vậy JRC đã tham gia quyết định admissibility. Nó không thể đồng thời được quảng bá là validation độc lập của cùng decision. Artifact hiện tại còn cho thấy ở 38 ô applied:

- 34 ô có `jrc_occurrence_buffer_max_pct = 0%`;
- 4 ô có max 43%.

Do đó câu “JRC xác nhận 38 cut” là sai. Chính xác hơn:

> **“JRC là một nhánh supplemental evidence trong topology gate; phần lớn applied cells được support qua upstream-area branch chứ không qua JRC occurrence.”**

## 4. D8 `strict / bounded / reject`: ý nghĩa khoa học đúng

### 4.1 `DIRECT_D8_TRACE` chứng minh điều gì

D8 là single-flow-direction scheme: mỗi cell thoát về một trong tám neighbor theo hướng dốc nhất. HydroSHEDS mô tả đúng logic D8 này trong lớp drainage direction [S1]. O'Callaghan & Mark là nguồn kinh điển của raster drainage extraction [S12]. Tarboton chỉ ra giới hạn của các phương pháp ép flow vào tám hướng: **grid bias**, là một lý do phát triển D∞ [S13].

Do đó `24/24 component có DIRECT_D8_TRACE` chứng minh:

> **“trên routing surface V41 và cách mã hóa D8 hiện tại, tìm được cặp anchor upstream/downstream nối trực tiếp theo D8 cho 24 seed components.”**

Nó không chứng minh:

- tuyến chảy ngoài thực địa đi chính xác theo path D8;
- D8 là flow representation duy nhất hợp lý;
- cống/cầu thật tồn tại tại cell cut;
- target linear profile là bathymetry thật.

### 4.2 `AUTO_APPROVE_STRICT`

Theo code V46, một component chỉ vào strict khi qua toàn bộ gate geometry + D8 + supplemental evidence + constrained caps, đồng thời:

- max cut ≤1 m;
- số ô cut ≤4.

Hiện chỉ có **1 component / 1 cut cell** thuộc lớp này. “Strict” vì mức perturbation nhỏ hơn theo rule nội bộ; không phải vì có độ tin cậy thống kê đã đo.

### 4.3 `REVIEW_APPROVE_BOUNDED`

Theo code, bounded cũng phải qua geometry + D8 + supplemental evidence và global constraints, nhưng không đạt strict sub-cap. Global caps là:

- max cut ≤3 m;
- số ô cut ≤8/component;
- path span ≤20 cells;
- max projection offset ≤1 cell;
- JRC≥25% **hoặc** upstream area≥0,5 km².

Hiện có **15 components / 37 cut cells** thuộc lớp bounded.

Ý nghĩa khoa học phù hợp của “bounded”:

> **“candidate passes the stated topology/evidence checks and the magnitude/spatial extent of the imposed DEM perturbation stays within predeclared caps.”**

Đây là cùng triết lý với selective/constrained breaching: giới hạn độ sâu/chiều dài để giảm tác động DEM [S2, S14]. Tuy nhiên **bounded ở V46 là rule riêng của dự án**, không phải một confidence interval hay chuẩn phân loại quốc tế.

Nếu chưa có artifact review thủ công riêng, nên đổi wording trong luận văn từ “review approved” thành:

- `bounded / constraint-admissible class`, hoặc
- “bounded class được áp dụng theo rule/cờ thực thi”.

Không nên viết “15 component đã được chuyên gia phê duyệt” khi chưa có biên bản/QGIS review độc lập.

### 4.4 `REJECT`

Reject là fail-closed theo rule hiện tại. Tám component reject vì geometry/evidence/cut cap không đạt. Đây là điểm mạnh của methodology vì nó cho thấy algorithm có khả năng **không chỉnh sửa** khi evidence/constraint không đủ.

Tuy nhiên reject vẫn là reject theo rule, không có nghĩa terrain gốc chắc chắn đúng tại đó.

## 5. Corridor sensitivity và cách claim “407 ô”

### 5.1 Sự thật toán học của ba run hiện tại

Các run:

| Run | OSM corridor | HydroRIVERS corridor | Tier A |
|---|---:|---:|---:|
| strict | 1 cell = 30 m | 2 cells = 60 m | 407 |
| base | 2 cells = 60 m | 3 cells = 90 m | 1.580 |
| wide | 3 cells = 90 m | 5 cells = 150 m | 4.530 |

Các tham số sau **không đổi** giữa các run:

- relief threshold = 1 m;
- relief window = 5;
- max slope = 5°;
- max elevation = 20 m.

Summary ghi:

- `strict_not_in_base = 0`;
- `base_not_in_wide = 0`.

Nghĩa là `strict ⊆ base ⊆ wide`. Vì thế:

`strict ∩ base ∩ wide = strict = 407 cells`.

Đây là tính chất retention/monotonicity khi **nới corridor**, không phải ba quan sát độc lập cùng hội tụ về 407.

### 5.2 Cách viết 407 ô có thể bảo vệ

**Câu nên dùng:**

> “Ở cấu hình corridor nghiêm ngặt 1 cell OSM / 2 cells HydroRIVERS có 407 Tier-A consensus cells. Toàn bộ 407 cells này vẫn thuộc Tier A khi mở rộng corridor lên 2/3 và 3/5 cells.”

Hoặc ngắn hơn:

> “407 strict-core cells được retained dưới hai mức nới corridor đã thử.”

**Không nên dùng:**

> “Sensitivity analysis chứng minh có 407 ô robust/stable bất kể tham số.”

> “407 ô là tập tối ưu.”

> “407 ô đã được xác nhận bởi ba sensitivity scenario độc lập.”

### 5.3 Nếu vẫn dùng tên `stable core`

Tên artifact `V46_stable_core_20260930` có thể giữ để truy vết kỹ thuật, nhưng trong luận văn nên định nghĩa rõ:

> **“stable-core under tested corridor widening”**

và liệt kê chính xác tham số nào đã/ chưa biến thiên.

### 5.4 Bằng chứng còn thiếu để dùng từ robustness mạnh hơn

Cần sensitivity ít nhất trên các nhóm:

1. OSM/HydroRIVERS corridor **không chỉ ba cặp lồng nhau**;
2. relief threshold;
3. slope cap;
4. elevation cap;
5. topology caps: max cut, max modified cells, path span;
6. supplemental gate: JRC threshold/upstream-area threshold;
7. flow-routing method hoặc ít nhất D8-vs-alternative connectivity check;
8. source holdout/leave-one-source-out.

## 6. Các kiểm định tiếp theo có thể làm bằng dữ liệu hiện có, không dùng Sentinel-1 2021 để chọn chỉnh sửa

Phần này ưu tiên kiểm định có thể làm **trước khi mở SAR holdout**.

### P0 — Sinh topology trực tiếp từ historical 407-core, bỏ selection từ current OSM

Đây là bước tăng độ mạnh evidence lớn nhất.

Hiện `v46_topology_paths.py` nhận `--core` và `--strict-csv`. Có thể chạy topology trên:

- core: `V46_stable_core_20260930/V46_stable_tierA_core.tif` (407 cells, 151 components);
- evidence CSV: historical strict candidate CSV;
- historical OSM snapshot 25/11/2021;
- V41-derived D8/upstream/HAND;
- JRC pre-event.

Kết quả cần báo riêng:

- bao nhiêu/151 components có direct D8 topology;
- bao nhiêu strict/bounded/reject;
- proposal cut count/volume;
- overlap với 55 seed cũ chỉ là **comparison**, không phải selection criterion.

Nếu sau đó chọn một subset, rule phải được khai báo trước và không xem SAR để chọn.

**Giá trị khoa học:** xóa điểm yếu “55 được current-OSM preselect rồi mới historical validate”.

### P1 — Multi-parameter sensitivity thật sự ở candidate stage

`v46_conditioning_dryrun.py` đã expose CLI cho:

- `--corridor-cells`;
- `--hydro-corridor-cells`;
- `--relief-threshold-m`;
- `--relief-window`;
- `--max-slope-deg`;
- `--max-elevation-m`.

Nên preregister một grid vừa phải, ví dụ:

- OSM corridor: 1 / 2 / 3 cells;
- HydroRIVERS: 2 / 3 / 5 cells;
- relief threshold: 0,75 / 1,0 / 1,5 m;
- slope cap: 3 / 5 / 7°;
- max elevation: 15 / 20 / 30 m.

Không nhất thiết chạy full Cartesian 243/729 cases. Có thể chọn một thiết kế cân bằng 27–45 run, nhưng phải khóa danh sách run trước khi xem kết quả SAR.

Metric cần lưu:

- per-cell survival frequency;
- per-component survival frequency;
- Jaccard giữa từng run và baseline;
- số component singleton/multi-cell;
- distribution local relief;
- số candidate chỉ xuất hiện ở một cấu hình;
- rank các cell/component theo stability **chỉ như robustness diagnostic**.

Nếu đặt threshold “robust khi survival ≥80%”, phải nói rõ 80% là **design criterion do nghiên cứu chọn**, không phải ngưỡng vật lý được quan trắc.

### P2 — Sensitivity ở topology/cut stage

`v46_topology_paths.py` đã expose:

- `--max-cut-m`;
- `--max-modified-cells`;
- `--max-path-span-cells`.

Có thể chạy grid pre-SAR như:

- max cut: 1 / 2 / 3 m;
- max cells: 4 / 6 / 8;
- max path span: 10 / 15 / 20 cells.

Mục tiêu không phải tìm tổ hợp cho CSI tốt nhất. Mục tiêu là trả lời:

- component nào chỉ được approve khi cap rất rộng;
- component nào tồn tại ở hầu hết cấu hình;
- 38 applied cells hiện tại có phải nằm trong vùng parameter-sensitive hay không.

Nên báo **transition matrix strict/bounded/reject** qua các cấu hình.

### P3 — Leave-one-source-out / source holdout

Đây là cách tốt nhất để biến OSM/JRC/HydroRIVERS thành validation tương đối độc lập, thay vì vừa dùng chọn vừa dùng xác nhận.

Thiết kế đề xuất:

1. **OSM-held-out:** sinh candidate bằng HydroRIVERS + terrain/flow, sau đó đo khoảng cách/overlap với historical OSM.
2. **HydroRIVERS-held-out:** sinh candidate bằng historical OSM + terrain/flow, sau đó đo overlap/topology agreement với HydroRIVERS.
3. **JRC-held-out:** không dùng JRC trong gate, sinh candidate bằng hydrography + flow; sau đó chỉ dùng JRC occurrence như external corroboration statistic.

Không dùng source held-out để quay lại sửa threshold trong cùng vòng. Nếu thay rule, phải coi là một development iteration mới và giữ một source/period khác làm holdout tiếp theo.

**Giới hạn:** các nguồn global có thể không hoàn toàn statistically independent, nhưng thiết kế này vẫn mạnh hơn việc dùng cùng evidence ở selection và validation.

### P4 — D8-vs-alternative flow routing sensitivity

Từ cùng V41 có thể tạo một flow-routing alternative, ưu tiên D∞ theo Tarboton hoặc một MFD method, rồi hỏi:

- anchor connectivity có còn tồn tại không;
- component classification thay đổi bao nhiêu;
- các component chỉ tồn tại dưới D8 có tập trung theo hướng diagonal/cardinal không.

Tarboton nêu rõ eight-direction routing có grid bias [S13], nên đây là kiểm định khoa học trực tiếp cho sự phụ thuộc vào D8.

Nếu chưa triển khai D∞, ít nhất phải viết limitation rằng topology hiện tại là **D8-specific**.

### P5 — Before/after routing diagnostics trên V41 và V46

Không cần SAR, và có thể chạy ngay:

- số/diện tích depression còn lại quanh 16 applied components;
- fill depth trước/sau;
- direct downstream reachability từ anchor;
- upstream area monotonicity;
- số edge/path có elevation rise downstream;
- thay đổi flow accumulation ở vùng lân cận;
- xác nhận mọi thay đổi nằm đúng 38 audit rows và ngoài đó delta=0.

Đây là **internal process validation**, không phải ground-truth validation. Wording nên là:

> “conditioning improved the specified routing diagnostics under the chosen flow representation.”

Không suy ra “địa hình thật chính xác hơn”.

### P6 — Negative-control / specificity test

Từ V41 và các masks hiện có, tạo matched control cells/components có slope/elevation/local relief tương tự nhưng nằm ngoài hydrography corridor. Chạy cùng obstruction/topology logic và đo tỷ lệ false admissibility.

Nếu algorithm approve nhiều matched controls không gắn với hydrography, rule đang thiếu specificity. Nếu approve rate rất thấp ở controls, đây là bằng chứng process-level tốt mà không cần SAR.

Phải cố định cách sample controls trước khi xem kết quả.

### P7 — Cross-DEM diagnostic với ALOS/SRTM sẵn có

Repo có con trỏ tới ALOS 12,5 m và SRTM 30 m từ giai đoạn cũ. Nếu các file thật còn tồn tại và bao phủ đúng Phú Yên, có thể:

- reproject/resample về cùng grid;
- so V41/V46 residual với từng DEM tại 38 cells và matched neighboring/control cells;
- kiểm tra liệu V46 move closer/farther from consensus của DEM khác.

Chỉ gọi là **cross-product consistency**. Không gọi là vertical validation vì ALOS/SRTM cũng có bias, resolution, acquisition time và vertical datum khác.

### P8 — Freeze protocol trước Sentinel-1

Trước khi mở SAR-2021 để tính CSI/F1/IoU:

1. khóa input hashes;
2. khóa candidate/topology thresholds;
3. khóa strict/bounded/reject rules;
4. khóa lựa chọn output DEM dùng cho validation;
5. lưu manifest và timestamp;
6. sau đó mới chạy SAR metrics một lần như holdout evaluation.

Nếu SAR result khiến thay đổi rule, version sau phải ghi rõ là **SAR-informed development** và không được dùng cùng SAR như independent validation nữa.

## 7. Ma trận claim: mạnh/yếu và wording luận văn

| Claim | Mức bằng chứng hiện tại | Nên viết | Không nên viết |
|---|---|---|---|
| V46 là hydrologically conditioned surface | **Mạnh** | Conditioning có audit, 38 cells, constrained topology/rules | “Địa hình thật đã được hiệu chỉnh chính xác” |
| Vertical accuracy của V46 tốt hơn | **Chưa có** | Chưa đánh giá bằng independent elevation checkpoints | “V46 chính xác cao độ hơn V41” |
| Source là Copernicus GLO-30 | **Trung bình theo lineage nội bộ** | Project documentation identifies Copernicus GLO-30; cần raw→V46 manifest | “Datum/accuracy raw Copernicus đã được chứng nhận cho V46” |
| Historical OSM là pre-event | **Mạnh** | Snapshot 25/11/2021, trước SAR 30/11/2021 | “OSM là ground truth” |
| 55 seed hoàn toàn pre-event selected | **Yếu** | 55/55 historically corroborated | “55 seed sinh hoàn toàn từ historical inputs” |
| JRC là pre-event evidence | **Mạnh về thời gian, vừa về chất lượng** | GSW1.3 1984–2020 làm auxiliary evidence | “JRC ground truth / xác nhận tất cả 38 cut” |
| JRC v1.3 occurrence hoàn toàn ổn định | **Yếu** | Nêu version và known occurrence issue; làm version sensitivity | Bỏ qua warning v1.2–v1.4 của JRC |
| 24/24 có direct D8 topology | **Mạnh trong mô hình D8** | D8-consistent connectivity under V41-derived routing | “Đường dòng thực địa đã được chứng minh” |
| Bounded = đã review thủ công | **Không có artifact** | Constraint-admissible/bounded class applied by rule | “15 bounded components đã được chuyên gia duyệt” |
| 407 cells stable | **Mạnh nhưng hẹp** | 407 strict cells retained under tested corridor widening | “407 robust với mọi tham số/phương pháp” |
| 38 cut cải thiện routing | **Có thể kiểm thêm ngay** | Báo before/after routing diagnostics | Suy ra vertical/field accuracy từ routing alone |

## 8. Wording đề xuất cho luận văn

### 8.1 Đoạn có thể dùng gần như nguyên văn

> DEM V46 được xây dựng như một **hydrologically conditioned routing surface** từ V41. Các thay đổi cao độ được dùng để cưỡng bức tính liên tục thủy văn theo historical hydrography và topology trên raster, với giới hạn về độ sâu cut, số ô thay đổi và chiều dài path. Vì conditioning chủ động làm biến đổi elevation surface, V46 không được diễn giải như phép đo lại cao độ địa hình hay bằng chứng rằng vertical accuracy đã được cải thiện. Việc đánh giá vertical accuracy theo nghĩa trắc địa cần checkpoint cao độ độc lập và thống nhất vertical datum.

> Historical OSM snapshot ngày 25/11/2021 và JRC Global Surface Water 1984–2020 đều có thời gian trước ảnh Sentinel-1 ngày 30/11/2021, nên có giá trị như bằng chứng pre-event. Tuy nhiên các nguồn này cũng tham gia candidate/topology selection, do đó không được xem là independent validation của chính các edits được chọn. JRC occurrence được dùng như auxiliary evidence về open surface water, không phải bathymetry hay event flood extent.

> Sensitivity hiện tại theo corridor cho thấy 407 Tier-A cells ở cấu hình strict vẫn được giữ khi corridor được mở rộng. Vì strict, base và wide là các tập lồng nhau, kết quả này được diễn giải là retention under corridor widening, không phải robustness với mọi tham số của thuật toán.

### 8.2 Một câu nên thêm vào limitations

> Topology V46 hiện được đánh giá bằng D8 single-flow-direction; do D8 có thể chịu grid-direction bias, cần xem kết quả topology là D8-specific cho đến khi được đối chiếu bằng một flow-routing alternative hoặc quan trắc độc lập.

## 9. Thứ tự công việc đề xuất trước khi sửa luận văn chính

1. **P0:** chạy topology trên toàn historical 407-core, không dùng seed 55 current-OSM-derived làm selection.
2. **P1/P2:** chạy sensitivity candidate + topology đa tham số, xuất cell/component survival + transition strict/bounded/reject.
3. **P3:** làm ít nhất một leave-one-source-out analysis, ưu tiên JRC-held-out và OSM-held-out.
4. **P5:** before/after routing diagnostics V41↔V46.
5. **P4:** D8-vs-D∞ nếu có thể; nếu chưa, ghi limitation rõ.
6. **Provenance:** khóa raw DEM source/datum/resampling chain; nếu không đủ, hạ wording về lineage-only.
7. **Freeze** config/hashes/decision rules.
8. **Cuối cùng** mới mở Sentinel-1 2021 để validation; không dùng metric SAR để quay lại chọn edits của version đó.

## 10. Nguồn sơ cấp/official/DOI

### Hydrological conditioning / elevation accuracy

**[S1] HydroSHEDS Technical Documentation v1.4**, mục 5.2 và 5.3. Tài liệu chính thức ghi conditioned DEM đã bị alter và có thể không phù hợp ngoài mục đích drainage direction; cũng mô tả D8 single-flow direction.  
https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf

**[S2] Lindsay, J.B. (2016).** *Efficient hybrid breaching-filling sink removal methods for flow path enforcement in digital elevation models*. Hydrological Processes 30, 846–857.  
https://doi.org/10.1002/hyp.10648

**[S3] USGS Lidar Base Specification — Data Processing and Handling Requirements.** Checkpoints phải là independent set dùng riêng cho vertical accuracy assessment.  
https://www.usgs.gov/ngp-standards-and-specifications/lidar-base-specification-data-processing-and-handling-requirements

**[S4] ASPRS Positional Accuracy Standards for Digital Geospatial Data, Edition 2.** Vertical accuracy được báo bằng RMSEV/NVA/VVA theo reference/checkpoint framework.  
https://asprs.org/Main/Main/Standards/Positional-Accuracy-Standards.aspx

**[S5] Copernicus DEM Product Handbook v5.0.** GLO-30, vertical datum EGM2008, nominal absolute vertical accuracy <4 m LE90; local deviations can occur.  
https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf  
Dataset landing page/DOI: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM ; https://doi.org/10.5270/ESA-c5d3d65

### OSM / JRC pre-event evidence

**[S6] OpenStreetMap Wiki — Overpass QL `date`.** `date` trả database state tại thời điểm quá khứ.  
https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL#Date

**[S7] OpenStreetMap Wiki — Accuracy.** Mô tả các nguồn sai số positional/map accuracy và nhu cầu kiểm tra source.  
https://wiki.openstreetmap.org/wiki/Accuracy

**[S8] OpenStreetMap Wiki — Limitations / Completeness.** Nêu giới hạn completeness, staleness và volunteer-update model.  
https://wiki.openstreetmap.org/wiki/Limitations  
https://wiki.openstreetmap.org/wiki/Completeness

**[S9] European Commission JRC — Global Surface Water Data Access.** Trang official; hiện ghi rõ issue của Occurrence v1.2–v1.4 và recomputation trong v1.5.  
https://global-surface-water.appspot.com/download

**[S10] European Commission JRC — Global Surface Water FAQ.** Mô tả open water, valid observations và ý nghĩa các layers.  
https://global-surface-water.appspot.com/faq

**[S11] Pekel, J.-F. et al. (2016).** *High-resolution mapping of global surface water and its long-term changes*. Nature 540, 418–422.  
https://doi.org/10.1038/nature20584

### Flow topology / D8 / bounded edits

**[S12] O'Callaghan, J.F. & Mark, D.M. (1984).** *The extraction of drainage networks from digital elevation data*. Computer Vision, Graphics, and Image Processing 28(3), 323–344.  
https://doi.org/10.1016/S0734-189X(84)80011-0

**[S13] Tarboton, D.G. (1997).** *A new method for the determination of flow directions and upslope areas in grid digital elevation models*. Water Resources Research 33(2), 309–319. Abstract nêu hạn chế grid bias của flow directions bị giới hạn vào tám hướng.  
https://doi.org/10.1029/96WR03137

**[S14] Lindsay, J.B. — author preprint / algorithm description.** Selective/constrained breaching dùng maximum breach depth/length như constraints.  
https://jblindsay.github.io/ghrg/pubs/Lindsay-HP-preprint.pdf

**[S15] Lindsay, J.B. (2016).** *The practice of DEM stream burning revisited*. Earth Surface Processes and Landforms 41(5), 658–668. Mismatch scale giữa vector hydrography và raster DEM có thể tạo topology error.  
https://doi.org/10.1002/esp.3888

**[S16] Yamazaki, D. et al. (2019).** *MERIT Hydro: A High-Resolution Global Hydrography Map Based on Latest Topography Dataset*. Water Resources Research 55, 5053–5073. Dùng DEM + GSW + OSM để xây hydrologically adjusted elevation/flow direction; không biến adjusted elevation thành surveyed terrain.  
https://doi.org/10.1029/2019WR024873

## 11. Bằng chứng cục bộ V46 đã đọc

- `V46_Nghien_cuu_bo_sung_cho_do_an_20260930.md`
- `V46_Nghien_cuu_hydro_conditioning_nguon_mo_20260930.md`
- `05-Du-lieu-GIS/process_dem.py`
- `v46_conditioning_dryrun.py`
- `v46_consolidate_sensitivity.py`
- `v46_validate_seed55.py`
- `v46_topology_paths.py`
- `v46_apply_conditioning.py`
- `v46_verify_final.py`
- `V46_stable_core_20260930/V46_stable_core_summary.json`
- `V46_seed55_historical_validated_20260930/V46_seed55_validation_summary.json`
- `V46_topology_20260930/V46_topology_summary.json`
- `V46_audit_20260930/V46_conditioning_summary.json`
- `V46_audit_20260930/V46_final_verification.json`
- `V46_hydro_evidence_20260930/V46_hydro_evidence_summary.json`
- `V46_dryrun_sensitivity/strict_1_2/V46_dryrun_summary.json`
- `V46_dryrun_20260930/V46_dryrun_summary.json`
- `V46_dryrun_sensitivity/wide_3_5/V46_dryrun_summary.json`

## 12. Kết luận cuối cho người viết luận văn

V46 hiện đã đủ tốt để bảo vệ một luận điểm **methodological**: chỉnh sửa DEM có audit, giới hạn tác động, dựa trên hydrography pre-event và topology, không dùng trực tiếp Sentinel-1 2021 trong candidate/topology/apply. Điểm cần tránh là biến luận điểm đó thành claim **measurement accuracy** hoặc **independent validation** rộng hơn bằng chứng.

Nếu chỉ làm thêm một nhánh trước khi chốt luận văn, ưu tiên: **historical 407-core topology → multi-parameter sensitivity → leave-one-source-out → freeze → SAR holdout**. Chuỗi này trực tiếp xử lý ba phản biện khó nhất hiện nay: selection leakage của seed 55, “stable 407” còn quá hẹp, và việc OSM/JRC đang vừa tham gia selection vừa bị dùng như validation.
