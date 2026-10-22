# Kiểm tra tình trạng triển khai V49

**Cập nhật sau xử lý tồn đọng ngày 13/10/2026:** dùng [báo cáo R3 hiện tại](D:/VTP/River_Bathymetry_Project/V49_R3_UNPASSED_REMEDIATION_20261013.md) và [audit tổng hợp](D:/VTP/River_Bathymetry_Project/V49_ALL_PHASE_AUDIT_20261013.json). Hồi quy 102/102 PASS; 15 kiểm tra triển khai/tính toàn vẹn PASS. C/D/C.1/E/F có bộ R3; đã kiểm lại 12 tháng ảnh nước 2021 và khảo sát bãi cát Phú Sen 2024. CENTRAL đang chạy nền. UNKNOWN còn 29, queue còn 43, major omissions là 9; Gate G vẫn PENDING. Nội dung dưới đây là snapshot lịch sử, bao gồm trạng thái chưa khởi chạy G trước đó.

Kiểm tra A–F và bộ chuẩn bị G lần đầu: **13/10/2026, khoảng 00:36 (UTC+7)**. Cập nhật và chạy lại validator G mới: **13/10/2026, khoảng 07:14 (UTC+7)**.

**Kết luận:** V49 đã triển khai và đạt các gate A, B, C, D, C.1, E, F theo phạm vi nghiệm thu hiện tại. V49-G đã hoàn tất bộ chuẩn bị thí nghiệm, validator và báo cáo triển khai; preparation PASS, Gate G PENDING. Chưa có kết quả mô phỏng đối chứng CENTRAL/LOW/HIGH. V49 chưa hoàn tất mục tiêu bathymetry toàn miền và chưa đủ điều kiện thay thế DEM đang dùng cho mô phỏng chính thức.

## Trạng thái từng phần

| Phần | Trạng thái được kiểm tra | Kết quả và giới hạn |
|---|---|---|
| A — Kiểm kê mặt nước | PASS | 80 thủy vực nội địa, tổng 113,8572 km²; thêm 1 đối tượng biển được loại khỏi thống kê nội địa. |
| B — Mạng thủy văn | PASS về topology | 370 đoạn, 396 nút, 168 hợp lưu; 0 đoạn lớn cô lập, 0 chu trình có hướng. PASS này không xác nhận cao độ đáy sông. |
| C — Phân loại | PASS về hồ sơ phân loại và quy tắc xử lý | 81/81 đối tượng có lớp/quy tắc hoặc được đưa vào diện cần xem xét; 42 đối tượng vẫn UNKNOWN_REVIEW_REQUIRED. |
| D — Ước lượng hình học | PASS trong phạm vi cho phép | Giữ đủ 370 đoạn; 95 đoạn thuộc phạm vi kênh/sông có thể xem xét; chỉ 3 đoạn được D cho phép chuyển tiếp. |
| C.1 — Đối chiếu bằng chứng mặt nước | PASS | 17 đối tượng CONFIRMED_PERSISTENT, 6 SEASONAL_DYNAMIC, 16 CONFLICT_REVIEW_REQUIRED, 42 INSUFFICIENT_EVIDENCE; chỉ giữ lại 2 đoạn được xử lý tự động, có 58 đối tượng cần xem xét. |
| E — Tạo DEM đáy thủy lực | PASS trong phạm vi 2 đoạn | Đã xuất DEM riêng; 72 ô thay đổi, hạ tối đa 0,3742065 m, thể tích hạ 8.008,2092 m³. |
| F — QA/QC khoa học và độ phủ | PASS về tính đầy đủ báo cáo | Công khai độ phủ rất thấp, nguồn hình học suy luận và các phần bỏ sót; hydraulic_promotion_ready=false. |
| G — Kiểm chứng thủy lực | Preparation PASS; Gate G PENDING | Có DEM LOW/HIGH, CENTRAL dạng ASC, cấu hình BASE/CENTRAL/LOW/HIGH, manifest, validator và báo cáo triển khai; chưa có NetCDF CENTRAL/LOW/HIGH. Chạy lại validator lúc cập nhật xác nhận PREPARED_PENDING_MATCHED_BG_FLOOD_RUNS. |

## Những gì đã kiểm chứng lại

- Chạy lại cả 7 validator A/B/C/D/C.1/E/F: tất cả PASS. Chặn thao tác ghi báo cáo của validator trong lần kiểm tra để giữ nguyên kết quả đã có.
- Chạy bộ kiểm thử A–F: **44/44 tests PASS**.
- Chạy thêm bộ kiểm thử chuẩn bị G mới xuất hiện trong phiên làm việc: **2/2 tests PASS**. Tổng hai bộ: **46 tests PASS**.
- So sánh SHA-256 trước/sau kiểm tra của 32 file mã nguồn/dữ liệu lõi: không file nào thay đổi trong khoảng chạy các validator.
- Đọc trực tiếp raster gốc và raster E, tính lại chênh cao, số ô thay đổi, diện tích sửa và thể tích hạ: khớp báo cáo E/F.
- Không sửa ngoài mask cho phép, không nâng ô địa hình, mask NoData giữ nguyên; validator E xác nhận 0 ô thuộc vùng bảo vệ Đồng Cam bị sửa.
- Đọc trực tiếp bảng C/E và tính lại độ phủ theo các object_id đã chuẩn hóa khoảng trắng: khớp báo cáo F.
- DEM nguồn vẫn có SHA-256 `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`.
- Lần cập nhật 07:14 chạy riêng `validate_v49_g()` mới theo chế độ không ghi đè báo cáo: 14/14 preparation checks đạt, BASE có frame SAR hợp lệ (lệch khoảng 1.388,83 giây, dưới giới hạn 5.400 giây); NetCDF CENTRAL/LOW/HIGH đều MISSING. `gate_g_pass=false`, `hydraulic_promotion_ready=false`. Bộ 46 tests ở trên thuộc lần kiểm tra 00:36; lần cập nhật này không chạy lại bộ tests đó.

Các kiểm tra trên xác nhận trạng thái triển khai và tính nhất quán của sản phẩm. Chúng chưa chứng minh độ sâu suy luận đúng ngoài thực địa hoặc chất lượng mô phỏng lũ đã cải thiện.

## Giới hạn quan trọng

1. **Phạm vi đáy thủy lực rất nhỏ.** E chỉ xử lý `HR_41349822` và `HR_41352752`. Hai đoạn này liên quan 3/80 thủy vực nội địa (3,75% số đối tượng), diện tích toàn bộ các đối tượng liên quan là 0,1638 km², tương đương **0,143864%** diện tích nước nội địa trong danh mục. Diện tích raster thực sự bị sửa chỉ **0,0648 km²**. Liên kết với một thủy vực không đồng nghĩa đã tái tạo đáy cho toàn bộ thủy vực đó.

2. **Năm thủy vực lớn, đã xác nhận tồn tại lâu dài, chưa có biểu diễn thủy lực được chấp nhận:** `W20_0059` (LAKE_RESERVOIR, 42,7806 km²), `W20_0026`, `W20_0068`, `W20_0066`, `W20_0041`. Một số đối tượng sông còn thiếu hỗ trợ từ graph: `W20_0011`, `W20_0062` theo báo cáo F.

3. **Nguồn hình học chủ yếu là suy luận.** Trong 95 đoạn thuộc phạm vi C-eligible: 0% khảo sát đáy/mặt cắt, 7/95 (7,3684%) hydraulic inversion, 86/95 (90,5263%) empirical fallback, 2/95 (2,1053%) chưa giải quyết. Hai đoạn được E chấp nhận vẫn có uncertainty HIGH/VERY_HIGH.

4. **Kiểm chứng mô hình chưa hoàn tất.** Manifest G ghi `PREPARED_PENDING_MATCHED_BG_FLOOD_RUNS`, `gate_g_pass=false`, `hydraulic_promotion_ready=false`. Kết quả BASE có sẵn chỉ tới khoảng 105 giờ, chưa đủ 120 giờ của kịch bản chính thức. File SAR so với BASE đã có CSI khoảng 0,3855 và F1 khoảng 0,5565; đây là số liệu BASE, không phải bằng chứng V49 cải thiện.

5. **Dữ liệu kiểm chứng còn thiếu.** Manifest G ghi chưa có chuỗi mực nước/thời gian có datum và lineage được xác minh, bộ dấu vết lũ khảo sát, hoặc tập điểm ngập/không ngập đã chốt. Sentinel-1 hiện được mô tả là so sánh xác nhận hồi cứu; ảnh sự kiện đã từng được xem trong V39–V45, nên chưa thể coi là bộ kiểm chứng ngoài hoàn toàn độc lập.

6. **Một sản phẩm kiến trúc còn cần đối chiếu bổ sung.** Kế hoạch nêu hai sản phẩm riêng DEM_HYDRO_CONDITIONED và DEM_HYDRAULIC_BED; tại mốc kiểm tra chưa thấy module dự kiến `v49_build_hydro_conditioned_dem.py` hoặc sản phẩm V49 hydro-conditioned riêng được báo cáo nghiệm thu. Điều này không làm các gate A–F hiện tại tự động FAIL, nhưng mục tiêu kiến trúc toàn bộ chưa được xác nhận hoàn tất.

7. **Đối chứng legacy có giới hạn.** Manifest G giữ mô hình năm nhánh cũ ở diện chẩn đoán, không coi là arm so sánh trực tiếp: 10.740 ô hợp lệ có cao độ <= -4 m sẽ bị loại nếu áp canonical minmask=-4 m. BASE/CENTRAL/LOW/HIGH được chuẩn bị để dùng cùng miền và cấu hình; cần ghi rõ giới hạn này khi diễn giải kế hoạch năm kịch bản.

## Công việc còn lại để hoàn tất V49

- Giải quyết hàng đợi 58 đối tượng, các thiếu hụt graph và 5 thủy vực lớn chưa được biểu diễn; bổ sung mặt cắt/bathymetry hoặc mô hình lưu trữ phù hợp cho hồ, cửa sông và vùng triều.
- Chạy và kiểm chứng các mô phỏng đối chứng BASE/CENTRAL/LOW/HIGH cùng forcing, cấu hình và miền tính; giữ legacy ở diện chẩn đoán theo manifest. Hoàn tất thời lượng BASE theo protocol.
- Đánh giá độ nhạy phạm vi ngập, mực nước, vận tốc, thời gian và cân bằng khối lượng; công khai chỉ số không thể tính do thiếu quan trắc.
- Chỉ nghiệm thu G và nâng trạng thái sử dụng chính thức sau khi đáp ứng điều kiện khoa học của kế hoạch, bao gồm các giới hạn độ phủ.

## Bằng chứng tham chiếu

- [Kế hoạch V49](D:/VTP/River_Bathymetry_Project/V49_IMPLEMENTATION_PLAN_20261012.md)
- [Báo cáo C.1](D:/VTP/River_Bathymetry_Project/V49_C1_IMPLEMENTATION_REPORT_20261012.md)
- [Báo cáo E](D:/VTP/River_Bathymetry_Project/V49_E_IMPLEMENTATION_REPORT_20261012.md)
- [Báo cáo F](D:/VTP/River_Bathymetry_Project/V49_F_IMPLEMENTATION_REPORT_20261013.md)
- [Kết quả validation E](D:/VTP/River_Bathymetry_Project/V49_E_20261012/V49_E_validation_report.json)
- [Kết quả validation F](D:/VTP/River_Bathymetry_Project/V49_F_20261013/V49_F_validation_report.json)
- [Manifest chuẩn bị G](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_PREPARATION_MANIFEST.json)
- [Báo cáo triển khai G](D:/VTP/River_Bathymetry_Project/V49_G_IMPLEMENTATION_REPORT_20261013.md)
- [Kết quả validation G](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_validation_report.json)
- [Chỉ số SAR của BASE](D:/VTP/River_Bathymetry_Project/V49_G_20261013/SAR_vs_V48_BASE_frame_33_metrics.json)

Báo cáo ghi rõ hai mốc kiểm tra ở đầu tài liệu. Chat “Bắt đầu V49-F QA/QC” còn hoạt động trong lần đối chiếu 00:36; bộ chuẩn bị G được tạo trong chính khoảng kiểm tra đó. Lần cập nhật 07:14 xác nhận validator và báo cáo G đã được bổ sung. Không thay đổi DEM, cấu hình chạy hoặc mã nguồn triển khai trong công việc kiểm tra này.
