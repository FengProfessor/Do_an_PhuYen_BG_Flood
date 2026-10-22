# V49 — Cơ sở khoa học để kiểm định ngập bằng Sentinel-1

Ngày tổng hợp: 14/10/2026. Phạm vi: kiểm định diện ngập và diễn giải Gate G; không khảo sát nguồn mưa hay kiểm toán mã chấp nhận.
Ghi chú tách ba lớp: bằng chứng công bố; dữ kiện kiểm tra từ hồ sơ dự án; đề xuất phương pháp.
Không mở NetCDF/raster, không chạy solver/evaluator, không sửa tệp hiện có; chỉ tạo ghi chú này.
Kết luận phương pháp: đối chiếu Sentinel-1 hỗ trợ đánh giá diện ngập có thể quan sát tại thời điểm chụp; không tự chứng minh đáy sông hoặc datum.

## 1. Bằng chứng đã công bố

### 1.1 Một ảnh chụp và diện ngập cực đại

GFM tạo Observed Flood Extent từ lần Sentinel-1 đi qua tại một ngày/thời điểm; đó là sản phẩm quan sát theo lần chụp. [GFM PUM, §3.1](https://extwiki.eodc.eu/GFM/PUM/Products).
Maximum Flood Extent của GFM là tổ hợp các lớp ngập có sẵn trong khoảng thời gian chọn; không phải tên gọi thay thế cho một ảnh. [GFM PUM, §3.1.1](https://extwiki.eodc.eu/GFM/PUM/Products).
Rebolho et al. gộp các bản đồ mô phỏng theo ngày thành cực đại để so với bản đồ cực đại; tác giả nói rõ phép so này không kiểm định động lực thời gian. [Rebolho et al. 2018, §4.1](https://hess.copernicus.org/articles/22/5967/2018/).
Suy luận áp dụng: so một ảnh với hmax toàn trận trộn hai đại lượng khác nhau; ngập đã rút hoặc sẽ xuất hiện có thể bị tính là sai dù không đồng thời với ảnh.
Suy luận áp dụng: cực đại từ những lần chụp thưa chỉ là cực đại đã quan sát; không bảo đảm bao trùm cực đại thật giữa các lần chụp.

### 1.2 Nước thường xuyên và miền chấm điểm

GFM phân biệt Observed Water Extent với Observed Flood Extent; lớp ngập loại các vùng nước tham chiếu thường xuyên/theo mùa bằng Reference Water Mask theo tháng. [GFM PUM, §3.1–3.3](https://extwiki.eodc.eu/GFM/PUM/Products).
Khuyến nghị của tác giả: nếu đánh giá ngập mới trên đất, loại nước tham chiếu khỏi miền chấm điểm chung của cả quan sát và dự báo.
Loại đối xứng như vậy tránh điểm TP dễ đạt trong lòng sông; lưu riêng kết quả tổng mặt nước nếu cần đánh giá mục tiêu khác.
Không đồng nhất một biến mang tên water_density với JRC occurrence, hay với Reference Water Mask của GFM, khi chưa có nguồn gốc được xác minh.

### 1.3 Quan sát được, không quan sát được và lớp địa vật

Mason et al. mô tả shadow có thể tối như nước, layover có thể sáng che ngập, và khai thác tăng tán xạ kép nước–nhà bằng phương pháp chuyên biệt. [Mason et al. 2021, §1, §6](https://centaur.reading.ac.uk/95506/9/032003_1.pdf).
Tsyganskaya et al. tách nước thoáng và thực vật ngập bằng chuỗi Sentinel-1; thực vật ngập có tán xạ kép/đa lần mạnh, cần đặc trưng và thông tin bổ trợ thích hợp. [Tsyganskaya et al. 2018, §2.2, §6](https://www.mdpi.com/2072-4292/10/8/1286).
Vì thế không được gộp mọi đô thị/thực vật thành “SAR không phát hiện được”, hoặc coi mọi pixel sáng là khô; phải xác định khả năng quan sát của phương pháp cụ thể.
GFM dùng Exclusion Mask cho vùng không thể phân lớp đáng tin và Advisory Flags cho một số điều kiện làm giảm tương phản; gió có thể làm mặt nước sáng hơn. [GFM PUM, §4.1–4.3](https://extwiki.eodc.eu/GFM/PUM/Recommendations).
GFM mô tả vùng không thể phân lớp là no-data; đây khác trạng thái khô đã quan sát. [GFM PUM, §4.3](https://extwiki.eodc.eu/GFM/PUM/Recommendations).
Khuyến nghị: báo diện tích M_obs, diện tích bị loại, diện tích còn bất định và tỷ lệ bao phủ AOI; lưu các lý do loại và phân tầng theo địa vật.
Tên RTC hoặc raster nhị phân không chứng minh đã khôi phục quan sát trong shadow/layover; ghi chú này không đánh giá thực nghiệm raster địa phương.

### 1.4 Thời điểm thủy lực và hai loại ngưỡng

Gobeyn et al. dùng khung ảnh SAR tổng hợp để nghiên cứu thời điểm hiệu chỉnh; trong ca đó, ảnh trước đỉnh ràng buộc nhám tốt hơn ảnh gần/sau đỉnh. Không suy thành quy tắc tối ưu phổ quát. [Gobeyn et al. 2017, abstract](https://research-information.bris.ac.uk/ws/portalfiles/portal/98339258/Manuscript_AWR.pdf).
Bài này thay đổi ngưỡng tán xạ SAR theo dB để lập bảng nhầm lẫn; ngưỡng tín hiệu ảnh và ngưỡng độ sâu mô hình là hai đại lượng khác nhau. [Gobeyn et al. 2017, §2.3](https://research-information.bris.ac.uk/ws/portalfiles/portal/98339258/Manuscript_AWR.pdf).
Suy luận: h > h0 xác định mặt nạ dự báo; Otsu trên ảnh không tự chứng minh SAR phát hiện chính xác mọi ô h > 0,3 m.
Khuyến nghị: khóa thời điểm theo timestamp quan sát và quy tắc ghép đã định; các frame lân cận chỉ phục vụ chẩn đoán độ nhạy.
Theo toán học, nội suy h rồi áp ngưỡng không đồng nghĩa nội suy mặt nạ 0/1; cần ghi rõ phép nội suy, giả định và sai số thời gian.

### 1.5 Chỉ số và diện tích

Trên cùng miền hợp lệ, TP là cùng ngập, FP là chỉ mô hình ngập, FN là chỉ quan sát ngập, TN là cùng khô.
CSI phạt cả FP/FN; BIAS diện tích là tỷ số số ô mô phỏng ngập với số ô quan sát ngập, và BIAS = 1 vẫn có thể bù sai vị trí. [Rebolho et al. 2018, §4.1, Table 3](https://hess.copernicus.org/articles/22/5967/2018/).
Các công thức dưới đây là định nghĩa/toán học áp dụng cho cùng mặt nạ; dùng trọng số diện tích nếu ô có diện tích khác nhau:

| Đại lượng | Công thức | Diễn giải |
| --- | --- | --- |
| CSI / IoU | TP/(TP+FP+FN) | Giao trên hợp diện ngập |
| Precision | TP/(TP+FP) | Phần dự báo ngập trùng quan sát |
| Recall | TP/(TP+FN) | Phần ngập quan sát được dự báo |
| F1 / Dice | 2TP/(2TP+FP+FN) | Cân bằng precision và recall |
| Tỷ số diện tích B | (TP+FP)/(TP+FN) | B > 1: dư diện tích; B < 1: thiếu |
| Sai lệch diện tích b | B−1 = (FP−FN)/(TP+FN) | b × 100% là phần trăm sai lệch |
| Tổng bất đồng | FP+FN | Sai vị trí có thể lớn dù b gần 0 |

Tự suy đại số: F1 = 2CSI/(1+CSI); trên cùng phân lớp/mặt nạ, đây không phải hai bằng chứng độc lập và cho cùng thứ hạng.
Nếu mẫu số bằng 0, ghi NA và nguyên nhân; không tự đặt điểm hoàn hảo cho vùng không có ngập để so sánh.
Stephens et al. chỉ ra CSI phụ thuộc quy mô trận và độ dốc địa hình, và có thể thiên về dự báo dư; cùng sai số cao độ có thể cho điểm khác nhau. [Stephens et al. 2014, abstract](https://research-information.bris.ac.uk/en/publications/problems-with-binary-pattern-measures-for-flood-model-evaluation/).
Do đó ghi chú không đặt một CSI/F1 phổ quát làm giá trị “đạt”; cần đọc cùng diện tích, bản đồ FP/FN, bao phủ và bất định.

### 1.6 Hiệu chỉnh, kiểm định độc lập, đáy và datum

Horritt & Bates hiệu chỉnh bằng một trận, kiểm định bằng trận thứ hai; thiết kế này kiểm tra năng lực dự báo vượt ngoài dữ liệu hiệu chỉnh. [Horritt & Bates 2002, abstract, §1](https://doi.org/10.1016/S0022-1694(02)00121-X).
Neal et al. cho thấy hiệu chỉnh nhám có thể đạt độ khớp mực nước tương tự hiệu chỉnh hình học nhưng làm truyền sóng chậm sai nhiều giờ; độ khớp không xác định duy nhất hình học đúng. [Neal et al. 2015, Summary](https://www.sciencedirect.com/science/article/pii/S0022169415005235).
Ví dụ USGS đo, chụp ảnh và khảo sát HWM nối với datum NAVD 88; đó là bằng chứng cao độ có quy chiếu cụ thể, không chỉ dấu nước có vị trí đại khái. [USGS, bộ HWM Hurricane Ida 2021](https://www.usgs.gov/data/high-water-marks-new-jersey-following-hurricane-ida-and-associated-floods-september-2021).
Suy luận về định danh cao độ: h = zs−zb không đổi khi zs và zb cùng cộng c; kiểm tra quan hệ nội bộ này không xác lập datum tuyệt đối.
Ví dụ chỉ minh họa dịch chuyển chung hệ quy chiếu, không khẳng định dịch riêng đáy và giữ mọi điều kiện khác sẽ cho nghiệm như cũ.
Một ảnh nhị phân không trực tiếp đo đỉnh toàn trận, thời gian đến, vận tốc, WSE, đáy hoặc datum; phạm vi chứng minh cần giới hạn ở đại lượng đã quan sát.
Muốn xác nhận đáy/cao độ tuyệt đối: bổ sung khảo sát đáy có tọa độ, datum và bất định, cùng chuỗi WSE/HWM đã nối cùng datum; đây là đề xuất kiểm chứng độc lập.

## 2. Dữ kiện cục bộ từ hồ sơ dự án

Nguồn phần này là mã/báo cáo/JSON của dự án; không phải nghiên cứu công bố hay một lần kiểm định NetCDF độc lập.
Các diễn giải mã dưới đây chỉ xác định ý nghĩa mặt nạ và trạng thái thiếu; không kiểm toán điều kiện chấp nhận.

### 2.1 Thiết kế và timestamp ghi trong tệp

Báo cáo mô tả BASE/CENTRAL/LOW/HIGH ghép cấu hình 30 m, chỉ terrain/output thay đổi; BASE cũ khoảng 105 h, chưa đủ 120 h. [Báo cáo triển khai](D:/VTP/River_Bathymetry_Project/V49_G_IMPLEMENTATION_REPORT_20261013.md).
Manifest ghi epoch 2021-11-25T17:00:00Z, endtime 432000 s, output 10800 s (3 h). [Manifest, cấu hình thời gian](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_PREPARATION_MANIFEST.json:477).
Ảnh Otsu S1RTC: D:/VTP/05-Du-lieu-GIS/DakLak_PhuYen_FloodExtent_Otsu_S1RTC_20211130_05h36_V48.tif. [Manifest](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_PREPARATION_MANIFEST.json:489).
SHA256 đóng băng được ghi: 9c1ad68908c220456c82a2459380e14193242a3daa32c0001989c4ffd8292db6; chưa tính lại trong nghiên cứu này. [Manifest](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_PREPARATION_MANIFEST.json:489).
Midpoint chụp 2021-11-29T22:36:51.298763Z = khoảng 05:36:51 ngày 30/11/2021 UTC+07; elapsed tính từ epoch 365811.298763 s ≈ 101,61425 h. [Manifest; phép tính từ timestamp](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_PREPARATION_MANIFEST.json:489).
Quy ước chính: h > 0,3 m; water_density ≤ 0,5; HAND ≥ 0; frame gần nhất, lệch tối đa 5400 s, hòa chọn frame sớm. [Manifest](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_PREPARATION_MANIFEST.json:494), [quy tắc frame](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:26).
Parent xác minh SAR được giữ ngoài conditioning nhưng từng xem ở V39–V45: gọi là đối chiếu xác nhận hồi cứu, chưa phải kiểm định hoàn toàn độc lập. [Báo cáo triển khai](D:/VTP/River_Bathymetry_Project/V49_G_IMPLEMENTATION_REPORT_20261013.md).

### 2.2 Ý nghĩa mã mặt nạ và thiếu dữ liệu

Raster được căn chỉnh bằng nearest-neighbor. [Mã căn chỉnh](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:71).
Miền hiện tại: isin(sar,[0,1]) & (water ≤ threshold) & (hand ≥ 0); nước tham chiếu được loại đối xứng khỏi bảng nhầm lẫn. [Mã mặt nạ](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:108).
Ngữ nghĩa hạn chế: nhãn SAR 0/1 hợp lệ về mã không chứng minh đô thị, thực vật, shadow/layover đều quan sát được; M_obs vật lý cần bằng chứng riêng.
Water nodata được điền −9999, do đó có thể vượt qua điều kiện ≤ 0,5. Kiểm toán raster tĩnh bổ sung ngày 14/10 xác nhận **0 ô water-density thiếu** trên grid và trong mask, nên pattern này không ảnh hưởng phép chấm trên raster hiện tại. [Mã căn chỉnh/mặt nạ](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:71), [audit tĩnh](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_static_mask_audit.json).
NaN, gồm masked h được fill thành NaN, chuyển thành 0 trong tính bảng nhầm lẫn; mọi h không hữu hạn được đếm riêng. +Inf/−Inf mặc định chuyển thành số hữu hạn rất lớn dương/âm, không phải 0. [Chuyển h](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:112), [đếm thiếu](D:/VTP/River_Bathymetry_Project/v49_evaluate_hydraulic_validation.py:123).
Diễn giải: thiếu h là chưa biết, không phải khô đã quan sát; chuyển NaN thành 0 có thể tính thiếu như dự báo khô. BASE ghi missing = 0 nên không có hiệu ứng đó trên miền BASE đã ghi. [BASE metrics](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_BASE_hydraulic_metrics.json:23).
Giữ miền so sánh đã đóng băng giữa các arm; mọi mặt nạ quan sát cải tiến phải có nhãn chẩn đoán, không tương đương với điểm chính cũ.

### 2.3 Snapshot BASE đã ghi và giới hạn Gate G

Frame 33 tại 367200.125 s, lệch timestamp 1388.826237 s ≈ 23,15 phút; complete_to_120h = false. [BASE metrics](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_BASE_hydraulic_metrics.json:8).
Các trị sau được đọc từ JSON; các diện tích FP/FN/miền là phép tính từ số ô và diện tích ô 30 × 30 m, không phải lần chạy mới:

| Đại lượng | BASE đã ghi / phép tính |
| --- | --- |
| TP / FP / FN / TN | 314637 / 241912 / 259630 / 2032081 |
| CSI / F1 | 0,385500 / 0,556478 |
| Precision / recall | 0,565336 / 0,547893 |
| Diện ngập quan sát / dự báo | 516,8403 / 500,8941 km² |
| b = A_pred/A_obs − 1 | −0,03085324 ≈ −3,0853% |
| Miền đánh giá | 2848260 ô = 2563,434 km² |
| FP / FN / tổng bất đồng | 217,7208 / 233,6670 / 451,3878 km² |

Nguồn bảng: [BASE metrics](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_BASE_hydraulic_metrics.json).
Diễn giải: diện tích tổng gần nhau nhưng bất đồng 451,3878 km²; F1/CSI và area bias cần đọc đồng thời với FP/FN.
BASE cũ dùng được làm đối chiếu snapshot đã ghi; không đại diện cho một arm ghép cấu hình đã hoàn tất hợp đồng 120 h.
JSON ghép hiện có BASE, CENTRAL/LOW/HIGH pending; gate_g_pass = false, promotion = false là trạng thái ghi sẵn. [Matched metrics](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_matched_hydraulic_metrics.json).
Metadata đọc gần nhất được cập nhật 2026-10-13T22:50:50.200120Z, ghi CENTRAL RUNNING và queue LOW,HIGH,BASE; không xác minh tiến độ solver sống. [Execution state](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_EXECUTION_STATE.json).
BASE ghi WSE UNAVAILABLE_NO_VERIFIED_DATUM_AND_GAUGE_SERIES; timing UNAVAILABLE_NO_VERIFIED_TIMESTAMPED_GAUGE_SERIES. [BASE metrics](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_BASE_hydraulic_metrics.json:38).
Có chẩn đoán bổ sung 20 HWM công bố với vị trí thô; absolute_wse_error_computed = false, cao độ tuyệt đối chưa kiểm định vì datum/tọa độ chính xác chưa xác minh. [BASE metrics](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_BASE_hydraulic_metrics.json:294).
Không diễn giải “chưa có WSE xác minh” thành “không có bất kỳ bằng chứng HWM”; các điểm thô chỉ hỗ trợ chẩn đoán bao giá trị.

### 2.4 Dữ kiện kiểm toán forcing bổ sung ngày 14/10

Nguồn là [kiểm toán offline và checksum](D:/VTP/River_Bathymetry_Project/V49_RESEARCH_20261014/V49_forcing_audit.json), [báo cáo bổ sung](D:/VTP/River_Bathymetry_Project/V49_CONTINUED_RESEARCH_20261014.md), không phải một lần chạy NetCDF mới.
Audit offline xác minh V34 = 2 × V23; mưa native linear 120 h là 394,67376 mm, so với mean 256,29375 mm của bản dẫn xuất Open-Meteo ERA5 lưu trữ đã căn đúng t0 = 2021-11-25T17:00:00Z.
Chênh +53,99% lấy sản phẩm dẫn xuất làm tham chiếu: đây là so sánh giữa sản phẩm forcing, không phải sai lệch so với lượng mưa quan trắc.
Phần carved được chấp nhận là 72 pixel = 0,0648 km²; coldstart toàn miền 794,467 triệu m³, trong R3OCEANmask 762,448 triệu m³ ≈ 95,97%.
Diễn giải có điều kiện: các dữ kiện này là bối cảnh cho so sánh địa hình ghép cặp dưới cùng forcing (CONDITIONAL); không biến phép so thành hiệu chỉnh/kiểm định tuyệt đối độc lập.

## 3. Giao thức tập trung được đề xuất

Đây là đề xuất của tác giả; chưa thực thi, không phải chuẩn đạt do các bài báo công bố.

1. Khóa mục tiêu chính là ngập tại midpoint ảnh; tách hoàn toàn phép đối chiếu cực đại toàn trận.
2. Lưu timestamp UTC, footprint, phân cực/quỹ đạo/phương pháp phân lớp, checksum và mọi no-data/quality mask đã xác minh.
3. Kiểm kê khả năng quan sát M_obs, bao phủ AOI, vùng không biết và lý do loại; không mặc định ô chưa quan sát là 0. Mọi M_obs bổ sung chỉ là chẩn đoán, không thay miền chính đã khóa.
4. Miền chính giữ đúng preregistration chung, loại nước thường xuyên đối xứng; không chọn mặt nạ riêng cho từng arm để tối đa điểm.
5. Chẩn đoán bổ sung về M_obs/water nodata phải ghi rõ miền mới, diện tích thay đổi và tính không tương đương với điểm chính; không thay mặt nạ/ngưỡng chính hậu nghiệm.
6. Ghép tất cả arm theo frame gần nhất, dung sai 5400 s, hòa chọn sớm như đã khóa; không tìm frame tối ưu riêng. Frame trước/sau chỉ chẩn đoán và phải được chỉ định trước khi xem kết quả.
7. Nếu thiếu h, báo số ô/diện tích và độ bao phủ từng arm; giữ thiếu là unknown. Phép chấm trên giao miền h hữu hạn chung phải tách riêng, không âm thầm thay điểm chính.
8. Giữ h > 0,3 m cho phép so chính; các ngưỡng 0,1/0,3/0,5 m chỉ là độ nhạy bổ sung mang tính khám phá, cùng miền/thời điểm, không thay ngưỡng chính.
9. Các trị thăm dò là lựa chọn khám phá của tác giả, không phải ngưỡng SAR hoặc chuẩn chấp nhận; không chọn trị đẹp nhất sau khi thấy CSI.
10. Độ nhạy phân lớp SAR cần ảnh tán xạ/quy trình gốc hoặc sản phẩm uncertainty; raster nhị phân hiện có không đủ để tái tạo độ nhạy Otsu.
11. Khi có đủ đầu vào, khóa trước các biến thể ngưỡng SAR có cơ sở từ histogram/uncertainty và so cùng arm; báo dải CSI, bias, FP/FN và thay đổi thứ hạng.
12. Báo CSI toàn miền chính đã khóa, TP/FP/FN/TN, precision/recall, F1, A_obs/A_pred, b và bản đồ FP/FN; phân tầng đô thị/thực vật chỉ trên phần đã chứng minh quan sát được.
13. Chỉ lập cực đại quan sát khi có chuỗi ảnh; đối chiếu thêm cực đại mô hình tại các thời điểm ảnh, kèm coverage từng ảnh, để tách sai số lấy mẫu thời gian.
14. Khóa mô hình/quy trình trước một trận hoặc ảnh chưa dùng phát triển; lưu lịch sử SAR đã xem để không gọi hồi cứu là kiểm định độc lập.
15. Điều kiện đánh giá Gate G cần dựa mục tiêu sử dụng, sai số quan sát và thiết kế so sánh đã định; ghi chú này không đề xuất universal pass CSI/F1.
16. Tách hai kết luận: hỗ trợ diện ngập snapshot có điều kiện, và hoàn thành hợp đồng arm ghép 120 h; chỉ kết luận arm tốt hơn khi có các arm đủ và cùng support.
17. Khai báo reach/AOI theo địa lý/thủy lực trước khi đọc kết quả hoàn tất: quanh HR_41349822/HR_41352752 và bãi ngập kết nối; ghi ranh giới/tiêu chí kết nối, không chọn AOI hậu nghiệm để thắng điểm.
18. Khi các arm ghép hoàn tất, chẩn đoán LOCAL trên cùng ô quan sát hợp lệ trong miền đã khóa: bản đồ ngập/khô, sai khác ngập giữa arm và BASE ghép, cùng bản đồ FP/FN ở các reach/bãi ngập đã khai báo.
19. Báo coverage, thiếu/bất định, CSI và FP/FN địa phương, diện tích thay đổi tuyệt đối A_change = diện tích các ô hai arm khác trạng thái ngập (km²), Δh và thống kê |Δh| (m) trên cùng ô h hữu hạn; không thay bằng chênh diện tích thuần.
20. Muốn kết luận đáy/datum: bổ sung khảo sát đáy độc lập, WSE/HWM nối datum, tọa độ/thời gian/bất định; zs−zb=h chỉ là nhất quán số học nội bộ. Một lần chụp không kiểm chứng vận tốc hoặc datum WSE.

Gate G có thể hỗ trợ lựa chọn cấu hình tái hiện diện ngập trong miền và thời điểm kiểm tra; điểm diện ngập tự nó không cấp bằng chứng xác nhận cao độ đáy hay hệ quy chiếu đứng.

## 4. Nguồn gốc và giới hạn tiếp cận

Các nguồn dưới đây là bài nghiên cứu gốc hoặc tài liệu chính thức; không dùng bài tổng quan/bài viết thứ cấp làm bằng chứng.


- [GFM Product User Manual, §3](https://extwiki.eodc.eu/GFM/PUM/Products): snapshot, composite cực đại, nước/ngập và reference water.
- [GFM Product User Manual, §4](https://extwiki.eodc.eu/GFM/PUM/Recommendations): false/missed alarms, Exclusion Mask, Advisory Flags và no-data.
- [Mason, Dance & Cloke 2021](https://doi.org/10.1117/1.JRS.15.032003): Journal of Applied Remote Sensing 15, 032003; nội dung bản xuất bản từ kho Reading.
- [Tsyganskaya et al. 2018](https://doi.org/10.3390/rs10081286): Remote Sensing 10, 1286; §2.2 và §6, [bản xuất bản DLR](https://elib.dlr.de/122281/1/remotesensing-10-01286-v2.pdf).
- [Gobeyn et al. 2017](https://doi.org/10.1016/j.advwatres.2016.12.005): Advances in Water Resources 100, 126–138; bản tác giả được chấp nhận tại Bristol.
- [Rebolho, Andréassian & Le Moine 2018](https://doi.org/10.5194/hess-22-5967-2018): HESS 22, 5967–5985; toàn văn §4.1 và Table 3.
- [Stephens, Schumann & Bates 2014](https://doi.org/10.1002/hyp.9979): Hydrological Processes 28, 4928–4937; abstract do Bristol/Oxford lưu.
- [Horritt & Bates 2002](https://doi.org/10.1016/S0022-1694(02)00121-X): Journal of Hydrology 268, 87–99; [toàn văn bản xuất bản](https://repository.geologyscience.ru/bitstream/handle/123456789/28355/Horr_02.pdf?sequence=1).
- [Neal et al. 2015](https://doi.org/10.1016/j.jhydrol.2015.07.026): Journal of Hydrology 529, 169–183; Summary trên trang nhà xuất bản.
- [USGS HWM Hurricane Ida 2021](https://www.usgs.gov/data/high-water-marks-new-jersey-following-hurricane-ida-and-associated-floods-september-2021): ví dụ dữ liệu khảo sát nối datum; không suy NAVD 88 áp dụng cho V49.
Giới hạn đọc: một số trang/PDF bị 403/429, chống bot hoặc vượt kích thước; Mason/Tsyganskaya/GFM có đoạn nguồn gốc lập chỉ mục, không tải trọn PDF qua công cụ.
Stephens được dùng trong phạm vi abstract; Neal trong phạm vi Summary. Không gán thông số hay ngưỡng đạt ngoài nội dung đã đọc.
Giới hạn thực nghiệm: chưa xác minh độ đúng phân lớp Otsu, nguồn water_density, NetCDF hoặc tiến độ solver sống. Kiểm toán raster tĩnh bổ sung đã xác minh số ô thiếu và mask như liên kết ở §2.2; điều này không chứng minh khả năng quan sát vật lý của SAR.
