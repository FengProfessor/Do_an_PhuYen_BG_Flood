# Đánh giá kết quả V45 và kế hoạch triển khai V48

> **Cập nhật sau sửa ngày 04/10/2026:** Runtime V48 R1 đã sửa hai lỗi đơn vị mưa và lưới, qua kiểm thử và khóa cấu hình BASE/CONDITIONED. Xem [báo cáo bản sửa và lệnh chạy hiện hành](D:/VTP/V48_RUNTIME_FIX_REPORT_20261004.md). Phần đánh giá bên dưới được thực hiện trước bản sửa; chưa có kết quả formal 120 giờ bằng R1.

Ngày rà soát: **04/10/2026, UTC+7**. Đã đọc đúng [V45_Live_Execution_Status.md](C:/Users/CuongHM/.gemini/antigravity/brain/2a14d3b9-0c61-4507-b922-ac4882d9ae0d/V45_Live_Execution_Status.md:1), báo cáo cập nhật lúc 17:30. Đối soát mới lấy snapshot lúc **17:55**. Đây là đánh giá dữ liệu đã lưu; không khởi chạy mô phỏng mới hay sửa đầu vào của phiên GPU hiện hành.

## 1. Kết luận

V45 có cải thiện rõ về khả năng bắt vùng ngập so với kết quả V44 lịch sử, nhưng báo ngập dư lớn và chưa chứng minh được tác dụng riêng của việc chỉnh địa hình. Một số diễn giải trong báo cáo vượt quá bằng chứng; thống kê ngập trên các ô DEM chỉnh sửa có lỗi chiều lưới đã tái lập được.

V48 có thiết kế thí nghiệm tốt hơn: trở về DEM Copernicus gốc, giới hạn conditioning, khóa provenance và chuẩn bị cặp BASE–CONDITIONED. Bản cuối là **66 ô / 47 components**, không phải release 55 ô. Đã có một lần chạy BASE dừng trước frame đầu tiên; chưa có kết quả SAR chính thức để khẳng định V48 tốt hơn. **Chưa nên chạy formal bằng lệnh hiện tại**: lệnh gọi cây mã Python cũ còn lỗi chia mưa thêm **3.600.000 lần**; output thử chỉ có 2099×2099 ô và còn rủi ro nội suy lệch nửa ô.

## 2. Kết quả V45 đã kiểm lại

Đọc trực tiếp NetCDF: 34 frame, lưới 2100×2100, output cuối ở 102 giờ. Ledger tại snapshot đạt **103,8084/120 giờ = 86,507%**. Vì vậy đã đến cửa sổ quan sát SAR dự kiến nhưng chưa hoàn tất trận 120 giờ. [Bằng chứng mới](D:/VTP/V45_runs/20260928_engine_r1/results/V45_doc_soat_20261004.json:1).

Tái tính confusion matrix từ NetCDF và SAR GeoTIFF có CRS; đưa SAR, water mask và HAND về đúng transform; chỉ dùng ô mô hình hữu hạn. Kết quả khớp chính xác bốn số đếm trong JSON V45 đã công bố.

| Chỉ tiêu | V44 lịch sử, khoảng 102h | V45, 102h |
|---|---:|---:|
| CSI | 20,64% | 32,40% |
| Recall | 24,97% | 72,95% |
| Precision | 54,32% | 36,83% |
| TP | 64,95 km² | 189,79 km² |
| FP | 54,63 km² | 325,58 km² |
| FN | 195,13 km² | 70,39 km² |
| Diện tích mô hình trong mask | 119,58 km² | 515,38 km² |

Nguồn V44: [JSON tái kiểm](D:/VTP/BG_Flood_Project/BG_Flood/results/V45_audit_V44_recheck.json:1). Nguồn V45: [JSON frame 33](D:/VTP/V45_runs/20260928_engine_r1/results/V45_Frame33_metrics.json:1) và [đối soát độc lập mới](D:/VTP/V45_runs/20260928_engine_r1/results/V45_doc_soat_20261004.json:1).

CSI tăng **11,76 điểm phần trăm**, nhưng precision giảm **17,49 điểm phần trăm**. Trong mask V45, SAR có 260,18 km² ngập, mô hình có 515,38 km²: sai lệch diện tích **+98,08%**, F1 **48,94%**. Vì thế chưa có căn cứ gọi toàn bộ FP là ngập tràn bờ đúng thực tế. So sánh V44–V45 này là đối chiếu lịch sử: khác phiên bản engine, hình học lưới và cách xử lý forcing; không phải thí nghiệm chỉ đổi DEM.

## 3. Những chỗ cần sửa trong diễn giải V45

### 3.1. Thống kê trên ô DEM sửa bị đảo chiều Bắc–Nam

ASC lưu hàng phía Bắc trước; trục y NetCDF tăng từ Nam lên Bắc. NetCDF `zb` khớp chính xác với ASC sau khi đảo hàng. Báo cáo [kế hoạch V45, mục 79](D:/VTP/V45_Ke_hoach_trien_khai.md:1197) có các con số khớp chính xác với phép chồng **không đảo hàng**:

| Trên 41.907 ô DEM sửa | Báo cáo | Chồng đúng tọa độ |
|---|---:|---:|
| h > 0,10 m | 33.961 | **21.224** |
| h > 0,30 m | 32.717 (78,07%) | **18.649 (44,50%)** |
| h > 0,50 m | 32.251 | **17.933** |
| h > 1,00 m | 30.617 | **15.282** |
| h cực đại | 5,657 m | **4,891 m** |

Sai lệch này ảnh hưởng kết luận về tác động tại vùng conditioning, không làm thay đổi confusion matrix SAR toàn mask đã tái lập. Có thể chạy lại [script đọc đối soát](D:/VTP/V45_runs/20260928_engine_r1/work/audit_v45_review_20261004.py:1); mục `dem_mask_orientation_audit` trong JSON giữ cả hai cách chồng.

### 3.2. Residual nhỏ không chứng minh bảo toàn vật lý tuyệt đối

Frame 102h không có độ sâu âm hay ô h không hữu hạn; `zb` khớp DEM V45; thể tích NetCDF lệch ledger tại cùng frame chỉ **0,056 m³**. Đây là kiểm chứng nhất quán số học tốt.

Tuy nhiên, ledger đến snapshot có tổng `corrector_clip_m3` **+813.391 m³**, lớn nhất một bước **266,974 m³**. Công thức ledger cộng clip vào thể tích dự đoán rồi mới tính residual, nên một bước residual=0 không có nghĩa clip tích lũy=0 hoặc bảo toàn vật lý tuyệt đối. Cần báo riêng tổng clip, vị trí và thời gian phát sinh. [Công thức ledger](D:/VTP/V45_runs/20260928_engine_r1/python/bg_flood/water_budget.py:143), [báo cáo live đang diễn giải quá mức](C:/Users/CuongHM/.gemini/antigravity/brain/2a14d3b9-0c61-4507-b922-ac4882d9ae0d/V45_Live_Execution_Status.md:43).

### 3.3. Thời gian SAR và diện tích phải gọi đúng

- Không gọi 102h là khớp SAR 100% hay đỉnh lũ đã xác nhận. Theo epoch và midpoint cảnh mới khóa cho V48, frame 102h muộn **1.388,701 s ≈ 23 phút 9 giây**. Danh tính cảnh mới V48 cũng không tự chứng minh lineage của TIFF Otsu cũ dùng chấm V45. [Quy tắc thời gian](D:/VTP/V48_FORMAL_RUN_PAIR_PREP_20261002.json:36).
- Các frame 3h–99h đều được so với cùng một ảnh SAR gần 101,6h. Đường CSI theo frame là phép khảo sát độ nhạy thời gian, không phải chuỗi kiểm định với ảnh vệ tinh đồng thời. Không chọn frame 96h vì CSI cao nhất.
- 515,38 km² là diện tích trong mask đánh giá. Toàn miền `h > 0,3 m` tại 102h là **1.345,38 km²**; khởi tạo `zsinit=1 m` đã làm ướt khoảng **788 km²**. Phải tách ngập sẵn, ngập mới và vùng quan sát hợp lệ. [Kết quả đọc trực tiếp](D:/VTP/V45_runs/20260928_engine_r1/results/V45_doc_soat_20261004.json:1).
- Không gọi toàn bộ 41.907 ô sửa là đê có căn cứ thực địa: mức hạ sâu nhất lịch sử tới **171,669 m**, và nguồn hình học chưa đủ. [Kiểm toán đầu vào](D:/VTP/V45_runs/20260928_engine_r1/results/V45_bao_cao_ra_soat_dau_vao_dau_ra_code_danh_gia_20260930_v1.md:27).

## 4. Kế hoạch V48 cần đọc theo thứ tự phiên bản

1. [Nghiên cứu ban đầu](D:/VTP/V48_Nghien_cuu_hydro_conditioning_20261002.md:1): dry-run, chưa apply, đề nghị làm holdout và topology-cap sensitivity.
2. [Báo cáo DEM 55 ô](D:/VTP/V48_FINAL_DEM_REPORT_20261002.md:1): freeze ban đầu, 40 components; giữ làm lịch sử.
3. [Release closed-loop cuối](D:/VTP/V48_CLOSED_LOOP_FROZEN_RELEASE_20261002.json:31): 16 lần phát sinh cut, **66 ô / 47 components**, max hạ tích lũy **0,99596 m**, không còn strict component phải cắt theo rule hiện có. DEM hash `e75019ce5d0c02996bfab421623bda33ab3d56ff5bfd8a06e51f2ca2b3cd4feb`.
4. [Preregistration SAR](D:/VTP/V48_SAR_preregistration_20261002.md:1): ảnh RTC mới có provenance; epoch UTC khóa; threshold h>0,30 m, mask chung, chọn frame theo midpoint và cùng engine/forcing cho BASE–CONDITIONED. Cùng sự kiện SAR đã được xem trong các phiên bản cũ, nên tài liệu gọi đúng là đối chiếu xác nhận hồi cứu, held-out khỏi pipeline V48.
5. [Hồ sơ lần chạy thực tế](D:/VTP/V48_FORMAL_BG_FLOOD_ATTEMPT_20261002.json:1): BASE đã thử tới **493,94 s** rồi dừng có chủ ý do thời gian thực thi; frame đầu ở 10.800 s chưa tới, NetCDF có **0 frame**. Các câu “chưa từng bắt đầu” ở ghi chú trước đó đã lỗi thời; diễn đạt đúng là chưa có run chính thức hoàn tất hay SAR metrics chính thức.

`READY_FOR_FORMAL_EVALUATION` xác nhận các gate integrity/preregistration đã ghi nhận, không chứng minh forcing và vật lý trận lũ đã chuẩn. Cặp V48 còn giữ V34 rain×2, Q lịch sử, IL/CL V36, `zsinit=1` và biên free outflow. Cần mô tả đây là giả định/kịch bản, đồng thời đánh giá độ nhạy. [Cấu hình BASE](D:/VTP/BG_Flood_Project/BG_Flood/BG_param_PhuYen_30m_V48_FORMAL_BASE.txt:21).

Rà soát mới đã kiểm lại các hash và ba validator V48 mà không ghi đè manifest: contract PASS, observation PASS, preregistration READY. Tuy nhiên lệnh formal gọi `BG_Flood_Project/BG_Flood/python`, trong khi các sửa engine R1 được kiểm chứng ở `V45_runs/20260928_engine_r1/python`. Đọc NetCDF aborted thấy x=y=2099; bộ đọc/khởi tạo vẫn có đường nội suy corner→center lệch 15 m. Contract chỉ khóa một phần module, chưa bao phủ toàn driver/solver/writer/backend. Vì thế cần xác nhận rõ engine nào sẽ thực thi hai arm, chứng minh `zb` giữ đúng DEM trên cùng grid, rồi khóa lại toàn mã và preregistration liên quan trước khi xem kết quả. [Phân tích runtime mới](D:/VTP/V48_Danh_gia_san_sang_trien_khai_20261004.md:1), [writer formal](D:/VTP/BG_Flood_Project/BG_Flood/python/bg_flood/write_output.py:39), [khởi tạo formal](D:/VTP/BG_Flood_Project/BG_Flood/python/bg_flood/initial_conditions.py:149).

**Lỗi đơn vị mưa đã xác định trên đường thực thi hiện tại:** file V34 ghi m/s; loader cũ đọc nguyên giá trị; `add_rain_vec` lại chia `1000×3600`, tức lượng mưa đưa vào solver nhỏ hơn đúng SI **3.600.000 lần**. Parser cũ cũng không xử lý `rainunits`, nên chỉ thêm dòng config không đủ. Contract không khóa `read_forcing.py` và `updateforcing.py`; ba validator PASS không phát hiện lỗi. Cần dùng một runtime đã sửa/kiểm chứng, khóa phiên bản và phát hành hồ sơ mới trước khi chạy, giữ nguyên các hồ sơ freeze cũ làm lịch sử. [Header mưa](D:/VTP/Scenarios/rain_v34_era5_x2.txt:2), [loader cũ](D:/VTP/BG_Flood_Project/BG_Flood/python/bg_flood/read_forcing.py:22), [phép chia sai](D:/VTP/BG_Flood_Project/BG_Flood/python/bg_flood/updateforcing.py:214).

## 5. Thứ tự triển khai đề xuất

| Ưu tiên | Việc làm | Điều kiện hoàn tất |
|---|---|---|
| 1 | Sửa thống kê chiều lưới và cách diễn giải báo cáo V45; thống nhất trạng thái V48 theo release cuối và lần chạy đã dừng. | Bảng ô chỉnh sửa tái lập từ cùng CRS/transform; không gọi FP là ngập đã kiểm chứng. |
| 2 | Xử lý khác biệt engine formal với R1: kiểm đơn vị mưa, corner/center, grid output, biên/thấm/budget; khóa lại mã, config và gate. | `zb` đúng giá trị DEM, output 2100×2100; BASE–CONDITIONED chỉ khác địa hình và tên output; manifest bao phủ toàn mã Python thực chạy. |
| 3 | Bố trí phiên chạy dài và checkpoint/restart đã chứng minh trên engine dùng cho V48. | Không tranh GPU với V45 đang chạy; chạy có log và output riêng; không sửa DEM/forcing sau khi xem SAR. |
| 4 | Hoàn tất cặp BASE–CONDITIONED 120h, kiểm output tại cùng cửa sổ SAR. | Đủ frame, thời gian thật trong NetCDF, finite/nonnegative, budget và clip được báo riêng. |
| 5 | Chấm theo preregistration đã khóa. | Báo cả hai nhánh, TP/FP/FN/TN, CSI/recall/precision/F1, area bias, Δh/Δzs tại 66 ô và vùng hạ lưu; không dùng CSI tăng làm tiêu chí duy nhất. |
| 6 | Làm sensitivity forcing/initial stage/biên và quan trắc trạm hoặc sự kiện khác. | Kết luận về độ đúng vật lý và khả năng tổng quát hóa được tách khỏi ảnh hưởng conditioning trong một kịch bản cố định. |

Đánh giá triển khai V48 chi tiết và các kiểm tra integrity mới được lưu tại [ghi chú V48](D:/VTP/V48_Danh_gia_san_sang_trien_khai_20261004.md:1).
