# Báo Cáo Thực Thi Bộ Kiểm Chuẩn Cô Lập R3 Trên CUDA GPU (19/11/2026)

## 1. Tổng quan thực thi nguyên bản (`As-Is`)
- **Commit đầu vào:** `c413d575db662e573d6232f0e8a9c56994eb9164` (`Add isolated R3 small simulation suite`), chạy nguyên bản 100% không chỉnh sửa mã nguồn.
- **Môi trường phần cứng & Runtime:** Windows PowerShell, `C:\Users\CuongHM\anaconda3\python.exe` (`Python 3.11.11`, `cupy 13.4.1`), GPU 0 (`NVIDIA RTX A4000`), runtime [`V48_runs/20261118_runtime_fix_r3/`](../../V48_runs/20261118_runtime_fix_r3/) (`digest = 8e83d93cafa08dfd8583874483316a5b00e1f533de917f8394b0df04b8206ca2`).
- **Kiểm thử & tiền kiểm:**
  - `pytest` (`test_small_benchmarks.py` + `test_gradient_boundaries.py`): **34/34 PASS** (`rc = 0`).
  - `operator_checks.py --device cuda`: **12/12 PASS** trên GPU 0.
  - `geometry_checks.json`: **PASS** (`channel` & `sill`).
- **Thư mục kết quả đầy đủ:** [`results/R3_cuda_20261119_075158_189/`](results/R3_cuda_20261119_075158_189/)
- **Gói ZIP báo cáo tổng hợp:** [`results/R3_cuda_20261119_075158_189/benchmark_report_20261119T022207517294Z.zip`](results/R3_cuda_20261119_075158_189/benchmark_report_20261119T022207517294Z.zip) (`185` mục, `628,854` B, CRC sạch).

---

## 2. Kết quả kiểm chứng 6 nhóm / 20 kịch bản duy nhất trên GPU CUDA (`6/6 PASS`)

### 2.1 Nhóm `smoke` (`5/5 PASS`) & `closed` (`2/2 PASS`)
- Toàn bộ 5 ca `smoke` (`grid`, `rain_mm`, `rain_ms`, `lake`, `river_volume`) đạt **PASS**.
- Hai ca nước chuyển động trong miền kín không ma sát (`closed_one` `16×16` và `closed_multi` `32×32`, `300s`) xác nhận sửa đổi gradient biên tường của R3 triệt tiêu trôi thể tích về sát epsilon máy tính:
  - `closed_one`: độ trôi thể tích tương đối **`5.04 × 10⁻¹⁶`** (`≤ 10⁻⁸`).
  - `closed_multi`: độ trôi thể tích tương đối **`3.79 × 10⁻¹⁶`** (`≤ 10⁻⁸`).

### 2.2 Nhóm `channel` (`4/4 PASS`) — [`reports/channel_comparison.csv`](results/R3_cuda_20261119_075158_189/reports/channel_comparison.csv)
| Phương án | `bed_rmse_m` | `zs_rmse_fixed_common_wet_m` (`583` ô) | `h_rmse_all_cells_m` | `hmax_saved_map_rmse_m` | `wet_iou_at_0_3` | `bed_lowering_volume_m3` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `channel_REF` | `0.0000` | `0.0000` | `0.0000` | `0.0000` | `1.0000` | `1,219,015.38` |
| `channel_RAW` | `0.5271` | `0.7893` | `0.2632` | `0.2951` | `0.0000` | `0.00` |
| `channel_SIMPLE` | `0.3176` | `0.3176` | `0.1750` | `0.1900` | `0.6000` | `1,785,600.00` |
| **`channel_V49`** | **`0.1433`** | **`0.2275`** | **`0.0801`** | **`0.0807`** | **`0.7500`** | **`901,295.03`** |

### 2.3 Nhóm `sill` (`4/4 PASS`) — [`reports/sill_comparison.csv`](results/R3_cuda_20261119_075158_189/reports/sill_comparison.csv)
| Phương án | `bed_rmse_m` | `zs_rmse_fixed_common_wet_m` (`623` ô) | `h_rmse_all_cells_m` | `hmax_saved_map_rmse_m` | `wet_iou_at_0_3` | `bed_lowering_volume_m3` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `sill_REF` | `0.0000` | `0.0000` | `0.0000` | `0.0000` | `1.0000` | `1,199,353.84` |
| `sill_RAW` | `0.5228` | `0.4812` | `0.3074` | `0.3142` | `0.0000` | `0.00` |
| `sill_SIMPLE` | `0.3272` | `0.5628` | `0.1722` | `0.1744` | `0.6410` | `1,785,600.00` |
| **`sill_V49`** | **`0.1421`** | **`0.1402`** | **`0.0746`** | **`0.0697`** | **`0.8469`** | **`886,758.01`** |

### 2.4 Nhóm `depth` (`4/4 PASS`) — [`reports/depth_comparison.csv`](results/R3_cuda_20261119_075158_189/reports/depth_comparison.csv)
| Phương án | `bed_rmse_m` | `zs_rmse_fixed_common_wet_m` (`714` ô) | `h_rmse_all_cells_m` | `hmax_saved_map_rmse_m` | `wet_iou_at_0_3` | `bed_lowering_volume_m3` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `channel_HALF` (1 m) | `0.3204` | `0.6347` | `0.1155` | `0.1357` | `0.7655` | `450,647.51` |
| **`channel_V49` (2 m)** | **`0.1433`** | **`0.2485`** | **`0.0801`** | **`0.0807`** | **`0.7500`** | **`901,295.03`** |
| `channel_DOUBLE` (4 m) | `0.3612` | `1.0535` | `0.1691` | `0.1779` | `0.7019` | `1,792,212.43` |

### 2.5 Nhóm `ablation` (`PASS` — Bóc tách hiệu ứng hình dạng mặt cắt và mặt nạ bảo vệ) — [`reports/ablation_comparison.csv`](results/R3_cuda_20261119_075158_189/reports/ablation_comparison.csv)
| Phương án | `bed_rmse_m` | `zs_rmse_fixed_common_wet_m` | `h_rmse_all_cells_m` | `hmax_saved_map_rmse_m` | `wet_iou_at_0_3` | `bed_lowering_volume_m3` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `channel_SIMPLE` | `0.3176` | `0.3880` (`861` ô) | `0.1750` | `0.1900` | `0.6000` | `1,785,600.00` |
| `channel_RECT_EQVOL` *(đẳng thể tích)* | `0.2597` | `0.4496` (`861` ô) | `0.1753` | `0.1900` | `0.6000` | `901,295.03` |
| **`channel_V49`** | **`0.1433`** | **`0.2611`** (`861` ô) | **`0.0801`** | **`0.0807`** | **`0.7500`** | **`901,295.03`** |
| `sill_SIMPLE` *(chữ nhật, không bảo vệ)* | `0.3272` | `0.5948` (`691` ô) | `0.1722` | `0.1744` | `0.6410` | `1,785,600.00` |
| `sill_RECT_PROTECTED` *(chữ nhật, có bảo vệ)* | `0.3150` | `0.4691` (`691` ô) | `0.1543` | `0.1580` | `0.8333` | `1,756,800.00` |
| `sill_V49_UNPROTECTED` *(cos², bỏ bảo vệ)* | `0.1523` | `0.0878` (`691` ô) | `0.1878` | `0.1769` | `0.5042` | `901,295.03` |
| **`sill_V49`** *(cos² + bảo vệ 24/24 ô)* | **`0.1421`** | **`0.1443`** (`691` ô) | **`0.0746`** | **`0.0697`** | **`0.8469`** | **`886,758.01`** |

*(Ghi chú phương pháp: Theo quy ước tại `Small_Benchmarks_R3/README.md`, toàn bộ kết quả thuộc miền giả lập có đáy tham chiếu `REF` cùng bộ giải, tách biệt với mô phỏng toàn tỉnh Phú Yên và kiểm định thực địa.)*
