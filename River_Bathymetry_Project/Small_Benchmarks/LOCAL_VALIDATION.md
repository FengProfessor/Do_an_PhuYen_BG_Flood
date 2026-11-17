# Kiểm tra tại máy phân tích — 17/11/2026

## Đã thực hiện

- Tạo đủ 15 ca bằng các hàm raster Method1 thật trên lưới nhỏ. Gọi các hàm gốc để kiểm tra đoạn lặp, hai đoạn cắt nhau, giữ vùng bảo vệ, không nâng nền, ô dưới sàn và trọng số mặt cắt: đạt các kiểm tra đã định.
- Chạy 15 kiểm thử phần mềm bằng pytest. Bao gồm dữ liệu tham chiếu độc lập, đầu vào dùng chung, round-trip ASC, chặn ghi đè/sửa dữ liệu và các trường hợp kết quả thiếu thời gian, sai đơn vị, lệch tọa độ, NaN, sai đáy, thiếu bằng chứng thực thi.
- Thử thực tế `Run-Benchmarks.ps1 -PrepareOnly`; tạo đủ dữ liệu và hình. Đã xem hình đầu vào miền sill để kiểm tra vị trí kênh và vùng bảo vệ.
- Chạy wrapper PowerShell và năm ca smoke trên **runtime cũ ở máy phân tích** (`BG_Flood_Project/BG_Flood/python`). Cả năm tiến trình hoàn thành; kiểm tra đầu ra trả **FAIL** do lưới mất hàng/cột: ca grid 31×47 thay vì 32×48; bốn ca còn lại 31×31 thay vì 32×32. Bộ kiểm tra không cắt lưới để làm khớp.
- Wrapper vẫn tạo ZIP báo cáo khi smoke FAIL, sau đó trả lỗi rõ ràng. Runtime cũ thiếu API của observer R1; bộ chạy ghi nhận điều đó, chỉ dùng kiểm tra trực tiếp cho smoke.
- Kiểm tra Ruff E9/F, biên dịch Python, cú pháp PowerShell và `git diff --check` trước khi commit.

## Chưa được xác nhận

Máy phân tích không có runtime R1 đã dùng cho cặp NetCDF Phú Yên. Chưa chạy kênh/sill/depth trên R1, chưa đo thời gian trên GPU máy mô phỏng, chưa có bảng chứng minh V49 tốt hơn SIMPLE/RAW trong bộ thử này.

NetCDF do unit test tạo là fixture nhân tạo, chỉ kiểm tra trình phân tích. Không đưa chúng vào bảng kết quả mô phỏng. PASS của pytest/hình học khác với PASS của runtime, và PASS của runtime khác với kết luận cải thiện độ chính xác.

Đối chứng âm trên runtime cũ xác nhận đường chạy và khả năng bắt lỗi lưới; chưa chứng minh sửa lỗi R1 cho tới khi chạy cùng bộ thử trên R1. Kết quả trên máy mô phỏng phải giữ nguyên hash, log và cấu hình do runner tạo.
