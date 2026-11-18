# Báo Cáo Thực Thi Bộ Thử Nhỏ Trên CUDA GPU & Đối Chứng Runtime R1 → R2 (18/11/2026)

## 1. Tổng quan thực thi
- **Máy thực thi:** Máy mô phỏng GPU (`NVIDIA RTX A4000`, CUDA Device 0, CuPy tăng tốc phần cứng).
- **Commit kế hoạch đầu vào:** `e96bd9b58e70d830de0412e66a184d8f354ce450` (`Add small DEM and runtime benchmarks`).
- **Kiểm thử phần mềm & tiền kiểm:**
  - `pytest River_Bathymetry_Project/Small_Benchmarks/test_small_benchmarks.py -v`: **15/15 PASS**.
  - `tests/test_runtime_fixes.py`: **6/6 PASS**.
  - `geometry_checks.json`: **PASS** cho cả `channel` và `sill` (`protected_cells = 24/24`, đạt trọn vẹn 8/8 bất biến hình học của Method1).

---

## 2. Chẩn đoán trên Runtime R1 đóng băng & Thiết lập Runtime R2 (Theo Option C)

### 2.1 Phát hiện khi chạy `smoke` trên Runtime R1 (`20261004_runtime_fix_r1`)
Thư mục bằng chứng giữ nguyên vẹn: [`results/r1_cuda_20261118_023917/`](results/r1_cuda_20261118_023917/) (`runtime_4948de2f9081.json`).
1. **Lỗi tuần tự hóa JSON (`analyze_cases.py` dòng 104, 114–117):** Phép toán NumPy trả về kiểu `np.bool_` / scalar làm `json.dumps` báo `TypeError` ở ca `river_volume`. Đã ép kiểu tường minh sang `float(...)` và `bool(...)` gốc của Python mà không thay đổi bất kỳ ngưỡng hay công thức nào.
2. **Lỗi vật lý tại biên ngoài của R1 (`fill_halo_flux_vec` / `boundary.py`):** Trên ca hồ tĩnh đáy nghiêng `lake` (`32×32`, 120s), hàm `fill_halo_flux_vec` chép đè giá trị flux lên các cạnh biên vật lý ngoài cùng (`LB == ib`, `RB == ib`, `BL == ib`, `TL == ib`), kết hợp với tường phản xạ chưa đảo dấu vận tốc pháp tuyến (`un_new = 0` thay vì `-un_in`) và thiếu bước `update_bnd` sau `fill_halo_all` ở bước Predictor, gây thất thoát thể tích **`-2.758,767 m³`**.

### 2.2 Bản vá Runtime R2 tách biệt (`V48_runs/20261118_runtime_fix_r2`)
Tuân thủ quy tắc bảo toàn của `README.md` (mục 103–104), runtime R1 đóng băng được giữ nguyên 100% không chỉnh sửa; bản sao tách biệt [`V48_runs/20261118_runtime_fix_r2/`](../../V48_runs/20261118_runtime_fix_r2/) (`digest = 33781f051537e5f56d59d26733df799a0a3e8414c9cb2cbec4fe760b30b95161`) áp dụng 3 chỉnh sửa tối thiểu tại biên:
1. `bg_flood/block_index.py`, `bg_flood/halo.py`, `bg_flood/flow_gpu.py`: Tách chỉ số `flux_halo_*` chỉ trao đổi giữa các block nội bộ (`LB != ib`, `RB != ib`, `BL != ib`, `TL != ib`), không ghi đè flux tại biên ngoài miền tính.
2. `bg_flood/flow_gpu.py`: Gọi `update_bnd(param, loop, forcing, model, evolv=model.evolv)` ngay sau `fill_halo_all` ở bước Predictor (đồng bộ thứ tự với bước Corrector).
3. `bg_flood/boundary.py`: Áp dụng điều kiện tường kín phản xạ chuẩn `un_new = -un_in` cho `side.type == 0`.

---

## 3. Kết quả chạy toàn diện 4 nhóm (15/15 ca) trên GPU CUDA với Runtime R2

- **Thư mục kết quả chính thức:** [`results/r2_cuda_20261118_034940/`](results/r2_cuda_20261118_034940/)
- **Gói ZIP báo cáo tổng hợp:** [`results/r2_cuda_20261118_034940/benchmark_report_20261117T221752238835Z.zip`](results/r2_cuda_20261118_034940/benchmark_report_20261117T221752238835Z.zip) (`109` tệp, khớp SHA-256 `109/109`).
- **Độ lặp lại trên GPU:** Chạy đối chứng độc lập lại nhóm `smoke` trên GPU 0 khớp từng bit (`max_abs_diff = 0.0`).

### 3.1 Nhóm `smoke` (`5/5 PASS`) — [`reports/smoke_summary.md`](results/r2_cuda_20261118_034940/reports/smoke_summary.md)
| Ca kiểm tra | Trạng thái | Chỉ số kiểm chứng chính |
| :--- | :---: | :--- |
| `grid` (`32×48`, 1s) | **PASS** | `bed_err = 0.0 m`, giữ nguyên kích thước lưới bất đối xứng và cao độ âm |
| `rain_mm` (`32×32`, 3600s) | **PASS** | `h = 0.0100 m`, thể tích `9,216.0 m³`, sai số giải tích `2.235×10⁻¹⁰ m` |
| `rain_ms` (`32×32`, 3600s) | **PASS** | Khớp tuyệt đối `0.0 m` trên cả 60 khung thời gian so với `rain_mm` |
| `lake` (`32×32`, 120s) | **PASS** | `zs_err = 0.0 m`, `max_speed = 4.178×10⁻¹⁵ m/s`, `flux_div = 3.92×10⁻¹² m³` |
| `river_volume` (`32×32`, 60s) | **PASS** | Thể tích tăng `+600.000001 m³` (sai số tương đối `1.863×10⁻⁹`, residual `0.0 m³`) |

### 3.2 Nhóm `channel` (`4/4 PASS`) — [`reports/channel_comparison.csv`](results/r2_cuda_20261118_034940/reports/channel_comparison.csv)
| Phương án | `bed_rmse_m` | `common_wet_cells` | `zs_rmse_common_wet_m` | `h_rmse_all_cells_m` | `wet_iou_at_0_3` | `area_h_gt_0_3_m2` | `bed_lowering_volume_m3` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `channel_REF` | `0.0000` | `972` | `0.0000` | `0.0000` | `1.0000` | `527,400.0` | `1,219,015.38` |
| `channel_RAW` | `0.5271` | `582` | `0.7915` | `0.2634` | `0.0000` | `0.0` | `0.00` |
| `channel_SIMPLE` | `0.3176` | `864` | `0.3996` | `0.1750` | `0.6005` | `662,400.0` | `1,785,600.00` |
| **`channel_V49`** | **`0.1433`** | **`950`** | **`0.2917`** | **`0.0801`** | **`0.7533`** | **`432,000.0`** | **`901,295.03`** |

### 3.3 Nhóm `sill` (`4/4 PASS`) — [`reports/sill_comparison.csv`](results/r2_cuda_20261118_034940/reports/sill_comparison.csv)
| Phương án | `bed_rmse_m` | `common_wet_cells` | `zs_rmse_common_wet_m` | `h_rmse_all_cells_m` | `wet_iou_at_0_3` | Bảo toàn 24 ô vùng bảo vệ (sill) |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `sill_REF` | `0.0000` | `934` | `0.0000` | `0.0000` | `1.0000` | Tham chiếu chuẩn |
| `sill_RAW` | `0.5228` | `638` | `0.4821` | `0.3076` | `0.0000` | Không đào lòng dẫn |
| `sill_SIMPLE` | `0.3272` | `732` | `0.6165` | `0.1735` | `0.6329` | Phá vỡ **16/24 ô** (`-2.0000 m`) |
| **`sill_V49`** | **`0.1421`** | **`922`** | **`0.1544`** | **`0.0746`** | **`0.8469`** | Bảo toàn **24/24 ô** (sai số `0.0000 m`) |

### 3.4 Nhóm `depth` (`4/4 PASS`) — [`reports/depth_comparison.csv`](results/r2_cuda_20261118_034940/reports/depth_comparison.csv)
| Phương án | `bed_rmse_m` | `common_wet_cells` | `zs_rmse_common_wet_m` | `h_rmse_all_cells_m` | `wet_iou_at_0_3` | `area_h_gt_0_3_m2` | `bed_lowering_volume_m3` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `channel_HALF` (1 m) | `0.3204` | `872` | `0.6768` | `0.1151` | `0.7711` | `454,500.0` | `450,647.51` |
| **`channel_V49` (2 m)** | **`0.1433`** | **`950`** | **`0.2917`** | **`0.0801`** | **`0.7533`** | **`432,000.0`** | **`901,295.03`** |
| `channel_DOUBLE` (4 m) | `0.3612` | `782` | `1.0367` | `0.1689` | `0.7067` | `431,100.0` | `1,792,212.43` |

*(Ghi chú phương pháp: Theo đúng quy ước của `Small_Benchmarks/README.md`, `REF` là nghiệm tham chiếu cùng bộ giải trên địa hình đáy hình thang biết trước trên miền giả lập, tách biệt với thực nghiệm Phú Yên và số đo thực địa.)*
