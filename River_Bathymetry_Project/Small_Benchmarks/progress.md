# Tiến độ bộ thử nhỏ

## 17/11/2026

- Đóng gói trình tạo 15 ca, gọi hàm DEM Method1 gốc, runner runtime Python R1, phân tích NetCDF, hình/bảng/ZIP, wrapper PowerShell và hướng dẫn.
- Nhóm chạy: smoke (5), channel (4), sill (4), depth (2 mới + tái dùng REF/V49). Chạy tuần tự, timeout từng ca, hash đầu vào/runtime, chặn ghi đè và chặn nhóm lớn khi smoke chưa đạt.
- Đã kiểm tra phần mềm, hình học, wrapper; chạy smoke runtime cũ để xác nhận bộ kiểm tra phát hiện mất hàng/cột. Chi tiết trong LOCAL_VALIDATION.md.
- Việc trên máy mô phỏng: dùng đúng Python/R1, chạy smoke trước; nếu PASS chạy channel; sill/depth tùy thời gian. Mang ZIP báo cáo cùng việc giữ NetCDF gốc về để phân tích.
- Không sửa solver, Method1, dữ liệu Phú Yên hay các cấu hình 120 giờ. Không có kết quả R1 mới được nhận trước khi thực thi.

## 18/11/2026 — Hoàn tất chạy CUDA GPU & kiểm toán độc lập

- Đã chạy chẩn đoán `smoke` trên runtime R1 (`results/r1_cuda_20261118_023917/`), phát hiện lỗi biên `fill_halo_flux_vec` trên ca `lake` (`-2.758,767 m³`) và ép kiểu JSON gốc `float`/`bool` tại `analyze_cases.py`.
- Bảo toàn nguyên vẹn R1, thiết lập runtime R2 tách biệt (`V48_runs/20261118_runtime_fix_r2`, `6/6 test_runtime_fixes.py`, `15/15 pytest`) và chạy hoàn tất toàn bộ 4 nhóm (`smoke`, `channel`, `sill`, `depth` — **15/15 ca PASS**) trên GPU `NVIDIA RTX A4000` tại `results/r2_cuda_20261118_034940/`.
- Đóng gói đầy đủ 16 tệp báo cáo/biểu đồ và gói `benchmark_report_20261117T221752238835Z.zip`. Chi tiết tại [`CUDA_EXECUTION_REPORT_20261118.md`](CUDA_EXECUTION_REPORT_20261118.md).
