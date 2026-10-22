# Báo cáo Trực quan hóa Diễn biến Thủy lực V49-G (CENTRAL) tại mốc t = 57.0h

Bộ mô phỏng thủy lực 2D **V49-G (CENTRAL)** trên card **NVIDIA RTX A4000** đã tính toán liên tục suốt **57 giờ 18 phút GPU** và xuất thành công **19 khung dữ liệu không gian 3D NetCDF** ($t = 3.0\text{h} \rightarrow 57.0\text{h}$).

Dưới đây là các hình ảnh cập nhật mới nhất kết xuất từ tệp dữ liệu gốc [V49_G_CENTRAL.nc](file:///D:/VTP/River_Bathymetry_Project/V49_G_attempt_2/results/V49_G_CENTRAL.nc).

---

## 1. Bộ sưu tập hình ảnh cập nhật (Image Carousel)

````carousel
![Bản đồ độ sâu ngập lũ mới nhất t = 57h](C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/flood_depth_map_latest.png)
<!-- slide -->
![Chuỗi diễn biến lan truyền sóng lũ 4 giai đoạn](C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/flood_evolution_progression.png)
<!-- slide -->
![Đồ thị diện tích ngập lụt theo thời gian (3h - 57h)](C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/inundation_area_time_series.png)
<!-- slide -->
![Trường vận tốc dòng lũ t = 57h](C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/flow_velocity_map_latest.png)
````

---

## 2. Diễn biến thủy lực nổi bật tại mốc t = 57.0h (47.5% tiến độ)

### 2.1. Bản đồ độ sâu ngập lũ diện rộng ($t = 57.0\text{h}$)
* **Tệp ảnh**: [flood_depth_map_latest.png](file:///C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/flood_depth_map_latest.png)
* **Nhận xét**:
  - Diện tích ngập sâu ($h \ge 0.3\text{m}$) tiếp tục mở rộng vững chắc trên toàn bộ châu thổ hạ lưu sông Ba và bãi trũng Tuy An.
  - Vùng hạ lưu chân đập Đồng Cam và hợp lưu sông Hinh ghi nhận mức dâng cao độ mặt nước ổn định, không có xung đột số học hay tạo xoáy bất thường.

### 2.2. Chuỗi so sánh 4 giai đoạn lũ ($t = 6\text{h} \rightarrow 21\text{h} \rightarrow 36\text{h} \rightarrow 57\text{h}$)
* **Tệp ảnh**: [flood_evolution_progression.png](file:///C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/flood_evolution_progression.png)
* Cho thấy rõ sự dịch chuyển của sóng lũ từ vùng thắt hẹp thượng nguồn lan tỏa dần ra toàn bộ vùng đồng bằng ven biển. Mốc $57\text{h}$ thể hiện diện ngập liên tục, nối kết hoàn chỉnh giữa hệ thống sông và các vùng đầm trũng ven biển.

### 2.3. Đồ thị diện tích ngập theo thời gian (19 Frames)
* **Tệp ảnh**: [inundation_area_time_series.png](file:///C:/Users/CuongHM/.gemini/antigravity/brain/303aa3cb-1e89-49b2-8549-ccb345e3d166/inundation_area_time_series.png)
* Đường cong ngập lụt tiếp tục dâng đều đặn và bắt đầu tiến vào giai đoạn lũ bão hòa, chuẩn bị đón nhận đỉnh lũ lớn trước khi đạt mốc vệ tinh Sentinel-1 SAR ($t = 101.61\text{h}$).

---

> [!NOTE]
> GPU đang tiến rất gần mốc 50% (còn 3 giờ mô phỏng nữa sẽ chạm mốc 60.0h). Bước tích phân $dt \approx 0.34\text{s}$ được duy trì tối ưu.
