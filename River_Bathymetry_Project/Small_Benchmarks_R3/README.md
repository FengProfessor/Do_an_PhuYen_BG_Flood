# R3 — chỉ chạy mẫu nhỏ, kiểm chứng trước khi so DEM

Gói này không chạy Phú Yên toàn miền. Miền lớn nhất **64×128 ô, dx30m**, thời gian vật lý dài nhất **3.600s**. Runtime riêng: `V48_runs/20261118_runtime_fix_r3`; giữ nguyên R1/R2 và dữ liệu cũ. Bộ kiểm tra và runner có giới hạn kích thước/thời gian.

## Lệnh cho máy GPU

Chạy từ thư mục checkout (máy trước là `D:\VTP`):

```powershell
cd D:\VTP
git pull --ff-only
& .\River_Bathymetry_Project\Small_Benchmarks_R3\Run-Small-R3.ps1 `
  -Python 'C:\Users\CuongHM\anaconda3\python.exe' -Device cuda
```

Nếu đường dẫn Python khác, thay bằng Python đã chạy thành công bộ R2/CuPy. Gói không tự cài hay đổi CUDA. Phụ thuộc còn thiếu có thể cài từ `requirements.txt` bằng đúng Python đó; không cần nâng cấp toàn bộ môi trường đang dùng.

Lệnh trên tự tạo thư mục `Small_Benchmarks_R3/results/R3_cuda_<timestamp>/`, chuẩn bị dữ liệu giả lập, chạy kiểm tra operator trên thiết bị đã chọn, chạy tuần tự các nhóm, xuất báo cáo và ZIP. **Một lệnh, 20 ca duy nhất.** Các ca lặp lại trong nhóm depth/ablation được tái sử dụng sau kiểm tra hash và chất lượng, không chạy lại nhiều lần.

Gặp lỗi tính toán, timeout hoặc tiêu chí chất lượng không đạt: dừng, không chạy các ca còn lại. Gửi `benchmark_report_*.zip` kể cả khi FAIL; giữ NetCDF và thư mục kết quả trên máy mô phỏng. Không thay ngưỡng hoặc xóa bằng chứng lỗi để được PASS.

## Các nhóm thực sự chạy

| Nhóm | Nội dung | Số ca mới |
|---|---|---:|
| smoke | Lưới bất đối xứng; mưa mm/h và m/s; hồ tĩnh; nguồn sông hằng | 5 |
| closed | Nước chuyển động trong miền kín16×16 và32×32;300s | 2 |
| channel | REF/RAW/SIMPLE/V49 trên kênh giả lập | 4 |
| sill | REF/RAW/SIMPLE/V49 với ngưỡng và vùng bảo vệ biết trước | 4 |
| depth | HALF1m,DOUBLE4m; dùng lại REF/V49 | 2 |
| ablation | Hạ đều cùng thể tích; hạ đều có bảo vệ; V49 không bảo vệ | 3 |
| **Tổng** | Không có mô phỏng tỉnh hoặc dữ liệu thực địa | **20** |

Các phép operator trước đó là phép tính tức thời trên một/bốn block, đếm riêng; không cộng thành các sự kiện lũ độc lập. Gói mặc định không bao gồm vòng Q300 hoặc quét thêm tham số.

## Vì sao cần R3 và tiêu chí dừng

R2 phản xạ giá trị vận tốc ở tường nhưng chưa hoàn thiện gradient halo của trạng thái tái dựng. Phép thử vận tốc biến thiên trên miền kín tạo thông lượng khối lượng khác0. R3 điền gradient nội bộ và dùng parity đúng tại tường ở cả Predictor/Corrector, giữ thông lượng động lượng áp suất.

Runtime R3 này chỉ hỗ trợ lưới đều, halo1, tường0 và outflow2; loại biên khác dừng với lỗi rõ ràng. Chưa dùng nó để thay runtime Phú Yên có biên mực nước.

Ca closed khởi tạo độ sâu2m cộng nhiễu Gaussian0,05m lệch tâm, không ma sát/nguồn/thấm; luôn ướt. Bộ khởi tạo đọc `initial_h.npy` sau hàm init thật và trước khi chạy solver. Không viết một bộ giải thay thế.

Các tiêu chí đã khóa trong manifest:

- Thông lượng khối lượng tối đa từng mặt và tổng cạnh tường ≤1e−10m³/s.
- Sai lệch giữa tổng phân kỳ và tổng flux ngoại biên ≤1e−8m³/s, kiểm tra ở cả hai stage.
- Closed: trôi thể tích float64 tối đa ≤1e−8 tương đối, không clamp, biến thiên độ sâu ở ô sát biên ≥1e−5m để xác nhận biên đã chịu tác động.
- Đủ thời gian và lưới, không NaN, giữ DEM, h/zs/zb nhất quán, ngân sách rời rạc; giữ ngưỡng smoke trước đó.

Đây là ngưỡng kỹ thuật cho fixture nhỏ, không phải chuẩn kiểm định thực địa. `boundary_budget.json` theo dõi bốn cạnh độc lập; `budget.json` giữ observer cũ. Hai observer chỉ đo và gọi hàm gốc, không điều chỉnh mảng mô phỏng. Các tệp này cùng NetCDF được gắn hash vào trạng thái chạy.

## Các đối chứng DEM mới

- `channel_RECT_EQVOL`: cùng992ô chỉnh sửa và tổng thể tích hạ với V49, độ hạ đều khoảng1,009515m. Tổng thể tích bằng nhau không có nghĩa độ sâu cực đại bằng nhau; đây là biến hình dạng đang đánh giá.
- `sill_RECT_PROTECTED`: bật mặt nạ24ô trên phương án hạ đều2m.
- `sill_V49_UNPROTECTED`: bỏ riêng mặt nạ bảo vệ trong Method1, vẫn giữ ngưỡng trên DEM RAW.

Hai ca sill hoàn thiện2×2 kiểu mặt cắt×bảo vệ. Hiệu ứng dung tích giữa các kiểu sill vẫn khác nhau. REF dùng cùng bộ giải trên đáy hình thang biết trước, không phải nghiệm thủy lực giải tích hay quan trắc. Độ sâu cấp sẵn nên chưa kiểm định DHG/Manning hoặc độ sâu thật Phú Yên.

JSON/CSV có RMSE h cuối, RMSE max(h) của các khung lưu, RMSE zs từng cặp và trên một miền ướt chung cố định trong nhóm, IoU tại0,3m, diện tích và thể tích hạ. Đọc cả kết quả bất lợi; PASS chỉ nghĩa kiểm tra số đạt, không tự nghĩa V49 tối ưu. Đánh giá thêm ngưỡng ngập khác có thể thực hiện từ NetCDF đã giữ, không cần chạy lại mô hình.

## Chạy từng bước hoặc tiếp tục sau gián đoạn

```powershell
$py = 'C:\Users\CuongHM\anaconda3\python.exe'
$run = '.\River_Bathymetry_Project\Small_Benchmarks_R3\Run-Small-R3.ps1'
$out = 'D:\VTP\River_Bathymetry_Project\Small_Benchmarks_R3\results\R3_cuda_review'
& $run -Python $py -Device cuda -OutputDir $out -Suite smoke
& $run -Python $py -Device cuda -OutputDir $out -Suite closed
& $run -Python $py -Device cuda -OutputDir $out -Suite all
```

`-TimeoutSeconds 900` giới hạn 900 giây thực cho từng ca, không phải tổng. `-RetryFailed` chỉ dùng khi đã xử lý nguyên nhân môi trường/gián đoạn; lần thất bại được chuyển vào `attempts/`. Nếu đổi nguồn runtime, script, gói Python hoặc thiết bị, tạo thư mục mới. Lần chạy đã hoàn thành nhưng không đạt chất lượng cũng cần thư mục mới sau sửa. File `.running.lock` còn sau mất điện phải kiểm tra tiến trình trước khi xử lý, không tự xóa khóa.

`-Device cpu` dùng cùng vectorized solver với NumPy. `-PrepareOnly` chỉ tạo đầu vào. `-ChannelSeconds 300` tạo pilot ngắn, không thay số liệu nghiên cứu 3600 s. Không so hai ca có thời gian hoặc runtime khác nhau.

Nguồn R2 cũ đo khoảng56phút cho15ca trên GPU; bản R3 và observer mới có thể tốn khác. Đọc `wall_seconds` thực tế trong run.json. Xem `LOCAL_VALIDATION.md` để biết phần đã kiểm tra tại máy soạn mã; GPU vẫn phải được xác nhận trên máy chạy.
