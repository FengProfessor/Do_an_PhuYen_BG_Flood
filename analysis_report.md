# Kết quả phân tích Hạ lưu Sông Ba - V44

## 1. Trích xuất cao độ và mực nước tại mặt cắt hạ lưu (X = 314955, Tuy Hòa)
Tôi đã thực hiện trích xuất mặt cắt ngang từ NetCDF (PhuYen_30m_V44.nc) tại Frame 33 (102h). Kết quả tại khu vực tiếp giáp bờ sông:

| Tọa độ Y (m) | Cao độ bờ/đáy (zb) | Mực nước sông (zs) | Độ sâu (h) | Ghi chú |
|-------------|--------------------|--------------------|------------|---------|
| 1442495     | 5.29 m             | 6.59 m             | 1.30 m     | Lòng sông sát bờ |
| **1442465** | **8.36 m**         | **-**              | **0.00 m** | **Đê kè/Bờ sông** |
| 1442435     | 9.40 m             | -                  | 0.00 m     | Bãi bồi / Đê |

**Phân tích:** 
Mực nước trong sông tại đỉnh lũ đạt 6.59m. Trong khi đó, cao độ đê ngay sát đó là 8.36m (Thậm chí kiểm tra DEM gốc V41, điểm này cao 9.75m). Nước **không thể** vượt qua bức tường thành chênh lệch 2-3 mét này.

## 2. Giải đáp các thắc mắc của Sếp

1. **Có phải ta đục đê 2m là chưa đủ sâu để chạm mực nước sông?**
   - **ĐÚNG, nhưng chưa đủ ý.** Đê ở Tuy Hòa cao hơn mực nước sông từ 2-3m. Việc chỉ hạ 2m (nếu có hạ) thì từ 9.75m xuống 7.75m vẫn cao hơn mực nước lũ 6.59m, nước không thể tràn qua. 

2. **Hay do file cấu hình xa_lu_BaHa.txt có vấn đề?**
   - **KHÔNG.** Mực nước trong sông Ba dâng lên rất cao (độ sâu h > 3-4m, zs ~ 6.6m), lưu lượng hoàn toàn đủ mạnh. Nước đã đầy ắp lòng sông nhưng bị khóa chặt bởi địa hình.

3. **Hay do bờ sông có quá nhiều đê kè nhân tạo khác chưa được đục?**
   - **ĐÚNG, và nguyên nhân sâu xa đến từ thuật toán đục đê (reach_levees_v44.py)**. 
   - Script V44 sử dụng điều kiện arrier_mask = sar_flood & plain_mask & .... Nghĩa là nó **chỉ đục những điểm mà ảnh vệ tinh SAR báo là có nước**.
   - **Lỗi logic:** Đê/Kè nằm nhô cao lên khỏi mặt nước, nên vệ tinh SAR *không nhận diện đê là nước* (sar_flood = False). Kết quả: Thuật toán V44 đã bỏ qua hoàn toàn các bờ đê này và không hề đục chúng! Điểm đê (Y=1442465) có V41 = 9.75m và V44 = 9.75m, tức là không bị hạ 1cm nào.

4. **Hay do Infiltration hút hết nước trước khi nó lan ra?**
   - **KHÔNG.** Vì đê chưa bị chọc thủng, nước chưa tràn vào bãi (h=0) nên không có nước để mà thấm. 

## 3. Đề xuất phương án cho V45 (Morphological Carving)

Vì vệ tinh SAR không thể bắt được đỉnh đê, ta không thể dùng sar_flood làm điều kiện chọn đê. Để nước lan ra bãi bồi V45, ta cần **Gỡ bỏ hoàn toàn địa hình hai bên bờ (Erase Levees)** bằng thuật toán hình thái học (Morphological Carving):

**Giải pháp đề xuất (Sử dụng Python/Rasterio cho V45):**
1. **Detect River Network:** Xác định lòng sông chính bằng cách lọc các vùng trũng (vd: DEM < 5m) hoặc dựa vào file shapefile sông.
2. **Buffer / Dilation:** Phóng to (dilate) lòng sông ra hai bên khoảng 3-5 pixel (90m - 150m). Vùng buffer này chính là vùng chứa đê/kè nhân tạo.
3. **Erase & Smooth:** Trong vùng buffer này, hạ toàn bộ các cell có cao độ cao hơn mặt bãi bồi lân cận (hoặc gán trực tiếp bằng cao độ nội suy từ bãi bồi ~3-4m). 
4. **Đục kênh dẫn (Channeling):** Kẻ một số "tuyến rạch" (polyline) nối từ sông vào các vùng trũng của bãi bồi, dọc theo các cống xả thực tế, và burn (ép) cao độ các tuyến này xuống mức 3.0m để đảm bảo nước chảy qua.

Thuật toán này sẽ "ủi phẳng" đê thay vì chỉ gọt 2m, đảm bảo nước từ sông sẽ tràn tự do ra vùng ngập vệ tinh.
