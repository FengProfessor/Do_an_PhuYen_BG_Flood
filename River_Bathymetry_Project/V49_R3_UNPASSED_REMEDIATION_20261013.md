# V49 R3 — xử lý các phần chưa đạt, 13/10/2026

**Đã thực thi R3 và kiểm tra lại: 15/15 kiểm tra triển khai/tính toàn vẹn PASS; 102/102 test PASS. Nghiệm thu khoa học toàn miền chưa hoàn tất, Gate G=PENDING và `hydraulic_promotion_ready=false`.**

Audit hiện hành: [V49_ALL_PHASE_AUDIT_20261013.json](D:/VTP/River_Bathymetry_Project/V49_ALL_PHASE_AUDIT_20261013.json). Sản phẩm R3 ở `D:/VTP/River_Bathymetry_Project/V49_R3_20261013`. Cấu hình và input G đã đóng băng vẫn được giữ nguyên; E R3 có cùng SHA-256 với E gốc và R2.

## Các phần đã giải quyết trong lượt này

| Công việc | Kết quả thực tế |
|---|---|
| Fragment sông chưa có loại | W20_0034 → RIVER_STREAM; W20_0050 và W20_0052 → ESTUARY_TIDAL_RIVER/coastal review. UNKNOWN giảm 32→29. |
| Bằng chứng kết nối | Kiểm tra cùng component liên thông của polygon OSM, không lấy chiều dài graph ở một component xa. Overlap lần lượt 100%, 76,44%, 78,50%; graph trong cùng component 3.075,9 m hoặc 13.611,9 m. |
| Kiểm tra lại các phase phụ thuộc | Dựng lại C/D/C.1/E/F trong R3; tất cả validator PASS. Không tự cấp thêm geometry hoặc carving từ nhận dạng loại thủy vực. |
| Bằng chứng nước đúng năm 2021 | Tải 12 TIFF MonthlyHistory từ kho JRC chính thức; đọc lại SHA-256, band/grid và class thật. Tạo 972 dòng object/tháng cho 81 object, bảng tháng 11 và tổng hợp quan trắc năm. |
| Khảo sát thực địa công bố | Đối chiếu ảnh bản gốc Phú Sen tháng 1/2024; nhập 7 điểm góc, footprint và 11 cao độ miệng lỗ khoan trên 4 tuyến địa chất. |
| Hệ chiếu ngang khảo sát | EPSG:9218 → EPSG:3406 tái lập hai bảng tọa độ in trên bản vẽ, residual tối đa 0,0061 m. Chuyển sang EPSG:32649 bằng phép chuyển VN-2000/WGS84 được định nghĩa, độ chính xác phép chuyển công bố 1 m. |
| Nguồn trạm/mặt cắt | Kiểm lại 7 file nguồn mới: 5 PDF, 1 RAR và 1 HTML chính thức. Xác định nguồn lưu trữ của các mặt cắt và giữ xung đột tọa độ Củng Sơn. Chưa thu được chuỗi giờ 2021 có datum/provenance đạt yêu cầu. |
| Kiểm thử | 102 passed in 41,60 s, gồm dữ liệu thiếu quan trắc, polygon rời nhau, nguồn/output bị sửa, và ngăn cao độ bãi cát bị cấp quyền thành bathymetry; kiểm lại cả geometry và thuộc tính lưu trong GeoPackage. |

[Bằng chứng fragment đã đọc lại](D:/VTP/River_Bathymetry_Project/V49_R3_20261013/PARENT_SUPPORT/V49_parent_channel_support.csv) và [báo cáo dựng lại R3](D:/VTP/River_Bathymetry_Project/V49_R3_20261013/V49_R3_REBUILD_REPORT.json) ghi từng quyết định và nguồn checksum.

## Bằng chứng 2021 và giới hạn sử dụng

[Registry 12 nguồn TIFF](D:/VTP/River_Bathymetry_Project/V49_R3_20261013/WATER_HISTORY_2021/V49_2021_WATER_HISTORY_REGISTER.json) ghi URL, byte count và SHA-256 riêng từng tháng. Đây là **GSW v1.4 MonthlyHistory 2021**, kho FTP `VER5-0` công bố năm 2022. Tên thư mục VER5-0 không phải bằng chứng rằng đây là bản GSW v1.5 hiệu chỉnh năm 2026.

Mã 0 là không có quan trắc dùng được; mã 1 là quan trắc không có nước; mã 2 là quan trắc có nước. Mọi tỷ lệ giữ riêng mẫu số toàn object và mẫu số có quan trắc. Không resample lưới native; mask dùng tâm pixel. Theo [tài liệu MonthlyHistory của nhà cung cấp](https://developers.google.com/earth-engine/datasets/catalog/JRC_GSW1_4_MonthlyHistory), đây là tổng hợp tháng; nó không cung cấp mực nước hoặc bờ nước chính xác vào ngày Sentinel-1 chụp.

Tháng 11/2021: **24/80 object nội địa không có quan trắc**, 54 có ít nhất một pixel được quan trắc là nước, 2 chỉ có quan trắc không nước trên phần footprint được nhìn thấy. Các con số này không chứng nhận toàn bộ diện tích object luôn có nước. Bảng tương ứng được nối vào [hồ sơ tồn đọng từng object R3](D:/VTP/River_Bathymetry_Project/V49_R3_20261013/REMAINING_EVIDENCE/V49_object_evidence_and_pixel_coverage.csv).

JRC đã thông báo hiệu chỉnh Seasonality/YearlyHistory 2016–2021 trong bản mới; R3 sử dụng ảnh quan trắc tháng đã lấy được, không dùng bảng annual cũ để gán permanent hoặc giả nhận bản hiệu chỉnh chưa tải. [Ghi chú cập nhật chính thức](https://global-surface-water.appspot.com/download).

Attribution: Source: EC JRC/Google. [Pekel et al., Nature 2016, DOI:10.1038/nature20584](https://doi.org/10.1038/nature20584).

## Khảo sát Phú Sen đã nhập

[Registry khảo sát](D:/VTP/River_Bathymetry_Project/V49_R3_20261013/SURVEY_CONTEXT/V49_PhuSen_2024_survey_register.json), [GeoPackage footprint/điểm góc](D:/VTP/River_Bathymetry_Project/V49_R3_20261013/SURVEY_CONTEXT/V49_PhuSen_2024_survey_context.gpkg) và [bảng cao độ miệng lỗ khoan](D:/VTP/River_Bathymetry_Project/V49_R3_20261013/SURVEY_CONTEXT/V49_PhuSen_2024_collar_heights.csv) được kiểm tra lại từ bảng đã đối chiếu ảnh gốc.

Footprint tính từ các điểm góc là 91.418,1152 m², khớp diện tích in 9,1419 ha trong độ làm tròn. Bản vẽ có cả hai hệ VN-2000; phép chiếu xác nhận cột 6° là kinh tuyến 111°, và tọa độ điểm A trên bản vẽ dùng northing 1.437.932,48 m. Hai lỗi/khác biệt trong phần mô tả p31 được giữ trong registry, không sửa source PDF.

Footprint nằm trên bãi cát; **không giao các polygon nước của inventory hiện tại**. Đây là dữ liệu khảo sát địa chất/bãi cát năm 2024, chưa có tie hệ cao độ và chưa phải mặt cắt bathymetry toàn bề ngang sông năm 2021. Không có geometry reach mới được chấp nhận, không suy đáy sông từ độ sâu khoan hoặc đường giới hạn khai thác +9 m. [Tài liệu gốc công bố bởi cơ quan tỉnh, PDF pp.208–209](https://snnmt.daklak.gov.vn/uploads/sonnmt/ccbvmt/0%20.DTM%20Phu%20Sen%20Binh%20An.pdf).

## Các phần chưa thể đóng

| Phase/chủ đề | Tồn đọng thực tế sau R3 | Điều kiện cần để đóng |
|---|---|---|
| C | 29 object UNKNOWN | Bằng chứng nhận dạng và kết nối tại chính object; hiện vẫn giữ no-carve. |
| C.1 | 43 mục review: 37 insufficient + 6 conflict; 28 confirmed và 10 seasonal | Quan trắc có thời gian/phạm vi phù hợp; coastal objects cần xác minh chế độ triều/backwater. |
| B / graph support | 7 object không có graph trong 90 m; W20_0032 cần alignment review; 7 cạnh OSM vẫn là ứng viên | Kiểm tra đúng nhánh, hướng dòng và kết nối; không thêm graph cho fragment bờ nước chỉ để đạt coverage. |
| D/E/F | 9 major persistent omissions; chưa có bathymetry khảo sát được nhận | Mặt cắt/XYZ hoặc inversion có discharge, bank geometry, datum và niên đại; khảo sát bãi cát mới chưa đáp ứng điều kiện đó. |
| Hồ chứa | 17 lake/reservoir objects, còn các yêu cầu footprint/datum/dated operation | Nối đúng toàn footprint, ZFW/geometry, hệ cao độ và thời điểm vận hành; không dựng một mặt đáy duy nhất từ tổng dung tích. |
| Quan trắc G | Chưa có raw chuỗi giờ năm 2021 và metadata hệ cao độ trạm được xác minh | Xác minh vị trí trạm đúng thời kỳ, gauge zero/benchmark, units, QC và timestamp. Nguồn hiện tìm được có xung đột tọa độ Củng Sơn và không có raw export. |
| Gate G | CENTRAL đang chạy, LOW/HIGH/BASE 120 h đang chờ | Hoàn thành run, đánh giá cùng hợp đồng Sentinel-1, velocity/numerical budget và bằng chứng quan trắc phù hợp; sau đó ghi quyết định khoa học. |

Graph review R3: W20_0004, W20_0008, W20_0011, W20_0034, W20_0050, W20_0052, W20_0062. Việc xác minh class ở ba fragment làm nhu cầu QA kết nối được ghi rõ hơn; không có nhánh mới tự động được đưa vào graph 370 reaches.

E R3 vẫn 2 reaches được phép, 72 pixel thực sự chỉnh, 8.008,2092 m³ lowering, 0 pixel ngoài mask và 0 pixel Đồng Cam bị chỉnh. SHA-256 E gốc/R2/R3: `181115942dc88a95503a1e193b2f90149e918b6f8354a262085b293e11df2552`. Source DEM: `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`.

## Trạng thái thực thi và kiểm tra lại

Snapshot lúc **18:43 ngày 13/10/2026 UTC+7**: CENTRAL **15,34%**, đã mô phỏng 66.276,77/432.000 s; supervisor PID 12616 và worker PID 4040 đều sống. Queue **LOW → HIGH → BASE**. Đây là snapshot tiến độ, không phải dự báo thời gian hoàn thành. [Trạng thái đang chạy](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_EXECUTION_STATE.json).

```powershell
Set-Location -LiteralPath 'D:\VTP\River_Bathymetry_Project'
& 'C:\Users\CuongHM\anaconda3\python.exe' -X utf8 -B v49_audit_all_phases.py
& 'C:\Users\CuongHM\anaconda3\python.exe' -X utf8 -B v49_run_hydraulic_validation.py status
```

[Nghiên cứu nguồn trạm/mặt cắt](D:/VTP/River_Bathymetry_Project/V49_R3_station_and_geometry_research_20261013.md) và [registry kiểm checksum 7 file nguồn](D:/VTP/River_Bathymetry_Project/V49_R3_20261013/V49_R3_PRIMARY_RESEARCH_REGISTER.json) ghi các kết quả truy cập công khai và đơn vị lưu trữ được tài liệu gốc chỉ ra. Chưa có bằng chứng để chuyển các hold về quan trắc/hình học sang PASS hoặc tuyên bố “chuẩn 100%”.
