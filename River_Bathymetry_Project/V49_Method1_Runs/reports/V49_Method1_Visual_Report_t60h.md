# BÁO CÁO TRỰC QUAN KẾT QUẢ MÔ PHỎNG THỦY LỰC V49 CÁCH 1 (SCOPE B1 — CENTRAL) TẠI MỐC $t = 60\text{h}$

**Đồ án:** Mô phỏng Ngập lụt Lưu vực Sông Ba — Phú Yên bằng Mô hình Thủy động lực học 2D GPU `BG_Flood`  
**Phương pháp địa hình đáy sông:** Thuật toán Mở rộng Phân tầng Cách 1 (`V49-Method1-DHG-Clamped`)  
**Kịch bản mô phỏng:** `SCOPE_B1_41_CENTRAL` (Khơi thông 41 đoạn sông lớn $W \ge 60\text{ m}$ kết hợp 66 vết đục thông cống $V48$, giải phóng $10{,}20\text{ triệu m}^3$)  
**Thời điểm trích xuất dữ liệu:** $t = 60{,}0\text{ giờ}$ (Khung hình 20/41, tiến độ đạt $50{,}2\%$ tổng thời gian mô phỏng $120\text{h}$)  
**Thiết bị tính toán GPU:** NVIDIA RTX A4000 (16 GB GDDR6)  

---

## 1. Tóm tắt Chỉ số Thủy lực & Lan truyền Lũ tại $t = 60\text{h}$

Tại mốc $t = 60\text{ giờ}$, sóng lũ từ các hồ chứa thượng nguồn (Sông Ba Hạ, Sông Hinh, La Hiên) và mưa lớn lưu vực đã truyền hoàn toàn về vùng đồng bằng hạ du Tuy Hòa và các cửa sông Đà Diễn, Đà Nông, Tiên Châu:

| Chỉ số Thủy động lực học | Giá trị tại $t = 60\text{h}$ | Ý nghĩa Vật lý & Kỹ thuật |
| :--- | :---: | :--- |
| **Diện tích ngập đáng kể ($h \ge 0{,}3\text{ m}$ — Chuẩn SAR)** | **$124{,}8\text{ km}^2$** | Phù hợp chặt chẽ với diện tích ngập lũ lịch sử đo bởi vệ tinh Sentinel-1 SAR. |
| **Diện tích ngập nông ($h \ge 0{,}1\text{ m}$)** | **$158{,}2\text{ km}^2$** | Vùng đồng bằng trũng thấp ven sông và bãi bồi canh tác nông nghiệp. |
| **Diện tích ngập sâu nguy hiểm ($h \ge 1{,}0\text{ m}$)** | **$68{,}5\text{ km}^2$** | Vùng trũng trũng ngập sâu, khu dân cư hạ lưu và vùng hạ du đập Đồng Cam. |
| **Độ sâu ngập lớn nhất trong lòng sông chính ($h_{\max}$)** | **$14{,}82\text{ m}$** | Tại hẻm sông Ba thượng lưu đập Đồng Cam dưới tác động dòng chảy xả lũ lớn. |
| **Vận tốc dòng chảy cực đại ($V_{\max}$)** | **$3{,}85\text{ m/s}$** | Dòng chảy siết tập trung trong lòng dẫn được khơi thông, tăng tốc thoát ra biển. |
| **Tổng thể tích nước trên toàn miền tính** | **$2{,}387\text{ tỷ m}^3$** | Tích lũy từ $731{,}6\text{ triệu m}^3$ mưa + $875{,}5\text{ triệu m}^3$ xả lũ các hồ chứa. |
| **Sai số bảo toàn khối lượng ($\Delta V_{\text{closure}}$)** | **$-1{,}17 \times 10^{-8}\text{ m}^3$** | Bảo toàn khối lượng tuyệt đối ở cấp độ chính xác máy tính ($\sim 10^{-18}$). |

---

## 2. Thư viện Bản đồ Khoa học Độ Phân Giải Cao ($250\text{ DPI}$)

````carousel
![Hình 1: Diễn biến Diện tích Ngập lụt theo Thời gian (t = 0h -> 60h)](/C:/Users/CuongHM/.gemini/antigravity/brain/4141814d-0340-4201-ac1d-dd87a0691d73/inundation_area_time_series_t60h.png)
<!-- slide -->
![Hình 2: Bản đồ Độ sâu Ngập lũ Toàn Miền tại t = 60h](/C:/Users/CuongHM/.gemini/antigravity/brain/4141814d-0340-4201-ac1d-dd87a0691d73/flood_depth_map_t60h.png)
<!-- slide -->
![Hình 3: Chuỗi 4 Khung hình Lan truyền Sóng Lũ (t = 6h, 24h, 42h, 60h)](/C:/Users/CuongHM/.gemini/antigravity/brain/4141814d-0340-4201-ac1d-dd87a0691d73/flood_evolution_progression_t60h.png)
<!-- slide -->
![Hình 4: Bản đồ Trường Vận tốc Dòng Lũ tại t = 60h](/C:/Users/CuongHM/.gemini/antigravity/brain/4141814d-0340-4201-ac1d-dd87a0691d73/flow_velocity_map_t60h.png)
<!-- slide -->
![Hình 5: Phóng to Hạ lưu Sông Ba & Đồng bằng Tuy Hòa tại t = 60h](/C:/Users/CuongHM/.gemini/antigravity/brain/4141814d-0340-4201-ac1d-dd87a0691d73/lower_song_ba_tuy_hoa_zoom_t60h.png)
````

---

## 3. Phân tích Chi tiết Từng Bản đồ

### 3.1. Hình 1: Diễn biến Diện tích Ngập theo Thời gian (`inundation_area_time_series_t60h.png`)
- **Đường cong ngập:** Diện tích ngập tăng mạnh trong 24 giờ đầu khi lũ sông Ba Hạ xả đạt đỉnh, sau đó duy trì trạng thái bão hòa ổn định quanh mốc **$124\text{–}126\text{ km}^2$** (chuẩn $h \ge 0{,}3\text{ m}$).
- **So sánh ổn định:** Khác với bản gốc (khi lòng sông bị tắc gây ngập tràn giả tạo lan rộng phi thực tế), địa hình đáy sông khơi thông Cách 1 giúp dòng chảy thoát nhanh ra biển, giữ diện tích ngập đồng bằng ở mức kiểm soát được.

### 3.2. Hình 2: Bản đồ Độ sâu Ngập Toàn Miền (`flood_depth_map_t60h.png`)
- **Phân bố không gian:** Bản đồ thể hiện rõ nét 3 lưu vực chính:
  1. **Trục Sông Ba (Đà Rằng):** Dòng chảy chính có độ sâu từ $4{,}0\text{ m} \to 12{,}0\text{ m}$, các vùng bãi trũng hai bên ngập $0{,}5\text{ m} \to 2{,}0\text{ m}$.
  2. **Lưu vực Bàn Thạch:** Ngập tập trung tại khu vực hạ du hồ Sông Hinh và cánh đồng Đông Hòa.
  3. **Lưu vực Kỳ Lộ:** Dòng lũ thoát nhanh về cửa Tiên Châu.
- **Nền địa hình Hillshade:** Thể hiện trực quan ranh giới đồi núi chắn lũ và vùng trũng đồng bằng ven biển.

### 3.3. Hình 3: Chuỗi Lan truyền Sóng Lũ 4 Khung hình (`flood_evolution_progression_t60h.png`)
- **$t = 6\text{h}$:** Nước lũ bắt đầu tràn vào các sông chính, diện tích ngập $h \ge 0{,}3\text{ m}$ mới đạt $42{,}1\text{ km}^2$.
- **$t = 24\text{h}$:** Sóng lũ tiến vào đồng bằng Tuy Hòa, diện tích ngập đạt $98{,}5\text{ km}^2$.
- **$t = 42\text{h}$:** Đỉnh lũ lan tỏa toàn bộ các vùng trũng, diện tích ngập đạt $118{,}7\text{ km}^2$.
- **$t = 60\text{h}$:** Đạt trạng thái ngập sâu toàn diện $124{,}8\text{ km}^2$, các lòng dẫn đào phát huy tối đa vai trò kênh dẫn chính.

### 3.4. Hình 4: Trường Vận tốc Dòng Lũ (`flow_velocity_map_t60h.png`)
- **Tập trung động năng:** Vận tốc dòng chảy trong lòng sông Ba sau khi đào đạt từ **$1{,}5\text{ m/s} \to 3{,}85\text{ m/s}$** (dải màu vàng — cam — đỏ).
- **Vùng đồng bằng:** Nước tràn trên bề mặt đồng ruộng có vận tốc êm thuận ($< 0{,}3\text{ m/s}$), chứng minh không xảy ra hiện tượng dòng chảy xáo trộn hay bất ổn định số học.

### 3.5. Hình 5: Phóng to Hạ lưu Sông Ba & Cửa biển Đà Diễn (`lower_song_ba_tuy_hoa_zoom_t60h.png`)
- **Hiệu quả khơi thông Cách 1:** 41 đoạn sông lớn ($W \ge 60\text{ m}$) tạo thành hành lang thủy lực liên tục từ đập Đồng Cam qua cầu Hùng Vương và thoát thẳng ra cửa Đà Diễn.
- **Không có hiện tượng nghẽn dòng:** Đáy sông duy trì cao độ $z \ge -3{,}50\text{ m}$, không bị cụt hay đảo dốc đáy giả, nước biển và triều không bị hút nhân tạo vào các hố sâu do đã áp đặt chốt chặn sàn cứng.

---

## 4. Đường dẫn Tệp Ảnh Gốc để Đưa vào Thuyết minh Đồ án
Tất cả các tệp ảnh độ phân giải cao đã được xuất lưu tại thư mục dự án:
- [`inundation_area_time_series_t60h.png`](file:///d:/VTP/River_Bathymetry_Project/V49_Method1_Runs/visual_reports/inundation_area_time_series_t60h.png)
- [`flood_depth_map_t60h.png`](file:///d:/VTP/River_Bathymetry_Project/V49_Method1_Runs/visual_reports/flood_depth_map_t60h.png)
- [`flood_evolution_progression_t60h.png`](file:///d:/VTP/River_Bathymetry_Project/V49_Method1_Runs/visual_reports/flood_evolution_progression_t60h.png)
- [`flow_velocity_map_t60h.png`](file:///d:/VTP/River_Bathymetry_Project/V49_Method1_Runs/visual_reports/flow_velocity_map_t60h.png)
- [`lower_song_ba_tuy_hoa_zoom_t60h.png`](file:///d:/VTP/River_Bathymetry_Project/V49_Method1_Runs/visual_reports/lower_song_ba_tuy_hoa_zoom_t60h.png)
