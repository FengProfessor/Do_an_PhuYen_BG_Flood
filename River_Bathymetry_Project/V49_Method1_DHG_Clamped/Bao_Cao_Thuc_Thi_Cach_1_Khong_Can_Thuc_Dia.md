# BÁO CÁO NGHIÊN CỨU & THỰC THI CÁCH 1: THUẬT TOÁN ĐÀO SÔNG ĐA NHÁNH KHÔNG CẦN SỐ ĐO THỰC ĐỊA (`V49-METHOD-1`)

**Tên chuyên đề:** Giải pháp Mở rộng Hạ thấp Cao độ Đáy Sông Đa Nhánh từ Dữ liệu Viễn thám Mở bằng Quan hệ Hình học Thủy lực Hạ lưu (*Downstream Hydraulic Geometry — DHG*) kết hợp Khóa Sàn Đáy Cứng (*Hard Bed-Elevation Clamping* $z_{\text{floor}} = -3{,}50\text{ m}$) và Bảo vệ Công trình Đập Đồng Cam  
**Mã quy trình:** `V49-Method1-DHG-Clamped-2.0-RealDEM`  
**Tệp DEM nền thực thi (`Read-Only Source`):** `05-Du-lieu-GIS/PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif` (`SHA-256 = 0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`)  
**Tọa độ & Lưới tính toán:** `EPSG:32649` (UTM Zone 49N), kích thước lưới $2100 \times 2100$ ô ($30\text{ m} \times 30\text{ m} = 900\text{ m}^2/\text{ô}$, `nodata = -9999.0`, `valid_min = -3,00 m`, `valid_max = +1449,0325 m`)  
**Mã nguồn thực thi:** [`v49_method1_dhg_clamped.py`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/v49_method1_dhg_clamped.py)  
**Bộ kiểm thử tự động:** [`test_v49_method1_dhg_clamped.py`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/test_v49_method1_dhg_clamped.py)  
**Dữ liệu kiểm toán & Raster xuất ra:** [`V49_Method1_Audit_Summary.json`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/V49_Method1_Audit_Summary.json) | [`V49_Method1_Reach_Table.csv`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/V49_Method1_Reach_Table.csv) | [`rasters/`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/rasters) (18 tệp `.tif`)

---

## 1. Tóm tắt Điều hành (Executive Summary)

Trong bài toán mô phỏng ngập lụt lưu vực Sông Ba — Bàn Thạch — Kỳ Lộ (tỉnh Phú Yên) trên nền địa hình số FABDEM/SRTM độ phân giải $30\text{ m}$, tín hiệu radar/quang học của vệ tinh chỉ phản xạ trên **mặt nước lúc chụp ảnh** mà không xuyên qua được cột nước đục. Do đó, lòng dẫn dưới mặt nước của các sông lớn bị "lấp đầy" trên DEM gốc, làm suy giảm nghiêm trọng khả năng tiêu thoát lũ.

Trước khi có nghiên cứu này, dự án đối mặt với một **thế lưỡng nan kỹ thuật** giữa hai thái cực:
1. **Thái cực 1 — Bản cũ Pre-V49 Legacy (Đào cưỡng bức 5 nhánh nhưng vi phạm vật lý):** Cắt gọt trên `83.429` ô lưới (`75,09 km²`, thể tích $\Delta V = 213{,}95\text{ triệu m}^3$), nhưng dùng độ sâu giả định quá lớn tại vùng cửa sông và cho phép đào cả 2 kênh tưới nhân tạo Bắc — Nam Đồng Cam. Hậu quả là làm **thủng đáy âm sâu tới $-13{,}52\text{ m}$** (`valid_min = -8,39 m` trên raster xuất ra), tạo ra **`10.740` ô lưới có $z \le -4{,}0\text{ m}$** (bị bộ giải GPU `BG_Flood` cắt cụt hoặc nhận nhầm thành biên biển mở do tham số `minmask = -4.0 m`) và xâm phạm trực tiếp mặt đập Đồng Cam.
2. **Thái cực 2 — Bản đóng băng chuẩn `V49-E` (An toàn tuyệt đối nhưng phạm vi quá hẹp):** Áp dụng cổng giao hội cực kỳ khắt khe `C.1 ∩ D` (đòi hỏi đồng thời đoạn sông thuộc lớp `RIVER_STREAM`, có bề rộng đo trực tiếp $\ge 3$ mặt cắt, không đi qua nút hợp lưu có đảo dốc đáy giả, và nằm hoàn toàn ngoài vùng ảnh hưởng thủy triều). Kết quả chỉ còn đúng **`2` đoạn thượng nguồn** (`HR_41349822` và `HR_41352752`, tổng dài `5,53 km`, sửa `73` ô trước lượng tử hóa / `72` ô sau lượng tử hóa `float32`, $\Delta V_{\text{central}} = 8.008{,}33\text{ m}^3$ / $8.008{,}21\text{ m}^3$). Toàn bộ hạ lưu Sông Ba (Đà Rằng), Sông Bàn Thạch và Sông Kỳ Lộ bị giữ nguyên cao độ mặt nước vì tại vùng đồng bằng ven biển, độ dốc mặt nước DEM $S \approx 0$ khiến công thức nghịch đảo Manning suy biến ($S^{-3/10} \to \infty$).

**Giải pháp Cách 1 (`v49_method1_dhg_clamped.py`)** giải quyết triệt để thế lưỡng nan trên mà **KHÔNG CẦN bất kỳ số đo mặt cắt thực địa nào**, thông qua **3 chốt chặn toán học tự động hoàn toàn từ dữ liệu viễn thám mở**:
- **Chốt chặn 1 (Hình học Thủy lực Hạ lưu — DHG):** Kết hợp nghịch đảo Manning ở thượng/trung lưu với quy luật lũy thừa lưu lượng trung bình năm $h = 0{,}27 \cdot Q_{\text{mean}}^{0{,}30}$ (HydroMT/Yamazaki) ở vùng triều/hạ lưu (`DHG-1`), đồng thời tự hiệu chuẩn thêm 2 mô hình đối chứng theo bề rộng mặt nước vệ tinh (`DHG-2`: $h = 0{,}1837 \cdot W^{0{,}1321}$) và theo diện tích lưu vực (`DHG-3`: $h = 0{,}1099 \cdot A_{\text{drain}}^{0{,}2250}$).
- **Chốt chặn 2 (Khóa sàn đáy cứng — Hard Bed-Elevation Clamping):** Kẹp cứng cao độ đáy sau khi đào tại $z_{\text{floor}} = -3{,}50\text{ m}$ theo bất đẳng thức $z_{\text{new}}(i, j) = \max\!\big(z_{\text{DEM}}(i, j) - \Delta z(i, j),\; -3{,}50\text{ m}\big)$, tạo lớp đệm an toàn $0{,}50\text{ m}$ phía trên ngưỡng biên biển `minmask = -4.00 m` của `BG_Flood`.
- **Chốt chặn 3 (Bảo vệ Đập Đồng Cam & Loại trừ kênh tưới nhân tạo):** Khóa cứng $\Delta z = 0$ tại toàn bộ `187` ô công trình đầu mối Đập Đồng Cam và loại bỏ hoàn toàn `2` tuyến kênh chính Bắc & Nam Đồng Cam (`55,21 km`).

Kết quả thực thi chứng minh Cách 1 mở rộng phạm vi đào từ **`2` đoạn (`8.008 m³`)** lên **`21` đoạn (`483.941 m³`)**, **`41` đoạn sông lớn $W \ge 60\text{ m}$ (`10,17 triệu m³`)**, và **`82` đoạn toàn mạng lưới 3 hệ thống sông (`10,58 triệu m³`)** với **cam kết toán học tuyệt đối: `0` ô vi phạm `minmask = -4.0 m`, `0` ô xâm phạm Đập Đồng Cam, và `0` ô đào nhầm kênh tưới nhân tạo**.

---

## 2. Cơ sở Toán học và Ba Chốt Chặn Vật lý của Cách 1

### 2.1. Chốt chặn 1: Ba mô hình Quan hệ Hình học Thủy lực Hạ lưu (Downstream Hydraulic Geometry — DHG)

Tại các đoạn sông hạ lưu và cửa sông chịu ảnh hưởng thủy triều, mặt nước trên DEM gần như nằm ngang ($S \to 0$). Nếu dùng trực tiếp phương trình Manning cho kênh chữ nhật rộng:

$$h_{\text{Manning}} = \left(\frac{n \cdot Q_{\text{bf}}}{W \cdot \sqrt{S}}\right)^{3/5}$$

thì khi $S \to 0$, $h_{\text{Manning}} \to \infty$ (gây thủng đáy âm sâu). Cách 1 khắc phục hoàn toàn hiện tượng suy biến này bằng họ mô hình **Downstream Hydraulic Geometry (DHG)** của Leopold & Maddock (1953) và Yamazaki et al. (2014) / HydroMT:

1. **Mô hình `DHG-1` (Chuẩn V49-D Hybrid — Khuyên dùng chính thức):**
   - Tại các đoạn sông tự nhiên có bề rộng đo trực tiếp từ mặt nạ nước thường trực JRC ($W \ge 60\text{ m}$) và độ dốc mặt nước dương ổn định ($S \ge 10^{-4}$), sử dụng nghiệm nghịch đảo Manning chữ nhật đầy đủ (`FULL_RECTANGULAR_MANNING_INVERSION`, $n = 0{,}035$).
   - Tại tất cả các đoạn hạ lưu, cửa sông chịu ảnh hưởng thủy triều ($S \approx 0$) hoặc nhánh sông phụ thiếu độ dốc mặt nước cục bộ, tự động chuyển sang quy luật lũy thừa lưu lượng trung bình năm (`HYDROMT_POWER_LAW_FALLBACK`):
     $$h_{\text{DHG1}} = 0{,}27 \cdot \left(Q_{\text{mean}}\right)^{0{,}30} \quad (\text{m})$$
     trong đó $Q_{\text{mean}} = \text{DIS\_AV\_CMS}$ ($\text{m}^3/\text{s}$) là lưu lượng trung bình nhiều năm trích xuất trực tiếp từ cơ sở dữ liệu toàn cầu HydroRIVERS (không phụ thuộc vào độ dốc $S$).

2. **Mô hình `DHG-2` (Leopold & Maddock theo bề rộng mặt nước vệ tinh $W$):**
   Tự hiệu chuẩn (*Self-Calibration*) bằng hồi quy log-tuyến tính $\ln h = \ln a + b \ln W$ trên 21 đoạn sông tự nhiên thuộc lớp `RIVER_STREAM` (`Scope A`), cho phương trình không cần độ dốc $S$:
   $$h_{\text{DHG2}} = a \cdot W^{b} = 0{,}1837 \cdot W^{0{,}1321} \quad (\text{m})$$

3. **Mô hình `DHG-3` (Quy luật lũy thừa theo diện tích lưu vực tích lũy $A_{\text{drain}}$):**
   Tự hiệu chuẩn bằng hồi quy log-tuyến tính $\ln h = \ln \alpha + \beta \ln A_{\text{drain}}$ trên 21 đoạn sông `Scope A` theo diện tích lưu vực tích lũy $A_{\text{drain}} = \text{UPLAND\_SKM}$ ($\text{km}^2$):
   $$h_{\text{DHG3}} = \alpha \cdot \left(A_{\text{drain}}\right)^{\beta} = 0{,}1099 \cdot \left(A_{\text{drain}}\right)^{0{,}2250} \quad (\text{m})$$

4. **Ba kịch bản biên độ bất định (`LOW / CENTRAL / HIGH`) và Mặt cắt ngang Cosin nâng (`Raised-Cosine Taper`):**
   - Để phục vụ phân tích độ nhạy trong đồ án, mỗi đoạn sông đều được tính đồng thời trên 3 kịch bản độ sâu tâm dòng:
     $$h_{\text{LOW}} = 0{,}50 \cdot h_{\text{central}}, \qquad h_{\text{CENTRAL}} = 1{,}00 \cdot h_{\text{central}}, \qquad h_{\text{HIGH}} = 1{,}70 \cdot h_{\text{central}}$$
   - Trên mặt cắt ngang có bán kính hành lang $r = W / 2$, độ hạ đáy tại ô lưới $(i, j)$ cách tim sông một khoảng $d(i, j)$ được làm trơn bằng hàm cosin nâng:
     $$\Delta z(i, j) = h \cdot w\!\big(d(i, j)\big), \qquad w(d) = \begin{cases} 1{,}0 & \text{nếu ô thuộc đường tim (thalweg) hoặc } d \le 0, \\ \cos^2\!\left(\dfrac{\pi d}{2r}\right) = \dfrac{1}{2}\left[1 + \cos\!\left(\dfrac{\pi d}{r}\right)\right] & \text{nếu } 0 < d < r, \\ 0{,}0 & \text{nếu } d \ge r. \end{cases}$$

### 2.2. Chốt chặn 2: Khóa sàn đáy cứng (Hard Bed-Elevation Clamping) bảo vệ ngưỡng `minmask = -4.0 m`

Trong bộ giải thủy động lực học GPU `BG_Flood`, tham số cấu hình chuẩn `minmask = -4.0 m` quy định mọi ô lưới có cao độ $z \le -4{,}0\text{ m}$ bị xem là vùng biển sâu ngoài khơi hoặc bị cắt khỏi miền dòng chảy nội đồng. Để đảm bảo **không bao giờ xảy ra hiện tượng thủng đáy** ngay cả ở kịch bản cực đoan nhất (`HIGH = 1,70 × CENTRAL`) tại các cửa sông Đà Diễn, Đà Nông, Tiên Châu và đầm Ô Loan, Cách 1 áp đặt **toán tử khóa sàn đáy cứng (Hard Floor Clamp)** tại cao độ $z_{\text{floor}} = -3{,}50\text{ m}$:

$$z_{\text{new}}(i, j) = \begin{cases} \max\!\Big(z_{\text{DEM}}(i, j) - \Delta z(i, j),\; z_{\text{floor}}\Big) & \text{nếu } \Delta z(i, j) > 0 \text{ và } z_{\text{DEM}}(i, j) > z_{\text{floor}}, \\ z_{\text{DEM}}(i, j) & \text{trong các trường hợp còn lại.} \end{cases}$$

Độ hạ đáy hiệu dụng thực tế được phép thực thi tại mỗi ô lưới là:

$$\Delta z_{\text{eff}}(i, j) = \max\!\Big(0{,}0,\; z_{\text{DEM}}(i, j) - z_{\text{new}}(i, j)\Big)$$

**Định lý an toàn biên biển:** Vì $z_{\text{floor}} = -3{,}50\text{ m} > \text{minmask} = -4{,}00\text{ m}$, mọi ô lưới sông được đào bởi Cách 1 đều thỏa mãn bất đẳng thức:
$$z_{\text{new}}(i, j) \ge -3{,}50\text{ m} > -4{,}00\text{ m}$$
tạo ra một **khoảng đệm an toàn tuyệt đối dày $0{,}50\text{ m}$** phía trên ngưỡng cắt biên biển của `BG_Flood`, đồng thời không bao giờ đào sâu thêm hoặc đắp đất nhân tạo tại các ô vốn dĩ đã nằm dưới $-3{,}50\text{ m}$.

### 2.3. Chốt chặn 3: Khóa cứng Công trình Đầu mối Đập Đồng Cam & Loại trừ Kênh tưới Nhân tạo (`Phase F`)

1. **Khóa cứng 187 ô mặt đập Đồng Cam:** Toàn bộ vùng mặt nạ công trình đầu mối Đập Đồng Cam (`row 1272..1288`, `col 1212..1222`, kích thước $17 \times 11 = 187$ ô lưới $= 0{,}1683\text{ km}^2$) được áp điều kiện biên cứng:
   $$\forall (i, j) \in \Omega_{\text{Đồng Cam}}:\quad \Delta z(i, j) \equiv 0 \implies \text{Số ô đập bị sửa đổi} = 0.$$
2. **Loại trừ vĩnh viễn 2 tuyến kênh tưới nhân tạo Bắc & Nam Đồng Cam:** Trong tổng số `91` đoạn nằm trong hành lang mặt nước `V49C_ELIGIBLE_CHANNEL`, có đúng `2` tuyến kênh nhân tạo (`source_type == 'LEGACY_CANAL_CANDIDATE'`, tổng dài `55,21 km`):
   - `LEGACY_CANAL_1_DONG_CAM_NORTH` (`31,83 km`, chênh cao đầu — cuối $\Delta z_{\text{up-down}} = -29{,}87\text{ m}$: leo ngược sườn đồi trên DEM 30m).
   - `LEGACY_CANAL_2_DONG_CAM_SOUTH` (`23,38 km`, chênh cao đầu — cuối $\Delta z_{\text{up-down}} = -21{,}48\text{ m}$: leo ngược sườn đồi trên DEM 30m).
   Cách 1 khóa cứng `in_scope = False` đối với cả 2 tuyến kênh này ở mọi cấp độ mở rộng, giữ nguyên số ô kênh bị đào là `0`.

---

## 3. Phân hoạch Toán học 370 Đoạn Sông và Bảng Kiểm toán 5 Cấp độ Mở rộng

### 3.1. Phân hoạch chính xác 370 đoạn sông trong `V49_reach_geometry.gpkg`

> **Lưu ý kỹ thuật về hai con số tổng chiều dài (`1.089,52 km` vs `643,84 km`):**
> - Trong lớp đồ thị đã cắt theo khung miền tính `V49-B` (`V49_hydro_graph.gpkg`), tổng chiều dài 370 đoạn là **`643,84 km`** (`635,96 km` sông tự nhiên + `7,88 km` phần kênh nằm trong khung cắt).
> - Trong lớp hình học thủy lực `V49-D` (`V49_reach_geometry.gpkg`), hình học gốc của các đoạn vắt qua biên được giữ nguyên để tính toán thủy văn lưu vực, có tổng chiều dài là **`1.089,52 km`**. Cả hai con số đều phản ánh cùng một tập hợp **370 đoạn sông**.

Bảng dưới đây trình bày phân hoạch đầy đủ 370 đoạn sông theo phạm vi hành lang mặt nước và hệ thống sông:

| Nhóm phân hoạch trong `V49_reach_geometry.gpkg` | Số đoạn | Chiều dài hình học `V49-D` (km) | Trạng thái trong Cách 1 | Giải thích vật lý & Thủy lực |
| :--- | :---: | :---: | :---: | :--- |
| **1. Ngoài hành lang mặt nước (`OUTSIDE_V49C_ELIGIBLE_CHANNEL`)** | **279** | 745,74 | Giữ nguyên DEM ($\Delta z = 0$) | Các nhánh suối nhỏ miền núi có bề rộng thực tế $< 30\text{ m}$ (nhỏ hơn 1 ô lưới DEM), không tạo thành đa giác nước thường trực trên ảnh vệ tinh JRC. |
| **2. Kênh tưới nhân tạo trong V49-C (`LEGACY_CANAL_CANDIDATE`)** | **2** | 55,21 | **CẤM ĐÀO ($\Delta z = 0$)** | Kênh chính Bắc (`31,83 km`) & Kênh chính Nam (`23,38 km`) của hệ thống thủy lợi Đồng Cam; đi nổi ven sườn đồi, nếu đào sẽ tạo hào thoát lũ giả. |
| **3. Sông tự nhiên trong V49-C thuộc 3 hệ thống sông chính (`Scope B2`)** | **82** | 261,14 | **ĐƯỢC ĐÀO THEO PHÂN TẦNG** | Gồm **59 đoạn Sông Ba** (`186,19 km`), **12 đoạn Sông Bàn Thạch** (`40,33 km`), và **11 đoạn Sông Kỳ Lộ** (`34,63 km`). |
| **4. Nhánh gắn với Đầm Ô Loan (`W20_0009`, mở rộng lên `Scope B3`)** | **7** | 27,43 | Tùy chọn đối chứng (`Scope B3`) | Gắn với đầm phá ven biển Đầm Ô Loan (`dem_min = -3,00 m`), nơi khóa sàn đáy $z_{\text{floor}} = -3{,}50\text{ m}$ phát huy tác dụng kẹp trực tiếp ở kịch bản `HIGH`. |
| **TỔNG CỘNG TOÀN MIỀN (`279 + 2 + 82 + 7`)** | **370** | **1.089,52** | — | Khớp tuyệt đối 100% cơ sở dữ liệu `V49 R3`. |

### 3.2. Bảng tổng hợp định lượng 5 cấp độ mở rộng + Tích hợp 2 tầng `V48 + V49` (Mô hình chuẩn `DHG-1` trên DEM thực `float32`)

| Cấp độ (Scope) | Định nghĩa kỹ thuật | Số đoạn | Chiều dài (km) | Số ô sửa `float32` *(Trước lượng tử hóa)* | Diện tích sửa ($\text{km}^2$) | Thể tích đào `LOW` ($\text{m}^3$) | Thể tích đào `CENTRAL` ($\text{m}^3$) | Thể tích đào `HIGH` ($\text{m}^3$) | Độ hạ đáy lớn nhất $\Delta z_{\max}$ `CENTRAL` (m) | Cao độ đáy sửa thấp nhất `HIGH` (m) | Số ô $\le -4{,}0\text{ m}$ (`minmask`) | Số ô đập Đồng Cam bị sửa |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`V49_E_2`** *(Chuẩn đóng băng)* | Chỉ 2 đoạn thượng nguồn vượt cổng `C.1 ∩ D` (`HR_41349822`, `HR_41352752`) | **2** | 5,53 | **72** *(73)* | 0,0648 *(0,0657)* | 3.597,86 *(3.597,74)* | **8.008,21** *(8.008,33)* | 14.020,67 *(14.020,59)* | 0,3742 | +144,41 *(+143,74)* | **0** | **0** |
| **`SCOPE_A_21`** *(Cấp độ A — Bảo thủ)* | Toàn bộ **21 đoạn** sông tự nhiên có giao cắt với lớp `RIVER_STREAM` | **21** | 79,52 | **2.369** *(2.370)* | 2,1321 *(2,1330)* | 187.690,23 *(187.690,28)* | **483.941,14** *(483.941,43)* | 922.208,29 *(922.207,96)* | 1,1918 | -0,79 *(-1,07)* | **0** | **0** |
| **`SCOPE_B1_41`** *(Cấp độ B1 — **Khuyên dùng**)* | **41 đoạn** sông tự nhiên có bề rộng đo trực tiếp từ vệ tinh $W \ge 60\text{ m}$ ($\ge 2$ pixel) | **41** | 102,82 | **18.320** *(18.321)* | 16,4880 *(16,4889)* | 3.560.839,75 *(3.560.839,73)* | **10.170.012,30** *(10.170.012,50)* | 20.335.866,83 *(20.335.866,81)* | 1,6469 | -2,79 | **0** | **0** |
| **`V48_66CUTS + SCOPE_B1_41`** *(Tích hợp 2 tầng chuẩn)* | **66 ô** thông cống/cầu cục bộ `V46–V48` (`31.806,64 m³`) $\cup$ **41 đoạn** sông lớn $W \ge 60\text{ m}$ (giao nhau đúng 1 ô tại `(1535, 1904)`) | **41** (+66 ô) | 102,82 | **18.385** *(18.386)* | 16,5465 | 3.592.463,25 | **10.201.295,70** | 20.366.777,11 | 1,6469 | -2,79 | **0** | **0** |
| **`SCOPE_B2_82`** *(Cấp độ B2 — Toàn bộ 3 sông)* | Toàn bộ **82 đoạn** tự nhiên của 3 hệ thống Sông Ba, Bàn Thạch, Kỳ Lộ (trừ Đầm Ô Loan) | **82** | 261,14 | **19.992** *(19.993)* | 17,9928 *(17,9937)* | 3.721.429,32 *(3.721.429,36)* | **10.580.338,52** *(10.580.338,78)* | 21.115.002,77 *(21.115.002,66)* | 1,6469 | -2,79 | **0** | **0** |
| **`SCOPE_B3_89`** *(Cấp độ B3 — Đối chứng Đầm Ô Loan)* | Toàn bộ **89 đoạn** tự nhiên trong `V49-C` (gồm cả 7 đoạn gắn với Đầm Ô Loan `W20_0009`) | **89** | 288,57 | **36.249** *(36.250)* | 32,6241 *(32,6250)* | 4.626.090,40 *(4.626.090,44)* | **13.165.084,47** *(13.165.084,73)* | 26.284.494,67 *(26.284.494,56)* | 1,6469 | -3,44 *(Kẹp sàn -3,50 từ -3,81 m)* | **0** | **0** |

> **Giải thích sự minh bạch giữa số ô trước lượng tử hóa (`float64`) và sau lượng tử hóa trên DEM gốc (`float32`):** Khi trừ trường hạ đáy vào raster DEM thực `PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif` (`dtype = float32`) ở vùng núi cao (`z ≈ 264,1 m` tại đoạn `HR_41352752` có mặt trong cả 5 cấp độ), 1 ô sát bờ có độ hạ đáy lý thuyết $\Delta z = 7{,}72 \times 10^{-6}\text{ m}$ nhỏ hơn nửa bước nhảy lượng tử `0,5 ULP` của `float32` ở cao độ $264\text{ m}$ ($1\text{ ULP} = 2^{-15} \approx 3{,}05 \times 10^{-5}\text{ m}$) nên tự động làm tròn về `0`. Nhờ đó, trên DEM thực `float32`, số ô thay đổi thực sự giảm đúng `1` ô (`73 → 72`, `2.370 → 2.369`, `18.321 → 18.320`, `19.993 → 19.992`, `36.250 → 36.249`) và chênh lệch thể tích chỉ là `0,12 — 0,29 m³` (`< 0,0015%`). Đặc biệt, khi chạy Cách 1 ở cấp `V49_E_2_CENTRAL`, tệp GeoTIFF sinh ra khớp **100% từng byte (`SHA-256`)** với tệp chuẩn đóng băng `V49_E_hydraulic_bed.tif` (`181115942dc88a95503a1e193b2f90149e918b6f8354a262085b293e11df2552`).

### 3.3. Danh mục 18 Tệp GeoTIFF (`.tif`) Đã Tạo Trực Tiếp Từ DEM Gốc & Mã Băm Kiểm Toán `SHA-256`

Toàn bộ các tệp địa hình đáy sông đã đào (`Carved Hydraulic Bed DEM`) và trường độ sâu hạ đáy thực tế (`DeltaZ`) được xuất chuẩn `GeoTIFF (float32, EPSG:32649, 2100×2100, DEFLATE, PREDICTOR=3)` tại thư mục [`rasters/`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/rasters) và đồng bộ sang `05-Du-lieu-GIS/`:

| Mã kịch bản (`Scenario Key`) | Tên tệp DEM Đáy Sông Đã Đào (`Carved DEM .tif`) | Mã băm `SHA-256` (Carved DEM) | Tên tệp Trường Hạ Đáy (`DeltaZ .tif`) | Mã băm `SHA-256` (DeltaZ) | Số ô sửa | Thể tích đào $\Delta V$ ($\text{m}^3$) | Đáy sửa thấp nhất $z_{\min}$ (m) |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **`SCOPE_B1_41_LOW`** | `PhuYen_DEM_30m_V49_Method1_ScopeB1_41Reaches_LOW.tif` | `6ca44f5f0446c2577c5de097c05749049ccdddb54f15d938d85bb50bbfb07cb9` | `V49_Method1_ScopeB1_41Reaches_DeltaZ_LOW.tif` | `aedbe6e4295e92907ef5506d8d2d804862c7f956923d55b32b963c3f99720478` | 18.312 | 3.560.839,75 | -0,3766 |
| **`SCOPE_B1_41_CENTRAL`** *(Khuyên dùng)* | `PhuYen_DEM_30m_V49_Method1_ScopeB1_41Reaches_CENTRAL.tif` | `65df30b74037866804b52ad5665207535934f09c73df28a5b960e459514f2d2b` | `V49_Method1_ScopeB1_41Reaches_DeltaZ_CENTRAL.tif` | `18c48e770da31351ef97649200b288a9d8994cb2cfb559b87ce588bec04557a2` | 18.320 | **10.170.012,30** | -1,1469 |
| **`SCOPE_B1_41_HIGH`** | `PhuYen_DEM_30m_V49_Method1_ScopeB1_41Reaches_HIGH.tif` | `56602447b1a8c136d1816e0f1f90e2e38b2e5cb24e7b1b20b13279940b239399` | `V49_Method1_ScopeB1_41Reaches_DeltaZ_HIGH.tif` | `281c35822537cfd30afcbc5467885f08de634418b1e4234130f49d406fb17283` | 18.326 | 20.335.866,83 | -2,7938 |
| **`V48_66CUTS_PLUS_SCOPE_B1_41_LOW`** | `PhuYen_DEM_30m_V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_LOW.tif` | `76dd65292dd5a0a85609d3bfabbe77ae520afbbab2eee2abd90012d0f0c812aa` | `V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_DeltaZ_LOW.tif` | `f7257a70eb8916b19e664832229cb3f4a9fcb983d9bb00cca5861029c46953ac` | 18.377 | 3.592.463,25 | -0,3766 |
| **`V48_66CUTS_PLUS_SCOPE_B1_41_CENTRAL`** *(Tích hợp 2 tầng)* | `PhuYen_DEM_30m_V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_CENTRAL.tif` | `967ac3a832ead2aafcf8dba538ee7f1a9060b1bad8432322ef7a744e158a74db` | `V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_DeltaZ_CENTRAL.tif` | `62890dc2ef9431dcee3a135d943950664e1b4834fab92a80194a55703f7d7b39` | 18.385 | **10.201.295,70** | -1,1469 |
| **`V48_66CUTS_PLUS_SCOPE_B1_41_HIGH`** | `PhuYen_DEM_30m_V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_HIGH.tif` | `ecb14db97e1100d173662a6cf9b957199aecdc839b417f0d9c429892e4f25672` | `V48_66Cuts_Plus_V49_Method1_ScopeB1_41Reaches_DeltaZ_HIGH.tif` | `9148372bda7bc39f5218fe2c39d18a9f4d273d86f960f58c3ec396b9e031ed1e` | 18.391 | 20.366.777,11 | -2,7938 |
| **`SCOPE_A_21_CENTRAL`** | `PhuYen_DEM_30m_V49_Method1_ScopeA_21Reaches_CENTRAL.tif` | `f57e2dd49565c51b112d7f05097b2cb4bf6a05d505acfb3e835712e8d4550324` | `V49_Method1_ScopeA_21Reaches_DeltaZ_CENTRAL.tif` | `8a23f85b835b015bcc3fa7eee7f54380aa24c286e3697402f8b71cf13da9d948` | 2.369 | **483.941,14** | -0,3951 |
| **`SCOPE_B2_82_CENTRAL`** | `PhuYen_DEM_30m_V49_Method1_ScopeB2_82Reaches_CENTRAL.tif` | `3dea18e6e8f141b9a46b75b071b745d0fb2921dd3d201e4d3015e634a912f172` | `V49_Method1_ScopeB2_82Reaches_DeltaZ_CENTRAL.tif` | `454a2f2e54e5af6fcbb39b3e04116e025a48af8a173066057e124ca1d251bccc` | 19.992 | **10.580.338,52** | -1,1469 |
| **`V49_E_2_CENTRAL`** *(Đối chứng V49-E)* | `PhuYen_DEM_30m_V49_E_2Reaches_CENTRAL.tif` | `181115942dc88a95503a1e193b2f90149e918b6f8354a262085b293e11df2552` | `V49_E_2Reaches_DeltaZ_CENTRAL.tif` | `a9402641059853cd574deda213440e88fb0a84f32928da880590fcc175898980` | 72 | **8.008,21** | +144,6677 |

---

## 4. Phân rã Chi tiết theo 3 Hệ thống Sông Tự nhiên & Phát hiện Quy luật Pareto

Bảng dưới đây bóc tách chi tiết đóng góp của từng hệ thống sông (**Sông Ba**, **Sông Bàn Thạch**, **Sông Kỳ Lộ**) ở kịch bản chuẩn `DHG-1 (CENTRAL)` (khớp chính xác 100% với trường `river_breakdown` trong [`V49_Method1_Audit_Summary.json`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/V49_Method1_Audit_Summary.json)):

| Cấp độ mở rộng | Hệ thống sông | Mã lưu vực `MAIN_RIV` | Số đoạn đào | Chiều dài (km) | Số ô sửa ($30\times 30\text{ m}$) | Diện tích sửa ($\text{km}^2$) | Bề rộng TB $W$ (m) | Độ sâu tâm TB $h_{\text{central}}$ (m) | Độ sâu tâm lớn nhất $h_{\max}$ (m) | Thể tích đào `LOW` ($\text{m}^3$) | Thể tích đào `CENTRAL` ($\text{m}^3$) | Thể tích đào `HIGH` ($\text{m}^3$) | Tỷ trọng $\Delta V_{\text{central}}$ (%) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`SCOPE_A_21`** *(21 đoạn)* | **1. Hệ thống Sông Ba** | `41347969`, `41347692`, `41348408` | 12 | 43,69 | 627 | 0,5643 | 140,26 | 0,3729 | 0,7740 | 51.455,18 | **110.905,59** | 192.537,11 | 22,92% |
| | **2. Hệ thống Sông Bàn Thạch** | `41349827`, `41349988` | 5 | 19,49 | 1.622 | 1,4598 | 226,16 | 0,2873 | 0,5620 | 113.347,55 | **320.854,19** | 637.758,77 | 66,30% |
| | **3. Hệ thống Sông Kỳ Lộ** | `41342672`, `41342884` | 4 | 16,33 | 121 | 0,1089 | 222,13 | 0,7893 | 1,1918 | 22.887,56 | **52.181,65** | 91.912,08 | 10,78% |
| | **Tổng cộng `SCOPE_A_21`** | — | **21** | **79,52** | **2.370** | **2,1330** | — | — | 1,1918 | **187.690,28** | **483.941,43** | **922.207,96** | **100,00%** |
| **`SCOPE_B1_41`** *(41 đoạn $W \ge 60\text{ m}$)* | **1. Hệ thống Sông Ba** | `41347969`, `41347692`, `41348408` | 32 | 76,01 | 11.378 | 10,2402 | 313,40 | 1,2460 | 1,6469 | 2.930.716,19 | **8.369.659,52** | 16.735.160,85 | **82,30%** |
| | **2. Hệ thống Sông Bàn Thạch** | `41349827`, `41349988` | 6 | 18,85 | 6.171 | 5,5539 | 500,16 | 0,4475 | 0,5873 | 514.289,08 | **1.469.397,37** | 2.938.794,75 | **14,45%** |
| | **3. Hệ thống Sông Kỳ Lộ** | `41342672`, `41342884` | 3 | 7,96 | 772 | 0,6948 | 205,44 | 0,9121 | 0,9144 | 115.834,46 | **330.955,61** | 661.911,22 | **3,25%** |
| | **Tổng cộng `SCOPE_B1_41`** | — | **41** | **102,82** | **18.321** | **16,4889** | — | — | 1,6469 | **3.560.839,73** | **10.170.012,50** | **20.335.866,81** | **100,00%** |
| **`SCOPE_B2_82`** *(82 đoạn toàn 3 sông)* | **1. Hệ thống Sông Ba** | `41347969`, `41347692`, `41348408` | 59 | 186,19 | 12.529 | 11,2761 | 299,43 | 0,8432 | 1,6469 | 3.021.621,69 | **8.597.095,61** | 17.164.917,16 | **81,26%** |
| | **2. Hệ thống Sông Bàn Thạch** | `41349827`, `41349988` | 12 | 40,33 | 6.295 | 5,6655 | 347,87 | 0,3413 | 0,5873 | 523.361,17 | **1.492.321,66** | 2.980.693,72 | **14,10%** |
| | **3. Hệ thống Sông Kỳ Lộ** | `41342672`, `41342884` | 11 | 34,63 | 1.169 | 1,0521 | 399,90 | 0,6670 | 1,1918 | 176.446,50 | **490.921,50** | 969.391,78 | **4,64%** |
| | **Tổng cộng `SCOPE_B2_82`** | — | **82** | **261,14** | **19.993** | **17,9937** | — | — | 1,6469 | **3.721.429,36** | **10.580.338,78** | **21.115.002,66** | **100,00%** |

### Phát hiện Khoa học Quan trọng: Quy luật Pareto 96,12% giữa `Scope B1` (41 đoạn) và `Scope B2` (82 đoạn)

Khi so sánh trực tiếp giữa `SCOPE_B1_41` (chỉ chọn **41 đoạn sông lớn** có bề rộng đo trực tiếp từ mặt nạ nước thường trực JRC $W \ge 60\text{ m}$, tức tối thiểu $\ge 2$ ô lưới 30m) và `SCOPE_B2_82` (lấy toàn bộ **82 đoạn** bao gồm cả 41 nhánh phụ nhỏ dùng bề rộng mặc định $W = 30\text{ m}$):
- **Về số đoạn:** `Scope B1` chỉ bằng đúng **$50{,}0\%$** số đoạn của `Scope B2` (`41 / 82` đoạn).
- **Về diện tích mặt nước được khơi thông:** `Scope B1` chiếm tới **$91{,}64\%$** tổng số ô lưới (`18.321 / 19.993` ô, tương ứng `16,49 / 17,99 km²`).
- **Về thể tích lòng dẫn giải phóng ($\Delta V_{\text{central}}$):** `Scope B1` giải phóng tới **$96{,}12\%$** tổng dung tích đào của toàn bộ 3 hệ thống sông (`10.170.012,50 / 10.580.338,78 m³`)! Phần 41 nhánh nhỏ còn lại ($W = 30\text{ m}$) chỉ đóng góp thêm `3,88%` thể tích (`410.326,28 m³`).

**Ý nghĩa bảo vệ đồ án:** Phát hiện này cho phép sinh viên đề xuất **`SCOPE_B1_41` (41 đoạn sông lớn $W \ge 60\text{ m}$) làm Phương án Khuyến nghị Chính thức (Recommended Production Tier)**: vừa loại bỏ hoàn toàn sai số của các nhánh suối hẹp 1 pixel ($W = 30\text{ m}$), vừa thu hồi hơn `96%` dung tích trữ và tiêu thoát lũ của cả 3 lưu vực Sông Ba, Bàn Thạch, Kỳ Lộ!

---

## 5. Phân tích Độ nhạy giữa 3 Mô hình Hình học Thủy lực (`DHG-1`, `DHG-2`, `DHG-3`)

Bảng dưới đây đối chiếu kết quả của cả 3 phương trình Hình học Thủy lực Hạ lưu (`DHG-1`, `DHG-2`, `DHG-3`) trên cả 5 cấp độ mở rộng (khớp chính xác 100% với [`V49_Method1_Audit_Summary.json`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/V49_Method1_Audit_Summary.json)):

| Cấp độ (Scope) | Mô hình DHG | Phương trình toán học trung tâm | Thể tích đào `LOW` ($\text{m}^3$) | Thể tích đào `CENTRAL` ($\text{m}^3$) | Thể tích đào `HIGH` ($\text{m}^3$) | Độ hạ đáy lớn nhất $\Delta z_{\max}$ `CENTRAL` (m) | Độ hạ đáy TB $\overline{\Delta z}$ `CENTRAL` (m) | Cao độ đáy thấp nhất $z_{\min}$ `HIGH` (m) | Số ô vi phạm `minmask` ($\le -4{,}0\text{ m}$) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`V49_E_2`** *(2 đoạn)* | **`DHG-1`** | Manning ($n=0{,}035$) + $0{,}27 Q^{0{,}30}$ | 3.597,74 | **8.008,33** | 14.020,59 | 0,3742 | 0,1219 | +143,74 | **0** |
| | **`DHG-2`** | $h = 0{,}1837 \cdot W^{0{,}1321}$ | 5.756,96 | **11.513,92** | 19.573,66 | 0,3532 | 0,1752 | +143,84 | **0** |
| | **`DHG-3`** | $h = 0{,}1099 \cdot A_{\text{drain}}^{0{,}2250}$ | 4.683,61 | **9.367,21** | 15.924,26 | 0,5061 | 0,1426 | +143,52 | **0** |
| **`SCOPE_A_21`** *(21 đoạn)* | **`DHG-1`** | Manning ($n=0{,}035$) + $0{,}27 Q^{0{,}30}$ | 187.690,28 | **483.941,43** | 922.207,96 | 1,1918 | 0,2269 | -1,07 | **0** |
| | **`DHG-2`** | $h = 0{,}1837 \cdot W^{0{,}1321}$ | 238.751,43 | **477.502,86** | 811.754,86 | 0,4426 | 0,2239 | -1,03 | **0** |
| | **`DHG-3`** | $h = 0{,}1099 \cdot A_{\text{drain}}^{0{,}2250}$ | 209.677,96 | **419.355,92** | 712.905,06 | 0,8954 | 0,1966 | -0,81 | **0** |
| **`SCOPE_B1_41`** *(41 đoạn $W \ge 60\text{ m}$)* | **`DHG-1`** | Manning ($n=0{,}035$) + $0{,}27 Q^{0{,}30}$ | 3.560.839,73 | **10.170.012,50** | 20.335.866,81 | 1,6469 | 0,6168 | -2,79 | **0** |
| | **`DHG-2`** | $h = 0{,}1837 \cdot W^{0{,}1321}$ | 1.796.048,24 | **3.592.096,49** | 6.106.564,04 | 0,4703 | 0,2179 | -1,08 | **0** |
| | **`DHG-3`** | $h = 0{,}1099 \cdot A_{\text{drain}}^{0{,}2250}$ | 3.041.278,13 | **6.082.556,27** | 10.340.345,66 | 0,9292 | 0,3689 | -1,08 | **0** |
| **`SCOPE_B2_82`** *(82 đoạn toàn 3 sông)* | **`DHG-1`** | Manning ($n=0{,}035$) + $0{,}27 Q^{0{,}30}$ | 3.721.429,36 | **10.580.338,78** | 21.115.002,66 | 1,6469 | 0,5880 | -2,79 | **0** |
| | **`DHG-2`** | $h = 0{,}1837 \cdot W^{0{,}1321}$ | 1.970.347,87 | **3.940.695,75** | 6.699.182,78 | 0,4703 | 0,2191 | -1,08 | **0** |
| | **`DHG-3`** | $h = 0{,}1099 \cdot A_{\text{drain}}^{0{,}2250}$ | 3.211.764,32 | **6.423.528,65** | 10.919.998,71 | 0,9292 | 0,3570 | -1,08 | **0** |
| **`SCOPE_B3_89`** *(89 đoạn + Đầm Ô Loan)* | **`DHG-1`** | Manning ($n=0{,}035$) + $0{,}27 Q^{0{,}30}$ | 4.626.090,44 | **13.165.084,73** | 26.284.494,56 | 1,6469 | 0,4035 | **-3,50** *(Kẹp sàn)* | **0** |
| | **`DHG-2`** | $h = 0{,}1837 \cdot W^{0{,}1321}$ | 4.385.096,64 | **8.770.193,29** | 14.909.328,61 | 0,5284 | 0,2688 | **-3,50** *(Kẹp sàn)* | **0** |
| | **`DHG-3`** | $h = 0{,}1099 \cdot A_{\text{drain}}^{0{,}2250}$ | 4.330.160,49 | **8.660.320,98** | 14.722.545,67 | 0,9292 | 0,2655 | **-3,50** *(Kẹp sàn)* | **0** |

**Nhận xét học thuật từ bảng độ nhạy:**
1. Trên tập hiệu chuẩn thượng nguồn `SCOPE_A_21` (`21` đoạn), hai mô hình `DHG-1` (`483.941,43 m³`) và `DHG-2` (`477.502,86 m³`) hội tụ sát nhau tới **$98{,}67\%$** (sai khác chỉ `1,33%`), chứng tỏ bộ tham số tự hiệu chuẩn Leopold & Maddock ($a = 0{,}1837, b = 0{,}1321$) hoàn toàn nhất quán với nghiệm thủy lực Manning ở vùng không triều.
2. Khi mở rộng xuống hạ lưu Sông Ba (`SCOPE_B1_41` và `SCOPE_B2_82`), nơi lưu lượng trung bình năm đạt $Q_{\text{mean}} = 278{,}28\text{ m}^3/\text{s}$ và diện tích lưu vực tích lũy lên tới $A_{\text{drain}} = 13.417{,}4\text{ km}^2$:
   - `DHG-2` (chỉ phụ thuộc bề rộng $W$) cho ước lượng bảo thủ nhất (`3,59 — 3,94 triệu m³`, độ sâu cực đại `0,4703 m`) vì tại đồng bằng Tuy Hòa, lòng sông mở rộng thành bãi bồi nông ($W \sim 300\text{–}900\text{ m}$).
   - `DHG-3` (phụ thuộc diện tích lưu vực $A_{\text{drain}}$) cho ước lượng trung gian (`6,08 — 6,42 triệu m³`, độ sâu cực đại `0,9292 m`).
   - `DHG-1` (phụ thuộc lưu lượng $Q_{\text{mean}}$ theo HydroMT $h = 0{,}27 Q^{0{,}30}$) phản ánh đúng năng lượng dòng chảy tập trung của Sông Ba tại hạ du (`10,17 — 10,58 triệu m³`, độ sâu tâm dòng đạt `1,46 — 1,6469 m`).
3. Đặc biệt, trên **tất cả 15 tổ hợp (5 Cấp độ × 3 Mô hình DHG)** và cả 3 kịch bản (`LOW`, `CENTRAL`, `HIGH` — tổng cộng **45 kịch bản mô phỏng**), số ô vi phạm ngưỡng `minmask = -4.0 m` đều bằng **`0` tuyệt đối**. Ngay cả khi đưa cả Đầm Ô Loan (`W20_0009`, có `dem_min = -3,00 m`) vào `SCOPE_B3_89` ở kịch bản cực đoan `HIGH` (nơi đáy chưa kẹp sẽ tụt xuống `-3,8117 m` hoặc `-3,8982 m`), khóa sàn đáy $z_{\text{floor}} = -3{,}50\text{ m}$ lập tức kích hoạt và giữ đáy ở đúng **`-3,50 m`**.

---

## 6. Hệ thống Hình ảnh Minh họa Nền Trắng (`#FFFFFF`) Đưa vào Đồ án

### 6.1. Hình 1: Bản đồ so sánh không gian 4 cấp độ mở rộng của Cách 1 (`2 → 21 → 41 → 82` đoạn)

![Hình 1 - Bản đồ phân tầng mở rộng đào sông tự nhiên Cách 1 nền trắng](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/Hinh_Cach1_Ban_Do_3_Cap_Do_21_41_82_Doan_Nen_Trang.png)

- **Đường dẫn file ảnh độ phân giải cao (240 DPI, nền trắng `#FFFFFF`):** [`Hinh_Cach1_Ban_Do_3_Cap_Do_21_41_82_Doan_Nen_Trang.png`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/Hinh_Cach1_Ban_Do_3_Cap_Do_21_41_82_Doan_Nen_Trang.png)
- **Nội dung thuyết minh trên bản đồ:**
  - **Panel (A):** Chuẩn đóng băng `V49-E` chỉ đào đúng 2 đoạn thượng nguồn (`73` ô trước lượng tử hóa / `72` ô sau lượng tử hóa DEM, $\Delta V = 8.008\text{ m}^3$).
  - **Panel (B):** Cách 1 — Cấp độ A (`SCOPE_A_21`) mở khóa toàn bộ 21 đoạn sông lớp `RIVER_STREAM` (`12` Sông Ba + `5` Bàn Thạch + `4` Kỳ Lộ, sửa `2.370` ô, $\Delta V = 483.941\text{ m}^3$).
  - **Panel (C):** Cách 1 — Cấp độ B1 (`SCOPE_B1_41`, **Khuyên dùng**) mở khóa 41 đoạn sông lớn có bề rộng vệ tinh trực tiếp $W \ge 60\text{ m}$ (`32` Sông Ba + `6` Bàn Thạch + `3` Kỳ Lộ, sửa `18.321` ô, $\Delta V = 10{,}17\text{ triệu m}^3$).
  - **Panel (D):** Cách 1 — Cấp độ B2 (`SCOPE_B2_82`) bao phủ trọn vẹn 82 đoạn của 3 hệ thống sông chính (`59` Sông Ba + `12` Bàn Thạch + `11` Kỳ Lộ, sửa `19.993` ô, $\Delta V = 10{,}58\text{ triệu m}^3$), trong khi vẫn khóa cứng 187 ô Đập Đồng Cam và gạch đỏ cấm đào 2 tuyến kênh tưới Bắc — Nam Đồng Cam.

### 6.2. Hình 2: Biểu đồ phân tích định lượng Thể tích đào $\Delta V$, Cơ cấu 3 hệ thống sông & Chứng minh an toàn đáy `minmask`

![Hình 2 - Biểu đồ phân tích định lượng và chứng minh an toàn đáy Cách 1 nền trắng](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/Hinh_Cach1_So_Sanh_The_Tich_Va_An_Toan_Day_Nen_Trang.png)

- **Đường dẫn file ảnh độ phân giải cao (240 DPI, nền trắng `#FFFFFF`):** [`Hinh_Cach1_So_Sanh_The_Tich_Va_An_Toan_Day_Nen_Trang.png`](file:///D:/DoAnSv/research/dao-song/cach-1-khong-can-thuc-dia/Hinh_Cach1_So_Sanh_The_Tich_Va_An_Toan_Day_Nen_Trang.png)
- **Nội dung thuyết minh trên biểu đồ:**
  - **Panel (A):** So sánh quy mô thể tích đào $\Delta V$ (`LOW / CENTRAL / HIGH`) và chỉ ra quy luật Pareto `96,12%` giữa `Scope B1` (`41` đoạn) và `Scope B2` (`82` đoạn).
  - **Panel (B):** Đối chiếu cao độ đáy thấp nhất $z_{\min}$ giữa bản cũ Pre-V49 Legacy (`-13,52 m`, thủng `10.740` ô dưới `-4,0 m`) và các cấp độ của Cách 1 (tất cả đều nằm trên đường khóa sàn xanh lá $z_{\text{floor}} = -3{,}50\text{ m}$ và cách ngưỡng đỏ `minmask = -4,00 m` một khoảng đệm an toàn `0,50 m`).
  - **Panel (C):** Phân rã thể tích đào theo 3 hệ thống sông tự nhiên, chứng minh Sông Ba chiếm từ `81,26%` đến `82,30%` tổng dung tích lòng dẫn được khơi thông.
  - **Panel (D):** So sánh độ nhạy giữa 3 phương trình `DHG-1`, `DHG-2`, `DHG-3`.

---

## 7. Văn mẫu Chuẩn Học thuật để Sinh viên Copy-Paste Trực tiếp vào Đồ án Tốt nghiệp

### 7.1. Đoạn văn mẫu đưa vào Chương 2 (Cơ sở phương pháp luận — Mục 2.4: Phương pháp ước lượng độ sâu lòng dẫn đa nhánh không cần số đo thực địa)

> *"Do dữ liệu địa hình số toàn cầu FABDEM/SRTM độ phân giải $30\text{ m}$ chỉ phản ánh cao độ mặt nước tại thời điểm thu nhận tín hiệu vệ tinh, lòng dẫn ngập nước của các sông lớn trong lưu vực bị lấp đầy nhân tạo. Tuy nhiên, nếu áp dụng trực tiếp phương trình nghịch đảo Manning trên toàn mạng lưới sông như các tiếp cận truyền thống, độ dốc mặt nước $S \to 0$ tại vùng cửa sông chịu ảnh hưởng thủy triều (Đà Diễn, Đà Nông, Tiên Châu) sẽ làm độ sâu ước lượng phân kỳ ($h \propto S^{-3/10} \to \infty$), gây thủng đáy âm sâu dưới ngưỡng biên biển `minmask = -4,0 m` của mô hình `BG_Flood`. Ngược lại, nếu chỉ giữ lại các đoạn sông vượt qua toàn bộ cổng kiểm toán bảo thủ `C.1 ∩ D` (Phương án chuẩn đóng băng `V49-E`), phạm vi can thiệp bị thu hẹp về 2 đoạn thượng nguồn (`5,53 km`, $\Delta V = 8.008{,}21\text{ m}^3$).*
>
> *Để khắc phục hạn chế trên trong điều kiện không có số liệu đo đạc mặt cắt ngang thực địa trên toàn mạng lưới, đồ án thiết lập **Thuật toán Mở rộng Phân tầng Cách 1 (`V49-Method-1`)** dựa trên ba chốt chặn toán học tự động từ dữ liệu viễn thám mở:*
> 1. *Sử dụng **Quan hệ Hình học Thủy lực Hạ lưu (Downstream Hydraulic Geometry — DHG)** kết hợp nghiệm nghịch đảo Manning ($n = 0{,}035$) ở thượng/trung lưu với quy luật lũy thừa lưu lượng trung bình năm $h = 0{,}27 \cdot Q_{\text{mean}}^{0{,}30}$ ở vùng triều (`DHG-1`), đồng thời kiểm chứng chéo với hai mô hình tự hiệu chuẩn từ 21 đoạn sông thượng nguồn theo bề rộng mặt nước vệ tinh (`DHG-2`: $h = 0{,}1837 \cdot W^{0{,}1321}$) và theo diện tích lưu vực tích lũy (`DHG-3`: $h = 0{,}1099 \cdot A_{\text{drain}}^{0{,}2250}$).*
> 2. *Áp đặt **Toán tử Khóa sàn đáy cứng (Hard Bed-Elevation Clamping)** theo công thức $z_{\text{new}}(i, j) = \max\big(z_{\text{DEM}}(i, j) - \Delta z(i, j),\; z_{\text{floor}}\big)$ với $z_{\text{floor}} = -3{,}50\text{ m}$. Vì $z_{\text{floor}} = -3{,}50\text{ m} > \text{minmask} = -4{,}00\text{ m}$, thuật toán đảm bảo về mặt toán học rằng $100\%$ các ô lưới sau khi hạ đáy đều duy trì khoảng đệm an toàn tối thiểu $0{,}50\text{ m}$ phía trên ngưỡng cắt biên biển của bộ giải `BG_Flood`.*
> 3. *Thực thi **Chốt chặn Bảo vệ Công trình Thủy lợi (`Phase F`)**: khóa cứng $\Delta z = 0$ tại toàn bộ `187` ô lưới công trình đầu mối Đập Đồng Cam và loại trừ hoàn toàn `2` tuyến kênh tưới chính Bắc — Nam Đồng Cam (`55,21 km`) có hành vi đi nổi ven sườn đồi trên DEM."*

### 7.2. Đoạn văn mẫu đưa vào Chương 3 (Kết quả thực nghiệm — Mục 3.3: Kết quả khơi thông dung tích lòng dẫn theo các cấp độ mở rộng của Cách 1)

> *"Kết quả thực thi thuật toán Cách 1 trên lưới tính toán $2100 \times 2100$ ô ($30\text{ m} \times 30\text{ m}$) cho thấy sự gia tăng rõ rệt về dung tích lòng dẫn được giải phóng qua từng cấp độ mở rộng trong khi vẫn bảo toàn tuyệt đối các điều kiện biên vật lý:*
> - *Ở **Cấp độ A (`SCOPE_A_21` — 21 đoạn sông tự nhiên lớp `RIVER_STREAM`, tổng dài `79,52 km`)**, thuật toán hiệu chỉnh `2.370` ô lưới (`2,1330 km²`), giải phóng thể tích lòng dẫn $\Delta V = 483.941{,}43\text{ m}^3$ ở kịch bản `CENTRAL` (dao động từ `187.690,28 m³` ở kịch bản `LOW` đến `922.207,96 m³` ở kịch bản `HIGH`), gấp **60,4 lần** thể tích của bản chuẩn đóng băng `V49-E`.*
> - *Ở **Cấp độ B1 (`SCOPE_B1_41` — 41 đoạn sông lớn có bề rộng vệ tinh trực tiếp $W \ge 60\text{ m}$, tổng dài `102,82 km`)**, phạm vi khơi thông bao phủ trục chính hạ lưu Sông Ba (Đà Rằng), Sông Bàn Thạch và Sông Kỳ Lộ với `18.321` ô lưới (`16,4889 km²`), giải phóng thể tích $\Delta V_{\text{central}} = 10.170.012{,}50\text{ m}^3$ (`LOW`: `3,56 triệu m³`; `HIGH`: `20,34 triệu m³`). Trong đó, hệ thống Sông Ba đóng góp `8.369.659,52 m³` (`82,30%`), hệ thống Sông Bàn Thạch đóng góp `1.469.397,37 m³` (`14,45%`), và hệ thống Sông Kỳ Lộ đóng góp `330.955,61 m³` (`3,25%`).*
> - *Ở **Cấp độ B2 (`SCOPE_B2_82` — toàn bộ 82 đoạn sông tự nhiên của 3 hệ thống sông chính, tổng dài `261,14 km`)**, số ô lưới can thiệp tăng lên `19.993` ô (`17,9937 km²`) với tổng thể tích $\Delta V_{\text{central}} = 10.580.338{,}78\text{ m}^3$ (`Sông Ba`: `8.597.095,61 m³` — `81,26%`; `Sông Bàn Thạch`: `1.492.321,66 m³` — `14,10%`; `Sông Kỳ Lộ`: `490.921,50 m³` — `4,64%`). Phân tích so sánh chỉ ra **quy luật Pareto trên lưới 30 m**: `Cấp độ B1` chỉ cần can thiệp trên `50%` số đoạn sông (`41/82` đoạn có bề rộng đo trực tiếp $\ge 2$ pixel) nhưng đã thu hồi tới **`91,64%` diện tích mặt nước** và **`96,12%` tổng thể tích đào** của toàn bộ 3 hệ thống sông. Do đó, `Cấp độ B1 (41 đoạn)` được lựa chọn làm cấu hình tối ưu cho mô phỏng thủy lực mở rộng.*
> - *Trên tất cả 45 kịch bản tổ hợp (5 cấp độ × 3 mô hình `DHG-1/2/3` × 3 biên độ `LOW/CENTRAL/HIGH`), số ô lưới vi phạm ngưỡng `minmask = -4,0 m` đều bằng **`0`**, cao độ đáy thấp nhất luôn $\ge -3{,}50\text{ m}$, và công trình đầu mối Đập Đồng Cam (`187` ô) được bảo toàn nguyên vẹn 100%."*
