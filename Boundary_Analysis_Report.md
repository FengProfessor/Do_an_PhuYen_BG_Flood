
# Phân tích ranh giới False Negative V38

## 1. Phương pháp
- Đọc file DEM, SAR, và kết quả mô phỏng V38 (nc).
- Đồng bộ hệ tọa độ và lưới (resampling) về cùng shape của DEM.
- Phân loại: Sim Water (h > 0.1m) và SAR Water (SAR > 0).
- Xác định False Negative (FN): Vùng có SAR nhưng không có Sim Water.
- Dùng `scipy.ndimage.binary_dilation` để tìm ranh giới tiếp giáp giữa Sim Water và FN.

## 2. Kết quả rà quét
- Thời gian xử lý: 12.13 giây
- Tổng số pixel False Negative: 163202
- Số pixel ranh giới tiếp giáp: 25798

### Phân tích cao độ
- Cao độ DEM trung bình tại ranh giới: 17.46 m
- Mực nước trung bình tại vùng lân cận: 20.93 m
- Số điểm ranh giới là vật cản (DEM cao hơn mực nước lân cận): 2827

## 3. Đề xuất kịch bản V39
Dựa trên các vị trí vật cản (boundary_mask có DEM > mực nước), đề xuất "khoét" (breach) DEM tại các vị trí này xuống thấp hơn mực nước trung bình khoảng 0.5m để tạo kênh dẫn nước vào vùng False Negative, vì trên thực tế nước từ SAR đã vào được vùng này.
