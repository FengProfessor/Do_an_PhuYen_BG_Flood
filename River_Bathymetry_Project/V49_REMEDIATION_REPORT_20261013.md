# V49 — Báo cáo xử lý tồn đọng, 13/10/2026

**Kết quả hiện tại R3:** **15/15** kiểm tra triển khai/tính toàn vẹn PASS và **102/102** test PASS. UNKNOWN giảm 32→29; đã nhập 12 tháng ảnh nước năm 2021 và footprint khảo sát Phú Sen 2024 có hệ chiếu ngang được kiểm chứng. CENTRAL chạy nền, tự xếp tiếp LOW → HIGH → BASE 120 giờ. **Gate G=PENDING và `hydraulic_promotion_ready=false`.**

**Báo cáo hiện hành:** [V49_R3_UNPASSED_REMEDIATION_20261013.md](D:/VTP/River_Bathymetry_Project/V49_R3_UNPASSED_REMEDIATION_20261013.md). Phần R2 bên dưới là snapshot lịch sử đã được R3 bổ sung; các con số UNKNOWN 32 và 92 test trong snapshot không phải trạng thái mới nhất. Audit tổng hợp mặc định kiểm R3.

Không có tỷ lệ “100% đúng vật lý” suy ra từ số test hoặc số gate PASS. Trạng thái có thể kiểm tra lại bằng [v49_audit_all_phases.py](D:/VTP/River_Bathymetry_Project/v49_audit_all_phases.py) và [V49_ALL_PHASE_AUDIT_20261013.json](D:/VTP/River_Bathymetry_Project/V49_ALL_PHASE_AUDIT_20261013.json).

## 1. Snapshot từng phase ở R2, trước bổ sung R3

| Phase | Kết quả triển khai | Đã xử lý | Điều kiện khoa học còn mở |
|---|---|---|---|
| A | PASS | Giữ inventory 80 inland + 1 ocean, coverage và checksum DEM | Chỉ chứng nhận inventory trong ngưỡng/phạm vi nguồn, không chứng nhận mọi lòng sông thực địa |
| B | PASS topology | 370 reaches, 396 nodes; không cycle/orphan major; giữ Đồng Cam | B lịch sử ghi 2 object; QA R2 hiện có 4 object/ứng viên kênh thiếu graph trong 90 m và 1 object lệch vị trí 30/90 m; đã trích 7 cạnh OSM ứng viên |
| C, R2 | PASS | Đối chiếu OSM/JRC/coastal; 18 object đổi class, UNKNOWN 42→32 | 32 UNKNOWN; dữ liệu OSM 2026 không thay thế quan trắc 2021 |
| D, R2 | PASS có giới hạn | Kiểm tra đáy dốc ngược trước authorization; giữ 370 reaches và 168 confluences | Geometry đo đạc vẫn 0%; tidal/backwater và width gián tiếp còn hold |
| C.1, R2 | PASS | Sửa standing-water persistence; queue 58→43; đọc lại checksum 4 JRC + PBF và MD5 | 39 insufficient + 4 conflict; 10 seasonal được giữ là seasonal |
| E, R2 | PASS có giới hạn | D ∩ C.1 chỉ cho phép 2 reaches; terrain R2 có cùng SHA-256 với E gốc | 72 ô chỉnh sửa, 3 object có footprint; chưa có bathymetry cho mọi hồ/sông |
| F, R2 | PASS QA báo cáo | Báo cáo đúng coverage, storage, geometry provenance; bổ sung confluence lấy từ raster thật | 9 major persistent omissions; chưa đạt độ phủ hình học/quan trắc toàn miền |
| HydroDEM riêng | PASS topology/readback | D8 và accumulation cho 4.410.000 ô; 0 cycle, 0 unresolved nội bộ | Chỉ dùng drainage analysis; không dùng như hydraulic bed hay coi toàn mạng đã khớp |
| G preparation | PASS | 44 tham chiếu input thật được kiểm checksum; configs/terrain giữ đóng băng | PASS chuẩn bị không cấp quyền promotion |
| G execution/acceptance | RUNNING/PENDING | Supervisor một GPU; ngân sách nước thật; hậu xử lý SAR/velocity/coarse HWM | Hoàn thành 4 run đủ cửa sổ, giải quyết bằng chứng quan trắc và quyết định chấp nhận khoa học |

R2 là bộ xử lý bằng chứng mới trong `D:/VTP/River_Bathymetry_Project/V49_R2_20261013`; không ghi đè các sản phẩm C/D/C.1/E/F lịch sử. Các cấu hình G đã đóng băng vẫn trỏ E gốc. Điều này hợp lệ vì E R2 cuối cùng có **cùng byte/hash** với E gốc.

## 2. Lỗi đã sửa và kiểm chứng

- **Validator G từng có thể tin chuỗi hash/cờ ghi sẵn:** nay đọc lại solver, forcing, terrain, Sentinel và contract; từ chối thiếu SHA-256 hoặc group chỉ còn metadata. Regression cố ý sửa/xóa pin không thể PASS.
- **NetCDF/time/grid:** từ chối NaN, masked time, thời gian không tăng và lệch vị trí lưới dù số hàng/cột giống nhau; chọn frame gần thời điểm SAR trong giới hạn 5.400 s, hòa thì chọn sớm hơn. Không đọc NetCDF đang được worker ghi.
- **C.1 nhầm loại hồ với tính thường xuyên:** một tag hồ không tự chứng minh nước thường xuyên. Kết hợp JRC theo niên đại, giữ seasonal/insufficient; queue rỗng đã giải quyết không còn bị validator bắt phải có lỗi tồn đọng.
- **D cho phép profile dốc ngược:** một ứng viên thực tế `HR_41343261` tăng đáy khoảng 2,089 m bị E chặn; nay D chặn từ trước khi cấp quyền. Không ép toàn bộ mạng bằng bộ lọc đơn điệu.
- **Object ven biển:** W20_0002 chuyển sang coastal-channel review; tidal influence chưa được coi là đã xác minh. Tránh cấp thêm một reach và 350 ô khắc không đủ bằng chứng. Bản ứng viên trước sửa được giữ trong `superseded_coastal_candidate`.
- **HydroDEM bị flat/unresolved:** dùng priority-flood cục bộ với độ tăng tối thiểu 1e-9 m và float64; đọc lại raster, tái tính graph/accumulation và kiểm vòng. Không thay dependency đã đóng băng.
- **Trích nguồn công bố:** khóa SHA-256 PDF đã đối chiếu; phát hiện đổi PDF/CSV hoặc sai số dòng, từ chối một dung tích đơn lẻ làm ZFW, cấm ngoại suy ngoài bảng.
- **Graph support bị trộn ngưỡng 30/90 m:** dùng cùng bảng chẩn đoán cho F và dossier, phân biệt thiếu graph với lệch centerline. W20_0032 đã có reach trong 90 m; không cấp thêm nhánh trùng. Validator kiểm bảng, checksum nguồn và từ chối biến review thành quyền sửa graph/terrain.

## 3. Coverage và kiểm soát terrain

| Đại lượng | R2 cuối cùng |
|---|---:|
| Class | RIVER 27; ESTUARY/coastal review 4; LAKE/RESERVOIR 17; OCEAN 1; UNKNOWN 32 |
| C.1 | CONFIRMED 28; SEASONAL 10; CONFLICT 4; INSUFFICIENT 39 |
| Reaches E được phép | HR_41349822 và HR_41352752 |
| Mask / ô thực sự chỉnh | 73 / 72 |
| Tổng hạ terrain | 8.008,2092 m³ |
| Hạ tối đa | 0,3742065 m |
| Ô chỉnh ngoài mask / ô Đồng Cam bị chỉnh | 0 / 0 trên 187 ô bảo vệ |
| Object có ô thực sự chỉnh | 3/80 = 3,75% |
| Diện tích object liên kết với reach được nhận | 0,1638 km² = 0,143864% inland-water area |
| Diện tích raster thực sự chỉnh | 0,0648 km² |
| Geometry khảo sát được nhận | 0% |

Major omissions trong R2: W20_0059, W20_0028, W20_0012, W20_0014, W20_0078, W20_0026, W20_0068, W20_0066, W20_0041. Con số tăng 5→9 do đối chiếu/classification xác định thêm vùng nước thường xuyên; không được che bằng cách đổi ngưỡng QA.

[Hồ sơ từng object](D:/VTP/River_Bathymetry_Project/V49_R2_20261013/REMAINING_EVIDENCE/V49_object_evidence_and_pixel_coverage.csv) nêu đúng loại bằng chứng còn thiếu, ZFW hoặc dung tích đã tìm được, hold reason và coverage theo ô. [GeoPackage](D:/VTP/River_Bathymetry_Project/V49_R2_20261013/REMAINING_EVIDENCE/V49_remaining_evidence.gpkg) lưu object và 7 cạnh OSM ứng viên. [343 cặp endpoint confluence lấy từ raster](D:/VTP/River_Bathymetry_Project/V49_R2_20261013/REMAINING_EVIDENCE/V49_actual_raster_confluence_samples.csv) bổ sung QA thực tế; chúng không tự chứng minh profile đáy vật lý hoặc thay đổi graph được chấp nhận.

[QA graph 30/90 m](D:/VTP/River_Bathymetry_Project/V49_R2_20261013/REMAINING_EVIDENCE/V49_graph_support_30m_90m.csv) ghi 4 object/ứng viên cần kết nối được xác minh: W20_0004, W20_0008, W20_0011, W20_0062. W20_0032 là alignment review. Không tự nhận 7 cạnh ứng viên vào 370 reaches hiện tại.

Source DEM vẫn SHA-256 `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`.
E gốc và E R2 đều SHA-256 `181115942dc88a95503a1e193b2f90149e918b6f8354a262085b293e11df2552`.

## 4. Kết quả nghiên cứu đã nhập vào workflow

[Hồ sơ nguồn và xung đột](D:/VTP/River_Bathymetry_Project/V49_EXTERNAL_EVIDENCE_RESEARCH_20261013.md) liên kết nguồn Chính phủ, Công báo, UBND, Viện Quy hoạch Thủy lợi và tài liệu nghiên cứu. Registry kiểm 8 PDF + 6 CSV thật; dữ liệu mới đã được nối vào dossier object và chẩn đoán G.

- Bảng ZFW Sông Ba Hạ/Sông Hinh: 30 dòng, tham chiếu thiết kế có giới hạn thời gian/footprint/datum.
- 6 hồ có thêm dung tích công bố và thông số đập: Phú Xuân, Đồng Tròn (Tuy An), Suối Vực, Đồng Khôn, Buôn Đức, Hóc Răm. Chưa tạo ZFW từ một giá trị dung tích.
- 8 vị trí tương đối từ danh mục bản đồ VN-2000 của Bộ đã được đối chiếu ảnh trang gốc và chuyển tọa độ bằng phép EPSG được định nghĩa. Bốn vị trí hồ nhỏ nằm trong polygon ứng viên; đây không phải tọa độ trạm đo. QA xác nhận polygon Sông Ba Hạ chạm biên miền tính, nên chưa áp dung tích toàn hồ lên object hiện tại.
- 3 đỉnh lũ báo cáo được chuẩn hóa múi giờ và giữ trạng thái tọa độ/hệ cao độ chưa xác minh.
- Tập dấu vết lũ công bố được dùng qua phương pháp vùng vị trí làm tròn đã đăng ký trước khi G hoàn tất; không cấp số RMSE điểm hoặc kết luận WSE tuyệt đối.
- Xung đột Phú Lâm, Sông Ba Hạ, Hoa Sơn và độ thô bảng Sông Hinh được giữ rõ trong registry, không chọn số nhằm làm đẹp kết quả.

## 5. G đã thực thi, chưa hoàn tất

Supervisor chạy ẩn trên Windows, lần lượt **CENTRAL → LOW → HIGH → BASE** với một CUDA job tại một thời điểm. BASE mới cũng chạy 120 giờ vì kết quả lịch sử chỉ có 105 giờ. Không thay runtime, forcing, minmask, miền lưới hoặc tham số vật lý của hợp đồng đóng băng.

Kiểm tra gần cuối phiên: CENTRAL worker và supervisor đều còn sống, tiến trình vẫn tăng; trạng thái cập nhật theo log trong [V49_G_EXECUTION_STATE.json](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_EXECUTION_STATE.json). Một arm có thể cần nhiều ngày; không suy ra thời gian hoàn tất chỉ từ tốc độ đầu run.

Snapshot 13/10/2026 lúc 14:06 UTC+7: CENTRAL khoảng 9,17% cửa sổ 432.000 s, worker/supervisor còn sống. GPU sau đó ở khoảng 93–94°C, driver báo `SW Thermal Slowdown: Active`; giới hạn vận hành driver công bố là 98°C. Thử hạ power cap 140→110 W bị driver từ chối `Insufficient Permissions`, nên không có thay đổi phần cứng hoặc dừng mô phỏng. Cần kiểm tra tản nhiệt/thông gió và quyền quản trị máy để xử lý giới hạn công suất. [Snapshot vận hành](D:/VTP/River_Bathymetry_Project/V49_G_20261013/V49_G_HARDWARE_HEALTH_20261013.json).

Observer đo các thành phần cập nhật số, boundary reset, flux divergence, mưa, river injection, infiltration và clamping. Snapshot đầu run lúc khoảng 4.443,7 s mô phỏng có closure residual khoảng 4,85e-10 m³ sau tính clamping; số âm trước clamp vẫn được ghi. Đây là budget của solver, không phải kiểm định bằng quan trắc. Tác động observer lên kết quả đã kiểm tra bằng run CPU thực 32×32: h/zs/u/v/time trùng byte, lượng mưa và closure được kiểm độc lập. Hiệu năng GPU có thể chịu overhead quan sát.

Sau mỗi arm hoàn tất, supervisor gọi evaluator. Evaluator kiểm frame/grid/terrain, đối chiếu cùng mask SAR, báo CSI/F1/precision/recall/area bias, velocity, budget và chẩn đoán vùng dấu vết lũ khi đủ registry. BASE lịch sử tái lập đúng CSI 0,385500 và F1 0,556478; không coi đó là mức đạt chuẩn.

Legacy five-branch tiếp tục chỉ diagnostic vì 10.740 ô <= -4 m sẽ đổi miền tính dưới canonical minmask. Nếu tiến trình bị tắt/reboot hoặc run lỗi, workflow ghi lỗi và giữ file để rà soát; chưa có cơ chế resume từ checkpoint. Không chạy chồng hoặc ghi đè partial result.

## 6. Kiểm chứng và cách kiểm tra lại

[Log hồi quy](D:/VTP/River_Bathymetry_Project/V49_REGRESSION_TESTS_20261013.log): **92 passed**, gồm numerical observer run, dữ liệu nguồn bị sửa, time/grid bị lỗi, seasonal-water authorization, profile dốc ngược, drainage cycles/flats, giới hạn nội suy nguồn công bố và graph thiếu support/lệch centerline.

Audit tổng hợp đã chạy lại validator A/B, R2 C/D/C.1/E/F, G preparation; đọc lại bốn raster HydroDEM rồi tái tính graph. **Tất cả kiểm tra triển khai và tính toàn vẹn PASS**. Trạng thái khoa học vẫn false trong JSON.

```powershell
Set-Location -LiteralPath 'D:\VTP\River_Bathymetry_Project'
& 'C:\Users\CuongHM\anaconda3\python.exe' -X utf8 -B v49_audit_all_phases.py
& 'C:\Users\CuongHM\anaconda3\python.exe' -X utf8 -B v49_run_hydraulic_validation.py status
```

Project hiện không phải Git repository. Các sản phẩm gốc, bộ R2 và source snapshot được giữ riêng; đây chưa phải lịch sử version control bằng Git.

## 7. Điều kiện để đóng toàn bộ các phase

1. Hoàn thành run matched đủ cửa sổ, kiểm metric SAR/velocity/budget và đánh giá kết quả sensitivity thực tế.
2. Giải quyết 32 object UNKNOWN, 43 mục persistence review, 4 object/ứng viên thiếu graph trong 90 m, 1 alignment review và geometry của 9 major omissions bằng bằng chứng phù hợp; chưa có bathymetry khảo sát được nhận.
3. Đối chiếu toàn footprint hồ, hệ cao độ, bồi lắng/niên đại và điều kiện vận hành trước khi dùng ZFW để ràng buộc lưu trữ hoặc terrain; không suy một mặt đáy duy nhất từ tổng dung tích.
4. Xác minh tọa độ trạm/dấu vết và phép chuyển hệ cao độ; giải quyết mốc Phú Lâm 119 h/121 h và cửa sổ quan trắc dài hơn 120 h; có biên triều/WSE và hình học thích hợp cho vùng tidal/backwater.
5. Ghi quyết định khoa học chấp nhận hoặc yêu cầu sửa dựa trên các kết quả trên. Không tự chuyển `hydraulic_promotion_ready` sang true vì output xuất hiện hoặc test PASS.

Những điều kiện này là phần còn tồn đọng thực tế. Chưa có bằng chứng cho tuyên bố “đã giải quyết hết” hoặc “chuẩn 100%”.
