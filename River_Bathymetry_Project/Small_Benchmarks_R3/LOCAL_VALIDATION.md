# Kiểm chứng tại máy soạn mã — 18/11/2026

**Đã chạy đầy đủ 20/20 ca nhỏ trên CPU/NumPy và tất cả đạt các tiêu chí đã khóa. Chưa chạy CUDA R3 tại máy này.** Đây không phải kiểm định Phú Yên hoặc khẳng định V49 tối ưu.

| Nội dung | Kết quả thực thi |
|---|---|
| Unit/integration tests bộ benchmark | 27 PASS |
| Hồi quy tái dựng gradient/loại biên/trao đổi nội bộ | 7 PASS |
| Operator thực R3, một/bốn block, X/Y và biến thiên h/u/v | 12 cấu hình PASS trên CPU |
| Negative control R2 | Các cấu hình vận tốc biến thiên tái hiện thông lượng tường sai; kiểm thử xác nhận FAIL dự kiến |
| Chạy wrapper `-Device cpu -Suite all` | 20 ca duy nhất PASS, gồm5smoke+2closed+10channel/sill/depth+3ablation |
| Tổng thời gian subprocess solver tại máy này | 406,9601 s, khoảng6,78phút; không gồm chuẩn bị/phân tích |
| ZIP báo cáo | 185 tệp đối chiếu đúng từng byte với thư mục nguồn |
| Lint/compile | Ruff E9/F mã benchmark và test mới PASS; compileall runtime/package PASS; PowerShell parser PASS |

Hai ca closed chạy300s vật lý, ghi30 khung mỗi ca:

- Một block16×16: trôi thể tích float64 lớn nhất1,2601×10⁻¹⁶ tương đối; độ sâu tại biên thay đổi tối đa0,02895m.
- Nhiều block32×32: trôi thể tích lớn nhất1,2624×10⁻¹⁶; độ sâu tại biên thay đổi0,01915m.
- Không clamp ở cả hai ca; flux khối lượng tại tường bằng0. Trên toàn bộ20ca CPU, giá trị lớn nhất của chỉ số flux tường bằng0. Sai số triệt tiêu nội bộ nằm trong ngưỡng định trước.

Chi tiết từng ca, mã băm nguồn, phiên bản Python/gói, thời gian, hash NetCDF và metric nằm trong `LOCAL_CPU_VALIDATION_20261118.json`. Dữ liệu đầy đủ giữ tại máy soạn mã, không đẩy NetCDF/raster/log/ZIP lên Git trong commit triển khai này.

R3 giữ nguyên28/29 tệp Python của R2 từng byte; chỉ sửa `flow_gpu.py`. `R3_SOURCE_MANIFEST.json` và `runtime_fixes_r3.patch` ghi cụ thể. Do giữ byte nguồn R2, có CRLF và khoảng trắng cũ; kiểm tra whitespace áp cho phần mã mới và dòng vá, không làm sạch hàng loạt để phá hash đối chứng.

Máy GPU cần chạy lệnh trong README với thư mục mới. Kết quả trên NumPy/Python3.14 không thay xác nhận CuPy/Python3.11. Hệ thống tự chạy lại operator trên thiết bị yêu cầu, kiểm tra backend thực, rồi chặn các nhóm DEM nếu smoke/closed không đạt. Các suite dùng lại ca đã hoàn thành chỉ khi nguồn, thiết bị, dữ liệu và chất lượng còn khớp.

Tệp kiểm tra và mẫu số nhỏ không đánh giá đầy đủ mọi kiểu biên, mặt khô–ướt hoặc điều kiện thực địa. Runtime này chủ động từ chối biên type1 và lưới không đều. Không dùng nó thay trực tiếp runtime Phú Yên.
