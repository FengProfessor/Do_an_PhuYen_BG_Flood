# V48: hoàn tất sửa đơn vị mưa và lưới — 04/10/2026

Đã sửa hai lỗi chặn triển khai trong runtime riêng **V48 R1**, tại `D:\VTP\V48_runs\20261004_runtime_fix_r1`. Sáu kiểm thử hồi quy, bài chạy solver một giờ và kiểm tra cả hai DEM V48 thật đều PASS. Bộ contract, preregistration và cấu hình BASE/CONDITIONED mới đã được khóa hash; trạng thái cặp chạy là `READY_TO_START_FORMAL_BG_FLOOD_PAIR_RUNTIME_R1`.

Chưa khởi chạy mô phỏng formal 120 giờ hoặc đánh giá SAR. Các kiểm thử dùng CPU NumPy; launcher kiểm tra CUDA khi bắt đầu một nhánh formal. Kết quả này xác nhận hai bản sửa và tính toàn vẹn đầu vào, chưa chứng minh chất lượng kết quả ngập V48.

## Hai lỗi đã sửa

| Lỗi | Hành vi cũ | Hành vi R1 |
|---|---|---|
| Đơn vị mưa | File đã là m/s nhưng nguồn mưa tiếp tục chia 3.600.000, làm giảm mưa 3,6 triệu lần | Đọc đơn vị từ header hoặc `rainunits`, chuẩn hóa về m/s đúng một lần tại loader; nguồn mưa dùng trực tiếp m/s. File mm/h được chuyển đổi tại loader; thiếu đơn vị hoặc xung đột config/header bị chặn. |
| Lưới và tọa độ DEM | Miền 2100×2100 bị tính thành 2099×2099; tâm ô, mép miền, nội suy và xuất NetCDF không đồng nhất | Phân biệt tâm ô và mép ngoài; giữ đủ hàng/cột biên, mặt nạ NODATA và cao độ âm; NetCDF xuất đúng 2100×2100 tại tâm ô nguồn. |

Các module thay đổi: `forcing.py`, `read_forcing.py`, `updateforcing.py`, `read_input.py`, `initial_conditions.py`, `mesh.py`, `utils.py`, `write_output.py`. Các thay đổi phục vụ hai lỗi trên. Bản sửa không thay thế toàn bộ solver bằng engine V45 R1; các phần solver khác không được coi là đã kiểm chứng bởi đợt sửa này.

Diff đầy đủ: [runtime_fixes.patch](D:/VTP/V48_runs/20261004_runtime_fix_r1/runtime_fixes.patch).

## Bằng chứng kiểm tra

| Kiểm tra | Kết quả |
|---|---|
| Hồi quy trước và sau sửa | 6 FAIL trên engine cũ → **6/6 PASS** trên R1 |
| Chạy driver thật, miền phẳng kín 32×32, không thấm, mưa 10 mm/h trong 3600 s | Độ sâu cuối **0,009999999776 m**, kỳ vọng 0,01 m; sai số lớn nhất **2,24×10⁻¹⁰ m** |
| BASE: khởi tạo lưới, nạp cao độ, xử lý biên và xuất NetCDF `zb` | **2100×2100**; cả **4.410.000 ô** khớp TIF đóng băng, sai số cao độ lớn nhất **0 m** |
| CONDITIONED: cùng quy trình | **2100×2100**; cả **4.410.000 ô** khớp TIF đóng băng, sai số cao độ lớn nhất **0 m** |
| Cao độ âm và biên DEM | Giữ đủ **760 ô cao độ âm** ở mỗi nhánh, hàng bắc và cột đông |
| Mưa V48 thật qua loader và nguồn mưa | **144 bản ghi** ở mỗi nhánh; tốc độ m/s khớp dữ liệu gốc |
| Chênh lệch BASE/CONDITIONED | Đúng **66 ô** hạ thấp; mức hạ lớn nhất **0,995960757 m** |
| Contract và preregistration R1 | `PASS_V48_BG_FLOOD_CONTRACT_VALIDATION`, `READY_FOR_FORMAL_EVALUATION` |
| Launcher kiểm tra hash | PASS trước thử thay đổi; chặn thay đổi trong `read_forcing.py`; phục hồi đúng từng byte rồi PASS |
| Tệp cũ | **69 tệp** được đối chiếu vẫn khớp hash, gồm toàn bộ **29 tệp Python** của runtime cũ |

Bằng chứng chi tiết:

- [Hồi quy trước sửa](D:/VTP/V48_runs/20261004_runtime_fix_r1/results/regressions_before_fix.txt), [sau sửa](D:/VTP/V48_runs/20261004_runtime_fix_r1/results/regressions_after_fix.txt).
- [Bài chạy solver một giờ](D:/VTP/V48_runs/20261004_runtime_fix_r1/results/cpu_solver_smoke.json).
- [Kiểm tra hai DEM và mưa thật](D:/VTP/V48_runs/20261004_runtime_fix_r1/results/formal_input_verification.json).
- [Kiểm tra khóa hash và bộ cũ](D:/VTP/V48_runs/20261004_runtime_fix_r1/results/release_guard_verification.json).

Hai file `V48_BASE_GRID_INPUT_PROBE.nc` và `V48_CONDITIONED_GRID_INPUT_PROBE.nc` trong thư mục `results` chỉ chứa cao độ khởi tạo tại t=0; chúng không phải kết quả mô phỏng ngập formal. Thời điểm xuất của solver được ghi theo thời gian thực tế; việc nghiệm thu SAR phải kiểm tra thời gian frame thực tế theo preregistration.

## Bộ chạy hiện hành

Runtime, interpreter, phiên bản thư viện, mã Python, mã kiểm thử, công cụ release, cấu hình và bằng chứng kiểm tra được tham chiếu tại [V48_RUNTIME_MANIFEST_R1.json](D:/VTP/V48_runs/20261004_runtime_fix_r1/V48_RUNTIME_MANIFEST_R1.json). Cặp chạy và đường dẫn đầu ra nằm trong [V48_FORMAL_RUN_PAIR_R1.json](D:/VTP/V48_runs/20261004_runtime_fix_r1/V48_FORMAL_RUN_PAIR_R1.json).

Đầu vào khoa học giữ nguyên: BASE Copernicus, CONDITIONED CLOSED_LOOP_FROZEN 66 ô, forcing mưa và bốn lưu lượng sông, Manning, IL/CL, mực nước khởi tạo, điều kiện biên, epoch và quy tắc đánh giá SAR. Config R1 chỉ bổ sung `rainunits = m/s` và đổi đường dẫn output; BASE và CONDITIONED vẫn chỉ khác `bathy` và `outfile`.

Kiểm tra trước chạy trong PowerShell; lệnh này chỉ kiểm tra hash và thư viện, không khởi chạy mô phỏng:

```powershell
& 'C:\Users\CuongHM\anaconda3\python.exe' -X utf8 -B 'D:\VTP\V48_runs\20261004_runtime_fix_r1\launch_formal.py' --check
```

Lệnh chạy từng nhánh formal qua launcher R1 khi bắt đầu triển khai. Chạy lần lượt để quản lý tài nguyên GPU:

```powershell
& 'C:\Users\CuongHM\anaconda3\python.exe' -X utf8 -B 'D:\VTP\V48_runs\20261004_runtime_fix_r1\launch_formal.py' --arm BASE
& 'C:\Users\CuongHM\anaconda3\python.exe' -X utf8 -B 'D:\VTP\V48_runs\20261004_runtime_fix_r1\launch_formal.py' --arm CONDITIONED
```

Launcher đặt working directory đúng runtime R1, kiểm tra toàn bộ hash và preregistration, kiểm tra CUDA, và chặn ghi đè output/log đã tồn tại. Output formal dự kiến: `results\V48_FORMAL_BASE_R1.nc` và `results\V48_FORMAL_CONDITIONED_R1.nc`; log mang tên tương ứng trong cùng thư mục.

Bộ hồ sơ ngày 02/10 và runtime gốc được giữ nguyên để truy vết lịch sử. Báo cáo rà soát trước sửa vẫn mô tả đúng tình trạng engine cũ; bộ R1 và báo cáo này là tham chiếu cho bước triển khai tiếp theo.
