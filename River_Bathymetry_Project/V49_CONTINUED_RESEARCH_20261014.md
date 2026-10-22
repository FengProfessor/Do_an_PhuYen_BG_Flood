# V49 — nghiên cứu tiếp trong thời gian chạy Gate G

Ngày: 14/10/2026, UTC+7. Phạm vi: kiểm toán forcing, khởi tạo, nguồn mưa đối chứng và thiết kế nghiệm thu khoa học. Đây là nghiên cứu bổ sung, không phải quyết định PASS cho Gate G.

**Kết luận:** bộ BASE/CENTRAL/LOW/HIGH có thể trả lời tác động tương đối của hai reach được chỉnh dưới cùng một hợp đồng đầu vào. Kết quả đó chưa chứng minh mưa, lưu lượng, mực nước khởi tạo hoặc bathymetry đúng ngoài thực địa. Ưu tiên tiếp theo là tách bằng chứng về DEM khỏi bất định của forcing và quan trắc.

## Sản phẩm có thể kiểm tra lại

- [Script kiểm toán offline](D:/VTP/River_Bathymetry_Project/v49_research_forcing_audit.py).
- [Số liệu và SHA-256](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_forcing_audit.json), [120 khoảng giờ đúng UTC](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_forcing_hourly_UTC.csv), [tọa độ 16 điểm đối chứng](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_archived_reference_points.csv).
- [Biểu đồ forcing](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_rainfall_forcing_comparison.png).
- [Script thu thập CHIRPS](D:/VTP/River_Bathymetry_Project/v49_fetch_chirps_context.py); dữ liệu context được giữ riêng trong `V49_RESEARCH_20261014/CHIRPS_CONTEXT`.
- [Nghiên cứu Sentinel-1 và 10 nguồn gốc](D:/VTP/River_Bathymetry_Project/V49_SENTINEL_VALIDATION_PRIMARY_RESEARCH_20261014.md); [kiểm toán mask tĩnh](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_static_mask_audit.json).

Script offline chỉ đọc input tĩnh và các JSON được runtime ghi nguyên tử. Không mở NetCDF đang ghi. SHA-256 của 22 file được kiểm tra trước/sau tính toán, gồm DEM nguồn, terrain G/E, bốn config, mưa, bốn hydrograph và mã được dùng làm bằng chứng. Kết quả kiểm toán tính toán/tính toàn vẹn PASS; `scientific_validation_complete=false`, `hydraulic_promotion_ready=false`.

## 1. Mưa hiện hành: nguồn phái sinh, hệ số x2 và cửa sổ thời gian

[prep_v34.py](D:/VTP/BG_Flood_Project/BG_Flood/prep_v34.py:20) thực sự nhân cường độ V23 với 2,0. Đọc lại toàn bộ 144 mốc cho thấy cùng trục thời gian 0–514.800 s và sai khác `V34 − 2×V23` bằng 0. Đây là phép biến đổi kịch bản, không phải đổi đơn vị.

[Cấu hình CENTRAL](D:/VTP/River_Bathymetry_Project/V49_G_20261013/BG_param_V49_G_CENTRAL.txt:27) dùng `rainunits=m/s`; [runtime](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/updateforcing.py:213) cộng trực tiếp tốc độ mưa SI lên ô hợp lệ. Bốn arm dùng cùng chuỗi. Lỗi chia đơn vị của runtime lịch sử không được suy sang runtime R1 đang chạy.

Epoch đã được hồ sơ V48 xác minh là **26/11/2021 00:00 UTC+7 = 25/11/2021 17:00 UTC**. [Hồ sơ epoch](D:/VTP/V48_RUN_EPOCH_PROVENANCE_20261002.json) dựa trên lệnh tạo dữ liệu giữ lại và lịch sử xóa một dòng cuối trùng/lùi thời gian. Bằng chứng này xác minh epoch; nó không tự xác minh toàn bộ dữ liệu khí tượng hay hệ số x2.

Đối chứng lần này dùng JSON Open-Meteo ERA5 đã tải ngày 28/09/2026, 16 điểm × 216 giờ, và kiểm lại checksum theo [manifest tải](D:/VTP/V45_runs/20260928_engine_r1/results/V45_openmeteo_era5_16point_20211125_20211203_v21_manifest.json). Đây là **bản phái sinh Open-Meteo**, không phải raw CDS hay response nguyên bản đã tạo V23. Theo [tài liệu nhà cung cấp](https://open-meteo.com/en/docs/historical-weather-api), precipitation là lượng mm trong giờ trước timestamp; tọa độ phản hồi là tâm ô khí tượng được chọn. Không coi 16 điểm lưới là 16 trạm đo.

Tính đúng 120 giờ từ `25/11 17:00Z` đến `30/11 17:00Z`: mỗi khoảng giờ đối chứng lấy mẫu có timestamp ở **cuối** khoảng; forcing hiện hành được tích phân chính xác theo nội suy tuyến tính của solver.

| Chuỗi | Tổng 120 giờ |
|---|---:|
| V23 x1, theo nội suy hiện hành | 197,33688 mm |
| V34 x2, theo nội suy hiện hành | 394,67376 mm |
| Open-Meteo ERA5 lưu trữ, trung bình 16 điểm, đúng khoảng UTC | 256,29375 mm |
| V34 so với bản đối chứng trên | +53,9927% |

**+53,99% là chênh lệch giữa hai sản phẩm/chuỗi đã xử lý, không phải rain-gauge bias.** Không dùng con số này để suy hệ số hiệu chỉnh mới hoặc tuyên bố x1 là đúng. Audit V45 cũ dùng giả định bắt đầu `26/11 00:00Z` cho đối chứng 255,85 mm; kết quả đó có cửa sổ khác. Nghiên cứu này kế thừa chứng cứ x2 đã biết và bổ sung phép đối chiếu đúng epoch cho V49, không mô tả x2 là phát hiện mới của dự án.

Trong 16 tâm điểm yêu cầu và 16 tâm ô phản hồi, chỉ **1 điểm mỗi nhóm** nằm trong hình chữ nhật miền V49. Đây không tự chứng minh trung bình regional sai: vùng lấy mẫu có thể nhằm đại diện lưu vực rộng hơn miền thủy lực. Tuy nhiên, chuỗi đó chưa được chứng minh là mưa trung bình diện tích trên miền mô hình hoặc trên phần lưu vực góp nước tương ứng.

[ECMWF về tích lũy](https://confluence.ecmwf.int/plugins/viewsource/viewpagesrc.action?pageId=197702797) phân biệt ERA5 hourly với ERA5-Land tích lũy từ đầu forecast. Phải dùng đúng metadata sản phẩm trước khi de-accumulate. Với dữ liệu lượng từng giờ, nội suy như tốc độ tức thời còn làm phân bố lại lượng giữa các khoảng; tổng và timing từng giờ cần kiểm riêng, dù epoch đã đúng.

## 2. Nước ban đầu và nước mưa toàn miền gồm phần biển

Theo [cold_start](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/init_evolv.py:15), `zsinit=1` là mực nước toàn cục: `h0=max(1−zb,0)`, vận tốc ban đầu bằng 0. Đây không phải đặt sâu 1 m trên mọi ô.

Tính trực tiếp trên ASC CENTRAL đang dùng, sau mask hợp lệ, rồi giao polygon OCEAN trong C R3 bằng tâm ô:

| Đại lượng | Kết quả |
|---|---:|
| Miền hợp lệ | 4.410.000 ô; 3.969,0000 km² |
| Phần thuộc polygon OCEAN hiện hành | 849.306 ô; 764,3754 km² |
| Thể tích nước khởi tạo toàn miền | 794.467.315,7706 m³ |
| Nước khởi tạo trong polygon OCEAN | 762.447.737,4371 m³; khoảng 95,97% tổng |
| Nước khởi tạo ngoài polygon OCEAN | 32.019.578,3335 m³ |

Ngoài OCEAN còn sông, hồ, cửa sông và đất; đây chưa phải mask đất khô được khảo sát. Polygon biển là inventory hiện có, không phải chứng cứ độc lập xác nhận mọi ô.

Mưa uniform được cộng cả trên phần biển hợp lệ. Vì thế thể tích mưa trong budget là nước đưa vào **toàn miền tính**, không phải lượng mưa trên riêng đất liền hay lượng nước lũ còn giữ lại. Khi báo thể tích ngập nội địa phải loại phần biển và tách nước thường xuyên, đồng thời giữ hợp đồng metric Sentinel đã đóng băng.

ASCII CENTRAL có 186 ô không bằng source khi so bit float; accepted E TIFF chỉ chỉnh **72 ô**. Đọc lại xác nhận sai khác ASCII/E tối đa **9,3132e-10 m**, do xuất 9 chữ số thập phân và đọc float32; chỉ 72 ô có thay đổi lớn hơn 1 micrometre. Đây là precision khi lưu, không phải thêm 114 ô carving. Lowering E giữ **8.008,2092285 m³**. Chênh initial volume CENTRAL−BASE khoảng −2,16e-6 m³, ở mức rounding; không dùng nó như thay đổi vật lý.

[USACE về khởi tạo 2D](https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.6/boundary-and-initial-conditions-for-2d-flow-areas/initial-conditions) mô tả initial WSE, restart và warm-up giữ biên ổn định. Đây là cơ sở phương pháp, không phải quy định phần mềm áp lên BG_Flood. **Suy luận cho V49:** cần thí nghiệm riêng về độ nhạy cold-start khi có điều kiện; 96 giờ đầu có forcing thay đổi không được tự gọi là một warm-up đã hội tụ.

## 3. Budget khép kín vẫn cần đánh giá chất lượng nghiệm

Snapshot được lưu cùng nghiên cứu ở [budget](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_CENTRAL_budget_snapshot.json) và [execution state](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_execution_snapshot.json), không phải trạng thái cuối run.

Tại khoảng 30,41 giờ mô phỏng, tích phân mưa toàn miền offline và budget rời rạc sai khác tương đối khoảng **−0,00123%**; thể tích ban đầu khác phép tính raster khoảng 1,18e-5 m³. Các số này hỗ trợ kiểm tra bookkeeping. Chưa có ngưỡng nghiệm thu được xác minh từ chúng.

Observer ghi riêng rain, river, infiltration, flux divergence, boundary reset và clamp. Phần closure residual rất nhỏ **sau khi** các thành phần, kể cả clamp, được tính. Không diễn giải nó thành solver không thêm nước số học. Snapshot có clamp-added khoảng **0,01745%** tổng nguồn dương rain+river; đây là mẫu số được khai báo cho chẩn đoán, không phải ngưỡng PASS.

Số `corrector_negative_raw_depth_cell_steps` là tổng ô-bước trước clamp, không phải số ô địa lý duy nhất hoặc độ sâu âm trong output cuối. Cần xem magnitudes, vị trí và ảnh hưởng tới vùng quan tâm ở kết quả hoàn thành.

Runtime [infiltration](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/updateforcing.py:391) áp dụng điều kiện `h < 0,05 m` và ngừng sink này khi vượt ngưỡng. Đây là rule đang chạy, chưa có chứng cứ tại Phú Yên xác minh ngưỡng. Tỷ lệ infiltration/rain toàn miền khoảng 0,0482% không chứng minh tỷ lệ tổn thất lưu vực: mẫu số gồm mưa trên biển và mô hình còn nhận Q sông.

## 4. Lưu lượng và phạm vi nguồn nước phải được hạch toán

Tích phân trực tiếp bốn hydrograph frozen theo cùng nội suy và 120 giờ:

| File nguồn | Peak trong file | Tích phân Q 120 giờ |
|---|---:|---:|
| Ba Hạ V40 sync | 11.000 m³/s | 970.200.000 m³ |
| Bàn Thạch V43 | 4.007,14 m³/s | 916.157.088 m³ |
| Kỳ Lộ V40 sync | 5.000 m³/s | 359.550.000 m³ |
| Tuy An V40 sync | 2.000 m³/s | 207.360.000 m³ |

Các con số là đặc tính file kịch bản, không tự trở thành peak/discharge quan trắc đã kiểm chứng. Cần sơ đồ vùng góp nước của từng inflow và vùng rain-on-grid để đánh giá overlap hoặc thiếu nguồn; chưa có phép kiểm này nên không kết luận mô hình đang double-count runoff.

[USACE về calibration](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/calibration/summary-of-the-calibration-procedure) yêu cầu cùng storm, rainfall spatial coverage, so peak/timing/volume và validation bằng dữ liệu ngoài calibration. **Suy luận:** chỉnh bathymetry để bù một sai lệch forcing chưa xác định có thể cho khớp ngập trong một event mà vẫn sai geometry. Bốn arm hiện hành chỉ kiểm hiệu ứng bed có điều kiện trên bộ forcing kế thừa.

## 5. Đã thu được CHIRPS v3 làm bằng chứng mưa không gian bổ sung

Tải trực tiếp COG final pentad 6 tháng 11/2021 từ [kho UCSB/CHC chính thức](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/pentads/global/cogs/chirps-v3.0.2021.11.6.cog), 21.165.500 bytes, SHA-256 `1d6d3f01f115eb0c8b91eb5393a92f8e6f3923be2399caa4653aab34297a765e`. [Registry](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/CHIRPS_CONTEXT/V49_CHIRPS_context_register.json) lưu URL, HTTP identity, checksum cả COG/README và crop.

[CHC mô tả CHIRPS v3](https://www.chc.ucsb.edu/data/chirps3) là mưa lưới 0,05° kết hợp infrared và stations. [Catalog phân phối](https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHC_CHIRPS_V3_PENTAD) xác nhận đơn vị mm/pentad. Chọn tổng pentad để bổ sung cấu trúc không gian; chưa dùng daily disaggregation rnl/sat để thay forcing giờ.

Đọc native grid, không resample về 30 m; trọng số là diện tích giao từng ô với hình chữ nhật V49 trừ polygon OCEAN R3, tính trong EPSG:32649:

| Thống kê context pentad 26–30/11/2021 | Giá trị |
|---|---:|
| Native crop | 13 × 13 ô EPSG:4326 |
| Ô có mưa hợp lệ giao vùng chọn | 141 |
| Diện tích vùng chọn có dữ liệu | 3.204,6246 km²; 100% vùng đã định |
| Trung bình có trọng số diện tích | 277,172922 mm |
| Min / max tại ô native giao vùng chọn | 215,838608 / 350,131317 mm |

COG tải thật không khai báo GDAL NoData nhưng có sentinel −9999 ngoài vùng đất. Script phát hiện và loại đúng sentinel, khai báo NoData cho crop riêng; không gán ô thiếu thành mưa 0. File COG gốc giữ nguyên byte/hash. [CHC diagnostics](https://www.chc.ucsb.edu/data/chirps3/diagnostics) cũng mô tả missing −9999 và khả năng gap-fill bằng ERA5 trong lịch sử.

**Chưa chứng minh pentad nhãn ngày tương đương cửa sổ `25/11 17Z → 30/11 17Z` của model.** Con số 277,17 mm không được trộn vào bảng so sánh cùng cửa sổ UTC ở mục 1, không dùng để xác nhận/đảo hệ số x2. Coverage 100% chỉ nói vùng chọn có ô CHIRPS hợp lệ; không nói 100% mưa đã đo tại trạm. Chưa kiểm station membership hoặc ảnh hưởng gap-fill tại Phú Yên.

CHIRPS v3 daily rnl phân bố tổng pentad theo ERA5; daily sat dùng IMERG Late. Nhà cung cấp nêu daily date label không đồng nhất cửa sổ đo của mọi trạm. Vì vậy cần ghi dependence và timing khi dùng các phiên bản này làm đối chứng; không gọi chúng hoàn toàn độc lập với ERA5 hoặc gauge ground truth. [Tài liệu CHC](https://www.chc.ucsb.edu/data/chirps3).

## 6. Sentinel-1: bổ sung kiểm toán mask và giới hạn nghiệm thu

[Ghi chú nguồn khoa học](D:/VTP/River_Bathymetry_Project/V49_SENTINEL_VALIDATION_PRIMARY_RESEARCH_20261014.md) tổng hợp 10 nguồn, phân biệt snapshot với cực đại, nước thường xuyên, SAR shadow/layover/vegetation, timing, CSI/F1 và kiểm định ngoài dữ liệu hiệu chỉnh. [Stephens et al. 2014](https://research-information.bris.ac.uk/en/publications/problems-with-binary-pattern-measures-for-flood-model-evaluation/) cho thấy CSI phụ thuộc quy mô trận/độ dốc và có thiên lệch; đây không phải lý do bỏ CSI mà là lý do đọc cùng bản đồ/FP/FN và uncertainty.

Tính lại từ **ba raster tĩnh**, không đọc kết quả model đang ghi, bằng [script mask](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_static_mask_audit.py): SHA SAR đúng bản đóng băng; mask chính 2.848.260 ô = 2.563,434 km², ngập quan sát 574.267 ô = 516,8403 km². Grid có 733.507 ô SAR class 255/không biết, được giữ ngoài phép chấm. Water-density thiếu = **0 ô** trên grid và trong mask; HAND thiếu = **0 ô** trong mask. Pattern mã có thể cho water NoData −9999 đi qua điều kiện ≤0,5, nhưng **không có hiệu ứng này trên raster hiện tại**. Chất lượng quan sát vật lý ở đô thị/thực vật vẫn chưa được kiểm chứng bằng các count này.

BASE lịch sử có area bias chỉ −3,0853% nhưng FP+FN tương ứng **451,3878 km²** trên mask chính: tổng diện tích gần nhau không có nghĩa đúng vị trí. CSI/F1 của cùng bảng nhầm lẫn liên hệ đại số, không là hai bằng chứng độc lập.

Đề xuất giữ nguyên phép so chính đã khóa (`h>0,3`, timestamp/frame rule và mask chung), thêm báo cáo quanh hai reach được phép và vùng bãi ngập kết nối theo AOI khai báo trước khi xem kết quả hoàn thành. Nếu thử threshold/frame/mask khác thì ghi exploratory, công bố mọi variant; không chọn variant tốt nhất làm primary PASS. Chưa dựng AOI hoặc tính kết quả local trong lượt nghiên cứu này.

## 7. Thứ tự nghiên cứu và đóng các tồn đọng

| Ưu tiên | Công việc cụ thể | Điều kiện để nhận kết quả |
|---|---|---|
| 1 | Hoàn thành matched G; đối chiếu đúng thời điểm SAR và cùng mask/threshold | Run đầy đủ, nguồn khóa đúng hash, metrics/velocity/budget có thể tái lập; quyết định khoa học được ghi riêng |
| 1 | Xác minh rainfall x2, Q và timezone/interval; phân vùng nguồn nước | Raw request/response hoặc CDS, units/interval, footprint weighting và gauge phù hợp; hiện context không đóng gate này |
| 1 | Quan trắc H/Q/XYZ đúng datum và epoch | Cung cấp station zero/benchmark, QC, thời gian và geometry liên quan; số liệu bãi cát 2024 không thay bathymetry 2021 |
| 2 | Đánh giá ảnh hưởng tại hai reach chỉnh trước khi kết luận từ CSI toàn miền | Region/report supplemental khai báo trước khi đọc kết quả hoàn thành; báo cả global primary lẫn local diagnostics |
| 2 | Breach/fill drainage benchmark và crossing review | Topology, sink thật, max incision, downstream connection; chỉ chuyển thành hydraulic candidate khi có tác động input được định nghĩa |
| 2 | Cold-start/loss/forcing sensitivity trong experiment mới | Mỗi thí nghiệm một thay đổi rõ, provenance riêng, không sửa run G đang chạy |

Validator hiện [gán `gate_g_pass=False`](D:/VTP/River_Bathymetry_Project/v49_validate_hydraulic_validation.py:428), evaluator cũng chỉ xuất metrics và giữ false. **Run hoàn thành không tự chuyển PASS.** Cần chức năng/quy trình nghiệm thu có quyết định rõ và kiểm bằng chứng; không đổi false thành true theo sự tồn tại của NetCDF.

Có thể ghi nhận một so sánh flood extent có phạm vi và điều kiện rõ khi đủ kết quả, nhưng hiện chưa được thực hiện. Không dùng một quyết định theo phạm vi để tuyên bố bathymetry, gauges, 29 UNKNOWN hoặc toàn miền đều chuẩn. Các hold D/F và thiếu datum giữ nguyên cho đến khi có chứng cứ phù hợp.

## Tái lập kiểm toán

```powershell
& 'C:\Users\CuongHM\anaconda3\python.exe' -X utf8 -B 'D:\VTP\River_Bathymetry_Project\v49_research_forcing_audit.py'
```

Lệnh tạo lại artifacts forcing và snapshot budget mới; số snapshot sẽ đổi khi simulation tiến lên. Tích phân forcing, grid, cold-start và hash input tĩnh phải giữ nguyên nếu nguồn không đổi. Hai script CHIRPS và static mask có lệnh chạy tương tự theo đường dẫn riêng. Không tái chạy regression solver vì solver/input/config không được sửa; checks thực hiện là checksum, UTC interval coverage, units, grid/mask identity, serialization, NoData và tính toán trực tiếp trên nguồn thật.
