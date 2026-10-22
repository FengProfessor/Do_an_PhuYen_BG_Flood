# V45 — kế hoạch thực thi tiếp nối nghiên cứu: gói A và B

Ngày lập: 28/09/2026. Tài liệu này triển khai cụ thể gói A/B của V45_Ke_hoach_trien_khai.md. Phạm vi lượt làm việc: rà soát mã, cấu hình, nguồn công khai và chuẩn bị thứ tự sửa. Các phép đo định lượng bên dưới kế thừa cuộc audit đã lưu; lượt này chưa chạy lại solver hoặc sinh nghiệm lũ mới.

## 1. Quyết định và căn cứ

**Quyết định:** Chưa dùng PhuYen_DEM_30m_V45.asc và prepare_v45_dem.py làm địa hình chuẩn để hiệu chỉnh. Khóa nguồn vào và sửa các hợp đồng đơn vị, ô lưới, thấm, biên, bảo toàn nước trước khi có run R1. Không dùng riêng mức tăng CSI để xác nhận một cao trình đê.

| Bằng chứng đã có | Tác động đến công việc |
|---|---|
| Audit V44 lưu CSI 20,64%, recall 24,97%, FN 195,13 km² trên mask của evaluator | Phải có baseline và mask cố định để so sánh; con số này là mốc V44 đã lưu, chưa phải kết quả V45 |
| Rain file đang dùng ghi m/s; add_rain_vec trong updateforcing.py lại chia 3.600.000 | Chốt đơn vị của từng nguồn mưa, chuyển đổi một lần tại loader |
| read_input.py đọc xllcorner/yllcorner làm tọa độ mẫu; output chỉ 2099×2099 trong khi ASC 2100×2100 | Sửa hình học toàn chuỗi đọc–mesh–nạp layer–ghi output theo một quy ước |
| Probe đã lưu ghi cập nhật cum_infilt không đi kèm tổn thất nước mặt và halo predictor ghi đè điều kiện tường | Kiểm chứng từng stage và ngân sách nước trước khi hiệu chỉnh công trình |
| V45 draft đã sửa 41.907 ô, có mức hạ cực đại 171,67 m | Cách chọn ô hiện tại không đủ căn cứ vật lý; chỉ giữ làm lịch sử |
| Cấu hình BG_param_PhuYen_30m_V45.txt vẫn ghi tiêu đề V44 và mô tả 15.561 ô/-2 m của V44 | Cần khai báo V45 như một scenario mới với manifest thực tế, không tin phần comment cũ |
| Rà các file .py/.js/.md/.json hiện có thấy nhiều chỗ sử dụng raster SAR nhưng chưa tìm thấy pipeline xuất ảnh gốc | Cần truy vết scene hoặc ghi thiếu provenance; tên 05h36 không đủ xác nhận UTC/UTC+7 |

Bằng chứng chi tiết: V45_Ke_hoach_trien_khai.md; V45_primary_sources.md; V45_audit/ và các đường mã được nêu trong bảng. Kết quả probe cũ thuộc backend NumPy CPU; chưa đại diện cho cả run GPU.

## 2. Gói A — khóa dữ liệu và tính tái lập

### A1. Đóng băng mốc V44/V45 lịch sử

- Kiểm tra tiến trình và tập tin đầu ra đang được sử dụng trước khi sửa code hoặc tạo run. Giữ nguyên V44.nc và DEM V41/V44/V45 draft; đặt tên run tiếp theo khác tên V45 đang có.
- Lập manifest chạy được tái lập gồm SHA256: engine Python, entrypoint, config, DEM, Manning, IL/CL, rain, tất cả Q, SAR, mask, mã evaluator. Manifest 38 tệp trước đây là mốc khảo sát, chưa bao trùm mọi phụ thuộc và chưa chứng minh chính là mã của run V44 lịch sử.
- Ghi phiên bản Python/NumPy/CuPy/GPU, backend, kích thước lưới, precision, ngày tạo và command line. Vì D:/VTP không có .git ở thư mục gốc theo lần kiểm tra này, cần bản lưu mã/config riêng cho mỗi run.

**Đầu ra:** V45_runs/<run_id>/manifest.json, config bản sao, bảng khác biệt với V44, bảng trạng thái tiến trình.

### A2. Hợp đồng nguồn dữ liệu

Mỗi input phải có: đường dẫn/ID, nguồn phát hành, cách tạo và phiên bản, đơn vị gốc, đơn vị nội bộ, hệ tọa độ ngang và đứng, NoData, thời gian/tz/t0, footprint, transform, SHA256, độ tin cậy và giả định. Bảng tối thiểu:

| Đầu vào | Việc phải truy | Quy tắc nếu chưa truy được |
|---|---|---|
| SAR 20211130_05h36, raster 90 m | ID từng Sentinel-1 scene, acquisition UTC, orbit/pass, footprint, thuật toán Otsu và ảnh tham chiếu, mosaic và export | Giữ hai giả thuyết 05:36 UTC+7 (t=101,6 h) và 05:36 UTC (t=108,6 h). Không gọi khớp đúng giờ chụp hoặc dùng CSI để chọn timezone |
| Rain rain_v34_era5_x2.txt | Tệp ERA5 tải gốc, điểm/lưới, biến, đơn vị, timezone, ý nghĩa hệ số x2; kiểm tra lại rain_v23_16stations.json toàn số 0 | Nhánh mưa x2 là giả định; không tuyên bố đây là lượng mưa quan trắc |
| Q sông Ba Hạ, Bàn Thạch, Kỳ Lộ, Tuy An | Nguồn số liệu, thời gian, vị trí mặt cắt và quan hệ các nhánh; kiểm tra Bàn Thạch V43 đỉnh t=15 h so với Ba Hạ t=111 h | Giữ nhãn bất định timeline và vị trí; tránh cộng trùng các nguồn thượng lưu |
| IL/CL | Đơn vị gốc của raster, ý nghĩa loss ban đầu/duy trì, dữ liệu hiệu chỉnh | Chỉ dùng các giá trị có đơn vị xác thực cho baseline chính; nếu chưa có thì lập kịch bản loss ghi nhãn, không tự đổi hệ số |
| DEM/bathymetry, trạm Phú Lâm, triều | Nguồn gốc và datum đứng, transform, thông tin mặt cắt và ranh giới nước | Không so cao trình tuyệt đối khác datum; triều thiếu số liệu phải ghi là giả định biên |
| SAR mask/evaluator | Mã lớp ngập/khô/NoData, nước thường xuyên, công thức mask, phép resampling, ngưỡng h | Khóa mask độc lập với nghiệm; báo cáo riêng 30 m để so lịch sử và 90 m theo support ảnh gốc |

**Đường truy SAR:** tra ảnh trong COPERNICUS/S1_GRD của Google Earth Engine theo ngày 29/11–01/12/2021 và footprint tỉnh Phú Yên, lấy image ID, system:time_start (UTC), orbitProperties_pass và thuộc tính quỹ đạo từ từng scene. Đối chiếu với script/hồ sơ xuất ảnh nếu tìm được. Danh sách scene tiềm năng chỉ là ứng viên; không thể chứng minh raster Otsu hiện tại thuộc một scene chỉ từ ngày và vùng phủ. Trang dataset chính thức: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD

**Điều kiện qua A:** có manifest và hợp đồng dữ liệu cho mọi nguồn của R1; dữ liệu chưa xác minh được gắn cờ cùng kịch bản thay thế. Thiếu giờ SAR hoặc datum không chặn sửa engine, nhưng chặn tuyên bố kiểm định thời gian hoặc độ sâu tuyệt đối.

## 3. Gói B — công việc engine theo thứ tự phụ thuộc

| Thứ tự | File/seam | Thay đổi thiết kế | Kiểm chứng đạt yêu cầu |
|---|---|---|---|
| B1 | read_forcing.py, forcing_update.py, updateforcing.py | Mỗi nguồn khai báo units; chuyển về m/s tại loader; add_rain_vec nhận SI ở cả nhánh uniform/grid/station; chống chuyển hai lần | Ô kín mưa 10 mm/h trong 1 h tạo 0,01 m khi tắt loss; đối chiếu tích phân file và lượng đưa vào |
| B2 | read_input.py, initial_conditions.py, mesh.py, write_output.py | Quy ước xllcorner là mép ngoài, xllcenter là tâm; cùng grid lấy mẫu đúng ô; đồng bộ mọi lớp và xuất đủ hàng/cột | ASC 2100×2100 giữ đúng giá trị/tọa độ/NoData nội miền; output đúng 2100×2100; không tự làm trơn đoạn đê |
| B3 | add_river_vec trong updateforcing.py và nơi khởi tạo mask | Sử dụng duy nhất quy ước tọa độ tâm; xuất số ô, diện tích, z đáy, Q dự kiến và Q thực bơm mỗi nguồn | Hình chữ nhật nguồn khớp map; tích phân thể tích bơm bằng tích phân Q trong sai số số học |
| B4 | updateforcing.py, flow_gpu.py, Model/evolv | Xác thực đơn vị IL/CL; tính sink, cumulative loss và predictor/corrector trên một hợp đồng thời gian; phân biệt loss ban đầu với loss duy trì | Nước mặt giảm bao nhiêu, cumulative loss tăng bấy nhiêu trên ô kín; thử hết IL, h quanh 0,05 m và cả hai stage |
| B5 | boundary.py, flow_gpu.py, mainloop.py | Trao đổi halo rồi áp biên vật lý trước gradient/flux ở mỗi stage; đo thông lượng biên, phân biệt tường với free outflow | Biên kín không rò, pháp tuyến tường bằng 0 ở predictor/corrector; biên stage biến thiên khớp điều kiện đặt |
| B6 | flow_gpu.py, write_output.py và sổ bước | Xuất Vrain/Vriver/Vinfil/Vboundary/Vout/ΔV và volume do clamp/reset, vùng masked; ghi thời gian NetCDF có origin/tz/calendar | Bài toán kín gần chính xác số; run thực tế có residual định lượng và giải thích, không giấu volume clamp |
| B7 | evaluator thống nhất, tách khỏi eval_v44.py lịch sử | Chọn frame theo timestamp hoặc nội suy các frame hợp lệ; không fallback; mask cố định; so 30/90 m, ±1 ô SAR, bờ/khoang | Reproduce mốc V44 khi dùng quy tắc cũ; quy tắc mới không biến NoData thành khô hoặc rò rỉ dữ liệu giữa hiệu chỉnh/kiểm định |

Điểm cần thống nhất trước khi sửa B4: thấm là mất nước mưa khi vừa rơi hay là thấm nước mặt đang ngập? Hợp đồng phương trình và việc ngừng thấm tại h≥0,05 m phải được định nghĩa vật lý. Không giữ nguyên hiệu chỉnh IL/CL cũ sau khi sửa đơn vị mưa.

**Quy tắc triển khai:** thay đổi từng seam, lưu diff và biểu đồ cân bằng; các thử nghiệm nhỏ trên miền cô lập trước khi diễn toán toàn miền. Không dùng snapshot V44 làm hotstart khi cấu trúc state/thấm hoặc thời gian đã đổi. Kiểm tra đối chiếu CPU/GPU trên cùng bài toán trước khi dùng GPU cho R1.

## 4. Quyết định triển khai run sau khi B đạt

- R0: V44 lưu sẵn, dùng như mốc lịch sử; mọi số đã công bố gắn evaluator/mask/frame cụ thể.
- R1a: engine đã sửa, DEM V44, nguồn có đơn vị và provenance chốt; geometry chưa sửa thêm. Bước này tách thay đổi engine/forcing khỏi địa hình.
- R1b: giữ R1a và đổi riêng giả thuyết giờ SAR 101,6/108,6 h nếu chưa có acquisition UTC. Ghi WSE/Q tại đúng mỗi mốc; không chọn một giờ vì điểm khớp cao.
- R2: cùng engine và forcing R1a, DEM V41 (trước chỉnh V44) để đo tác dụng của chỉnh 2 m.
- R3: chỉ sau khi phân khoang và vẽ profile/đường kết nối, thử một số hành lang có bằng chứng trên miền con có điều kiện biên từ mô phỏng toàn miền.
- R4/R5: module cống/tràn ở mặt ô và các nhóm độ nhạy thủy văn, triều, nhám, loss; chạy có kiểm soát sau R3.

R1a và R2 không nên trộn thay đổi đơn vị, time shift, nhám và DEM trong cùng một chênh lệch. Nếu phải thay nhiều yếu tố để có engine đúng, dùng một baseline sửa đầy đủ rồi tách thí nghiệm độ nhạy có khai báo.

## 5. Ngưỡng quyết định chuyển sang nghiên cứu đê/cửa thông

1. Hoàn thành A và B: đầu vào có đơn vị/transform/timestamp rõ hoặc cờ bất định, engine qua bài toán kín, có số dư thể tích từng bước và output đúng grid.
2. Baseline R1/R2: có h(t), zs(t), hmax; xuất Q tại nguồn và mặt cắt kiểm soát, volume theo khoang, bản đồ FN/FP trên mask bất biến.
3. Chỉ khoét khi tại vị trí có đối chứng địa hình/công trình và đường kết nối đủ độ dài qua tất cả mặt ô chắn. Ghi crest zc, chiều dài cửa dọc bờ L, chiều dày đê b, biến đổi thể tích địa hình, datum và nguồn bằng chứng.
4. Đối với cửa dưới 30 m, đưa lưu lượng qua cấu trúc tại mặt ô sau khi chứng minh không tính trùng với flux 2D. Phương pháp tràn tự do, tràn ngập chìm và vị trí lấy mực nước đuôi phải xét theo chế độ dòng. Tham khảo hướng dẫn công trình 2D của USACE HEC: https://www.hec.usace.army.mil/confluence/rasdocs/hgt/latest/guides/modeling-weirs-in-2d-areas
5. Chỉ tuyên bố đánh giá độ sâu khi có dữ liệu mực nước/vết lũ độc lập cùng datum. SAR extent 90 m là ràng buộc về diện tích và thời điểm ảnh, không đủ xác định duy nhất độ sâu hoặc cửa tràn dưới kích thước pixel.

## 6. Danh mục công việc kế tiếp có thể bắt đầu độc lập

- Dữ liệu: truy nguồn file rain_v23_era5_spatial.txt và archive tải ERA5; tìm GEE/export script hoặc scene IDs; lập sơ đồ nhánh sông và vị trí từng vùng bơm Q; điền bảng provenance.
- Kỹ thuật: chuẩn bị snapshot nguồn/config và thiết kế hợp đồng SI + raster-grid; mô tả phép đo volume tại từng stage; lập tiêu chí bài toán kín.
- Không gian: chuẩn bị đường tim sông/hành lang, polygon khoang ngập và profile tại các cụm FN lớn từ DEM gốc; chờ sau B2 để tính ngưỡng trên grid thực dùng.
- Đánh giá: khóa SAR mask ở 90 m, ghi vùng hợp lệ, quy tắc resampling và hai giả thuyết thời gian; dành các quan trắc chưa dùng cho kiểm định.

**Trạng thái tại thời điểm lập tài liệu:** nghiên cứu và phân rã đầu việc đã hoàn thành; A/B chưa triển khai, chưa sửa solver/DEM, chưa có run V45 mới được kiểm định. Trạng thái cập nhật được ghi trong phụ lục dưới đây.

## 7. Phụ lục tiến độ A/B — cập nhật 28/09/2026

Workspace thực thi cô lập: `D:/VTP/V45_runs/20260928_engine_r1`; báo cáo kỹ thuật và nhật ký quyết định: `results/V45_R1_Bao_cao_ky_thuat_20260928.md`. Những kết luận ở các phần 1–6 mô tả tình trạng tại thời điểm khảo sát ban đầu.

- **A — một phần:** preflight ban đầu kiểm tra năm raster ASC cùng lưới và băm 52 tệp (60 mục manifest). Cần chạy lại preflight sau thay đổi mã, rà danh mục nguồn và xác minh timestamp Sentinel-1, datum đứng, mưa, chuỗi Q và đơn vị IL/CL. Manifest cũ không đại diện cho mã R1 hiện tại.
- **B — một phần:** đã sửa trong bản sao R1 đường đưa mưa vào solver, lưới ASC/NetCDF, state thấm predictor/corrector, cập nhật biên ở predictor, mask nguồn Q, thông lượng qua tường/halo và giới hạn `dt` tới mốc xuất kế tiếp. Đã thêm CSV ngân sách nước mỗi bước dưới biến môi trường `BG_FLOOD_WATER_BUDGET_CSV`.
- **B — kiểm chứng đã quan sát:** 9 unit test CPU qua ở lần chạy trước; bốn bài GPU nguồn Q không bật ledger qua và xuất tại 60/120/180/240 s. Sáu CSV ngân sách hoàn tất: mưa thuần 2304 m³, mưa IL = 0,1 mm có 23,04 m³ thấm, bốn trường hợp nguồn Q mỗi trường hợp 240 m³; phần dư số học từng bước nhỏ hơn 10⁻¹² m³ trên các bài thử kín này. Những kết quả này chưa thay thế phép kiểm tra masked/padded grid, nhiều block, biên mở và cân bằng vật lý toàn miền.
- **Chưa thực hiện:** kiểm tra đủ ca thủy lực/biên/CPU–GPU, preflight cuối, khóa provenance và chạy R1a 120 giờ. DEM V45 nháp khoét 41.907 ô, độ sâu cực đại 171,67 m chưa có căn cứ để làm địa hình chính thức; chỉ dùng DEM V44 nguyên bản cho R1a sau khi đạt cổng kiểm chứng. Giữ nguyên V44 và dữ liệu production.

## 8. Cập nhật nghiệm thu A/B sau kiểm chứng — 28/09/2026, 16:53 ICT

Các mục 1–7 là kế hoạch/chụp trạng thái lúc lập. Kết quả thực nghiệm và căn cứ quyết định đầy đủ nằm tại `V45_runs/20260928_engine_r1/results/V45_R1_Bao_cao_ky_thuat_20260928.md`, mục 7.

| Gói/cổng | Bằng chứng mới | Trạng thái và việc tiếp theo |
|---|---|---|
| A1 — identity/config/grid | Preflight exit 0; 63 file SHA256 / 71 mục; 5 ASC 2100×2100 cùng grid; khác biệt config chỉ rainunits SI và outfile | **Đạt preflight kỹ thuật.** Manifest cuối: `results/manifest_preflight.json`; không coi đây là giấy xác nhận provenance. |
| A2 — nguồn dữ liệu/UTC/datum | Tệp hiện có chưa xác minh scene Sentinel-1, mưa ×2, Q, IL/CL và mốc đứng | **Đang mở.** Truy nguồn gốc, ghi giả thuyết và khóa timestamp/mask; chưa hiệu chỉnh nghiệm theo SAR. |
| B1–B4 — forcing, grid, Q, IL/CL | 15 unit; Q bốn vị trí; thấm CPU/GPU; rain 2304 m³ và NoData không nhận Q trong ca thử | **Đạt ca hiện có.** Chốt đơn vị thực địa, kiểm output 2100×2100, bổ sung hydrograph/time origin thật. |
| B5–B6 — halo, tường, stage/outlet và sổ nước | Hai hồ tĩnh, trao đổi block, ba mask/padding, bốn stage, outlet và block NoData hoàn toàn đều qua | **Đạt synthetic đã nêu.** Test mới tại nguồn đúng ô rìa biên mở có dòng ngược; cần chốt định nghĩa biên, thử dam-break, góc và hội tụ. |
| B backend | NumPy CPU và CuPy GPU cùng engine cho h,zs,u,v khớp tại 60/120 s trên 32×16; residual ≤4,547×10⁻¹³ m³ | **Đạt so backend của cùng solver.** Còn đối chứng nghiệm chuẩn/engine độc lập để kiểm tính đúng vật lý. |
| R1a 120 h | Chưa có preflight khoa học, thí nghiệm quy mô hay manifest cho forcing đã chốt | **Chưa khởi chạy.** Sử dụng DEM V44 nguyên bản sau khi đóng các cổng liên quan. |

Thiết lập `BG_FLOOD_PROGRESS_EVERY=1000` nếu cần tần suất thông báo mặc định của R1 (nhận số nguyên dương). CSV `BG_FLOOD_WATER_BUDGET_CSV` vẫn là opt-in; profile trước chạy lớn vì đồng bộ GPU ở mỗi bước có chi phí. Giữ ca nguồn sát outlet thất bại làm regression đầu vào cho quyết định biên tương lai, không xóa khỏi nhật ký.

## 9. Cặp hồi quy biên extrapolation — 28/09/2026, 17:01 ICT

Đã hiện thực ca `--edge-source` tại `V45_runs/20260928_engine_r1/tests/smoke_v45_missing_block.py` và chạy cùng ca mặc định, đều exit 0. Miền 48×16 có block giữa NoData: Q tại ô áp chót cho `block_edge_flux_net=−1358,094026 m³`; chuyển cùng Q sang ô ngoài cùng sát `right=2` cho `+3966,526648 m³` (dòng vào miền). Nước khoang tây không rò qua block giữa; hai CSV tương ứng nằm trong `results/`, báo cáo kỹ thuật mục 7.4.

Gói B5 **chưa được nghiệm thu cho bố trí nguồn sát cửa ra thực tế**. Cần chốt hình học nguồn/biên, dữ liệu mực nước đuôi và khả năng có triều trước khi chọn hoặc thay điều kiện biên; thử lại cặp hồi quy sau thay đổi. Preflight kỹ thuật tại thời điểm này chạy lúc 17:01:37 ICT đạt 63 file/71 mục; manifest mới sau kiểm toán nguồn nằm ở mục 10. Các cổng provenance và nghiệm thủy lực toàn miền vẫn mở; chưa chạy R1a 120 giờ.

## 10. Kiểm toán nguồn Q trong lưới thực — 28/09/2026, 17:09 ICT

Script `tests/audit_v45_source_geometry.py` đã chạy exit 0, đọc trực tiếp DEM V44 và DEM V45 nháp (không sửa raster), kiểm hình chữ nhật bơm trong hai config R1 và loại ô NoData/minmask theo hợp đồng nạp DEM. Cả bốn footprint chọn đúng cùng số ô trên hai DEM: Ba Hạ 1360, Bàn Thạch 1156, Kỳ Lộ 1156, Tuy An 1156; **không có ô mask hoặc block không hoạt động trong footprint**. Nguồn gần rìa nhất là Ba Hạ, cách tường trái 30 m; gần biên mở nhất là Kỳ Lộ, cách mép trên 500 m. Không nguồn nào đang đặt ở ô ngoài cùng.

Gói A1 có thêm bằng chứng hình học thực tại `results/source_geometry_audit.json` và báo cáo kỹ thuật mục 7.5. Preflight sau khi thêm script chạy **17:09:38 ICT**, 64 file/72 mục, năm ASC cùng grid; manifest SHA256 `8F1C01B3EDA229717E2BB23EF4EB7280106B196BC36A305A1E888A694309786C`. A2 vẫn mở về ID cảnh Sentinel-1, datum, mưa ×2, thời gian/nguồn Q và IL/CL. B5 vẫn phải thử tính đúng thủy lực của biên mở; audit tĩnh chưa kiểm tra thông lượng trong run. R1a 120 giờ chưa được khởi chạy.

## 11. Nghiệm thu kỹ thuật lưới thực 60 giây — 28/09/2026, 17:25 ICT

`BG_param_R1_V44_fullgrid_60s_engine_smoke.txt` chạy trên GPU và DEM V44 gốc đã **exit 0**. Engine xử lý 17.424 block hoạt động, 16 bước tới t=60 giây, tạo NetCDF `time=1, y=2100, x=2100` với năm biến `zs,h,zb,u,v`; CSV ngân sách có 16 bước, residual tối đa 3,5763×10⁻⁷ m³, không ghi nhận nước trong ô mask. Tổng thời gian 393,37 giây gồm 254,16 giây khởi tạo và 139,08 giây vòng tính. Đối chiếu thể tích cuối NetCDF và ledger chênh khoảng 0,0354 m³ trên 586,4 triệu m³. Báo cáo, lệnh tái hiện và giới hạn chi tiết ở `results/V45_R1_Bao_cao_ky_thuat_20260928.md` mục 7.6.

**B2/B6 kỹ thuật:** đã có bằng chứng chạy/output đủ kích thước lưới thực; công đoạn xuất qua vòng Python từng ô × năm biến là điểm cần đo và tối ưu trước 120 giờ. **A2/B5 khoa học:** chưa đóng nguồn gốc Q/rain/IL/CL, datum, UTC SAR, mực nước đuôi và nghiệm vật lý độc lập; các bài dam-break/đối xứng/hội tụ còn thiếu. R1a 120 giờ **chưa khởi chạy**. Sau mọi thay đổi mã/config, cập nhật preflight và manifest trước khi dùng làm mốc tái lập.

## 12. Cập nhật cổng A/B sau tối ưu NetCDF — 28/09/2026

Đã hoàn tất phiên `BG_param_R1_V44_fullgrid_60s_engine_smoke_v2.txt` trên DEM V44 gốc và GPU: exit 0, 16 bước đến 60 giây, frame NetCDF 2100×2100 chứa `zs,h,zb,u,v`. Writer vector hóa báo thời gian xuất frame **3,88 s**; vòng tính **14,44 s** và tổng **270,24 s** (ca trước tối ưu tương ứng 139,08 s và 393,37 s). Công cụ `tests/compare_v45_output_frames.py` xác nhận tọa độ và năm bản đồ khớp từng phần tử với ca cũ, kể cả vị trí NaN; hai CSV ngân sách 16 bước trùng chính xác. Hai phép chạy chỉ là nghiệm thu kỹ thuật 60 giây, không thay cho mô phỏng/kiểm định lũ 120 giờ. Chi tiết và hash tại báo cáo kỹ thuật R1, mục 7.7.

| Cổng | Trạng thái cập nhật | Bước tiếp theo |
|---|---|---|
| A1, B2/B6 — identity, lưới và output | **Đạt phạm vi smoke lưới thực.** Preflight exit 0; 68 file / 76 mục; cùng năm ASC 2100×2100. Writer mới khớp năm biến và toàn bộ ngân sách bản cũ. | Đo xuất nhiều frame, peak RAM/VRAM và overhead ledger; lưu manifest sau lần sửa cuối. |
| A2 — provenance/đồng bộ UTC | **Mở.** Chưa xác nhận ERA5 gốc, căn cứ ×2; Ban Thạch ×1,25, gốc Q khác, datum, IL/CL, `zsinit`, scene ID SAR và UTC. | Lập bảng file gốc, phép biến đổi, đơn vị, giờ chuẩn, sai số và bằng chứng độc lập; không dùng chỉ số CSI để quyết định timestamp. |
| B5 — động lực/biên | **Mở.** Các synthetic trước đã qua nhưng còn dam-break, đối xứng, hội tụ, góc và điều kiện cửa ra/triều; ca Q ngay biên `type=2` đã ghi nhận backflow. | Chạy bài toán đối chứng độc lập, đo vận tốc/mặt nước/khối lượng; chọn boundary theo thủy lực và dữ liệu thực địa rồi kiểm tra lại hồi quy. |
| R1a 120 giờ | **Chưa mở.** | Khóa A2/B5 thiết yếu, cấu hình DEM V44 gốc, origin UTC và manifest; chạy có theo dõi I/O, bước thời gian và ngân sách, sau đó mới đánh giá SAR. |

Lệnh xác minh writer: `C:/Users/CuongHM/anaconda3/python.exe tests/compare_v45_output_frames.py`. Lệnh preflight cần chạy trong shell có `$env:PYTHONIOENCODING='utf-8'` để tránh `UnicodeEncodeError` do console `cp1252`. Kết quả mới nhất: `results/manifest_preflight.json`, SHA256 `B3867789E9481B2673F14FA986E30BA7752F628F1AC5E9AA61AEA7191359D0EF`. Không chỉnh DEM nháp V45 hoặc production V44 ở giai đoạn này.

## 13. Cổng A2: nguồn mưa và hydrograph Bàn Thạch — 28/09/2026

Đối chiếu đủ 144 dòng mưa V23/V34 cho thấy V34 bằng chính xác `2 × V23`, thời gian không đổi; tổng 120 giờ tương ứng 197,33688/394,67376 mm. Nguồn biến đổi: `D:/VTP/BG_Flood_Project/BG_Flood/prep_v34.py`. Điều này xác nhận tuyến tạo file trong repo; việc trích ERA5 từ 16 điểm và lý do hiệu chỉnh ×2 vẫn cần nguồn độc lập. Bàn Thạch V43 có 33 mốc, `Q(0)=675 m³/s`; V40 đồng bộ có 9 mốc, `1,25 × Q_V40(0)=312,5 m³/s`. V43 không phải V40 nhân trực tiếp 1,25; bản gốc được gọi `Real Data` trong header chưa truy được.

**A2 vẫn mở:** tìm file/query gốc, hệ giờ, đơn vị, phương pháp hiệu chỉnh và sai số cho từng nguồn. Tạm giữ chính các forcing này trong smoke để bảo toàn phép so trước/sau writer; chưa xem là forcing đã đủ provenance cho R1a. Báo cáo kỹ thuật R1 mục 7.8 lưu số liệu đối chiếu. Dữ liệu gốc và production V44 giữ nguyên.

## 14. Cổng A/B sau sửa gradient và xuất ba frame — 28/09/2026

| Cổng | Bằng chứng cập nhật | Việc còn lại |
|---|---|---|
| B2/B6 — nối block, solver, ghi kết quả | Trao đổi gradient qua mép block ở hai giai đoạn; 21/21 unit và smoke mask/padding, block không hoạt động, biên/Q/thấm đạt. Ba frame 20/40/60 s trên DEM V44 thực, năm biến 2100×2100, 18 bước ledger; residual lớn nhất 1,1921×10^-7 m³, sai khác thể tích frame/ledger dưới 0,5 m³. | Kiểm cặp chạy có cùng lịch thời gian để tách riêng tác động sửa gradient; hoàn thiện giám sát tài nguyên 120 giờ. |
| B5 — vật lý và biên | 8/8 nghiệm đối chứng CPU/GPU Ritter/xung vuông, `dx=1/0,5`; kết quả synthetic đạt. Ca Q ở biên `right=2` trước đó có backflow; Q thực tế không nằm ở ô biên ngoài cùng. | Khóa hình học đê/cửa, mực nước đuôi/triều và datum; thử boundary dựa trên thủy lực thực, kiểm hội tụ và đối chứng độc lập ở cấu hình cần dùng. **Mở.** |
| A1 — danh tính dữ liệu | Preflight cuối exit 0: 71 tệp riêng / 79 mục, năm ASC cùng grid. Manifest SHA256 `2bf776dc5f030604bf698fc5b3fc3a5a6d917465efd2dbcd1249292cd44f90ee`. | Băm lại sau mọi sửa mã/test/config/input; khóa manifest trước R1a. |
| A2 — provenance và thời gian | Đã chứng minh V34 = 2 × V23 cho 144 mốc và V43 Bàn Thạch không phải V40 nhân trực tiếp 1,25. | Truy ERA5 gốc/16 điểm, lý do ×2, Q quan trắc gốc/nhánh/epoch, IL/CL, `zsinit`, datum, Sentinel-1 scene ID và acquisition UTC. **Mở.** |
| R1a 120 giờ và CSI | Ca 60 s sau sửa gradient đã chạy, profile ngoài 263,57 s, max WorkingSet khoảng 1.299,17 MiB; **không có số đo VRAM theo PID**. | Chỉ khởi chạy sau cổng A2/B5 thiết yếu, trên DEM V44 gốc; ghi checkpoint/ledger/I/O và đối chiếu SAR theo scene/mask/timestamp đã khóa. **Chưa chạy, chưa có CSI V45.** |

Chi tiết phương pháp, hạn chế và hash NetCDF/ledger: `D:/VTP/V45_runs/20260928_engine_r1/results/V45_R1_Bao_cao_ky_thuat_20260928.md` mục 7.9–7.12. Giữ nguyên production V44, forcing và hai ca smoke trước gradient; không dùng DEM V45 nháp khi chưa có chứng cứ địa hình.

## 15. Cổng A/B sau chạy V45 nháp — 28/09/2026

| Cổng | Kết quả đã kiểm | Việc còn lại |
|---|---|---|
| A1/B2/B6 kỹ thuật | V45 nháp GPU exit 0, 18 bước và ba frame 20/40/60 s, năm biến 2100×2100; residual 2.38418579102e-07 m³. Preflight 73 file/81 mục, SHA256 3cbabd78c06e0c0e996a60a6afcc73112f977544289db2c5da7181872a98ec04. | Đo mô phỏng dài và kiểm restart đầy đủ. |
| B5 địa hình và biên | 41,907 ô hạ trên DEM nháp, tối đa 171.669 m. Toàn bộ ô sửa vẫn khô qua ba frame, chưa có tác động ngập đo được. | Kiểm khảo sát mặt cắt đê/cửa, datum, tailwater/triều và phương án biên. **Mở.** |
| A2 provenance | Mưa V34 = 2 × V23 trong repo; dữ liệu ERA5 gốc, cơ sở ×2, Q nguồn/epoch và SAR acquisition UTC chưa xác minh. | Truy nguồn, mạng nhánh, IL/CL, zsinit và timestamp/datum. **Mở.** |
| Run 120 giờ / CSI | Chỉ xác minh 60 s của DEM nháp; script resume hiện đọc lại h,zs, chưa được kiểm đủ trạng thái. | Xây dựng checkpoint tin cậy hoặc chạy liên tục có kiểm soát, khóa A2/B5 rồi chạy 120 h và đánh giá SAR. **Chưa đạt.** |

Phương pháp, output hash và các điều kiện của kết luận nằm trong báo cáo R1 mục 7.13. Không sửa production V44.

## 16. Cổng A/B sau checkpoint 20 s GPU toàn miền — 28/09/2026

| Cổng | Bằng chứng đạt | Điều kiện còn thiếu |
|---|---|---|
| B2/B6 checkpoint/restart | Hồi quy synthetic 32×16: CPU/GPU 120 s liên tục trùng 60 s + resume; kiểm sửa hỏng checkpoint, đổi đầu vào và ledger vượt cursor đều bị từ chối. Ca GPU V45 nháp toàn miền dừng 20 s, NPZ lưu đủ 10 trạng thái float64; ba artifact khớp SHA256 metadata. Năm biến của frame 20 s và 5 bước ledger trùng tuyệt đối với ca liên tục tham chiếu. | Resume GPU toàn miền 20→60 s chưa thực thi do xét duyệt tự động từ chối; cần đối chiếu frame 40/60 s, toàn ledger và trạng thái cuối. |
| A1 danh tính và tái lập | Preflight UTF-8 exit 0: 77 tệp / 85 mục, năm ASC 2100×2100; manifest SHA256 `00e9890c861ff61960eb77dc464a36958bc7d5785254643f7a8a3bc3a374a5f2`. | Băm lại sau mọi thay đổi cuối; khóa config/manifest R1a sau A2/B5. |
| A2 nguồn, đơn vị và thời gian | 10 hash đầu vào/config của checkpoint khớp metadata; lineage nội bộ V34=2×V23 trên 144 mốc đã được đối chiếu. | Cần ERA5 gốc, 16 điểm/lý do ×2, Q gốc Bàn Thạch V43/epoch/mạng nhánh, IL/CL, `zsinit`, datum và Sentinel-1 scene ID/acquisition UTC. **Mở.** |
| B5 địa hình/biên | Ca 20 s trên DEM V45 nháp và cặp 60 s đã chạy kỹ thuật. | Thiếu khảo sát hình học đê/cửa, mực nước đuôi/triều và đối chứng biên theo dữ liệu; DEM nháp hạ 41.907 ô chưa đủ kiểm định. **Mở.** |
| R1a 120 giờ / CSI | Có cơ chế checkpoint R1 và bằng chứng tại điểm dừng 20 s. | Cần hoàn tất restart toàn miền và A2/B5 thiết yếu; chỉ chạy R1a 120 giờ trên DEM V44 gốc sau khi khóa nguồn/config. **Chưa chạy; chưa có CSI V45 kiểm định.** |

Chi tiết và giới hạn nằm trong báo cáo kỹ thuật R1 mục 7.14; script đọc kiểm chứng `tests/verify_v45_checkpoint_pilot.py`. Không thay đổi DEM, forcing hay sản phẩm production V44.

## 17. Công việc tiếp sau cổng SAR/nguồn — 28/09/2026, 20:24 ICT

**Kết quả đã có:** audit hai TIFF SAR trùng byte, chưa có scene ID/UTC; science gate R1a `ready=false` với 11 blocker; preflight UTF-8 exit 0 và manifest 81 file/89 mục. Đường dẫn, hash và phương pháp nằm tại báo cáo R1 mục 7.15. Giữ V44 production và DEM nháp hiện tại nguyên vẹn.

**Đợt A2 ưu tiên:**

1. Truy CDS request/product và dữ liệu ERA5 nguyên bản cho 16 điểm; ghi cell tọa độ, biến, chu kỳ tích lũy, UTC, phép nội suy, chuyển đơn vị và căn cứ hệ số ×2.
2. Truy thủy văn gốc Bàn Thạch V43 và ba hydrograph còn lại; khớp từng vị trí nguồn, giờ đo, mạng nhánh và độ trễ; đánh giá nguy cơ đếm trùng và nhãn `Real Data x1.25`.
3. Xác minh đơn vị/cơ sở IL/CL, `zsinit=1 m`, datum DEM/trạm/triều và các phép đổi cao độ; kết nối số đo Phú Lâm với hệ quy chiếu sau xác minh.
4. Lấy Sentinel-1 product ID, thời gian bắt đầu/kết thúc UTC, quỹ đạo, polarization và lineage tạo raster Otsu; xác định ảnh đơn, mosaic hay hợp nhiều thời điểm, rồi khóa mask/timestamp đánh giá độc lập.

**Đợt B5:** thu hồ sơ khảo sát đỉnh đê, cửa thông và mặt cắt kênh; xác định mực nước đuôi/triều; thử lựa chọn biên mở và backflow dựa trên dữ liệu có datum. Không dùng raster 90 m để tự suy ra bề rộng/cao trình cửa 5–60 m. Chỉ xem xét DEM V45 sau khi hình học được kiểm chứng.

**Đợt R1a:** hoàn thiện so full-grid GPU checkpoint 20→60 s khi được phép, khóa manifest/config/epoch/nguồn đã duyệt, chạy 120 giờ trên **DEM V44 gốc** với ledger, checkpoint và theo dõi tài nguyên. Sau khi có bản chạy hợp lệ và SAR độc lập được đồng bộ, mới tính CSI/độ nhạy và so các phương án V45. Không có chứng cứ mới để coi 120 giờ hay CSI đã hoàn tất.

## 18. Việc tiếp theo sau audit V42 và catalog ASF — 28/09/2026, 20:43 ICT

**Đã xác nhận:** cấu trúc V42 có hai nhánh Q giả định khi thiếu source, nội suy hai nguồn và cộng lưu lượng; cả bốn file hiện diện nhưng chưa đủ provenance gốc và lịch sử tạo V43. ASF có cảnh Sentinel-1A phù hợp vị trí và giờ địa phương 05:36 ngày 30/11/2021; chưa có liên kết từ scene gốc đến TIFF Otsu. Audit Q tại R1 `results/V45_BanThach_generator_audit.json`; nghiên cứu ASF tại `D:/VTP/V45_Sentinel1_scene_research_20260928.md`. Preflight hiện hành 86 tệp/94 mục; science gate còn 11 blocker.

**Thứ tự công việc:** (1) lấy log/version của quy trình tạo V42/V43, hai hydrograph quan trắc gốc và sơ đồ vị trí nguồn để đối chiếu thời điểm, trễ dòng và phép cộng, đồng thời chứng minh căn cứ x1.25; (2) lấy CDS request/ERA5 nguyên bản và bảng 16 điểm, xác minh khoảng tích lũy, UTC và lý do nhân mưa ×2; (3) tìm GEE export script/task, toàn bộ image ID và phép ghép/Otsu/SNIC để khóa source → TIFF → acquisition UTC và mask; (4) đo và chuyển đổi datum của DEM, Q/mực nước, IL/CL, zsinit, đỉnh đê/cửa, tailwater/triều; (5) khi được phép, kiểm checkpoint GPU toàn miền 20→60 s và so ca liên tục; (6) duyệt lại gate và khóa đầu vào rồi mới chạy R1a 120 giờ trên DEM V44 gốc, tiếp đến đánh giá độc lập và xây phương án V45. Không dùng scene ứng viên để tự chọn frame hoặc dùng SAR đã can thiệp DEM để kiểm định chính DEM ấy.

## 19. Sau kiểm tra loader forcing — 28/09/2026, sau 21:09 ICT

**Đã đóng ở mức kỹ thuật:** R1 từ chối forcing có timestamp không tăng nghiêm ngặt, NaN/Inf, số cột thay đổi hoặc rỗng. Nhóm unit đạt 22/22; hai tệp mưa V23/V34 đọc hợp lệ, file ERA5-Land lịch sử bị từ chối ở dòng 148; baseline V44 và V45 nháp đều nạp mưa V34 uniform trên khoảng 0..514800 s cho endtime=432000 s. Preflight đạt 87 file/95 mục. Các chi tiết tại báo cáo R1 mục 7.17.

**Đang mở:** science gate R1a còn 11 blocker. Thứ tự ưu tiên là (1) bản gốc CDS/ERA5 và toàn bộ lineage 16 điểm, khoảng tích lũy, timezone/epoch và căn cứ ×2; (2) Q quan trắc gốc, sơ đồ mạng và lịch tạo V42/V43/×1.25, bao gồm độ phủ thời gian bốn hydrograph; (3) nguồn đơn vị IL/CL, datum và cơ sở `zsinit`; (4) GEE export/script và scene ID → TIFF, mask/timestamp SAR; (5) khảo sát crest/cửa, triều/tailwater và biên; (6) restart GPU toàn miền khi được phép, so với chạy liên tục. Lệnh đọc thêm đường dẫn Q trong lượt này bị xét duyệt tự động chặn và không được chạy. Sau khi chứng cứ khoa học được thẩm định, khóa manifest và cấu hình trước khi cân nhắc R1a 120 giờ trên DEM V44 gốc. Không tự lấy 60 giây smoke làm nghiệm thu V45 hay tính CSI.

## 20. Kế hoạch sau đối soát đa khung và fingerprint checkpoint — 28/09/2026, sau 21:33 ICT

**Đã kiểm lại:** `smoke_v45_checkpoint.py` CPU/GPU PASS trên synthetic 32×16; smoke mưa GPU và bốn ca vị trí Q đều PASS. Verifier V44/V45 nháp 2100×2100 tại 20/40/60 s exit 0, mỗi ca đủ năm trường và 18 dòng ngân sách; preflight đạt 87 file/95 mục. Chi tiết tại báo cáo đối soát v6 trong R1/results.

**Còn mở:** metadata của checkpoint 20 s khớp cả ba artifact và toàn bộ 10 input/config; verifier mã hiện tại exit 1 vì `read_forcing.py` đã thay đổi sau khi tạo checkpoint. Không coi đây là một lượt resume và không bỏ qua fingerprint. `r1a_120h` tiếp tục `ready=false` với 11 blocker. Thu bản gốc ERA5/CDS, căn cứ mưa ×2, Q/mạng sông/epoch, đơn vị thấm và datum, lineage scene SAR, khảo sát đê/cửa và tailwater; sau đó đối chứng restart GPU toàn miền bằng bản mã phù hợp khi được phép. Chỉ khóa R1a 120 h trên DEM V44 gốc khi dữ liệu, biên và checkpoint đã đủ căn cứ; chưa tính CSI V45.
