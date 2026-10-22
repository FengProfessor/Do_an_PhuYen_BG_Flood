# V46 — Nghiên cứu hydrological conditioning bằng mạng sông mở

Ngày: 2026-09-30  
Mục tiêu: thay cách “sửa DEM để nước chạy/khớp SAR” bằng một quy trình hydrologically conditioned DEM có thể audit, giữ dữ liệu lũ Sentinel-1 2021 làm kiểm định độc lập.

## 1. Kết luận nghiên cứu

Có cơ sở khoa học mạnh để dùng mạng sông/hydrography mở, bản đồ nước lâu dài và địa hình để điều kiện hóa DEM. Cách làm này đã được công bố trong nhiều hướng độc lập:

- Lindsay (2016) mô tả complete/selective/constrained breaching và đặt giới hạn chiều dài/độ sâu breach để giảm tác động lên DEM.
- Lindsay (2016) về stream burning cho thấy raster hóa mạng sông vector trực tiếp có thể gây lỗi topology khi tỷ lệ dữ liệu không khớp DEM; cần ưu tiên topology và mức chi tiết phù hợp với kích thước cell.
- Poggio & Soille (2012) cho thấy phương pháp kết hợp filling + carving tạo mạng sông gần mạng tham chiếu hơn trong thí nghiệm của họ.
- MERIT Hydro (Yamazaki et al., 2019) là tiền lệ rất gần với mục tiêu V46: kết hợp DEM với Global Surface Water và OpenStreetMap, chỉnh dòng chảy và tạo lớp “hydrologically adjusted elevation”.
- JRC Global Surface Water (Pekel et al., 2016) cung cấp lịch sử nước mặt ở 30 m từ Landsat, phù hợp làm bằng chứng độc lập về vị trí nước thường xuyên/tái diễn.
- HAND (Nobre et al., 2011) dùng cao độ tương đối so với drainage gần nhất; về mặt thủy văn, đây là feature có ý nghĩa hơn khoảng cách ngang tới sông khi đánh giá kết nối bãi-sông.
- Chen et al. (2024) tiếp tục dùng stream burning trên các DEM toàn cầu 30 m như COP30/AW3D30/FABDEM để cải thiện vị trí mạng sông. Độ “burn” trong bài này phục vụ extraction/routing, không được hiểu là cao độ lòng sông vật lý để đưa thẳng vào mô hình ngập.
- Nghiên cứu tại Việt Nam của Hawker et al. (2024) cho thấy FABDEM 30 m cải thiện mô phỏng ngập so với MERIT tại các điểm nghiên cứu Tây Nguyên, củng cố yêu cầu phải xem DEM là một đầu vào khoa học cần đánh giá độc lập.

## 2. Tiền lệ nội bộ của dự án

Dự án đã từng sửa DEM bằng quy trình rõ ràng:

- `breach_levees_v44.py` tạo V44 từ V41.
- Audit độc lập tại `.agents/auditor_1/handoff.md` ghi nhận đúng 15.561 pixel bị hạ, mỗi pixel đúng 2.000 m; pixel khác không đổi; 17/17 test PASS.
- Tuy nhiên V44 dùng chính SAR flood extent để chọn `barrier_mask`, nên V44 không thể dùng làm nền cho một kiểm định độc lập bằng cùng SAR 2021.

V45 hiện yếu hơn về provenance:

`prepare_v45_dem.py` định nghĩa `river_core = dem < 3.0`, dilation 11x11 (~150 m), chọn ô >4 m trong buffer và một vùng pixel “nhắm chừng”, sau đó ép cao độ xuống 3.5 m. Audit dự án đã đo 41.907 ô bị hạ, cực đại khoảng 171.669 m. Đây không phải constrained breaching và không có bằng chứng hình học đủ để diễn giải tất cả thay đổi là địa hình/thủy công thật.

Kết luận lineage đề xuất:

`V41 (base sạch) -> V46 independent hydro-conditioning`

V44 chỉ giữ làm tiền lệ kỹ thuật/legacy. V45 giữ làm exploratory branch. Nếu SAR 2021 tiếp tục là validation target thì V46 khoa học không nên kế thừa trực tiếp các sửa đổi SAR-based của V44.

## 3. Dùng “bản đồ sông” và “khoảng cách tới sông” như thế nào

### 3.1 Mạng sông mở

Nên dùng ít nhất hai nguồn độc lập:

1. OpenStreetMap waterways: chi tiết cục bộ tốt, có thể có river/stream/canal và polygon water.
2. MERIT Hydro hoặc HydroRIVERS/HydroSHEDS: topology vùng/lưu vực và hướng dòng độc lập với V45.
3. JRC Global Surface Water: raster 30 m mô tả xác suất/tần suất nước mặt.

Không lấy một nguồn duy nhất làm ground truth. OSM có thể thiếu hoặc sai topology; HydroRIVERS có hình học quá thô để chọn chính xác một cell 30 m; JRC water occurrence mô tả nước nhìn thấy từ vệ tinh chứ không phải trực tiếp lòng dẫn/bathymetry.

### 3.2 Khoảng cách tới sông

`distance_to_river` hữu ích như một **spatial prior**:

- gần mạng sông đã xác nhận -> xác suất một vật cản DEM là artifact/đê/đường cần kiểm tra cao hơn;
- xa mạng sông -> chỉ cho phép sửa nếu terrain-derived drainage và nguồn độc lập khác cùng ủng hộ.

Không dùng rule kiểu “mọi ô cách sông <150 m thì hạ xuống X m”. Cách đó chỉ thay V45 bằng một buffer đẹp hơn nhưng vẫn không chứng minh cao độ cần sửa.

Ở lưới 30 m, distance nên được lưu theo mét và theo số cell, đồng thời chạy sensitivity theo các corridor 1/2/3/5 cell. Kết quả candidate nào chỉ tồn tại ở một buffer rất cụ thể phải bị đánh dấu nhạy cảm.

### 3.3 HAND

HAND là “height above nearest drainage”, không phải khoảng cách ngang. Với floodplain nó nên là feature audit quan trọng:

- horizontal distance trả lời “gần sông bao nhiêu?”;
- HAND trả lời “cao hơn drainage liên thông bao nhiêu?”;
- flow accumulation trả lời “drainage này có nhận diện tích góp nước lớn không?”.

Ba feature này bổ sung nhau.

Lưu ý: `D:/VTP/BG_Flood_Project/BG_Flood/Teamwork_Validation/PhuYen_HAND_30m.tif` đã tồn tại nhưng chưa được mặc định coi là input sạch cho V46; phải kiểm provenance/base DEM/drainage threshold trước. Tốt nhất V46 tự tái tạo HAND từ network/DEM có lineage rõ.

## 4. Kiến trúc V46 đề xuất

### Bước A — Base sạch và holdout

- Base: ưu tiên V41 hoặc một DTM 30 m độc lập tốt hơn sau khi so sánh; không kế thừa V44 nếu dùng SAR 2021 để validate.
- Holdout tuyệt đối: Sentinel-1 flood extent 2021, gauge/event observations dùng sau cùng để đánh giá; không tham gia chọn ô breach.
- Nếu dùng JRC GSW, ưu tiên tạo statistics từ các năm trước 2021 để tránh event leakage.

### Bước B — Tạo hydrography consensus

Chuẩn hóa tất cả về EPSG/grid của DEM, nhưng giữ vector gốc để audit.

Tạo các raster feature:
- `dist_osm_m`
- `dist_merit_or_hydrorivers_m`
- `water_occurrence_pre2021`
- `flow_accum_raw`
- `slope`
- `local_relief`
- `pit/depression_id`
- `hand_raw_or_candidate`
- `network_agreement_count`

Không cộng thành một score duy nhất ngay từ đầu. Giữ từng feature để tránh che mất nguyên nhân.

### Bước C — Candidate obstruction

Một cell/path chỉ được xem là candidate khi có đồng thời:

1. nằm trong corridor của hydrography độc lập;
2. topology cho thấy upstream/downstream cần nối;
3. DEM tạo một local rise/pit/obstruction làm đứt flow path;
4. ít nhất một bằng chứng bổ sung ủng hộ: water occurrence, flow accumulation cao, hoặc hai network nguồn trùng nhau.

Một river line đi qua sườn núi cao mà không có terrain/water evidence phải fail closed.

### Bước D — Constrained breach / least-impact path

Thay vì hạ toàn buffer về một cao độ cố định, tìm đường breach có tổng thay đổi DEM nhỏ nhất trong corridor.

Objective định tính:
- giảm tổng cut volume;
- giảm chiều dài path;
- phạt độ lệch xa centerline;
- bảo đảm downstream không cao hơn upstream trên tuyến drainage;
- không nâng/hạ vùng ngoài corridor.

Constraints bắt buộc:
- max breach depth;
- max path length;
- max corridor width;
- max modified area;
- không sửa NoData;
- không tạo NaN/Inf;
- fail closed nếu cần cut quá giới hạn.

Các giá trị max depth/path không chọn bằng cách tối đa CSI SAR. Giai đoạn đầu chỉ chạy dry-run sensitivity, ví dụ depth caps 1/2/3 m và path-length caps 2/4/8 cells; đây là dải kiểm tra độ nhạy, chưa phải tham số vật lý cuối cùng.

### Bước E — Dry-run trước khi tạo V46

Dry-run không ghi DEM. Nó phải xuất:

- raster candidate mask;
- GeoJSON/CSV candidate paths;
- summary JSON;
- bảng per-cell/per-path gồm:
  - row/col, x/y
  - original_z
  - proposed_z
  - cut_depth
  - distance tới từng network
  - water occurrence
  - flow accumulation
  - slope/local relief
  - HAND
  - matched source IDs
  - evidence count
  - reason code
  - max constraint margins
  - algorithm/config version
  - input hashes
  - auto/manual-review status.

Chỉ sau khi dry-run được kiểm tra mới sinh `PhuYen_DEM_30m_V46.asc`.

## 5. Cách phân cấp bằng chứng cho từng breach

**Tier A — auto candidate**
- >=2 hydrography sources đồng thuận;
- terrain obstruction rõ;
- water/flow evidence ủng hộ;
- cut nằm trong constraint.

**Tier B — review candidate**
- chỉ 1 network tốt + terrain evidence;
- hoặc topology rõ nhưng water occurrence yếu;
- hoặc sensitive với corridor/depth cap.

**Tier C — reject/fail closed**
- cần cut rất sâu/dài;
- line xung đột rõ với terrain;
- chỉ xuất hiện do một nguồn duy nhất;
- candidate phụ thuộc vào SAR 2021 validation raster.

## 6. Tiêu chí nghiệm thu V46 khoa học

V46 chỉ được gọi là hydrologically conditioned DEM khi:

1. Grid/CRS/nodata giữ nguyên.
2. 100% modified cells có reason/audit record.
3. Mọi cut đều nằm trong path đã duyệt và constraint.
4. Không có V45-style extreme cut không giải thích.
5. Network connectivity/flow routing cải thiện theo metric độc lập.
6. Kết quả ổn định tương đối qua sensitivity corridor/depth/path.
7. Chỉ sau khi khóa V46 mới đối chiếu SAR 2021/gauge.
8. Báo cáo SAR phải gọi đúng là validation nếu SAR chưa từng tham gia tạo V46.

## 7. Nguồn khoa học chính

1. Lindsay, J.B. (2016). Efficient hybrid breaching-filling sink removal methods for flow path enforcement in digital elevation models. Hydrological Processes 30(6), 846–857. DOI: https://doi.org/10.1002/hyp.10648
2. Lindsay, J.B. (2016). The practice of DEM stream burning revisited. Earth Surface Processes and Landforms 41(5), 658–668. DOI: https://doi.org/10.1002/esp.3888
3. Poggio, L. & Soille, P. (2012). Influence of Pit Removal Methods on River Network Position. Hydrological Processes. DOI: https://doi.org/10.1002/hyp.8290
4. Yamazaki, D. et al. (2019). MERIT Hydro: A High-Resolution Global Hydrography Map Based on Latest Topography Dataset. Water Resources Research 55, 5053–5073. DOI: https://doi.org/10.1029/2019WR024873
5. Pekel, J.-F. et al. (2016). High-resolution mapping of global surface water and its long-term changes. Nature 540, 418–422. DOI: https://doi.org/10.1038/nature20584
6. Nobre, A.D. et al. (2011). Height Above the Nearest Drainage — a hydrologically relevant new terrain model. Journal of Hydrology 404, 13–29. DOI: https://doi.org/10.1016/j.jhydrol.2011.03.051
7. Chen, Q., Mudd, S.M., Attal, M., Hancock, S. (2024). Extracting an accurate river network: Stream burning re-revisited. Remote Sensing of Environment 312, 114333. DOI: https://doi.org/10.1016/j.rse.2024.114333
8. Hawker, L. et al. (2024). Assessing LISFLOOD-FP with the next-generation digital elevation model FABDEM using household survey and remote sensing data in the Central Highlands of Vietnam. NHESS 24, 539–566. DOI: https://doi.org/10.5194/nhess-24-539-2024

## 8. Quyết định kỹ thuật hiện tại

Hướng hợp lý nhất cho V46 là:

**V41/base clean + OSM + MERIT/HydroRIVERS + JRC pre-2021 + terrain-derived flow -> consensus river corridor -> obstruction detection -> constrained least-impact breach -> full audit manifest -> freeze V46 -> independent SAR/gauge validation.**

Không tiếp tục logic `DEM < 3 m -> buffer -> ép về 3.5 m`. Không dùng SAR 2021 để chọn breach rồi lại dùng cùng SAR làm bằng chứng V46 đúng.

