# V49 — phục hồi và nghiên cứu sau mất điện, 14/10/2026

**Phục hồi được 11/11 khung không gian CENTRAL, từ giờ mô phỏng thứ 3 đến thứ 33. NetCDF còn đọc được đầy đủ. Log tới giờ 35,401; khoảng 2,401 giờ cuối không có bản ghi không gian. Dữ liệu này có giá trị nghiên cứu nhưng chưa đủ quyết định Gate G và chưa phải checkpoint để tiếp tục chính xác.**

Đã xác nhận không còn worker/supervisor Python trước khi đọc kết quả. Máy khởi động lại lúc 12:20:40 ngày 14/10 UTC+7 theo hệ điều hành; log ghi cuối khoảng 11:10 cùng ngày. Thời điểm mất điện chính xác không được suy từ timestamp file. Nguyên nhân mất điện là thông tin người dùng cung cấp.

## Dữ liệu giữ lại và tính toàn vẹn

Đã sao lưu 16 file: NetCDF, log, budget, execution state cũ, preparation manifest và 11 ảnh. Bản gốc kết quả không bị sửa/ghi đè. [Registry bản sao và SHA-256](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_RAW_PRESERVATION_REGISTER.json).

NetCDF gốc/bản sao có cùng SHA-256 `ab4fe8ea2ae35b71b201d088c40102ce5834d2971064da53652534a1ae26ac64`, kích thước 511.564.869 bytes. [Bản sao đọc được](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/RAW/V49_G_CENTRAL.nc).

Một lý do output còn dùng được là [writer](D:/VTP/V48_runs/20261004_runtime_fix_r1/python/bg_flood/write_output.py:195) sync và close NetCDF sau từng frame, trước khi vẽ PNG. Khi mất điện, file không nhất thiết đang mở để append. Ở đây đã kiểm chứng nội dung từng frame; không cần sửa cấu trúc HDF5 hoặc giả tái tạo dữ liệu bị thiếu.

| Mốc | Kết quả xác minh |
|---|---|
| Khung đã lưu | 11 mốc, khoảng 3/6/9/…/33 giờ, chu kỳ output 3 giờ |
| Khung cuối | 118.800,4453125 s = 33,000124 giờ; 27/11/2021 09:00:00,445 UTC+7 |
| Tiến độ có dữ liệu không gian | 27,5001% hợp đồng 120 giờ |
| Log cuối | 127.444,14 s = 35,40115 giờ; 29,5010% |
| Đuôi chưa ghi không gian | 8.643,6946875 s = 2,401026 giờ |
| LOW/HIGH/BASE 120 giờ mới | Chưa khởi chạy |
| Trạng thái execution hiện hành | `INTERRUPTED_POWER_LOSS`; PID đang chạy được xóa, queue giữ LOW/HIGH/BASE |

Trạng thái `RUNNING` cũ là metadata chưa được supervisor sửa khi nguồn điện tắt. Đã giữ bản cũ trong RAW rồi cập nhật [execution state](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_EXECUTION_STATE.json) theo kết quả kiểm tra process và phục hồi. Không tự khởi chạy mô hình mới trong lượt đánh giá này.

[Script phân tích có thể chạy lại](D:/VTP/River_Bathymetry_Project/v49_salvage_interrupted_results.py) kiểm checksum 16 bản sao, 22 input tĩnh từ hồ sơ nghiên cứu, hash BASE lịch sử và normalized config BASE/CENTRAL. Mỗi frame đều được đọc toàn bộ **h/zs/zb/u/v**, kiểm lưới tọa độ và miền hợp lệ, không chỉ mở header.

## Chất lượng những khung đã ghi

11/11 frame có năm trường hữu hạn trên toàn bộ 4.410.000 ô hợp lệ; không có frame đọc lỗi, không có độ sâu < −1e-6 m hay ô chạm cap 100 m trong các frame đã lưu. Sai khác `zs−zb−h` tối đa khoảng 6,1035e-5 m trên dữ liệu float32. Đây là kiểm tra tính toàn vẹn/số học của output, **không phải nghiệm thu vật lý**.

Budget cuối được lưu ở **35,399541 giờ**, khác frame cuối 33 giờ. Tổng rain 262.536.702,05 m³; river 505.352.908,08 m³; infiltration −64.405,93 m³; clamp-added 163.064,77 m³. Những số này là toàn miền gồm biển, không phải riêng lượng ngập nội địa ở giờ 33. [Budget được bảo toàn](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/RAW/V49_G_CENTRAL_discrete_budget.json).

Closure residual tính lại là khoảng 7,50e-6 m³ **sau khi tính cả residual/clamp**. Budget có 36.197.284 negative raw-depth cell-steps trước clamp; đó là tổng ô-bước, không phải 36 triệu ô địa lý hay depth âm trong ảnh output. Không diễn giải output không âm thành quá trình tính không có clamp.

## So sánh CENTRAL với BASE ở cùng giai đoạn đầu trận

BASE lịch sử có 35 frame đến 105 giờ. Hash giữ đúng bản được manifest ghi: `4d28b9db6379563b281f42411f4da7c0ac09b2ed02344e85a43e5fbdb20b5a5d`. Bốn forcing, initial WSE, losses, Manning, grid/mask và normalized config khớp; terrain/output khác. Đối chiếu 11 frame CENTRAL với frame BASE gần nhất, sai khác thời gian lớn nhất **0,0546875 s**.

Đây là so sánh **thăm dò phần đầu trận với BASE lịch sử**, không thay bộ BASE/CENTRAL/LOW/HIGH mới đủ 120 giờ. Thời điểm output hơi khác do timestep thích nghi; sai khác vật lý và độ nhạy số học cần được phân biệt khi đọc các cực trị.

Miền thống kê tạm thời loại polygon OCEAN, water_density >0,5 và HAND âm; threshold mô phỏng h>0,3 m. Miền này rộng 3.130,803 km² và **không phải mask Sentinel preregistered**. Không gọi diện tích này là ngập đã được vệ tinh xác nhận. [Thiết kế thăm dò đã ghi](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_EXPLORATORY_PARTIAL_ANALYSIS_DESIGN.json).

| Đại lượng ở giờ 33 | Kết quả |
|---|---:|
| Diện tích nước vượt 0,3 m CENTRAL trong miền thăm dò | 269,4096 km² |
| BASE trong cùng miền | 269,4132 km² |
| Chênh diện tích thuần | −0,0036 km² = −4 ô |
| Ô đổi trạng thái ngập/khô giữa hai arm | 98 ô = 0,0882 km² |
| Max \|Δh\| toàn miền | 0,54648 m |
| Mean \|Δh\| ngoài polygon biển | 0,00004616 m |
| Ô ngoài biển có \|Δh\| > 1 mm / > 1 cm | 18.286 / 2.603 |

**Diện tích toàn miền gần như không đổi ở giai đoạn này**, nhưng không có nghĩa hai nghiệm giống hoàn toàn. Chênh thuần 4 ô che 98 ô đổi trạng thái; tác động độ sâu cục bộ cần xem riêng. Chưa có quan trắc đúng thời điểm để xác định ô nào đúng hơn.

Quanh hai reach được chỉnh, dùng buffer 500 m theo geometry có sẵn, không điều chỉnh ranh theo vị trí có điểm đẹp:

| Reach / AOI | CENTRAL / BASE wet area ở giờ 33 | Max \|Δh\| | Mean \|Δh\| |
|---|---:|---:|---:|
| HR_41349822, 4,9347 km² | 1,1790 / 1,1799 km² | 0,47454 m | 0,001712 m |
| HR_41352752, 1,6722 km² | 0,1026 / 0,1017 km² | 0,13007 m | 0,002334 m |

[Bảng toàn bộ frame](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_partial_frame_metrics.csv), [bảng theo reach](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_partial_reach_metrics.csv).

## Những điểm nên nghiên cứu tiếp từ dữ liệu cứu được

1. **Độ sâu và mực nước phải tách riêng.** `Δh=Δzs−Δzb`; h tăng có thể chỉ do đáy hạ. Ở khung cuối, max |Δzs| khoảng 0,54651 m, mean toàn miền khoảng 3,76e-5 m. Sai khác đồng nhất thức Δh với Δzs−Δzb ở mức float32 khoảng 0,000126 m. Không dùng độ sâu tăng đơn thuần làm bằng chứng mực nước lũ được cải thiện.
2. **Điểm khác biệt lớn nhất nằm xa hai reach chỉnh.** Tại x=289.635 m, y=1.420.535 m (EPSG:32649), terrain cả hai arm đều 572,6219 m, h CENTRAL≈0,55455 m và BASE≈0,00807 m. Điểm này cách reach gần nhất khoảng 16,72 km. Không quy cực trị này thành lợi ích trực tiếp của carving. Cần kiểm trace thời gian, wet/dry transition và độ nhạy timestep trước khi quy nguyên nhân.
3. **Vận tốc cần QA địa điểm.** Max tốc độ ở khung cuối≈20,4522 m/s tại x=289.515 m, y=1.448.405 m; h≈1,453 m, terrain≈223,567 m, Froude suy từ h/v≈5,42. Có 454 ô h>0,3 m với speed>10 m/s. Đây là điểm cần xem profile/slope và numerical convergence, không là bằng chứng tự động sai hoặc đúng. P99 speed trong toàn bộ ô wet≈3,845 m/s. Điểm max cách reach chỉnh gần nhất≈19,95 km; không nằm trong hai AOI 500 m.
4. **Diễn biến đầu trận đã có thể phân tích.** Diện tích tạm thời tăng từ khoảng 17,95 km² ở giờ 3 lên 269,41 km² ở giờ 33; còn gồm nước do khởi tạo, inflow và rain-on-grid. Không thể từ đường cong này tách riêng đóng góp mưa hoặc suy đỉnh toàn trận.

[Chẩn đoán WSE/vận tốc và tọa độ](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_last_frame_WSE_velocity_diagnostics.json). Những điểm trên là mục tiêu nghiên cứu được dữ liệu chỉ ra; nguyên nhân số học/thủy lực chưa được xác định trong lượt phục hồi.

Đã trích [chuỗi tại hai hotspot qua 11 frame](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_hotspot_saved_frame_timeseries.csv). Tại điểm max speed, BASE cũng có **20,45154 m/s**, CENTRAL **20,45221 m/s** ở giờ 33: hiện tượng vận tốc cao có trong cả hai nghiệm, không thể quy là lỗi mới do V49 carving. Tại điểm max Δh, giờ 30 có h CENTRAL≈0,02836 m và BASE≈0,02859 m; đến giờ 33 thành 0,55455/0,00807 m. Khoảng output 3 giờ chưa xác định được lúc tách nghiệm hoặc nguyên nhân; đây là vị trí ưu tiên lấy trace tần suất cao trong thí nghiệm numerical sensitivity riêng.

## Sản phẩm đã xuất để dùng tiếp

- [Ảnh độ sâu và chênh lệch ở giờ 33](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_recovered_33h_depth_and_difference.png).
- [Đồ thị diễn biến 3–33 giờ](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_recovered_early_event_diagnostics.png).
- [GeoTIFF depth khung cuối](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_CENTRAL_last_saved_depth_33h.tif), [GeoTIFF CENTRAL−BASE](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_CENTRAL_minus_BASE_depth_last_saved.tif).
- [Maximum trên các frame đã lưu](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_CENTRAL_max_depth_saved_frames_3h_33h.tif): chỉ lấy 11 snapshot, **không phải hmax liên tục 0–33 giờ hay cực đại toàn trận**.
- [Báo cáo máy đọc JSON](D:/VTP/River_Bathymetry_Project/V49_G_POWERLOSS_RECOVERY_20261014/V49_POWERLOSS_SALVAGE_REPORT.json).

## Phần chưa cứu được và quyết định tiếp tục

Sentinel-1 yêu cầu giờ mô phỏng **101,61425**, trong khi mới có dữ liệu tới 33 giờ. Không chọn frame 33 thay frame vệ tinh, không tính CSI/F1 sai thời điểm. Gate G vẫn PENDING, `hydraulic_promotion_ready=false`.

NetCDF chứa h/zs/zb/u/v và thời gian output ở float32, trong khi solver cấp phát float64; thiếu cả hai bản đồ `evolv.cum_infilt`/`evolv_o.cum_infilt`, trạng thái loop và snapshot solver đầy đủ. Budget chỉ có tổng thể tích, không tái tạo được bản đồ trạng thái. Hàm `warm_start` hiện nội suy WSE từ biên và đặt vận tốc 0, không phải resume từ file kết quả; `hotstartfile` chỉ được parse/log, chưa có loader tiêu thụ nó trên đường khởi tạo hiện hành. [Kiểm toán mã restart và thiết kế checkpoint](D:/VTP/River_Bathymetry_Project/V49_POWERLOSS_RESTART_FEASIBILITY_20261014.md).

Vì vậy **không thể cam kết tiếp tục đúng nghiệm cũ từ giờ 33** bằng bộ file hiện có. Warm-start từ raster là một experiment khác cần triển khai/kiểm tra và ghi provenance riêng. Bộ input đã đóng băng vẫn có thể dùng chạy lại từ t0 vào output mới. Trước một run dài mới, nên tạo release có checkpoint atomic và kiểm nghiệm interrupted/restarted so với uninterrupted, đồng thời giữ R1/partial data làm bằng chứng lịch sử.

Không sửa solver, không đổi forcing/terrain, không tự cấp PASS và không tự khởi động lại queue trong lượt phục hồi này.
