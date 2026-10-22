# Nghiên cứu bản đồ án Phú Yên và cơ sở chuẩn hóa nội dung

Ngày rà soát 05/10/2026. Bản chính theo lựa chọn của tác giả là [Do_an_tot_nghiep_PhuYen_BG_Flood_SAR.docx](D:/VTP/Do_an_tot_nghiep_PhuYen_BG_Flood_SAR.docx). Đã đọc toàn bộ 433 đoạn văn và 9 bảng, đối chiếu với cấu hình, mã xử lý, log, 40 khung NetCDF V44 và danh mục 35 tài liệu. File Word nguồn được giữ nguyên.

**Bản chính có kết quả thực nghiệm có thể truy vết, nhưng cần sửa một số nội dung khoa học trước khi hoàn thiện văn phong.** V44 thực sự có 40 khung kết quả đến 432.000 giây; các chỉ số tại khung 33 tái lập đúng. Tuy nhiên, 7 dòng của bảng thời gian không khớp dữ liệu, nhiều mô tả đầu vào khác cấu hình chạy, và 8 DOI trỏ sang tài liệu khác. Những nhận định về HAND, kiểm định độc lập và học máy đang vượt quá bằng chứng hiện có.

Các vị trí `Pxxxx` và `TxRy` trong báo cáo là mã đoạn/bảng của [bản trích xuất](D:/VTP/Do_an_research_20261005/Do_an_tot_nghiep_PhuYen_BG_Flood_SAR.txt), không phải số trang Word. Các nhận xét định dạng dựa trên cấu trúc OOXML; chưa xác nhận bố cục từng trang qua một bản render mới.

[Đối chiếu cơ sở khoa học với nguồn gốc](D:/VTP/Do_an_research_20261005/Co_so_khoa_hoc_va_nguon_goc_20261005.md) giải thích sáu nhóm nhận định về solver, DEM, ERA5, SAR/Otsu, HAND và chỉ số đánh giá, kèm 10 nguồn chính. Tài liệu công bố hỗ trợ định nghĩa và phạm vi phương pháp; kết quả thực nghiệm trong báo cáo này được kiểm tra riêng từ dữ liệu dự án.

## Câu chuyện nghiên cứu nên giữ làm trục chính

Đồ án nghiên cứu khả năng mô phỏng phạm vi ngập trận cuối tháng 11/2021 bằng mô hình thủy lực hai chiều trên lưới 30 m và đối chiếu với sản phẩm SAR. Trọng tâm có thể bảo vệ được là **thiết lập quy trình, kiểm tra tính nhất quán của dữ liệu và nhận diện ảnh hưởng của biểu diễn địa hình tới kết nối dòng chảy**. Hiệu chỉnh địa hình là một giả thuyết kỹ thuật cần thử nghiệm có đối chứng, có giới hạn về hình học và độ bất định.

Ba câu hỏi nghiên cứu phù hợp với dữ liệu đang có:

1. Cấu hình thủy lực, dữ liệu raster và phép đối chiếu SAR có nhất quán về không gian, thời gian và đơn vị không?
2. Những vị trí địa hình nào có thể hạn chế kết nối từ lòng sông tới vùng thấp lân cận, và thay đổi chúng ảnh hưởng thế nào tới phạm vi ngập tính toán?
3. Mức độ trùng khớp với SAR thay đổi ra sao, đồng thời xuất hiện những đánh đổi nào giữa bỏ sót và báo ngập ngoài mặt nạ tham chiếu?

Không cần đặt mục tiêu “mô phỏng chính xác” hoặc “cảnh báo sớm tin cậy” làm kết quả đã đạt. Tốc độ tính toán nhanh hơn thời gian thực là một điều kiện kỹ thuật; hệ thống cảnh báo còn cần dữ liệu dự báo, thời gian chuẩn bị, quan trắc độc lập và đánh giá nhiều sự kiện.

## Kết quả V44 đã được xác nhận

[Đối soát dữ liệu dự án](D:/VTP/Do_an_research_20261005/project_evidence_audit.json) đọc trực tiếp NetCDF và tái tạo phép chồng xếp của `eval_v44.py`. Phạm vi kiểm chứng là phép đánh giá lịch sử với transform và mask của V44, chưa xác nhận rằng phương pháp căn chỉnh địa lý cũ là tối ưu hoặc rằng SAR là sự thật tuyệt đối.

| Nội dung | Bằng chứng hiện tại | Cách trình bày trong đồ án |
|---|---|---|
| Hoàn thành chuỗi mô phỏng | 40 khung, thời gian cuối 432.000 s; log ghi hoàn tất | Có thể ghi V44 hoàn thành 120 giờ mô hình |
| Khung đối chiếu chính | Frame 33, `time=367200,28125 s`, khoảng 102,000078 giờ | Ghi khung gần thời gian ảnh SAR và độ lệch thời gian, không tự gọi là đỉnh lũ |
| Ma trận nhầm lẫn | TP 72.168; FP 60.698; FN 216.808; TN 3.130.770 | Giữ số liệu và ghi rõ mask hợp lệ |
| Chỉ số tại frame 33 | CSI 20,638652%; Recall 24,973700%; Precision 54,316379% | Làm tròn thành 20,64%; 24,97%; 54,32% |
| Diện tích trong mask | Mô phỏng 119,5794 km²; SAR 260,0784 km² | Đây là diện tích trong phạm vi đánh giá, không phải diện tích ngập toàn tỉnh |
| HAND theo quy trình hiện có | 120.153/132.866 ô ngập có chỉ số ≤3,5 m, bằng 90,431713% | Giữ như chẩn đoán phân bố địa hình, kèm giới hạn phương pháp |
| Hiệu suất chạy | `Runtime=253274,39 s`, tương đương 70,354 giờ | Tỷ số 120/70,354 ≈1,706 lần thời gian thực theo thời gian solver |

Bảng 3.5 nhất quán về số học: F1≈34,21565%, Kappa≈0,305851, MCC≈0,332228. “Tương quan thuận mức khá” cần tiêu chí phân loại riêng; nên báo cáo giá trị thay vì tự gán mức chất lượng.

Tại frame 33, tỷ lệ bỏ sót so với SAR là khoảng 75,03% và tỷ lệ báo động sai trong diện tích mô phỏng là khoảng 45,68%. Precision 54,32% không đủ để khẳng định mô hình “kiểm soát tốt ngập giả”. Đây là kết quả đối chiếu còn hạn chế, hữu ích để chẩn đoán bước tiếp theo.

## Những sửa đổi quan trọng theo vị trí

| Vị trí trong bản chính | Vấn đề | Sửa theo bằng chứng |
|---|---|---|
| Tóm tắt P0023–P0024 và Abstract P0029–P0030 | Khẳng định nguyên nhân chính, tốc độ 1,75–1,83 và kiểm chứng HAND độc lập | Đưa hiệu suất V44 đo được; gọi SAR là sản phẩm tham chiếu; HAND là chẩn đoán địa hình; nêu giới hạn hiệu chỉnh |
| P0067, P0314–P0315 | Nhầm mốc xả, thông số thủy văn và gán Sông Hinh vào Bàn Thạch | Dẫn đúng bản tin/báo cáo và phân biệt số liệu quan trắc với lưu lượng kịch bản; sửa sơ đồ mạng sông |
| P0075, P0300, P0323 | Mô tả 145 trạm mưa không gian | Config V44 dùng một chuỗi mưa uniform 144 bản ghi, 0–514.800 s; header nói trung bình 16 điểm; không coi header là chứng minh dữ liệu ERA5 gốc |
| P0159, P0162 | Khẳng định VV luôn tốt hơn VH và Otsu đòi hỏi hai phân phối Gaussian | Nêu lý do lựa chọn phân cực theo dữ liệu thực nghiệm; Otsu tối ưu phân chia histogram, không có điều kiện bắt buộc Gaussian hoặc bảo đảm chính xác ngập |
| P0175–P0178, P0243, P0250, P0319 | Đồng nhất DEM với DTM trần và gán đầu vào cho FABDEM | Phân biệt DSM/DTM; chuỗi provenance cục bộ đang dẫn tới Copernicus GLO-30; FABDEM là dữ liệu khác, cần file nguồn nếu khẳng định đã dùng |
| P0191, P0220–P0224, T2R4 | Mô tả bộ giải HLLC và suy ra bảo toàn/positivity | Mã và log V44 dùng Kurganov–Petrova central-upwind; mô tả đúng fork Python đang chạy, tách khỏi tài liệu upstream |
| T2R5–T2R6, P0233 | Ghi CFL≤0,70 và một ngưỡng khô 0,001 m | Config không khai báo CFL; mặc định mã hiện tại là 0,5. `param.eps=0,0001 m`, nhánh GPU triệt tiêu vận tốc dưới 0,001 m; cần phân biệt vai trò từng ngưỡng |
| P0237–P0247 | Nêu đủ POD, calibration, Range-Doppler, Refined Lee 5×5 và ngưỡng −14,85 dB là quy trình đã thực hiện | Chỉ giữ những bước có script, tham số và log của đúng raster. Tách quy trình lý thuyết với quá trình tạo sản phẩm thực dùng |
| P0260, P0337, P0386 | Gọi các ô hạ DEM là vị trí cống thực tế | Đổi thành vị trí ứng viên theo quy tắc raster, trừ khi có hồ sơ công trình. Một ô hạ 30 m không tự tương đương cống rộng vài mét |
| P0269–P0274 | Bảng dùng `h≥0,3 m`, diễn giải và mã dùng `h>0,3 m` | Chuẩn hóa theo toán tử thực dùng, ghi riêng ngưỡng ướt/khô solver và ngưỡng phân loại ngập để chấm điểm |
| T3R2–T3R3 | Gán mã WorldCover 30 cho cropland và gộp shrubland/grassland | Mã 20 là shrubland; 30 là grassland; 40 là cropland. Kiểm tra bảng tra Manning tương ứng |
| P0322 | Gọi IL là tốc độ thấm mm/h | IL là lượng mất ban đầu theo quy ước của engine, CL là tốc độ mất liên tục; xác minh đơn vị raster V36 trước khi diễn giải hoặc quy đổi |
| P0323, P0343, P0385 | Đầu vào mưa có header m/s nhưng chưa xét phép quy đổi trong mã cũ | Loader hiện lưu bỏ qua header và nguồn mưa chia thêm 3.600.000. Ghi giới hạn runtime; chưa gán định lượng tác động lên V44 khi thiếu bản mã khóa lúc chạy |
| P0324–P0327, P0337 | Ba nguồn xả và tọa độ không đúng config | V44 có bốn polygon nguồn: Ba Hạ, Bàn Thạch, Kỳ Lộ, Tuy An; đưa đúng tọa độ và tệp cấu hình |
| P0338–P0344 và Bảng 3.4 | 7 dòng không khớp NetCDF; dùng một ảnh SAR để “kiểm định” cả quá trình | Thay số bằng bảng tính lại; gọi chuỗi là độ khớp với một mặt nạ cố định, chỉ chọn frame theo thời gian ảnh |
| P0293–P0297, P0350–P0353, P0388 | HAND độc lập; ngưỡng đạt 85–90%; kết luận xác nhận thủy lực | Không dùng tiêu chuẩn này như chuẩn chung. Kiểm tra thuật toán HAND và dùng làm chẩn đoán bổ trợ |
| P0366–P0367, P0389 | Số ô sửa DEM và tác dụng V45 trình bày như kết quả chắc chắn | Khóa theo đúng DEM/manifest và thời điểm. Số ô bị sửa không chứng minh đó là đê thật; kết quả V45 cần đánh giá riêng |
| P0368–P0376, T8 | Số liệu surrogate, số biến và latency thiếu chuỗi provenance | Kết quả ML hiện có khác bảng; tách bài toán, tập dữ liệu, split, metric và đo thời gian. Không tự thay bằng số của bộ ML khác |
| P0381–P0389 | Kết luận mạnh hơn kết quả đã kiểm tra | Kết luận theo dữ liệu và giới hạn; mô tả cảnh báo sớm, chuyển giao và GeoAI là hướng phát triển |

Các vấn đề này ảnh hưởng cách hiểu nghiên cứu, không thể xử lý chỉ bằng thay từ đồng nghĩa.

## Những điểm cần giải thích sâu hơn khi viết

### Dữ liệu đầu vào và tính tái lập

Config V44 dùng `rain_v34_era5_x2.txt`; `prep_v34.py` nhân cột mưa của V23 với 2,0. Bốn hydrograph đang được nạp có đỉnh lần lượt 11.000; 4.007,14; 5.000; 2.000 m³/s. Đây là giá trị trong tệp kịch bản, không tự là cực trị quan trắc của từng sông. Cần mô tả nguồn, mọi bước nội suy/điều chỉnh, đơn vị, epoch và cơ sở chọn hệ số.

Có thêm bằng chứng từ runtime cũ đang lưu: `read_forcing.py` đọc giá trị cột mưa trực tiếp và bỏ qua header; nhánh mưa uniform trong `updateforcing.py` tiếp tục chia cho 1.000 và 3.600. Với tệp đã là m/s, phép này làm nguồn mưa giảm 3,6 triệu lần. Đây là lỗi mã đã được kiểm thử và sửa ở V48 R1. Tuy nhiên, chưa có hash toàn bộ runtime tại thời điểm chạy V44 để xác nhận tuyệt đối rằng mã hiện lưu chính là từng byte mã đã sinh NetCDF V44. Cần ghi nhận nguy cơ này, không tự suy ra lượng mưa thực sự đóng góp hoặc toàn bộ sai số V44. [Loader cũ](D:/VTP/BG_Flood_Project/BG_Flood/python/bg_flood/read_forcing.py:15), [nguồn mưa cũ](D:/VTP/BG_Flood_Project/BG_Flood/python/bg_flood/updateforcing.py:214), [kiểm thử và bản sửa](D:/VTP/V48_RUNTIME_FIX_REPORT_20261004.md).

Đầu vào DEM V44 có 2100×2100 ô với mép miền X=[270.000;333.000] m, Y=[1.415.000;1.478.000] m. NetCDF V44 cũ có 2099×2099 ô. Viết riêng hai kích thước thay vì gọi DEM 2099×2099 là kích thước thiết kế. Chuỗi provenance Copernicus và các sửa đổi kế thừa đã được ghi trong [audit V47](D:/VTP/V47_lineage_audit_20261001.json) và [hồ sơ Copernicus](D:/VTP/V47_copernicus_provenance_20261001.json); không tự coi bản đã sửa là DTM đo mặt đất.

Ghi rõ `zsinit=1,0 m`, các biên trái/phải/trên/dưới và hệ quy chiếu cao độ. Biên số kiểu mở không chứng minh rằng chuỗi triều thực đo tại cửa sông đã được đưa vào mô hình. Hiệu chỉnh DEM, mực nước trạm và triều cần cùng datum trước khi so sánh cao độ tuyệt đối.

ESA phân biệt WorldCover 2020 v100 với WorldCover 2021 v200; mục [21] trong đồ án hiện trích bản 2020. Cần chọn trích dẫn theo phiên bản raster thực dùng. Mã lớp và tên lớp trong Bảng 3.2 phải đúng trước khi gán hệ số nhám; hệ số nhám là tham số mô hình, không phải phép đo do ESA cung cấp. [ESA WorldCover](https://esa-worldcover.org/en/data-access), [catalog sản phẩm](https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200).

### Thời gian ảnh và số liệu thủy văn

Ảnh lúc khoảng 05:36 ngày 30/11 không tự đại diện cho đỉnh lũ trên toàn miền. Báo cáo quốc gia ghi Phú Lâm đạt 4,63 m và ghi xả Ba Hạ 9.400 m³/s tại 15 giờ ngày 30/11; khác số 3,75 m và mốc rạng sáng trong bản chính. Cần kiểm tra chuỗi mực nước, timezone và thời điểm scene trước khi gọi khung 102 giờ là “đỉnh lũ”. [Thiên tai Việt Nam 2021](https://chinhsach.dmptc.gov.vn/Uploads/Thu%20vien%20tai%20lieu/Tai%20lieu%20truyen%20thong/Thien%20tai%20Viet%20Nam%202021%20fix%203.pdf), bản lưu cục bộ [trang số liệu](D:/VTP/V45_ThienTaiVietNam2021.txt:4209).

Nghiên cứu HEC-RAS tại hạ lưu sông Ba mô tả đoạn Sông Hinh sau hồ tới nhập lưu sông Ba, còn Bàn Thạch tới cửa Đà Nông. Vì vậy không đồng nhất nguồn Bàn Thạch trong config với xả hồ Sông Hinh nếu chưa có cơ sở mạng sông. Bài này cũng là nguồn cụ thể cho tổng quan nghiên cứu tại khu vực. [Lương Hữu Dũng và cộng sự 2024](https://imh.ac.vn/wp-content/uploads/2024/07/30.bai-6.pdf).

### SAR và tính độc lập của phép đánh giá

Mặt nạ SAR là một sản phẩm quan sát gián tiếp. Phải ghi scene ID, thời gian UTC, loại sản phẩm, phân cực, các bước xử lý, ngưỡng, vùng quan sát hợp lệ và phương pháp đưa về lưới mô hình. Tên file có ngày/giờ không thay thế metadata scene. Độ phân giải mô hình 30 m không tự chứng minh raster SAR gốc cũng có phân giải 30 m.

Otsu lựa chọn ngưỡng từ histogram bằng tiêu chí phân tách lớp; phương pháp không bắt buộc hai lớp có phân phối Gaussian. Ngưỡng tối ưu theo histogram không tự là ngưỡng tối ưu phân loại ngập ngoài thực địa. Việc dùng VV hay VH cần được giải thích theo điều kiện mặt phủ, sản phẩm và phép đánh giá thực tế, không khẳng định một phân cực luôn ưu việt. [Otsu 1979](https://doi.org/10.1109/TSMC.1979.4310076), [JRC về bất định SAR](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC119812/global_flood_monitoring.pdf).

Mã `breach_levees_v44.py` dùng `sar_flood` để chọn ô sửa địa hình. Khi cùng mặt nạ được dùng để chấm điểm, kết quả thể hiện độ khớp sau hiệu chỉnh với dữ liệu đó. Muốn gọi là kiểm định độc lập cần ảnh/sự kiện hoặc mực nước/vết lũ không tham gia chọn tham số và sửa DEM. Giới hạn SAR có thể giải thích một phần sai khác; không quy toàn bộ FP/FN cho vệ tinh khi forcing, datum, grid và solver còn bất định.

### HAND và bảo toàn vật lý

`compute_hand_validation.py` xác định mạng kênh bằng tích lũy D8, NDWI và water density, nhưng bước gán cao độ kênh sử dụng `distance_transform_edt` theo khoảng cách Euclid. Cách này khác định nghĩa truy tới kênh nhận nước theo đường dòng chảy D8 trong phần lý thuyết. Vì vậy cần gọi đúng là chỉ số chênh cao tới mạng thoát nước theo quy trình đang triển khai, hoặc tính lại HAND theo định nghĩa gốc rồi cập nhật bảng kết quả. [Mã tạo chỉ số](D:/VTP/BG_Flood_Project/BG_Flood/Teamwork_Validation/compute_hand_validation.py:98).

DOI của bài HAND gốc là `10.1016/j.jhydrol.2011.03.051`, cần thay DOI sai ở mục [6]. Với FABDEM, DOI bài Hawker và cộng sự là `10.1088/1748-9326/ac4d4f`, khác chuỗi đang ghi ở mục [8]. [HAND — bài gốc](https://doi.org/10.1016/j.jhydrol.2011.03.051), [FABDEM — metadata tác giả](https://research-information.bris.ac.uk/en/publications/a-30m-global-map-of-elevation-with-forests-and-buildings-removed/).

Tỷ lệ 90,43% chứng minh một đặc điểm phân bố của kết quả theo chỉ số đang dùng. Nó không chứng minh độ sâu, thời gian truyền lũ, bảo toàn thể tích hoặc khả năng dự báo. Cũng không đủ cơ sở đặt một tiêu chuẩn chung P_HAND≥85–90% cho mọi mô hình.

Mã GPU V44 có phép chặn độ sâu [0;100] m và vận tốc ±20 m/s. Cần đo ảnh hưởng của những phép sửa số học này tới cân bằng nước trước khi khẳng định “bảo toàn nghiêm ngặt”. Không NaN và hoàn tất mô phỏng là bằng chứng về thực thi, không tự chứng minh nghiệm đúng vật lý. [Mã GPU](D:/VTP/BG_Flood_Project/BG_Flood/python/bg_flood/flow_gpu.py:343).

### Phần học máy

`model_evaluation_results.csv` hiện có XGBoost R²≈0,875014, MAE≈0,112891 m; ANN R²≈0,864525, MAE≈0,128111 m; LSTM R²≈0,890914, MAE≈0,115712 m. Những số này khác bảng 3.7; script `train_ml.py` dùng 11 biến, có cả `h_t_minus_12`, khác mô tả 8 biến địa hình/mưa. Tệp CSV không có latency 2,8/4,1/7,6 giây. [Kết quả ML](D:/VTP/BG_Flood/results/results_ml_BG/model_evaluation_results.csv), [tập biến và phép chia](D:/VTP/BG_Flood/train_ml.py:51).

Đây là đầu mối một thí nghiệm khác, chưa đủ để thay số vào bảng đồ án vì chưa chứng minh cùng dữ liệu V44, cùng sự kiện và cùng cách đánh giá. Chọn một trong hai cách: tái lập đầy đủ thí nghiệm được báo cáo, hoặc đưa phần ML về hướng nghiên cứu tiếp theo. MAE=0 khi so solver với chính nhãn do solver sinh ra không phải độ chính xác 0 m ngoài thực tế. Kiểm định ngẫu nhiên trên pixel cũng chưa chứng minh khả năng dự báo sự kiện hoặc vùng độc lập.

## Bảng thời gian cần sửa

Dưới đây là 7 dòng sai, tính lại với cùng phép đối chiếu V44 lịch sử. Bộ đầy đủ 40 dòng có trong [bảng đối chiếu](D:/VTP/Do_an_research_20261005/Bang_doi_chieu_V44_va_tai_lieu_20261005.md).

| Frame | Giờ gần đúng | CSI trong Word | CSI tính lại | Recall tính lại | Precision tính lại |
|---:|---:|---:|---:|---:|---:|
| 32 | 99 | 20,35 | 20,24 | 24,34 | 54,63 |
| 34 | 105 | 20,78 | 21,08 | 25,84 | 53,37 |
| 35 | 108 | 20,91 | 21,85 | 27,41 | 51,86 |
| 36 | 111 | 21,02 | 22,84 | 29,83 | 49,35 |
| 37 | 114 | 21,08 | 24,14 | 32,67 | 48,06 |
| 38 | 117 | 21,12 | 26,21 | 36,46 | 48,25 |
| 39 | 120 | 21,15 | 28,76 | 40,78 | 49,39 |

Không chọn frame 120 giờ vì CSI cao hơn để đại diện cho ảnh khoảng 101,6 giờ. Sau sửa bảng, các đoạn P0340–P0344 phải viết lại: Precision không duy trì trên 52,2% suốt chuỗi và CSI tiếp tục tăng về cuối. Những chỉ số cuối chuỗi so với ảnh cố định không chứng minh rằng diễn biến ngập cuối trận được quan trắc xác nhận.

## Nguồn tham khảo và cách trích dẫn

Tám mục [3], [6], [10], [14], [15], [16], [24], [26] có DOI trả về tài liệu khác chủ đề/tiêu đề. Ví dụ [3] trả về OpenPIV-MATLAB, [6] trả về nghiên cứu SMOS độ ẩm đất, [14] trả về cảnh báo động đất. Cần sửa cả DOI, tác giả, tên, tạp chí/tập/trang bằng hồ sơ của tài liệu định trích, thay vì chỉ kiểm tra URL còn mở được. [Metadata kiểm tra](D:/VTP/Do_an_research_20261005/bibliography_registry_audit.json).

Các DOI chưa xác nhận qua Crossref không tự chứng minh tài liệu không tồn tại: WorldCover [21] và JRC [30] đã được xác nhận tại cơ quan phát hành. Các mục [17]–[19] hiện chưa được tìm thấy đúng danh tính đã ghi; không sử dụng để hỗ trợ kết luận cho tới khi có bài gốc. [12] và [32] là sách, có thể trích theo ISBN/nhà xuất bản sau xác minh mà không thêm DOI chưa chứng minh. Mọi mục trong danh sách 35 tài liệu đã có quyết định xử lý riêng tại [bảng đối chiếu tài liệu](D:/VTP/Do_an_research_20261005/Bang_doi_chieu_V44_va_tai_lieu_20261005.md).

Có lỗi trích dẫn trong thân bài: P0115 dẫn [10] cho lịch sử HEC-RAS trong khi [10] được khai là tài liệu viễn thám; P0247 dẫn [14] cho JRC nước thường trực trong khi [14] là Priority-Flood. Phải gắn tài liệu với đúng nhận định rồi mới đánh lại số theo chuẩn của khoa.

Thống kê WMO ở P0064 cũng cần thu hẹp đúng đối tượng: hơn 11.000 sự kiện, hơn 2 triệu người chết và 3,64 nghìn tỷ USD là tổng thiên tai liên quan thời tiết, khí hậu và nước giai đoạn 1970–2019, không riêng lũ lụt. [WMO](https://wmo.int/media/news/weather-related-disasters-increase-over-past-50-years-causing-more-damage-fewer-deaths).

Không dùng bản nhận xét GVHD trong thư mục làm bằng chứng khoa học cho các chỉ số hoặc làm xác nhận đã được ký. Ưu tiên dữ liệu gốc và công trình nguồn; nội dung nhận xét và việc ký thuộc thẩm quyền người hướng dẫn.

## Cấu trúc và cách viết cần chuẩn hóa

Giữ ba chương nhưng rút gọn tổng quan để phục vụ câu hỏi nghiên cứu. Chương 1 nên tập trung mô hình 2D, dữ liệu địa hình, SAR và các công trình thật tại khu vực. Chương 2 mô tả đúng dữ liệu và thuật toán đã sử dụng, có tham số đủ tái lập. Chương 3 trình bày kết quả, phân tích sai khác và giới hạn theo cùng bộ đánh giá.

Phần mở đầu nên dùng mục tiêu có thể kiểm tra: thiết lập, chạy, đối chiếu, phân tích. Kết luận trả lời lần lượt các mục tiêu và chỉ giữ những kết quả đã có bằng chứng. Tách kiến nghị LiDAR, triều, dữ liệu công trình, nhiều sự kiện và GeoAI khỏi kết quả đã đạt.

Mỗi đoạn kỹ thuật nên có một ý chính theo thứ tự: vấn đề hoặc câu hỏi; thao tác/định nghĩa; bằng chứng hoặc số liệu; ý nghĩa và giới hạn. Thay “xử lý triệt để”, “tái hiện trung thực”, “hoàn toàn khách quan”, “chứng minh tính chân thực” bằng mô tả quan sát cụ thể. Không biến giả thuyết về đê thành nguyên nhân duy nhất, hay thay đổi độ khớp thành xác nhận quan hệ nhân quả.

Chuẩn hóa thuật ngữ: dùng “mặt nạ ngập SAR tham chiếu”, “độ khớp phạm vi ngập”, “hiệu chỉnh địa hình”, “đánh giá bổ trợ theo địa hình”. Phân biệt precision với accuracy, thủy văn với thủy lực, tốc độ chạy với gia tốc so CPU, độ sâu ngập với chỉ số HAND, và độ phân giải raster với độ chính xác đo đạc.

Về cấu trúc Word, cả 433 đoạn đang dùng style Normal và không có outline level trực tiếp; không tìm thấy field mục lục TOC. Danh mục liệt kê 15 hình nhưng thân bài có 3 chú thích hình và 3 ảnh inline, với số hình không khớp danh mục. Cần chọn Heading 1/2/3, dựng mục lục tự động, đồng bộ caption/danh mục, bổ sung hoặc bỏ các hình chưa có. Phần bìa, cam đoan và cảm ơn vẫn có tên/MSSV/ngày dạng placeholder; không suy ra thông tin sinh viên từ tên tài khoản.

Các phương trình hiện là văn bản, không có OMML. Khi chỉnh Word cần kiểm tra chỉ số trên/dưới, ký hiệu và số phương trình, dùng biểu thức có thể sửa trong Word nếu phù hợp. Lề A4 quan sát khoảng trái 30, phải 20, trên 25, dưới 30 mm; chỉ kết luận đạt mẫu trường sau khi đối chiếu hướng dẫn chính thức của đơn vị đào tạo.

## Gắn V45 và V48 vào bản chính theo đúng trạng thái

V45 nên được trình bày như nhánh thực nghiệm tiếp theo, có runtime, DEM và mask đánh giá riêng. Snapshot ngày 05/10 cho thấy tệp exploratory có 35 frame đến 105 giờ; không đủ bằng chứng trong snapshot này để ghi hoàn thành 120 giờ. Chỉ số 102 giờ đã đối soát ngày 04/10 là CSI≈32,40%, Recall≈72,95%, Precision≈36,83%; độ phủ cao hơn đi kèm diện tích báo ngập ngoài SAR lớn. [Snapshot đầu ra](D:/VTP/Do_an_research_20261005/V45_runtime_output_snapshot_20261005.json), [đối soát ngày 04/10](D:/VTP/V45_runs/20260928_engine_r1/results/V45_doc_soat_20261004.json).

Không suy ra phần tăng CSI chỉ do sửa DEM: giữa V44 cũ và V45 R1 có thay đổi engine và phép đánh giá. Cần cùng runtime, cùng forcing, cùng epoch, mask và thời gian đối chiếu để định lượng riêng tác động địa hình.

V48 R1 đã sửa hai lỗi đơn vị mưa và lưới. Snapshot **12:49 ngày 05/10/2026 UTC+7** ghi BASE đang chạy tới khoảng 26,43/120 giờ, có 8 frame đến khoảng 24 giờ trên lưới 2100×2100; launcher/solver được xác nhận là các process đang chạy. Chưa có output formal CONDITIONED. Do đó chỉ ghi tiến độ và thiết kế cặp đối chứng, chưa viết V48 cải thiện CSI hoặc đã nghiệm thu. [Snapshot chạy](D:/VTP/Do_an_research_20261005/runtime_snapshot_20261005.json), [báo cáo sửa runtime](D:/VTP/V48_RUNTIME_FIX_REPORT_20261004.md).

## Bộ nội dung đã chuẩn bị để viết tiếp

[Các đoạn viết lại](D:/VTP/Do_an_research_20261005/Ban_viet_lai_cac_doan_trong_yeu_20261005.md) cung cấp bản tóm tắt, Abstract, mục tiêu, mô tả đầu vào, đánh giá V44, phần HAND và kết luận dựa trên bằng chứng đã kiểm tra. Các đoạn này là nền để chỉnh bản chính; không có thông tin cá nhân, số liệu thực đo hoặc kết quả V48 được tự bổ sung.

Thứ tự áp dụng hợp lý là sửa các dữ kiện và nguồn; khóa cách đánh giá và bảng kết quả; viết lại phần phương pháp/thảo luận; đồng bộ tóm tắt và kết luận; sau cùng mới hoàn thiện mục lục, hình, bảng và bố cục Word. Điều này giúp cách viết thống nhất với thí nghiệm thực sự đã làm.
