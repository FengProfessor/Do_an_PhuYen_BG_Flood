# Tiến độ bộ thử nhỏ

## 17/11/2026

- Đóng gói trình tạo 15 ca, gọi hàm DEM Method1 gốc, runner runtime Python R1, phân tích NetCDF, hình/bảng/ZIP, wrapper PowerShell và hướng dẫn.
- Nhóm chạy: smoke (5), channel (4), sill (4), depth (2 mới + tái dùng REF/V49). Chạy tuần tự, timeout từng ca, hash đầu vào/runtime, chặn ghi đè và chặn nhóm lớn khi smoke chưa đạt.
- Đã kiểm tra phần mềm, hình học, wrapper; chạy smoke runtime cũ để xác nhận bộ kiểm tra phát hiện mất hàng/cột. Chi tiết trong LOCAL_VALIDATION.md.
- Việc trên máy mô phỏng: dùng đúng Python/R1, chạy smoke trước; nếu PASS chạy channel; sill/depth tùy thời gian. Mang ZIP báo cáo cùng việc giữ NetCDF gốc về để phân tích.
- Không sửa solver, Method1, dữ liệu Phú Yên hay các cấu hình 120 giờ. Không có kết quả R1 mới được nhận trước khi thực thi.
