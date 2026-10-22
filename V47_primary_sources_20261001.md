# V47 — Primary-source memo cho BG_Flood Phú Yên

**Ngày:** 01/10/2026  
**Phạm vi:** chỉ dùng nguồn sơ cấp/high-trust cho 4 câu hỏi: hydrological conditioning và vertical accuracy; JRC GSW + historical OSM; diễn giải D8 strict/bounded/reject; sensitivity/corridor stability của 407 ô.  
**Nguyên tắc:** phân biệt rõ (a) bằng chứng từ nguồn ngoài, (b) suy luận khoa học áp vào BG_Flood, và (c) kết quả thực nghiệm nội bộ V47.  
**Không thực hiện:** không sửa DOCX; không sửa bất kỳ script V47 nào.

## Kết luận ngắn

1. **V41/V46 nên được gọi là hydrologically conditioned routing/elevation surface**, không phải DEM đã được “đo lại” hay đã chứng minh vertical accuracy tốt hơn. Priority-Flood và các thuật toán xử lý flat/depression chủ động thay đổi cao độ để tạo hướng thoát nước; đó là thao tác phục vụ routing. [S3][S4][S5]
2. **Nguồn Copernicus GLO-30 của raster nền hiện đã được khóa mạnh hơn trước:** bốn tile local khớp các object công khai và tái tạo `PhuYen_DEM_30m.tif` 4.410.000/4.410.000 ô, max absolute difference = 0 m. Tuy nhiên thông số vertical accuracy của raw Copernicus không tự động truyền sang V41/V46 sau clip/fill/epsilon/cut. [S1][S2]
3. **Epsilon của project là một global eastward ramp, không phải chỉ xử lý các flat.** `process_dem.py` cộng 0,001 m mỗi cột từ Đông sang Tây cho mọi ô hợp lệ; với 2.100 cột, offset nhân tạo cực đại là 2,099 m. Vì vậy không nên mô tả V41 như raw Copernicus có “thay đổi không đáng kể 0,001 m”. Đây là một deterministic routing bias do project thêm vào.
4. **JRC GSW1.3 1984–2020 là pre-event evidence nhưng không phải event ground truth, bathymetry hay vertical validation.** Occurrence là tần suất surface-water detection trong các valid Landsat observations; số valid observations ảnh hưởng độ tin cậy. JRC hiện còn ghi rõ Occurrence v1.2–v1.4 có lỗi/inconsistency ở các năm bổ sung và đã được recompute ở v1.5. [S6][S7][S8]
5. **Historical OSM `[date:]` chứng minh trạng thái database tại một thời điểm quá khứ**, không chứng minh bản đồ đầy đủ hay vị trí waterway chính xác tuyệt đối tại Phú Yên. OSM tự ghi nhận accuracy/completeness thay đổi và dữ liệu có thể stale hoặc thiếu. [S9][S10][S11]
6. **D8 direct trace chỉ là model-consistent connectivity.** D8 ép mỗi ô về một trong tám hướng; Tarboton chỉ ra hạn chế grid-direction bias của các phương pháp bị giới hạn vào tám hướng. Vì vậy “direct D8 trace” không đồng nghĩa đường dòng thực địa đã được chứng minh. [S12][S13]
7. **`strict / bounded / reject` là class nội bộ của BG_Flood, không phải chuẩn confidence quốc tế.** “bounded” chỉ nên claim là candidate qua các gate đã khai báo và mức perturbation nằm trong các cap dự án; không được viết là expert-approved, field-validated hay “khả năng đúng cao”.
8. **407 ô không còn nên gọi là robust/stable theo nghĩa rộng.** Sensitivity V47 trên 11 cấu hình cho thấy chỉ 82/407 ô tồn tại trong cả 11 cấu hình; 390/407 tồn tại ít nhất 9/11. Survival frequency là robustness diagnostic trong design đã thử, không phải xác suất đúng hay confidence level.

---

## 1. Hydrological conditioning / Priority-Flood + epsilon slope cho phép claim gì?

### 1.1 Nguồn raw Copernicus GLO-30: claim nào hiện đã khóa được

Copernicus DEM Product Handbook v5.0 ghi GLO-30 có vertical reference **EGM2008 (EPSG:3855)**, grid spacing **1 arc-second**, absolute vertical accuracy **<4 m LE90**, relative vertical accuracy **<2 m ở slope ≤20% và <4 m ở slope >20%**. Handbook cũng nói các accuracy statistics là giá trị trung bình trên phạm vi toàn cầu và **local deviations can occur**. [S1]

Handbook mô tả Copernicus DEM là **Digital Surface Model (DSM)**, vì vậy raster nguồn không đồng nghĩa bare-earth DTM và có thể phản ánh vật thể trên bề mặt ở nơi thích hợp. Tài liệu cũng cảnh báo hydrological consistency không được bảo đảm cho các sản phẩm GLO-30/GLO-90 đã qua resampling. Hai điểm này càng giới hạn việc dùng raw DEM như “ground truth địa hình thủy văn”. [S1]

Copernicus Data Space công bố DOI chính thức cho GLO-30/GLO-90 là **10.5270/ESA-c5d3d65**. [S2]

Audit nội bộ `V47_copernicus_provenance_20261001.json` đã chứng minh:

- 4 tile local trùng kích thước và ETag/MD5 với các object Copernicus GLO-30 công khai;
- reprojection về EPSG:32649, bilinear, bounds 270000–333000 / 1415000–1478000, shape 2100×2100;
- tái tạo `05-Du-lieu-GIS/PhuYen_DEM_30m.tif` **4.410.000/4.410.000 ô exact-equal**, max abs diff **0,0 m**.

**Claim được phép:**  
> “Raster nền của project được tái tạo chính xác từ bốn tile Copernicus DEM GLO-30 đã khóa hash/URL.”

**Claim chưa được phép:**  
> “V41/V46 vẫn có absolute vertical accuracy <4 m LE90.”

Lý do là specification <4 m thuộc **sản phẩm Copernicus**, trong khi V41/V46 đã bị biến đổi tiếp bởi project. [S1][S3][S4]

### 1.2 Priority-Flood thay đổi DEM để bảo đảm drainage, không phải để chứng minh elevation truth

Barnes et al. mô tả Priority-Flood là thuật toán **fill depressions** trong DEM; kết quả sau fill không còn depression/digital dam và mọi cell được bảo đảm có khả năng drain theo representation của thuật toán. Bài báo cũng nêu Priority-Flood có thể được mở rộng để xác định flow directions bằng incremental elevation changes hoặc carving. [S3]

Lindsay mô tả hydrologic flow enforcement gồm:

- **filling:** nâng cao độ trong depression;
- **breaching:** carve qua blockage;
- **hybrid methods:** kết hợp hai cách.

Đây là các phép xử lý để phục vụ hydrological flow routing và chúng có thể gây thay đổi đáng kể lên DEM. [S5]

**Suy luận cho BG_Flood:** Priority-Flood cho phép nói rằng project đã tạo một surface thuận lợi hơn cho flow routing theo giả thiết thuật toán. Nó **không cung cấp checkpoint cao độ độc lập**, nên không thể tự nó chứng minh physical elevation accuracy tốt hơn.

### 1.3 Flat-resolution / epsilon: gradient nhân tạo phục vụ drainage direction

Garbrecht & Martz (1997) chỉ ra flat surfaces khiến drainage direction không xác định; giải pháp của họ là **modify flat-surface elevations** để áp hai gradient, một gradient đi khỏi higher terrain và một gradient đi về lower terrain. [S4]

Barnes, Lehman & Mulla (2014) tiếp tục hướng này: flow trên flat được xác định bằng cách superimpose gradient đi khỏi higher terrain và đi về lower terrain, với mục đích tạo drainage field phù hợp hơn. [S14]

Điểm quan trọng là các nguồn trên mô tả **artificial gradients để giải quyết flow routing trên flats**. Chúng không nói rằng các increment nhân tạo là phép đo địa hình mới.

### 1.4 Implementation của BG_Flood khác đáng kể với “epsilon chỉ trên flats”

`05-Du-lieu-GIS/process_dem.py` thực hiện:

1. clip mọi elevation âm về 0;
2. Priority-Flood 8-neighbor;
3. cộng gradient:

```python
epsilon = 0.001
gradient[:, c] = epsilon * (ncols - 1 - c)
final_dem = filled_dem + gradient
```

Code comment ban đầu nói “only apply this to flat areas”, nhưng implementation thực tế cộng gradient cho **mọi valid cell**. Với 2.100 cột, tổng offset nhân tạo từ cột Đông nhất tới cột Tây nhất là **2,099 m**.

Vì vậy cách diễn giải khoa học an toàn là:

> “V41 là hydrologically conditioned routing surface: negative elevations were clipped, depressions were filled, and a deterministic eastward epsilon ramp was imposed to prevent unresolved flats / enforce an eastward drainage preference.”

Không nên viết:

> “V41 chỉ được chỉnh 0,001 m nên không ảnh hưởng vertical accuracy.”

0,001 m là **increment giữa hai cột kề nhau**, không phải maximum total perturbation.

### 1.5 Vertical accuracy: giới hạn claim

Copernicus Handbook cho accuracy của source product bằng reference-data validation; Priority-Flood/flat-routing literature mô tả biến đổi DEM phục vụ drainage. Hai loại bằng chứng trả lời hai câu hỏi khác nhau. [S1][S3][S4][S5]

Do đó:

- **Có thể claim:** routing consistency / sink removal / path connectivity dưới representation đã chọn.
- **Không thể claim chỉ từ conditioning:** V41/V46 “cao độ thật chính xác hơn”, “vertical accuracy improved”, hoặc cut nằm trong LE90 nên “đúng”.
- **Nếu cần claim vertical accuracy:** phải có reference elevation/checkpoint độc lập và cùng vertical datum; cross-DEM agreement chỉ nên gọi là cross-product consistency.

---

## 2. JRC GSW 1984–2020 và historical OSM: dùng làm evidence/validation đến đâu?

### 2.1 JRC GSW1.3 1984–2020: đúng là pre-event

JRC Data Access page liệt kê `JRC/GSW1_3/GlobalSurfaceWater` là asset **1984–2020**. [S7]

Với sự kiện/Sentinel-1 tháng 11/2021, GSW1.3 không chứa quan sát 2021 và vì vậy có thể dùng như **temporal pre-event evidence**.

### 2.2 Occurrence là long-term open-surface-water frequency

JRC Data Users Guide định nghĩa Water Occurrence là tần suất nước hiện diện trên bề mặt qua chuỗi Landsat; occurrence được tính từ water detections / valid observations theo tháng rồi tổng hợp dài hạn. Guide cũng nêu số observations và valid observations có thể dùng như proxy cho confidence, và precision của metric tăng khi số valid observations tăng. [S6]

Do đó occurrence:

- **có thể hỗ trợ:** water persistence/history, plausibility của river/lake/wet-channel context;
- **không trực tiếp đo:** bathymetry, culvert/bridge opening, channel-bed elevation, water depth, discharge, hay flood extent riêng của 11/2021.

### 2.3 Cảnh báo version 1.3 là material, phải ghi trong luận văn

Trang JRC hiện hành nêu:

- 1984–2015 v1.0 là **version of record** đã được validate cho bài Nature 2016;
- các update sau 2015 không trải qua cùng validation như original dataset;
- **Occurrence v1.2–v1.4** có inconsistency/error do các năm bổ sung không được xử lý hoàn toàn nhất quán với phép tính occurrence gốc;
- v1.5 đã recompute các năm đó để khôi phục consistency. [S7]

Vì BG_Flood dùng **GSW1.3 1984–2020**, cách viết nên là:

> “JRC GSW1.3 occurrence was used as pre-event auxiliary evidence; JRC now documents an occurrence-processing inconsistency in versions 1.2–1.4, so GSW1.3 is not treated as ground truth and should be checked against corrected v1.5 as a version-sensitivity test.”

### 2.4 Historical OSM snapshot chứng minh database state, không chứng minh field truth

Overpass QL `date` trả kết quả dựa trên trạng thái OSM database ở timestamp được chỉ định. Vì vậy snapshot 25/11/2021 chứng minh object/tag/geometry tương ứng **đã tồn tại trong database OSM tại thời điểm đó**. [S9]

Nó không tự chứng minh:

- feature đã tồn tại ngoài thực địa chính xác từ ngày nào;
- centerline chính xác ở mức ±1 cell;
- mapping đầy đủ;
- waterway tag đúng và cập nhật cho mọi nhánh.

OSM Wiki tự nêu accuracy/completeness khác nhau theo vùng, map có thể stale, thiếu coverage và có positional errors từ GPS/imagery/georeferencing. [S10][S11]

### 2.5 Selection evidence không đồng thời là independent validation

Nếu historical OSM/JRC đã tham gia:

- tạo candidate;
- gate topology;
- quyết định strict/bounded/reject;

thì cùng evidence đó không nên được gọi là **independent validation** của chính candidate/decision đã chọn.

Wording nên dùng:

> “pre-event corroborating / admissibility evidence”

thay vì:

> “independent ground-truth validation”.

### 2.6 JRC ở topology gate hiện tại không xác nhận toàn bộ cut

Rule nội bộ yêu cầu:

`JRC occurrence >=25% within 1 cell OR D8 upstream area >=0.5 km² within 2 cells`.

Vì đây là OR-gate, candidate có thể qua hoàn toàn nhờ upstream-area branch. Vì vậy không được viết “JRC xác nhận tất cả candidate/cut”.

---

## 3. Diễn giải strict / bounded / reject trong topology D8

### 3.1 D8 cho claim model-consistency, không cho claim physical truth

O'Callaghan & Mark (1984) là nền tảng cho raster drainage extraction từ gridded elevations. [S12]

Tarboton (1997) chỉ rõ các phương pháp giới hạn flow vào **tám hướng** có thể tạo **grid bias**; D∞ được đề xuất để giảm hạn chế đó. [S13]

Do đó:

> “DIRECT_D8_TRACE exists”

chỉ nên diễn giải:

> “A connected path exists under the chosen V41-derived D8 routing representation.”

Không nên suy ra:

> “Đường dòng thực địa/cống/kênh thật đã được chứng minh.”

### 3.2 Strict / bounded / reject là project-specific decision classes

Trong `v47_topology_paths.py`, class được tạo từ tổ hợp:

- historical OSM projection proximity;
- direct D8 trace;
- supplemental JRC/upstream-area evidence;
- maximum cut;
- maximum modified cells;
- path span;
- strict sub-cap.

Đây là **rule của BG_Flood**, không phải taxonomy chuẩn trong O'Callaghan/Mark, Tarboton, Priority-Flood hay Lindsay.

### 3.3 Cách diễn giải khoa học cho từng class

**AUTO_APPROVE_STRICT**

> Candidate qua toàn bộ gate và đồng thời nằm trong strict perturbation caps của project.

Có thể nói “strict under the project rules”. Không nên nói “high-confidence truth” nếu chưa có calibration/validation tương ứng.

**REVIEW_APPROVE_BOUNDED**

> Candidate qua topology/evidence gates và perturbation vẫn nằm trong bounded global caps, nhưng không đạt strict sub-cap.

Tên phù hợp trong luận văn:

- `bounded / constraint-admissible`;
- “bounded class under predeclared project constraints”.

Không nên viết:

- “đã được chuyên gia duyệt”;
- “đã kiểm chứng ngoài thực địa”;
- “confidence 95%”;
- “gần chắc chắn đúng”.

Lindsay cho thấy constrained/selective breaching có ý nghĩa là **giới hạn mức can thiệp** để tránh tác động quá lớn lên DEM, chứ không biến giới hạn đó thành một confidence interval về truth. [S5]

**REJECT**

> Candidate không qua một hoặc nhiều gate/cap đã định.

Reject nghĩa là “không admissible dưới rule hiện tại”, không có nghĩa terrain gốc chắc chắn đúng.

### 3.4 Kết quả mới: topology trực tiếp từ historical 407-core

`V47_topology_historical407_20261001/V46_topology_summary.json`:

- seed cells: **407**;
- components: **151**;
- direct D8 topology: **149/151**;
- strict: **13**;
- bounded: **81**;
- reject: **57**;
- strict proposed cut cells: **18**;
- strict proposed cut volume: **11.438,46 m³**;
- `dem_modified = false`;
- `seed_current_osm_used_as_evidence = false`;
- `sentinel1_2021_used = false`.

Kết quả này mạnh hơn seed-55 về provenance vì topology được sinh trực tiếp từ **historical strict Tier-A core**. Nhưng 149/151 direct traces vẫn chỉ là D8-consistency; 57/151 components bị reject chứng minh rằng direct trace một mình chưa đủ để approve.

---

## 4. Sensitivity / corridor stability: báo cáo thế nào để không phóng đại 407 ô

### 4.1 Ba corridor lồng nhau trước đây chỉ chứng minh retention khi nới corridor

Ba run cũ:

- strict 1/2 cells → 407;
- base 2/3 cells → 1.580;
- wide 3/5 cells → 4.530.

Do các rule corridor được nới đơn điệu và các tập thỏa mãn `strict ⊆ base ⊆ wide`, intersection bằng 407 là hệ quả của nesting. Nó **không phải ba phép thử độc lập cùng hội tụ về 407**.

Wording an toàn:

> “407 baseline strict-corridor cells were retained under the two tested corridor widenings.”

### 4.2 Sensitivity V47 11 cấu hình cho thấy robustness thực sự không đồng nhất

`V47_candidate_sensitivity_20261001/V47_candidate_sensitivity_summary.json` dùng 11 cấu hình, thay riêng:

- relief threshold;
- relief window;
- slope cap;
- elevation cap;
- OSM corridor;
- HydroRIVERS corridor;

và **không dùng Sentinel-1 2021 để selection**.

Kết quả:

- baseline: **407 cells / 151 components**;
- intersection cả 11 run: **82 cells = 20,15% baseline**, 37 components;
- sống **≥9/11**: **390 cells = 95,82% baseline**, 150 components;
- sống **≥10/11**: **284 cells = 69,78% baseline**;
- union across all runs: **1.714 cells**;
- baseline survival frequency:
  - 8/11: 17 cells;
  - 9/11: 106 cells;
  - 10/11: 202 cells;
  - 11/11: 82 cells.

Các perturbation làm giảm retention mạnh nhất trong design hiện tại:

- relief threshold 1,5 m: **233/407 = 57,25%**;
- slope cap 3°: **250/407 = 61,43%**;
- elevation cap 15 m: **339/407 = 83,29%**;
- relief window 3: **341/407 = 83,78%**.

Các run nới điều kiện giữ 100% baseline nhưng thêm candidate mới, ví dụ corridor 2/2 tạo 1.063 Tier-A cells và Jaccard với baseline chỉ 0,383. Điều đó cho thấy **retention 100% không đồng nghĩa overall set stability cao**.

### 4.3 Cách báo 407 ô

Nên viết:

> “The baseline strict configuration contains 407 Tier-A cells. Across 11 pre-SAR candidate-stage sensitivity configurations, 82/407 cells survived all configurations and 390/407 survived at least 9/11 configurations.”

Hoặc:

> “407 is the baseline strict candidate set; robustness is reported by per-cell survival frequency rather than by labeling all 407 cells as stable.”

Không nên viết:

> “407 ô đã được chứng minh robust.”

> “95,82% là confidence xác suất.”

> “390 ô có xác suất đúng ≥81,8%.”

11 cấu hình không phải random sample từ một probability distribution của parameter uncertainty; survival count chỉ là **sensitivity diagnostic trong design đã thử**.

### 4.4 Nên báo sensitivity bằng 5 metric tối thiểu

Cho mọi bảng/figure sensitivity nên báo:

1. exact parameter values của từng run;
2. Tier-A cell count và component count;
3. baseline retained count + %;
4. Jaccard với baseline;
5. per-cell survival frequency + intersection/union.

Nếu chọn threshold kiểu “robust = ≥9/11”, phải ghi rõ:

> “≥9/11 là reporting/design threshold do nghiên cứu chọn, không phải physical or statistical confidence threshold.”

### 4.5 Corridor stability phải tách khỏi parameter robustness

Hai câu khác nhau:

- **corridor retention:** baseline 407 được giữ khi chỉ nới corridor;
- **multi-parameter robustness:** chỉ 82/407 sống qua toàn bộ 11 cấu hình.

Không nên dùng kết quả corridor-only để đại diện cho relief/slope/elevation/topology robustness.

---

## 5. Ma trận claim cho luận văn

| Claim | Có thể bảo vệ? | Wording đề xuất | Không nên viết |
|---|---|---|---|
| Nguồn raw là Copernicus GLO-30 | **Có, mạnh** | 4 public GLO-30 tiles reproduce local base raster exactly | “V46 vẫn giữ nguyên accuracy spec raw” |
| V41 là hydrologically conditioned | **Có** | depression filling + deterministic eastward routing ramp | “đã đo lại địa hình” |
| Priority-Flood bảo đảm drainage trong model | **Có** | depression-free / model-drainable routing surface | “cao độ vật lý đúng hơn” |
| Epsilon 0,001 m là nhỏ không đáng kể | **Không nên nói như vậy** | 0,001 m là per-column increment; global ramp reaches 2,099 m | “max perturbation chỉ 0,001 m” |
| Copernicus <4 m LE90 áp cho V46 | **Không** | chỉ cite cho raw product specification | “cut <4 m nên hợp lệ” |
| JRC GSW1.3 là pre-event evidence | **Có** | long-term historical surface-water occurrence evidence | “event ground truth / bathymetry” |
| JRC1.3 là independent validation | **Không nếu đã dùng trong gate** | auxiliary/corroborating evidence | “JRC xác nhận các cut” |
| Historical OSM là pre-event DB state | **Có** | geometry/tag existed in OSM DB by snapshot date | “field truth chính xác ±30 m” |
| Direct D8 trace | **Có trong model** | D8-consistent connectivity on V41 routing representation | “đường dòng thật đã chứng minh” |
| Strict | **Có, rule-specific** | passes all gates + strict perturbation caps | “high-confidence truth” |
| Bounded | **Có, rule-specific** | passes gates within bounded project caps | “expert approved / statistically validated” |
| Reject | **Có, rule-specific** | fails at least one declared gate/cap | “terrain gốc chắc chắn đúng” |
| 407 stable | **Phải hạ wording** | baseline strict set; report survival frequencies | “407 robust với mọi tham số” |
| 390 cells ≥9/11 | **Có như diagnostic** | retained in at least 9 of 11 tested configs | “95,82% confidence/probability” |

---

## 6. Wording đề xuất dùng trực tiếp trong luận văn

### Hydrological conditioning

> “DEM dùng cho routing đã được hydrologically conditioned. Priority-Flood được dùng để loại các depression theo representation raster, sau đó project áp một eastward epsilon ramp để tránh các vùng phẳng không có hướng thoát. Các thao tác này chủ động làm thay đổi elevation values nhằm phục vụ flow routing, vì vậy sản phẩm conditioned không được diễn giải như phép đo lại cao độ thực địa hay bằng chứng rằng vertical accuracy đã được cải thiện.”

### JRC/OSM

> “Historical OSM và JRC Global Surface Water được dùng như pre-event corroborating evidence. Historical OSM phản ánh trạng thái database tại snapshot date; JRC occurrence phản ánh tần suất open surface water trên chuỗi Landsat valid observations. Hai nguồn này không được xem là field ground truth, và khi đã tham gia candidate/topology gating thì không được dùng đồng thời như independent validation của chính decision đó.”

### D8 class

> “Strict, bounded và reject là các decision classes do nghiên cứu định nghĩa. Strict và bounded đều yêu cầu topology/evidence gates; bounded chỉ cho phép perturbation lớn hơn trong các cap đã khai báo. Các nhãn này biểu diễn admissibility dưới rule của project, không phải confidence interval hay expert/field validation.”

### Sensitivity

> “407 cells là baseline strict candidate set. Trong 11 sensitivity configurations không dùng Sentinel-1 2021 để selection, 82/407 cells tồn tại ở toàn bộ cấu hình và 390/407 tồn tại ở ít nhất 9/11 cấu hình. Các survival frequencies được dùng như robustness diagnostics trong parameter design đã thử, không được diễn giải như xác suất đúng.”

---

## 7. Nguồn sơ cấp / high-trust

**[S1] Copernicus DEM Product Handbook v5.0 (official PDF).** CRS, EGM2008 vertical reference, GLO-30 spacing, LE90 specifications, global-mean/local-deviation caveat.  
https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf

**[S2] Copernicus Data Space — Copernicus DEM collection.** Official dataset landing page and DOI 10.5270/ESA-c5d3d65.  
https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM  
https://doi.org/10.5270/ESA-c5d3d65

**[S3] Barnes, R.; Lehman, C.; Mulla, D. (2014). Priority-Flood: An optimal depression-filling and watershed-labeling algorithm for digital elevation models. Computers & Geosciences 62:117–127.**  
https://doi.org/10.1016/j.cageo.2013.04.024

**[S4] Garbrecht, J.; Martz, L.W. (1997). The assignment of drainage direction over flat surfaces in raster digital elevation models. Journal of Hydrology 193:204–213.** Artificial gradients are imposed on flat surfaces to create drainage.  
https://doi.org/10.1016/S0022-1694(96)03138-1

**[S5] Lindsay, J.B. (2016). Efficient hybrid breaching-filling sink removal methods for flow path enforcement in digital elevation models. Hydrological Processes 30:846–857.**  
https://doi.org/10.1002/hyp.10648

**[S6] European Commission JRC — Global Surface Water Data Users Guide v4 (2021).** Official definition of occurrence, valid observations and metadata confidence proxies.  
https://storage.googleapis.com/global-surface-water/downloads_ancillary/DataUsersGuidev2021.pdf

**[S7] European Commission JRC — Global Surface Water Data Access.** Official asset/version table; warning that Occurrence v1.2–v1.4 added years were not processed fully consistently with original occurrence; v1.5 recomputed them.  
https://global-surface-water.appspot.com/download

**[S8] Pekel, J.-F.; Cottam, A.; Gorelick, N.; Belward, A.S. (2016). High-resolution mapping of global surface water and its long-term changes. Nature 540:418–422.**  
https://doi.org/10.1038/nature20584

**[S9] OpenStreetMap Wiki — Overpass QL, `date` setting.** Historical query returns OSM database state as of specified timestamp.  
https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL#Date

**[S10] OpenStreetMap Wiki — Accuracy.** First-party documentation of positional/source/georeferencing error issues.  
https://wiki.openstreetmap.org/wiki/Accuracy

**[S11] OpenStreetMap Wiki — Limitations / Completeness.** First-party documentation that completeness and freshness vary and volunteer updates can lag real-world change.  
https://wiki.openstreetmap.org/wiki/Limitations  
https://wiki.openstreetmap.org/wiki/Completeness

**[S12] O'Callaghan, J.F.; Mark, D.M. (1984). The extraction of drainage networks from digital elevation data. Computer Vision, Graphics, and Image Processing 28(3):323–344.**  
https://doi.org/10.1016/S0734-189X(84)80011-0

**[S13] Tarboton, D.G. (1997). A new method for the determination of flow directions and upslope areas in grid digital elevation models. Water Resources Research 33(2):309–319.** Notes grid bias from routing restricted to eight directions.  
https://doi.org/10.1029/96WR03137

**[S14] Barnes, R.; Lehman, C.; Mulla, D. (2014). An efficient assignment of drainage direction over flat surfaces in raster digital elevation models. Computers & Geosciences 62:128–135.**  
https://doi.org/10.1016/j.cageo.2013.01.009  
Author manuscript: https://arxiv.org/abs/1511.04433

**[S15] Lindsay, J.B. (2016). The practice of DEM stream burning revisited. Earth Surface Processes and Landforms 41(5):658–668.** Documents topological errors from scale mismatch between vector hydrography and raster DEMs.  
https://doi.org/10.1002/esp.3888

---

## 8. Local evidence / artifacts dùng để nối nguồn với BG_Flood

- `05-Du-lieu-GIS/process_dem.py` — Priority-Flood + global eastward epsilon ramp.
- `V47_copernicus_provenance_20261001.json` — exact raw GLO-30 provenance/reproduction.
- `V47_lineage_audit_20261001.json` — V41 numerical reproduction and inherited edit audit.
- `V47_topology_historical407_20261001/V46_topology_summary.json` — historical 407-core D8 dry run.
- `V47_candidate_sensitivity_design_20261001.json` — declared 11-run sensitivity design.
- `V47_candidate_sensitivity_20261001/V47_candidate_sensitivity_summary.json` — survival/Jaccard/intersection results.
- `v47_topology_paths.py` — strict/bounded/reject project rules.
- `v47_consolidate_candidate_sensitivity.py` — survival-frequency consolidation.

## 9. Kết luận dùng cho hội đồng

Luận điểm mạnh nhất hiện nay không phải “V46 có cao độ đúng hơn”, mà là:

> **BG_Flood đã xây dựng một hydrologically conditioned routing surface có provenance raw Copernicus được khóa, sử dụng pre-event hydrographic evidence, áp các topology/perturbation constraints fail-closed, và đã lượng hóa sensitivity của candidate set trước khi dùng Sentinel-1 2021 làm holdout.**

Giới hạn phải nói song song:

> **Conditioning làm thay đổi elevation values, D8 có representation/grid-bias limitations, JRC/OSM không phải ground truth và 407 là baseline candidate set chứ không phải 407 truth cells. Vertical accuracy cần reference elevation độc lập nếu muốn claim theo nghĩa trắc địa.**

