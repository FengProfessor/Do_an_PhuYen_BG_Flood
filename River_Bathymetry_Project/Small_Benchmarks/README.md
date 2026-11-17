# Bộ thử nhỏ: kiểm chứng runtime và phần hiệu chỉnh DEM

Bộ này chạy **runtime Python R1 thực tế của dự án**, qua `run_bgflood.run_model`. Không tự viết một bộ giải SWE khác, không thay mã R1 và không chạy lại toàn Phú Yên. Runtime R1 nằm ở máy mô phỏng, mặc định `D:/VTP/V48_runs/20261004_runtime_fix_r1`.

Mục tiêu: có kết quả ngắn, có đối chứng và có thể đưa vào chương thực nghiệm. Hiện mới xác nhận phần tạo dữ liệu, kiểm tra phần mềm và chạy đối chứng âm trên runtime cũ tại máy phân tích. **Chưa có kết quả thủy động lực R1 của bộ thử này.**

## Chạy nhanh trên máy mô phỏng

Mở PowerShell tại thư mục kho mã, kéo cập nhật. Dùng đúng Python đã chạy V49 (đường dẫn dưới theo hồ sơ máy chạy; đổi nếu khác).

```powershell
cd D:\VTP
git pull --ff-only
$pythonExe = 'C:\Users\CuongHM\anaconda3\python.exe'
$runner = '.\River_Bathymetry_Project\Small_Benchmarks\Run-Benchmarks.ps1'
$runtimeDir = 'D:\VTP\V48_runs\20261004_runtime_fix_r1'
$outputDir = Join-Path (Get-Location) ('River_Bathymetry_Project\Small_Benchmarks\results\r1_cpu_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
& $runner -Python $pythonExe -RuntimeDir $runtimeDir -OutputDir $outputDir -Suite smoke -Device cpu -TimeoutSeconds 180
```

**Bước 1 chỉ chạy năm ca kiểm tra nhỏ.** Nếu `smoke` PASS, giữ nguyên `$outputDir` rồi chạy bốn phương án sông:

```powershell
& $runner -Python $pythonExe -RuntimeDir $runtimeDir -OutputDir $outputDir -Suite channel -Device cpu -TimeoutSeconds 900
```

Nếu muốn GPU: dùng thư mục kết quả mới, đổi **cả smoke và channel** sang `-Device cuda`; cần CuPy/CUDA đang hoạt động. Các ca chạy tuần tự trên thiết bị 0, không tự mở nhiều lượt GPU. Bộ thử nhỏ có thể bắt đầu bằng CPU; thời gian thực tế sẽ được đo, không hứa trước tốc độ.

Nếu PowerShell không cho chạy `.ps1`, dùng Python trực tiếp, không cần đổi chính sách của máy:

```powershell
$scriptFile = '.\River_Bathymetry_Project\Small_Benchmarks\run_benchmarks.py'
& $pythonExe -X utf8 $scriptFile prepare --out $outputDir
# Chỉ dùng prepare khi thư mục chưa tồn tại; không ghi đè thư mục đã tạo.
& $pythonExe -X utf8 $scriptFile doctor --runtime $runtimeDir
& $pythonExe -X utf8 $scriptFile run --out $outputDir --runtime $runtimeDir --suite smoke --device cpu --timeout 180
# Sau khi smoke PASS:
& $pythonExe -X utf8 $scriptFile run --out $outputDir --runtime $runtimeDir --suite channel --device cpu --timeout 900
& $pythonExe -X utf8 $scriptFile bundle --out $outputDir
```

Python cần 3.10+ và các thư viện trong `requirements.txt`. Trước hết dùng môi trường hiện có đã chạy mô phỏng. Nếu báo thiếu thư viện, cài phần thiếu vào môi trường dành cho benchmark; không nâng cấp môi trường production chỉ để chạy thử. `doctor` chỉ kiểm tra đường dẫn và ghi phiên bản/hash, chưa chứng nhận bộ giải.

## Các kịch bản có sẵn

| Nhóm | Ca | Lưới và thời gian mô phỏng | Mục đích |
|---|---|---|---|
| `smoke` | `grid` | 32×48 ô, 1 giây | Raster bất đối xứng, có cao độ âm; bắt mất hàng/cột, lệch tâm, đảo trục |
| `smoke` | `rain_mm`, `rain_ms` | 32×32, 1 giờ | Cùng mưa 10 mm/h viết bằng hai đơn vị; kỳ vọng cuối 0,01 m, miền kín/không thấm |
| `smoke` | `lake` | 32×32, 120 giây | Nước tĩnh trên đáy không phẳng; kiểm tra mặt nước và vận tốc |
| `smoke` | `river_volume` | 32×32, 60 giây | Nguồn sông 10 m³/s vào miền kín; kỳ vọng thêm 600 m³ ở 60 giây |
| `channel` | REF, RAW, SIMPLE, V49 | 64×128, 1 giờ | Đối chứng bốn DEM trên kênh thẳng có bãi, một hydrograph chung |
| `sill` | REF, RAW, SIMPLE, V49 | 64×128, 1 giờ | Thêm dải cao cần giữ; lượng hóa tác động của việc bảo vệ vùng đã biết |
| `depth` | REF, V49, HALF, DOUBLE | 64×128, 1 giờ | Khảo sát mức hạ 1/2/4 m; tái dùng REF/V49 đã chạy trên cùng runtime |
| Khi `prepare` | Kiểm tra hình học | Không chạy thủy động lực | Đoạn lặp, hai đoạn cắt nhau, ô dưới sàn, không nâng nền, vùng bảo vệ |

Mọi lưới có bước 30 m. “1 giờ” là thời gian trong mô hình, **không phải thời gian chờ máy**. `-TimeoutSeconds` giới hạn thời gian thực cho **mỗi ca**. Mặc định kênh là thí nghiệm chuyển tiếp 3.600 giây, không tự nhận đã đạt dòng ổn định.

Chạy bổ sung sau nhóm chính, vẫn dùng cùng thư mục và thiết bị:

```powershell
& $runner -Python $pythonExe -RuntimeDir $runtimeDir -OutputDir $outputDir -Suite sill -Device cpu -TimeoutSeconds 900
& $runner -Python $pythonExe -RuntimeDir $runtimeDir -OutputDir $outputDir -Suite depth -Device cpu -TimeoutSeconds 900
```

Nếu chỉ đủ thời gian: **smoke → channel → lấy báo cáo**. Nhóm sill và depth là tùy chọn. Có 15 ca được chuẩn bị; không tự chạy hết. Nhóm depth chỉ phát sinh hai lượt mới nếu REF/V49 đã hoàn thành với đúng danh tính runtime.

## So sánh nào chứng minh điều gì?

- **REF**: đáy hình thang biết trước, tạo độc lập với mặt cắt cos² của Method1. Nghiệm trên REF là tham chiếu cùng bộ giải, không phải nghiệm thủy lực giải tích hoặc đo đạc thực tế.
- **RAW**: đáy bị lấp phẳng trong kênh. Đây là giả lập thiếu bathymetry, không đại diện mọi loại sai số Copernicus.
- **SIMPLE**: hạ đều 2 m theo cùng hành lang; không taper hoặc bảo vệ công trình.
- **V49**: gọi các hàm gốc `precompute_reach_footprints` và `generate_method1_carved_rasters`. Chỉ đổi kích thước lưới trong module nạp riêng; giữ gốc tọa độ và bước 30 m mà mã gốc đang dùng. Không sửa file Method1.

**Độ sâu 2 m được cấp như nhau cho SIMPLE và V49.** Bộ thử xác nhận phần biểu diễn, ghép và ràng buộc DEM, chưa kiểm chứng khâu suy độ sâu DHG/Manning/Qmean. Thể tích hạ của SIMPLE và V49 khác nhau; vì vậy chênh thủy lực không được quy riêng cho một ràng buộc. Kịch bản sill cố ý có một vùng bảo vệ đã biết để thử cơ chế đó; không chứng minh tính đúng của mask Đồng Cam ngoài thực địa.

Các phương án cùng miền dùng cùng bộ giải, nhám, biên, hydrograph, lưới, điều kiện khởi tạo và thời gian xuất. Khởi tạo khô cho miền sông để tránh đưa chênh thể tích nước ban đầu vào phép so sánh. Không gọi mức DOUBLE trong bộ thử giả lập là kết quả HIGH Phú Yên.

Phần hình học gọi hàm ghi raster gốc nên thư mục `geometry/` có vài tên legacy chứa ScopeB1/PhuYen. **Toàn bộ các raster trong output này là dữ liệu giả lập**, không phải các sản phẩm Phú Yên thật. Nhãn scope được dùng để đi qua đúng nhánh mã, không có 41 đoạn trong kênh giả lập.

## Kết quả mang về và đưa vào đồ án

Trong `$outputDir`:

- `reports/*_summary.md`, `*_summary.json`: trạng thái, sai số, runtime, thời gian chạy, kiểm tra cân bằng.
- `reports/*_comparison.csv`: RMSE đáy, RMSE mặt nước trên ô cùng ướt, số ô của miền thống kê, RMSE độ sâu toàn miền, IoU ngập tại 0,3 m và diện tích.
- `reports/*_inputs.png`: bốn DEM đầu vào giả lập; `*_cross_sections.png`: mặt cắt đáy và mặt nước khi có đầu ra hợp lệ.
- `geometry_checks.json`: kết quả gọi mã Method1 thực tế trên dữ liệu nhỏ.
- Mỗi ca có `BG_param.txt`, `case.json`, `run.json`, `result.nc`, `console.log`, `worker_metadata.json` và `budget.json` khi runtime hỗ trợ.
- `runtime_*.json` lưu hash mã Python, observer, bộ benchmark và phiên bản thư viện. `manifest.json` khóa đầu vào và ngưỡng kiểm tra.
- **`benchmark_report_*.zip`** gom báo cáo, hình, cấu hình, log và metadata; không gom NetCDF hoặc toàn bộ raster. Giữ NetCDF trên máy chạy, mang ZIP mới nhất về để phân tích/viết báo cáo.

Các ngưỡng được công bố trước trong manifest: sai số đáy/tâm ô 1e-5 m; mưa 1e-5 m; nước tĩnh 1e-4 m và 1e-4 m/s; khối lượng nguồn kín 1%; quan hệ h=zs−zb 1e-4 m. Đây là ngưỡng nghiệm thu của bộ thử, không phải chuẩn xác thực Phú Yên. Cân bằng có giữ phần nước do clamp/rounding; không trừ nó để khiến sai số có vẻ nhỏ.

`PASS` nghĩa là các kiểm tra số học/đầu vào đạt. **Không đồng nghĩa V49 thắng.** Cần đọc CSV và hình để so với RAW/SIMPLE, công bố cả kết quả không cải thiện. Cột RMSE mặt nước có miền cùng ướt riêng từng cặp và số ô đi kèm; không so sánh RMSE mà bỏ qua miền thống kê.

Nếu viết vào đồ án, dùng tên “Kiểm chứng quy trình trên miền giả lập có địa hình tham chiếu”. Tách khỏi thực nghiệm Phú Yên và khỏi kiểm định bằng quan trắc.

## Khi ca thử FAIL hoặc bị ngắt

1. Xem `reports/smoke_summary.md` và `console.log` của ca. Lỗi import/không tương thích API là lỗi thực thi, không phải kết luận thủy lực.
2. Lưới sai hoặc kết quả thiếu thời gian sẽ bị chặn; không tự cắt raster, đổi ngưỡng hoặc thay NaN thành 0 để qua kiểm tra.
3. Ca đã hoàn thành không bị chạy đè. Nếu timeout/lỗi, dùng `-RetryFailed` để lưu đầu ra cũ vào `attempts/` rồi chạy lại. Nếu solver đã hoàn thành nhưng sai kiểm tra khoa học, giữ bằng chứng và dùng thư mục mới sau khi sửa nguyên nhân.
4. Đổi mã runtime, thiết bị, thư viện hoặc đầu vào: tạo thư mục mới và chạy smoke lại. Mất điện có thể để lại `.running.lock`; kiểm tra không còn tiến trình thuộc bộ thử trước khi xóa đúng file khóa đó.
5. Chạy lại phân tích: `python run_benchmarks.py analyze --out <folder> --suite channel`. Chạy `bundle` lần nữa để đóng gói báo cáo mới nhất.

Runtime cũ có thể không tương thích observer của R1: các ca smoke vẫn được chạy với kiểm tra giải tích trực tiếp, ghi rõ thiếu observer; các ca channel/sill yêu cầu observer phù hợp. Không dùng executable C++/CUDA chính thức qua runner Python này. Việc so runtime cũ/R1 phải dùng hai thư mục riêng, cùng Python/thiết bị/đầu vào; không gộp kết quả từ hai runtime thành so sánh DEM.

## Kiểm tra phần mềm và tài liệu

```powershell
& $pythonExe -m pytest .\River_Bathymetry_Project\Small_Benchmarks\test_small_benchmarks.py -q
```

NetCDF trong kiểm thử đơn vị là fixture nhân tạo được gắn nhãn, không được tính là đầu ra BG_Flood. Thư mục `results/` bị Git bỏ qua; không đẩy dữ liệu lớn, môi trường Python hoặc thông tin bí mật.

Nguồn: [báo cáo runtime R1](../../V48_RUNTIME_FIX_REPORT_20261004.md), [mã Method1](../V49_Method1_DHG_Clamped/v49_method1_dhg_clamped.py), [observer đang dùng](../v49_runtime_observer.py). BG_Flood chính thức có [các kiểm tra mưa và nguồn sông](https://cyprienbosserelle.github.io/BG_Flood/BGFlood/Testing_8h/); bộ thử này vẫn phải xác nhận đúng runtime dự án, không lấy kết quả upstream thay cho R1.
