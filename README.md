# Đồ Án Tốt Nghiệp: Mô Phỏng Ngập Lụt Phú Yên Bằng Mô Hình BG_Flood (CUDA GPU) & Kiểm Chứng Với Ảnh Vệ Tinh Sentinel-1 SAR

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![BG_Flood](https://img.shields.io/badge/Model-BG__Flood%20(GPU%20CUDA)-orange.svg)](https://github.com/FlowConnectivity/BG_Flood)
[![Copernicus](https://img.shields.io/badge/DEM-Copernicus%20GLO--30-blue.svg)](https://spacedata.copernicus.eu/)
[![Sentinel-1](https://img.shields.io/badge/Remote%20Sensing-Sentinel--1%20SAR-success.svg)](https://sentinels.copernicus.eu/)

---

## 📌 Giới Thiệu (Overview)

Repository này chứa toàn bộ tài liệu thuyết minh đồ án tốt nghiệp, báo cáo tiến độ, hệ thống mã nguồn tự động hóa biên soạn văn bản, các kịch bản phân tích - xử lý địa hình số (Hydro-conditioning DEM), kịch bản hiệu chỉnh và kiểm chứng kết quả mô phỏng ngập lụt cho vùng hạ lưu sông Ba, tỉnh Phú Yên (sự kiện lũ lụt lịch sử tháng 11 - 12 năm 2021).

- **Cán bộ hướng dẫn:** TS. Hà Minh Cường (Viện Công nghệ Hàng không Vũ trụ, Trường Đại học Công nghệ – ĐHQGHN)
- **Điểm đánh giá GVHD:** 9.5 / 10

---

## 🔬 Tóm Tắt Khoa Học & Phương Pháp Luận

1. **Mô hình thủy lực 2D BG_Flood (Block-Adaptive GPU Hydrodynamic Modeling):**
   - Vận hành trên môi trường tính toán song song CUDA GPU với lưới độ phân giải cao 30m $\times$ 30m ($2100 \times 2100$ ô lưới, tương đương 4.41 triệu ô).
   - Miền tính bao phủ $63\text{ km} \times 63\text{ km}$ hạ lưu tỉnh Phú Yên từ đập thủy điện Sông Ba Hạ ra biển Đông.
   - Điều kiện biên dòng chảy: Lưu lượng xả lũ thực tế $\sim 11.000\text{ m}^3/\text{s}$ kết hợp dữ liệu lượng mưa ERA5 tái phân tích và bản đồ thảm phủ ESA WorldCover 10m (chuyển đổi hệ số nhám Manning và tổn thất thấm ban đầu / liên tục).

2. **Tiền xử lý & Hiệu chỉnh địa hình số (Hydro-Conditioning DEM):**
   - Nguồn DEM gốc: Copernicus GLO-30 (độ phân giải 30m).
   - Đột phá kỹ thuật: Phát hiện và khắc phục các vật cản dòng ảo (artificial flow obstructions do đê kè, đường cao tốc, công trình trên DEM) bằng thuật toán **Levee Breaching** và **Morphological Carving**, bảo toàn tính liên tục của dòng chảy tràn.

3. **Kiểm chứng không gian bằng ảnh vệ tinh Sentinel-1 SAR:**
   - Dữ liệu Radar khẩu độ tổng hợp Sentinel-1 (C-band, phân cực VV).
   - Quy trình xử lý: Hiệu chỉnh địa hình Range-Doppler, lọc nhiễu speckle bằng bộ lọc Lee, phân ngưỡng tự động Otsu kết hợp mặt nạ nước thường trực Global Surface Water (GSW).
   - Đánh giá định lượng qua các chỉ số CSI (Critical Success Index), Recall, Precision và kiểm chứng phân bố ngập lụt theo mô hình bãi bồi HAND (Height Above Nearest Drainage) đạt mức tương đồng **90.43%**.

---

## 📂 Cấu Trúc Repository

```text
├── Do_an_tot_nghiep_PhuYen_BG_Flood_SAR.docx             # Bản thuyết minh đồ án tốt nghiệp chính thức
├── Do_an_tot_nghiep_PhuYen_BG_Flood_SAR_da_kiem_chung.docx  # Thuyết minh bản đã kiểm chứng
├── Do_an_tot_nghiep_PhuYen_BG_Flood_SAR_V48_bo_sung_20261002.docx # Thuyết minh bản cập nhật V48
├── Bao_cao_Tien_do_v6.docx                               # Báo cáo tiến độ hoàn thiện v6
├── Ban_Nhan_Xet_GVHD_HaMinhCuong.md                      # Bản nhận xét của Cán bộ hướng dẫn (TS. Hà Minh Cường)
│
├── PROJECT.md                                            # Tài liệu kiến trúc mô phỏng, miền tính & hợp đồng giao diện
├── Boundary_Analysis_Report.md                           # Phân tích điều kiện biên thủy văn
├── Danh_gia_ket_qua_V45_va_ke_hoach_V48_20261004.md      # Đánh giá độ nhạy và đối sánh kịch bản
├── Nghien_cuu_do_an_va_co_so_viet_20261005.md            # Tổng hợp cơ sở lý thuyết và tài liệu tham khảo
│
├── build_complete_thesis.py                              # Kịch bản tự động dựng toàn bộ tài liệu thuyết minh
├── main_build_thesis.py                                  # Pipeline hợp nhất các chương đồ án
├── thesis_front_matter.py                                # Biên soạn bìa, lời cam đoan, mục lục, ký hiệu
├── thesis_introduction.py                                # Biên soạn Chương Mở đầu
├── thesis_chapter1.py                                    # Biên soạn Chương 1: Tổng quan nghiên cứu & cơ sở lý thuyết
├── thesis_chapter2.py                                    # Biên soạn Chương 2: Dữ liệu & Phương pháp nghiên cứu
├── thesis_chapter3.py                                    # Biên soạn Chương 3: Kết quả mô phỏng & Đánh giá kiểm chứng
├── thesis_conclusion_refs.py                             # Biên soạn Kết luận, Kiến nghị & Danh mục tài liệu tham khảo
│
├── v46_*.py                                              # Các kịch bản hiệu chỉnh thủy văn V46 (hydro-conditioning)
├── v47_*.py                                              # Các kịch bản phân tích độ nhạy topology & lineage audit
├── v48_*.py                                              # Quy trình đóng băng mô hình V48, đối soát vệ tinh Sentinel-1 RTC
├── stats_v37.py / plot_v37_sar.py                        # Trực quan hóa và trích xuất chỉ số đối sánh viễn thám
└── .gitignore                                            # Cấu hình bỏ qua dữ liệu raster GIS khổng lồ và kết quả chạy GPU (>35GB)
```

---

## ⚙️ Hướng Dẫn Cài Đặt & Sử Dụng

### 1. Môi trường yêu cầu
- **Hệ điều hành:** Windows 10/11 64-bit hoặc Linux Ubuntu 20.04+
- **Python:** $\ge 3.10$
- **Thư viện Python cần thiết:**
  ```bash
  pip install numpy scipy rasterio geopandas shapely matplotlib docx-python python-docx requests
  ```
- **Mô phỏng thủy lực (tùy chọn):** Card đồ họa NVIDIA hỗ trợ CUDA để chạy solver BG_Flood.

### 2. Biên soạn và tái tạo tài liệu đồ án
Để biên soạn tự động văn bản đồ án sang file `.docx`:
```bash
python main_build_thesis.py
# hoặc
python build_complete_thesis.py
```

### 3. Kiểm tra và đối soát kết quả viễn thám SAR
```bash
python v48_sar_observation_validate.py
python v48_verify_frozen.py
```

---

## 📜 Trích Dẫn & Bản Quyền

Đồ án tốt nghiệp thực hiện tại Trường Đại học Công nghệ – Đại học Quốc gia Hà Nội (VNU-UET).
Toàn bộ mã nguồn và tài liệu phục vụ mục đích nghiên cứu học thuật. Vui lòng trích dẫn nguồn khi tái sử dụng phương pháp hoặc mã nguồn.
