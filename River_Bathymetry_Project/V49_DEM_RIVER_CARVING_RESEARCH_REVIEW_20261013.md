# Kiểm tra nghiên cứu DEM preprocessing / river carving V49

Ngày kiểm tra: 13/10/2026. Tài liệu được kiểm tra: [V49_DEM_RIVER_CARVING_RESEARCH_20261013.md](D:/VTP/River_Bathymetry_Project/V49_DEM_RIVER_CARVING_RESEARCH_20261013.md), SHA-256 `603a945164642d8bde097290777eb865b40e31eea35f1bfc74e021e1aea2fe20`.

**Kết luận: hướng nghiên cứu có cơ sở, mô tả baseline khớp mã/dữ liệu; chưa có bằng chứng phương pháp đề xuất tốt hơn V49 tại Phú Yên. Cần sửa thiết kế thí nghiệm và điều kiện dữ liệu trước khi triển khai thay thế.** Đây là review phương pháp và nguồn, không phải kết quả benchmark hay quyết định Gate G.

## Những kết luận được xác nhận

- Tách DEM thoát nước khỏi DEM đáy dùng cho BG_Flood là đúng với kiến trúc dự án. [HydroDEM builder](D:/VTP/River_Bathymetry_Project/v49_build_hydro_conditioned_dem.py:1) ghi rõ vai trò chỉ phân tích thoát nước; [cấu hình CENTRAL](D:/VTP/River_Bathymetry_Project/V49_G_20261013/BG_param_V49_G_CENTRAL.txt:7) đọc hydraulic bed.
- HydroDEM dùng Priority-Flood nâng depression/flat và D8. Các số 4.410.000 ô hợp lệ, 1.177.695 ô nâng, 0 ô hạ, max raise 30,047241 m, 0 internal unresolved/cycle khớp [audit đã lưu](D:/VTP/River_Bathymetry_Project/V49_HYDRO_20261013/V49_HYDRO_validation_report.json).
- V49-E dùng depth theo reach trên bề mặt DEM cục bộ, kết hợp taper ngang; endpoint bed dùng kiểm tra thay vì dựng đường đáy theo chainage. [Mã thực thi](D:/VTP/River_Bathymetry_Project/v49_synthesize_hydraulic_bed.py:188) xác nhận. Công thức trong nghiên cứu là xấp xỉ hợp lý: các ô rasterized thalweg được weight=1, các ô còn lại dùng raised cosine, và chỉ áp dụng trong mask được phép.
- MERIT Hydro là tham khảo thiết kế phù hợp cho flow routing. Nguồn tác giả xác nhận lưới khoảng 90 m và hydrologically adjusted elevation; dữ liệu này không chứng nhận đáy sông 30 m của V49. [Nguồn MERIT Hydro](https://global-hydrodynamics.github.io/MERIT_Hydro/).
- FABDEM là ứng viên so sánh terrain, không phải bathymetry đã đo. [Dataset chính thức FABDEM v1.2](https://research-information.bris.ac.uk/en/datasets/fabdem-v1-2/) xác nhận mục tiêu loại bias do cây/nhà và grid 1 arc-second. Mục 7 của nghiên cứu hiện thiếu link nguồn này.

## Các điểm cần sửa, theo mức ảnh hưởng

### P1 — Thiếu đường truyền tác động từ HydroDEM sang BG_Flood

Vị trí nghiên cứu: dòng 127–149, 179 và 192.

Nghiên cứu giữ hai nhánh độc lập, nhưng lại dùng hiệu quả BG_Flood để lựa chọn ứng viên HydroDEM mà chưa định nghĩa đầu vào nào của mô hình thay đổi. Bốn config G hiện đọc BASE/CENTRAL/LOW/HIGH hydraulic bed; không đọc raster D8, accumulation hoặc HydroDEM. Runtime tính flux từ trạng thái nước và `zb`, như [flow_gpu.py](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/flow_gpu.py:459). [Manual BG_Flood](https://aliceharang.github.io/Manual.html) xác nhận đầu vào bottom elevation qua `bathy`.

**Suy luận từ các đầu vào này:** nếu chỉ đổi HydroDEM riêng, còn bed, forcing, mask và solver giữ nguyên, chưa có đường truyền để cải thiện ngập trong BG_Flood. Chạy lại mô hình như vậy không phải thí nghiệm thủy lực của thuật toán breaching.

Sửa: benchmark nhánh drainage bằng topology, outlet/basin agreement và độ biến dạng. Nếu đưa một phần crossing correction vào hydraulic terrain hoặc sửa catchment/forcing dựa trên drainage, phải tạo ứng viên hydraulic riêng, ghi chính xác thay đổi và kiểm định riêng. Không lấy toàn bộ HydroDEM đã breach/fill làm bed.

### P1 — Target thalweg chưa được xác định bằng dữ liệu thủy lực

Vị trí nghiên cứu: dòng 103–115, đặc biệt dòng 105–106 và 115.

Fit một profile robust/smooth từ proxy DEM rồi trừ depth chưa xác định được đáy bằng longitudinal hydraulics. [Geometry estimator](D:/VTP/River_Bathymetry_Project/v49_estimate_reach_geometry.py:596) đang dùng DEM surface-slope proxy và HydroRIVERS mean-discharge proxy; bank elevation cũng chỉ là DEM median ngoài mép nước. Hai reach được phép có uncertainty HIGH/VERY_HIGH; chưa có bathymetry khảo sát được chấp nhận. [Geometry audit R3](D:/VTP/River_Bathymetry_Project/V49_R3_20261013/D/V49_D_geometry_audit.json).

Không thể dùng water-surface elevation và bank elevation thay thế cho nhau rồi cùng trừ một depth. WSE và độ sâu phải tương ứng cùng trạng thái dòng; bank-based depth cần định nghĩa trạng thái bankfull và lưu lượng/quan hệ mặt cắt phù hợp. `DIS_AV_CMS` hiện không phải bankfull discharge.

Sửa: gọi đây là **profile candidate có ràng buộc hình học và bất định**. Chỉ gọi hydraulically constrained khi có phương trình/ràng buộc thủy lực cụ thể và dữ liệu cao độ, lưu lượng, mặt cắt, thời gian, datum phù hợp. Calibration cần tách dữ liệu hiệu chỉnh khỏi bằng chứng nghiệm thu. Bờ hoặc bãi cát chưa xác minh hệ cao độ không tạo quyền chỉnh thêm reach.

### P2 — Thống kê HydroDEM đúng nhưng chưa đủ chẩn đoán nguyên nhân

Vị trí nghiên cứu: dòng 13–19, 184 và 192.

Đọc lại [V49_HYDRO_DELTA_Z.tif](D:/VTP/River_Bathymetry_Project/V49_HYDRO_20261013/V49_HYDRO_DELTA_Z.tif), SHA-256 `4fff7d95430bba802cc25b97c90272f2542fa4be2273b95dc75ed0223b1363fb`, với valid mask thực và delta=`conditioned-source`, cho kết quả:

| Thống kê | Giá trị |
|---|---:|
| Ô có delta > 1e-9 m | 1.177.695 |
| Ô nâng > 0,001 m | 217.432 |
| Ô nâng > 0,01 m | 211.489 |
| Ô nâng > 0,1 m | 169.511 |
| Ô nâng > 1 m | 55.508 |
| Ô nâng > 5 m | 4.087 |
| Ô nâng > 10 m | 589 |
| Ô nâng > 20 m | 13 |
| P50 của các delta > 1e-9 m | 2,16e-7 m |
| P95 | 0,937843 m |
| P99 | 3,259939 m |
| Maximum | 30,047241 m |

Khoảng 81,5% ô thống kê là thay đổi không quá 1 mm. Số ô tổng gồm các thay đổi rất nhỏ dùng giải phẳng; không thể diễn giải tất cả là biến dạng địa hình đáng kể. Phần nâng lớn vẫn cần kiểm tra: cực đại ở row=1962, col=650, tâm ô EPSG:32649 x=289.515 m, y=1.419.125 m. Chưa xác định nguyên nhân riêng của ô/vùng đó trong lượt review.

Rasterize geometry của layer `classified_objects` trong C R3 về đúng grid bằng tâm ô, không buffer, cho thấy **841.022 ô nâng nằm trong object OCEAN**, khoảng 71,4% tổng ô nâng. Nghiên cứu chưa tách nhóm này khi dùng thống kê toàn miền để đánh giá biến dạng terrain nội địa. Đây là giao với inventory hiện tại, không phải phép xác nhận độc lập mọi vị trí nước:

| Nhóm vị trí theo C R3 | Ô nâng > 1 m | Max raise (m) |
|---|---:|---:|
| OCEAN | 0 | 0,818348 |
| ESTUARY_TIDAL_RIVER | 599 | 3,000000 |
| LAKE_RESERVOIR | 607 | 2,592123 |
| RIVER_STREAM | 121 | 1,863838 |
| UNKNOWN_REVIEW_REQUIRED | 349 | 4,476128 |
| Ngoài footprint water inventory hiện tại | 53.832 | 30,047241 |

Điểm cực đại không giao polygon nào trong water inventory hiện tại. Không có phép đối chiếu road/rail/culvert tại điểm đó trong review, nên không gán nó là road artifact. Các ô ngoài inventory vẫn có thể gồm dòng nhỏ/vùng nước chưa phát hiện; không coi chúng mặc nhiên là đất khô.

[Copernicus chính thức](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) xác nhận DSM có infrastructure/vegetation và đã có water editing. Điều này hỗ trợ kiểm tra artifact, không xác nhận riêng crossing QL1A nào đang gây sai trong mô hình.

Sửa: phân nhóm depression theo vị trí, diện tích, độ sâu, ảnh hưởng tới basin/outlet; đối chiếu road/rail, reservoir, wetland và sink thật. Ghi crossing ID, bằng chứng cầu/cống và profile trước/sau. Đổi khẳng định lỗi đã biết tại Phú Yên thành giả thuyết cần kiểm chứng khi chưa có hồ sơ địa điểm.

### P2 — Preserve true sinks cần thay đổi tiêu chí topology

Vị trí nghiên cứu: dòng 49, 131 và 164–167.

Audit HydroDEM hiện coi mọi interior unresolved cell là lỗi và yêu cầu mọi ô về explicit exterior outlet: [condition_array](D:/VTP/River_Bathymetry_Project/v49_build_hydro_conditioned_dem.py:115). Nếu ứng viên mới thực sự giữ sink tự nhiên, không thể áp nguyên tiêu chí này để buộc nó lấp sink cho PASS.

Sửa: đăng ký terminal sink có bằng chứng, phân biệt declared sink với unresolved error. Tiêu chí mới phải đếm đủ mọi ô góp nước tại outlet **hoặc** sink đã chấp nhận, không có cycle chưa giải thích. Mask cần rõ `allowed_change` và `protected`: delta ngoài allowed hoặc bên trong protected phải bằng 0.

USGS 3DHP cho phép true sinks và có exceptions cho dam/weir, complex channels, flow undefined. Quy tắc monotonicity của sản phẩm hydrography không chứng nhận độ dốc đáy cho toàn bộ sông triều/backwater Phú Yên. [Đặc tả USGS](https://www.usgs.gov/ngp-standards-and-specifications/elevation-derived-hydrography-data-acquisition-specifications-15).

### P2 — Breach qua đường không thay thế thủy lực cống

Vị trí nghiên cứu: dòng 71–86 và 133.

Một crossing stream-road chỉ là ứng viên; nó chưa chứng minh có opening, vị trí đúng, invert hoặc bề rộng hợp lệ. [USGS Culverts and Drainageways](https://www.usgs.gov/media/files/culverts-and-drainageways) nhấn mạnh phải tìm vị trí cầu nhỏ/cống thực tế.

[Tài liệu USACE về cống](https://www.hec.usace.army.mil/confluence/rasdocs/rasum/7.0/entering-and-editing-geometric-data/bridges-and-culverts/culvert-hydraulic-computations) xác nhận giới hạn inlet/outlet, ảnh hưởng tailwater và tổn thất. **Suy luận kỹ thuật:** hạ một ô 30 m thành khe hở mặt đất có thể cho khả năng thông nước khác xa cống thật. Phép breach cho routing không tự tạo một mô hình capacity của cống.

Sửa: phân biệt bỏ mặt cầu được DEM biểu diễn sai, cống có lưu lượng giới hạn, và đê/đập cần giữ. Nếu phải dùng approximation trong BG_Flood, ghi rõ geometry/capacity assumption và kiểm tra độ nhạy/quan trắc; không mở mọi crossing.

### P2 — Chỉ hạ DEM chưa bảo đảm tái tạo profile đã fit

Vị trí nghiên cứu: dòng 107–115.

Nếu quy tắc chỉ hạ được biểu diễn `z_final=min(z_DEM,z_target)` trong mask, một ô source nằm thấp hơn target vẫn giữ nguyên. Vì vậy target smooth chưa bảo đảm đáy xuất ra smooth; pits/noise thấp có thể còn nguyên. Đây là hệ quả toán học của đề xuất, chưa phải lỗi của code ứng viên vì code đó chưa tồn tại.

Sửa: audit profile từ raster xuất thật, so sánh với target, kiểm max incision, diện tích/thể tích thay đổi và junction continuity. Giữ chính sách chỉ hạ nếu đó là giới hạn được chọn, nhưng báo mọi residual thấp hơn target thay vì tuyên bố đã loại nhiễu. Không tự cho phép nâng hydraulic bed để đạt profile đẹp.

### P2 — Chưa đủ dữ liệu và tiêu chí để gọi pipeline tốt nhất

Vị trí nghiên cứu: tiêu đề, dòng 123, 179, 183–192.

Đây là xếp hạng ưu tiên nghiên cứu, chưa là kết quả so sánh tại Phú Yên. Nghiên cứu chưa có output candidate, cấu hình tham số đóng băng, matched results hoặc ngưỡng nghiệm thu định lượng. FABDEM cần version/source/checksum, khớp chính xác lưới 30 m hiện tại, datum, resampling và valid-mask trước A/B; thêm benchmark này không giải quyết thiếu bathymetry.

Sửa: dùng tên phương pháp ứng viên; preregister mask, phạm vi, tham số và metrics. Không chọn phương pháp chỉ theo minimum terrain change: breach có thể rất ít ô nhưng phá một hydraulic control thật. Không bắt HydroDEM phải cải thiện SAR khi nó không đi vào input của BG_Flood. Nếu một hydraulic candidate thay đổi thì kiểm matched metrics, độ nhạy và numerical/physical behavior với cùng observation contract.

## Thứ tự thử nghiệm đề nghị sau review

1. Hoàn thành các run V49 G đang chạy để có control thủy lực hiện tại; không sửa 44 input/config đã đóng băng.
2. Chọn một depression/crossing có định danh và bằng chứng địa điểm. Benchmark fill-only với constrained breach/hybrid cho drainage; thêm declared sinks vào audit nếu thực tế có.
3. Kiểm target-profile prototype chỉ trên 2 reach hiện được phép. Báo nguồn, uncertainty và raster readback; chưa mở rộng carving vì thuật toán mới.
4. Tạo hydraulic candidate riêng chỉ khi có thay đổi hợp lệ đi vào `bathy`/structures/forcing. Benchmark thủy lực một yếu tố mỗi lần; nhãn coastal/tidal/backwater không tự cấp quyền tạo bed discontinuity.
5. FABDEM là thí nghiệm terrain riêng sau khi chuẩn hóa grid/datum, giữ riêng ảnh hưởng terrain và channel geometry.

Review không tạo candidate DEM, không chạy WhiteboxTools, không đổi source DEM, hydraulic DEM, solver, dependencies hoặc config. Vì chỉ kiểm tra nguồn và tài liệu, không chạy lại toàn bộ 102 test đã đạt; không có mã sản phẩm được sửa.

## Kiểm tra primary-source Lindsay / Whitebox

Đã hoàn tất [kiểm tra nguồn độc lập](D:/VTP/River_Bathymetry_Project/V49_RIVER_CARVING_PRIMARY_SOURCE_CHECK_20261013.md). Review chính đối chiếu lại Bảng 2/Bảng III của hai PDF tác giả và signature Python ở commit WhiteboxTools `3d7c73cf562b6c58d2649c37f570e3e9a90322f2`. Không suy đoán executable/extension đang cài trên máy.

- **87% có nguồn:** complete breaching đạt 86,6% thời gian filling trong phép thử, trung bình nhân của tỷ lệ thời gian, loại I/O. Constrained mode kết hợp depth/length đạt 203,2%, nên không coi mọi mode là nhanh hơn filling. Không chuyển kết quả đó sang least-cost tool hiện hành hoặc runtime BG_Flood. [Lindsay, Bảng 2, PDF tr.15](https://jblindsay.github.io/ghrg/pubs/Lindsay-HP-preprint.pdf).
- **TBB chưa được chứng minh thắng ở Phú Yên 30 m:** Bảng III so TBB với FillBurn, không trực tiếp benchmark AGREE. Trường hợp SRTM-1 khoảng 27 m cho Kappa TBB=0,952, FillBurn=0,953; ưu thế ổn định của TBB rõ hơn khi lưới thô. [Lindsay, Bảng III, PDF tr.8](https://jblindsay.github.io/ghrg/pubs/2016_Lindsay_ESPL.pdf).
- **P2, cần làm rõ API ở dòng 43/47–54:** `BreachDepressionsLeastCost` dùng `dist` theo cells và `max_cost`; không có `max_depth`. Tham số depth nằm ở `BreachDepressions`. `fill=True` trong Python wrapper không chọn riêng micro-sinks và không có preserve-mask input. Phải định nghĩa thêm cơ chế giới hạn độ hạ/bảo vệ controls và kiểm output nếu dùng least-cost. [Source Python đã pin](https://raw.githubusercontent.com/jblindsay/whitebox-tools/3d7c73cf562b6c58d2649c37f570e3e9a90322f2/whitebox_tools.py).
- **P2, cần giữ routing constraints của TBB:** không thể mặc nhiên tái tạo ưu thế TBB bằng cách chỉ xuất DEM rồi tính D8 chuẩn như pipeline ở dòng 132–136. TBB còn giữ stream IDs/pointer; cần audit pruned network và dòng sau rasterization. [Manual nhà phát triển](https://www.whiteboxgeo.com/manuals/legacy/tool_help_wbwpro.html#topological_breach_burn).
- `BurnStreamsAtRoads` cần geometry/width/elevation hợp lệ; nhận định mọi output chỉ hạ là quá tuyệt đối. Source check ghi các nhánh có thể không đạt mục đích khi giao cô lập/NoData, nhưng chưa tái hiện lỗi tại V49; đây là rủi ro implementation cần test nếu chọn công cụ. Không trình bày thành lỗi đã quan sát ở dự án. [Source tool đã pin](https://raw.githubusercontent.com/jblindsay/whitebox-tools/3d7c73cf562b6c58d2649c37f570e3e9a90322f2/whitebox-tools-app/src/tools/hydro_analysis/burn_streams_at_roads.rs).

Đề nghị sửa tiêu đề nghiên cứu thành “Các phương pháp ứng viên cải thiện DEM preprocessing và river carving cho V49”; giữ các khuyến nghị dưới dạng giả thuyết cần benchmark. Bằng chứng hiện tại đủ để chọn thí nghiệm tiếp theo, chưa đủ để thay DEM được đóng băng hoặc chuyển Gate G sang PASS.
