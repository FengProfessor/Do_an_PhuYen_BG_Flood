# V49 — Hồ sơ nghiên cứu bằng chứng bên ngoài, 13/10/2026

**Phạm vi:** tìm và đối chiếu nguồn gốc số liệu hồ chứa, mực nước/dấu vết lũ 2021 và dữ liệu mặt cắt có thể dùng cho V49. Chỉ nhận số liệu thực sự công bố; phân biệt tham chiếu thiết kế, quan trắc và kết quả mô hình. Nguồn được tải bằng HTTPS có kiểm tra chứng chỉ, lưu bản PDF và SHA-256, trích bảng số rồi đối chiếu ảnh trang gốc.

**Kết quả sử dụng được:** 2 bảng Z–F–W với 30 dòng cho Sông Ba Hạ/Sông Hinh; 6 tham chiếu dung tích cho các hồ nhỏ hơn; 8 vị trí bản đồ tương đối; 3 đỉnh lũ được báo cáo; một tập dấu vết lũ chỉ đủ độ chính xác vị trí cho chẩn đoán vùng. Chưa có cơ sở công nhận toàn miền đạt độ chính xác thủy lực 100%.

## 1. Hồ Sông Ba Hạ và Sông Hinh

[Quyết định 878/QĐ-TTg năm 2018, bản PDF Chính phủ](https://datafiles.chinhphu.vn/cpp/files/vbpq/2018/07/878-qd-ttg.signed.pdf) có bảng cao trình–diện tích–dung tích ở trang PDF 45 và 47. Trang PDF 4 ghi thông số kỹ thuật cơ bản. Đây là tài liệu kỹ thuật lịch sử được phiên bản hóa; hồ sơ này không kết luận về hiệu lực pháp lý hiện tại.

| Hồ | Object chính trong V49 | Số dòng ZFW | CSV chuẩn hóa |
|---|---|---:|---|
| Sông Ba Hạ | W20_0028 | 22 | [SONG_BA_HA_published_ZFW.csv](D:/VTP/River_Bathymetry_Project/V49_PUBLIC_EVIDENCE_20261013/SONG_BA_HA_published_ZFW.csv) |
| Sông Hinh | W20_0059 | 8 | [SONG_HINH_published_ZFW.csv](D:/VTP/River_Bathymetry_Project/V49_PUBLIC_EVIDENCE_20261013/SONG_HINH_published_ZFW.csv) |

Sông Ba Hạ: dòng Z=105 m ghi F=54,66 km² và W=349,69 triệu m³; phần thông số cơ bản ghi 349,70 triệu m³. [Trang công ty Sông Ba Hạ](https://beta.sbh.vn/c3/gioi-thieu-c/Linh-vuc-hoat-dong-2-224) ghi tổng dung tích 394,70 triệu m³. Hai tham chiếu được giữ riêng; không điều chỉnh bảng công bố để ép khớp trang giới thiệu.

Sông Hinh: trang thông số ghi mực nước bình thường 209 m, tổng dung tích 357 triệu m³. Bảng ZFW có bước 5 m; nội suy tuyến tính giữa 205 và 210 m cho 362,592 triệu m³ tại 209 m. Độ lệch này phải được ghi nhận khi dùng bảng thô: giá trị nội suy không trở thành quan trắc hay thay thế thông số gốc. [Nguồn bảng và thông số](https://datafiles.chinhphu.vn/cpp/files/vbpq/2018/07/878-qd-ttg.signed.pdf).

Quy tắc đã thực thi: kiểm tra hữu hạn và tăng đơn điệu, chuyển triệu m³ thành m³, chỉ nội suy trong phạm vi công bố, cấm ngoại suy và cấm dùng một dung tích đơn lẻ như một đường cong. Bảng dung tích toàn hồ cần được đối chiếu với toàn bộ footprint hồ, thời điểm khảo sát/bồi lắng, hệ cao độ và trạng thái vận hành trước khi ràng buộc terrain. Các fragment OSM/GSW không mặc nhiên đại diện toàn hồ.

## 2. Hồ thủy lợi và nguy cơ trùng tên

[Danh mục hồ chứa Phú Yên, Quyết định 1136/QĐ-UBND ngày 01/7/2020, Công báo](https://congbao.daklak.gov.vn/FileCongBao/upload/2001592/convertPDFFile/61e0de92582d7c018305328d.pdf) công bố tên, xã, dung tích và thông số đập. Bản lưu hiện nằm trên cổng Công báo Đắk Lắk nhưng nội dung gốc là danh mục Phú Yên năm 2020; giữ nguyên địa danh và niên đại nguồn.

| Tên và địa điểm gốc | Object ứng viên | Dung tích hữu ích / toàn bộ (triệu m³) | Trang PDF |
|---|---|---|---:|
| Phú Xuân, Xuân Phước–Đồng Xuân | W20_0012 | 8,59 / 11,22 | 2 |
| Đồng Tròn, An Nghiệp–Tuy An | W20_0014 | 18,31 / 19,55 | 2 |
| Suối Vực, Suối Bạc–Sơn Hòa | W20_0020 | 9,94 / 10,510 | 2 |
| Đồng Khôn, Hòa Xuân Tây–Đông Hòa | W20_0069 | 2,61 / 2,716 | 2 |
| Buôn Đức, EaTrol–Sông Hinh | W20_0071 | không công bố ô hữu ích / 4,276 | 2 |
| Hóc Răm, Hòa Tân Tây–Tây Hòa | W20_0064 | 2,60 / 2,910 | 3 |

CSV giữ ô trống đúng nghĩa thiếu dữ liệu, không chuyển thành 0. Liên kết object còn là ứng viên tên–địa điểm, cần xác minh footprint; chưa tạo thêm quyền đào lòng sông. [CSV tham chiếu dung tích](D:/VTP/River_Bathymetry_Project/V49_PUBLIC_EVIDENCE_20261013/published_minor_reservoir_capacity_references.csv).

Danh mục còn có một hồ Đồng Tròn nhỏ tại Sơn Thành Đông–Tây Hòa. Vì vậy chỉ trùng tên không đủ để nối công trình với polygon. [Nguồn danh mục, trang PDF 5](https://congbao.daklak.gov.vn/FileCongBao/upload/2001592/convertPDFFile/61e0de92582d7c018305328d.pdf).

[Bản tin Viện Quy hoạch Thủy lợi ngày 30/9/2022](https://vanhanhtt.thuyloivietnam.gov.vn/resource/32f93d85-61e5-eddf-54fd-1fede2d4b613/Ban%20tin%20tich%20%20nuoc%20ho%20chua%20vung%20NTB.%20T10.pdf) bổ sung mực nước chết/bình thường cho Phú Xuân, Đồng Tròn và Suối Vực. File có chữ T10 nhưng niên đại in trong văn bản là **2022**, không phải sự kiện 2021. Hoa Sơn ở Vạn Ninh–Khánh Hòa; ngay trong tài liệu, bảng kỹ thuật trang 5 ghi MNDBT 27 m, bảng vận hành trang 6 ghi 26,5 m. Giữ cả hai tham chiếu, chưa chọn một mốc duy nhất.

[Bản tin tuần 08/10/2021 của Viện Quy hoạch Thủy lợi](https://vanhanhtt.thuyloivietnam.gov.vn/resource/32f93d85-61e5-eddf-54fd-1fede2d4b613/Nam%20Trung%20Bo_Ban%20tin%20Tuan_08.10.2021.pdf), trang PDF 8, có trạng thái mực nước từng hồ trước đợt lũ cuối tháng 11. Các điểm tháng 10 không được dùng làm điều kiện khởi đầu tháng 11 hay nội suy thành quan trắc trong trận lũ.

## 3. Đỉnh lũ, niên đại và hệ cao độ

[Báo cáo môi trường 2021–2025 trên cổng UBND Đắk Lắk, công bố năm 2026](https://vpubnd.daklak.gov.vn/CMS/Content/VanBan/2026/4.2026/1123_QD-UBND%20BC.pdf), trang PDF 211–212, tổng hợp các đỉnh lũ 2021 dưới đây. Niên đại sự kiện khác niên đại tài liệu.

| Trạm | Mực nước báo cáo (m) | Thời điểm địa phương UTC+7 |
|---|---:|---|
| Củng Sơn | 38,72 | 30/11/2021 19:00 |
| Phú Lâm | 4,63 | 30/11/2021 23:00 |
| Hà Bằng | 10,61 | 30/11/2021 16:00 |

[CSV đỉnh lũ](D:/VTP/River_Bathymetry_Project/V49_PUBLIC_EVIDENCE_20261013/2021_official_reported_flood_peaks.csv) giữ giờ địa phương và UTC, trang nguồn và SHA-256. Tọa độ trạm/hệ cao độ vẫn `UNVERIFIED`, nên chưa so sánh cao độ tuyệt đối với `zs` của BG_Flood.

[Báo cáo nhanh Bộ NN&PTNT lưu trong dự án](https://phongchongthientai.mard.gov.vn/FileUpload/2021-12/441ZXa7-i0CwGCPjBao%20cao%20nhanh%20ngay%2030-11.docx) ghi Phú Lâm 4,62 m lúc 01:00 ngày 01/12. Bản DOCX đã được xác minh trước đó có SHA-256 `92719e5867955db3d42e0e5f52b87f4fae97937e5b5bde957724b4e74465f0fa`. Hai đỉnh Phú Lâm lệch 0,01 m và 2 giờ; hồ sơ giữ nguồn đối lập để đối chiếu với sổ trạm gốc.

Epoch G đóng băng là 26/11/2021 00:00 UTC+7. Phú Lâm 23:00 ngày 30/11 tương ứng 119 giờ, còn 01:00 ngày 01/12 là 121 giờ. BASE cũ dừng 105 giờ; BASE mới 120 giờ được xếp chạy. Run 120 giờ vẫn không đủ cho mục tiêu 121 giờ nếu cuối cùng chọn báo cáo nhanh; cần nghiên cứu cửa sổ mở rộng riêng sau khi giải quyết mốc quan trắc.

## 4. Dấu vết lũ và mặt cắt

[Nghiên cứu của Viện Khoa học KTTV và BĐKH, số 30/2024](https://imh.ac.vn/wp-content/uploads/2024/07/30.bai-6.pdf), trang PDF 8, có 20 dấu vết lũ 2021. Tọa độ làm tròn 0,01° và thiếu thông tin hệ cao độ; chỉ dùng chẩn đoán vùng, chưa dùng RMSE điểm 30 m. Mặt cắt được nhắc trong nghiên cứu nhưng chưa có bảng thô tải được qua bài này. Không nhận sai số của HEC-RAS là sai số BG_Flood.

Tập trích chỉ giữ cột quan trắc; phương pháp chẩn đoán vùng được đăng ký khi các run G còn đang chạy. [Đăng ký chẩn đoán](D:/VTP/River_Bathymetry_Project/V49_PUBLIC_EVIDENCE_20261013/V49_HWM_DIAGNOSTIC_PREREGISTRATION.json). BASE lịch sử có nước mô phỏng trong cả 20 vùng bao vị trí, nhưng điều này không chứng minh nước tại đúng vị trí khảo sát hoặc khớp cao độ; cửa sổ sự kiện công bố còn dài hơn run hiện tại.

## 5. Vị trí địa danh và sản phẩm thoát nước riêng

[Danh mục địa danh Phú Yên năm 2015, PDF gốc trên cổng Bộ](https://vupc.mae.gov.vn/Data/files/25-2015-tt-btnmt.PDF) nêu hệ VN-2000, tỷ lệ 1:25.000 và ý nghĩa vị trí tương đối ở trang PDF 2. Tám dòng đã được đọc từ trang gốc: Đồng Khôn (31), Phú Xuân (39), Sông Ba Hạ (67 và 69), Sông Hinh (69), Hóc Răm (82), cầu Ngân Sơn (85), Đồng Tròn–Tuy An (96). OCR chỉ giúp tìm trang, không dùng làm bảng số được chấp nhận. [Trang giới thiệu chính thức](https://vupc.mae.gov.vn/do-dac-ban-do-va-thong-tin-dia-ly/3948/thong-tu-so-25-2015-tt-btnmt-ngay-28-05-2015-cua-bo-truong-bo-tai-nguyen-va-moi-truong-ban-hanh-danh).

[CSV vị trí gốc](D:/VTP/River_Bathymetry_Project/V49_PUBLIC_EVIDENCE_20261013/published_relative_geographic_locations.csv) giữ DMS và datum. [QA GIS vị trí/footprint](D:/VTP/River_Bathymetry_Project/V49_R2_20261013/REMAINING_EVIDENCE/V49_published_location_and_footprint_context.csv) dùng phép VN-2000→WGS84 được định nghĩa trong EPSG; độ chính xác ghi cho phép chuyển tọa độ không phải độ chính xác vị trí địa danh. Các vị trí hồ Phú Xuân, Đồng Tròn, Đồng Khôn và Hóc Răm nằm trong polygon ứng viên. Đây là bằng chứng định danh bổ sung, chưa chứng nhận bathymetry hoặc vị trí đo.

QA cục bộ xác nhận W20_0028 chạm biên miền mô hình; diện tích 5,6313 km² bằng khoảng 10,3024% diện tích tham chiếu thiết kế Sông Ba Hạ tại 105 m. Tỷ số giữa các thời điểm/mực nước khác nhau không phải phép đo độ đầy đủ footprint. Một vị trí Sông Ba Hạ trong danh mục nằm trong polygon, vị trí thuộc xã Suối Trai cách khoảng 3,20 km. Cần toàn footprint và điều kiện vận hành trước khi dùng dung tích toàn hồ.

Cầu Ngân Sơn là mốc địa danh, không phải trạm thủy văn; nó cách object ứng viên W20_0011 khoảng 5,11 km. Chỉ trùng tên không xác nhận object hay kết nối graph. Registry tiếp tục giữ tọa độ các trạm Củng Sơn/Phú Lâm/Hà Bằng chưa xác minh.

### Bằng chứng thuật toán

[Priority-Flood, Barnes và cộng sự](https://arxiv.org/abs/1511.04463) và [mã nguồn chính thức pysheds](https://github.com/pysheds/pysheds) là căn cứ cho sản phẩm thoát nước riêng. Kết quả cục bộ của V49 phải được kiểm tra bằng graph và raster đọc lại; một thuật toán lấp hố không cung cấp đáy sông đo đạc. DEM này có nhãn `DRAINAGE_ANALYSIS_ONLY` và chưa chứng minh sự phù hợp với toàn bộ network đã lập bản đồ.

## 6. Tính toàn vẹn và điều kiện còn thiếu

Registry lưu 8 PDF nguồn và 6 CSV kết quả, với checksum và số dòng. Mã ingest từ chối PDF thay đổi sau đối chiếu; validator kiểm tra lại file thật, không chỉ cờ PASS. [Registry và giới hạn sử dụng](D:/VTP/River_Bathymetry_Project/V49_PUBLIC_EVIDENCE_20261013/V49_PUBLIC_EVIDENCE_REGISTER.json).

| PDF lưu tại `V49_sources_20261013` | SHA-256 |
|---|---|
| QD878_2018_SongBa.pdf | 618b34beabc213ca495b61330a90e7abecaaa9c2f94178ecc873325efa1b26d2 |
| DakLak_environment_2021_2025_2026.pdf | c29c63ed68cd1e7e0afd4818f2890cde81f3e9528da93672097e437f2cef4c29 |
| QD1757_2010_ZFW.pdf | 7acbf83a34117efbaa85293e597e65e6ce5b7437bbc3afbe23b82d300d7a524c |
| IMH_HECRAS_PhuYen_2024.pdf | 3108d28a3941ae654b3239a556dcefbd88bc1be4110a158b18ecf98017ca588f |
| QD1136_2020_reservoir_inventory.pdf | 2c3c36531b306ea7d43e089e46e6a0a0ea58ae4e7fe028051c4a03a6b7d24205 |
| IWRP_storage_bulletin_20220930.pdf | 0d8d900136daa8e226ea30712e73534983d10031d07d356da35a9ff879fcb7fa |
| IWRP_weekly_20211008.pdf | 8bab2629b265e57e0f889a44ab3151f6da8470cf7f5f4c661ddb665e6b81172c |
| TT25_2015_PhuYen_geographic_names.pdf | 3785c61a37e0a1fb3448dc5276d73ead76b9e8433e7408431455863ddc75c631 |

[Quyết định 1757 năm 2010](https://congbao.chinhphu.vn/van-ban/quyet-dinh-so-1757-qd-ttg-3387/1435.htm) được lưu để đối chiếu lịch sử; bảng số 2018 được chọn cho bộ tham chiếu hiện tại.

Đã tìm trên cổng Chính phủ/Công báo, UBND địa phương, Viện Quy hoạch Thủy lợi, tài liệu chủ công trình, nguồn KTTV và thư mục nghiên cứu trong workspace. Trong các nguồn đã kiểm tra, chưa thu được đầy đủ mặt cắt thô có tọa độ/hệ cao độ, sổ mực nước theo giờ 2021 có metadata trạm, hoặc biên triều cùng hệ cao độ cho toàn miền. Đây là mô tả phạm vi kết quả tìm kiếm hiện tại, không phải kết luận dữ liệu đó không tồn tại.

Điều kiện tiếp nhận nguồn tiếp theo đã nằm trong [hồ sơ 80 object và coverage raster](D:/VTP/River_Bathymetry_Project/V49_R2_20261013/REMAINING_EVIDENCE/V49_object_evidence_and_pixel_coverage.csv): định danh đúng công trình/đoạn sông, tọa độ và footprint, niên đại quan trắc, hệ cao độ/chuyển đổi, hình học đáy hoặc ZFW đầy đủ, điều kiện vận hành và tính phù hợp với cửa sổ mô phỏng.
