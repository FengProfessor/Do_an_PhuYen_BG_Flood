# Báo cáo Bản đồ Độ sâu Mô phỏng Thủy lực V49-G (CENTRAL) - Mốc 60.0h (50% Chặng đường)

Mô hình thủy lực 2D **V49-G (CENTRAL)** trên card **NVIDIA RTX A4000** đã chính thức vượt qua mốc một nửa chặng đường (**$t = 60.0\text{h} / 120.0\text{h}$**, đạt **50.0%**), xuất thành công **20 khung dữ liệu không gian 3D NetCDF** (dung lượng gần 1 GB).

Dưới đây là bản đồ độ sâu ngập lũ và các phân tích thủy lực trực quan kết xuất từ tệp gốc [V49_G_CENTRAL.nc](file:///D:/VTP/River_Bathymetry_Project/V49_G_attempt_2/results/V49_G_CENTRAL.nc).

---

## 1. Bộ sưu tập hình ảnh trực quan (Image Carousel)

````carousel
![Bản đồ độ sâu ngập lũ tại mốc 60h](C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/flood_depth_map_t60h.png)
<!-- slide -->
![Chuỗi so sánh tiến trình sóng lũ 4 giai đoạn](C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/flood_evolution_progression.png)
<!-- slide -->
![Đồ thị diện tích ngập lũ theo thời gian (0h - 60h)](C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/inundation_area_time_series.png)
<!-- slide -->
![Bản đồ trường vận tốc dòng lũ](C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/flow_velocity_map_latest.png)
````

---

## 2. Thống kê thủy lực chi tiết tại mốc t = 60.0h (Frame 20)

| Chỉ số ngập lụt | Diện tích ghi nhận | Ý nghĩa thủy văn |
| :--- | :---: | :--- |
| **Tổng diện tích có nước ($h \ge 0.1\text{m}$)** | **`1,475.37 km²`** | Toàn bộ ranh giới vùng trũng và mạng lưới sông suối |
| **Diện tích ngập đáng kể ($h \ge 0.3\text{m}$)** | **`1,313.26 km²`** | **Tiêu chuẩn nhận diện mặt nước viễn thám Sentinel-1 SAR** |
| **Diện tích ngập sâu ($h \ge 1.0\text{m}$)** | **`1,073.06 km²`** | Vùng ngập nguy hiểm đe dọa khu dân cư và đồng ruộng |
| **Độ sâu ngập cực đại ($h_{\max}$)** | **`32.11 m`** | Tập trung tại hẻm vực thượng lưu chân đập sông Ba Hạ, sông Hinh |

---

## 3. Đặc điểm phân bố ngập lụt trên bản đồ

1. **Vùng hạ lưu sông Ba (Đồng bằng Tuy Hòa)**:
   - Sóng lũ đã tràn qua các bờ đê thấp, tạo thành một dải ngập mênh mông kéo dài từ sau đập Đồng Cam qua huyện Phú Hòa, thành phố Tuy Hòa và đổ ra cửa biển Đà Diễn.
   - Độ sâu ngập phổ biến trên các cánh đồng bãi bồi đạt từ **$1.0\text{m} - 2.5\text{m}$**.
2. **Khu vực hạ lưu sông Kỳ Lộ (Tuy An)**:
   - Toàn bộ vùng trũng thấp ven sông Kỳ Lộ và đầm Ô Loan ghi nhận diện ngập mở rộng, độ sâu nước từ **$0.5\text{m} - 2.0\text{m}$**.
3. **Khu vực hạ lưu sông Bàn Thạch (Đông Hòa)**:
   - Nước lũ từ thượng nguồn dâng cao và thoát qua cửa Đà Nông, tạo vùng ngập liên kết với châu thổ Tuy Hòa.

---

> [!NOTE]
> Mọi tệp ảnh gốc chất lượng cao và báo cáo đã được lưu trữ an toàn tại thư mục trên ổ D:
> 👉 [`D:\VTP\River_Bathymetry_Project\V49_G_attempt_2\visual_reports`](file:///D:/VTP/River_Bathymetry_Project/V49_G_attempt_2/visual_reports)
