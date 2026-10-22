# V45 — Truy nguồn cảnh Sentinel-1 quanh 30/11/2021 (hạ lưu sông Ba / Phú Yên)

**Ngày tra cứu:** 28/09/2026. **Phạm vi:** nghiên cứu sidecar, chỉ đọc dữ liệu tại `D:/VTP` và truy vấn catalog chính thức. **Đối tượng cần giải nghĩa:** `D:/VTP/05-Du-lieu-GIS/DakLak_PhuYen_FloodExtent_Otsu_20211130_05h36.tif`. Không thực hiện truy vấn Earth Engine có xác thực, tải ảnh SAR, xử lý ảnh hay chạy mô hình.

## Kết luận theo mức chứng cứ

1. **Đã xác minh trong catalog ASF:** cảnh Sentinel-1A IW GRD HD `S1A_IW_GRDH_1SDV_20211129T223638_20211129T223703_040792_04D7A0_7891` thu nhận **2021-11-29 22:36:38–22:37:03 UTC**, tức **2021-11-30 05:36:38–05:37:03 ICT (UTC+7)**. Footprint của cảnh này bao phủ **điểm truy vấn 109.25°E, 13.05°N** ở khu vực hạ lưu sông Ba. Vì vậy thời điểm bắt đầu của một cảnh thực có độ khớp đến phút với chuỗi `20211130_05h36` **nếu chuỗi đó là giờ Việt Nam**.
2. **Đã xác minh trong catalog ASF:** một lát GRD liền kề cùng datatake, `S1A_IW_GRDH_1SDV_20211129T223703_20211129T223728_040792_04D7A0_E47F`, thu nhận **22:37:03–22:37:28 UTC** (= **05:37:03–05:37:28 ICT ngày 30/11**). Cảnh này giao hộp tìm kiếm rộng nhưng **không** được truy vấn điểm nói trên trả về; là ứng viên khi xét sản phẩm ghép/phạm vi rộng, không có bằng chứng nó được sử dụng trong TIFF.
3. **Chưa xác minh liên kết đến TIFF:** không có ID sản phẩm Sentinel-1, giờ chụp, pass hay tên ảnh GEE trong metadata GeoTIFF được ghi ở hồ sơ provenance hiện có. `05h36` **có khả năng biểu thị ICT cao hơn UTC theo đối chiếu catalog**, nhưng chưa thể xác nhận quy ước đặt tên hoặc cảnh thực sự sinh ra TIFF. Cũng chưa biết ảnh là một lát, mosaic nhiều lát, ảnh tổ hợp nhiều ngày, hoặc tên gắn theo thời gian xuất ảnh.

**Quy tắc sử dụng cho V45:** ghi `filename_clock_timezone = unverified`; ghi **cảnh ASF khớp không gian/thời gian** riêng với **nguồn TIFF chưa chứng minh**. Không sử dụng CSI hoặc tên file để chọn timezone hay khẳng định khớp thời điểm quan sát.

## 1. Nguồn sơ cấp và cách hiểu thời gian

- [ASF Search API — tham số catalog](https://docs.asf.alaska.edu/api/keywords/): `start`/`end` là **UTC**; truy vấn hỗ trợ `bbox`, `intersectsWith`, `dataset`, `beamMode`, `processingLevel`, `output=geojson`. [ASF API basics](https://docs.asf.alaska.edu/api/basics/) mô tả endpoint `/services/search/param`.
- [Copernicus / ESA SentiWiki — Sentinel-1 products và naming](https://sentiwiki.copernicus.eu/web/s1-products): tên SAFE chứa mode, GRD, phân cực, thời điểm bắt đầu/kết thúc, quỹ đạo tuyệt đối và datatake; IW được cắt thành các lát khoảng 25 giây. **Tên TIFF đã xuất không theo chuẩn định danh SAFE** và không đủ để suy ra nguồn.
- [Google Earth Engine — `COPERNICUS/S1_GRD`](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD) và [hướng dẫn Sentinel-1](https://developers.google.com/earth-engine/guides/sentinel1): GEE cung cấp các thuộc tính `instrumentMode`, `transmitterReceiverPolarisation`, `orbitProperties_pass`, `relativeOrbitNumber_start` và ảnh GRD đã hiệu chỉnh.
- [GEE `ee.Image.date()`](https://developers.google.com/earth-engine/apidocs/ee-image-date): thời gian thu nhận lấy từ `system:time_start`. [GEE `filterDate`](https://developers.google.com/earth-engine/apidocs/ee-imagecollection-filterdate) lọc theo thuộc tính đó, đầu mút cuối loại trừ. [GEE `ee.Date.format`](https://developers.google.com/earth-engine/apidocs/ee-date-format): mặc định UTC; muốn thể hiện giờ Việt Nam phải chỉ định `Asia/Ho_Chi_Minh`.

## 2. Truy vấn thực sự đã chạy và kết quả

Truy vấn **chỉ đọc** qua PowerShell `Invoke-RestMethod` tới ASF Search API ngày 28/09/2026. Các URL dưới đây chứa đầy đủ tham số, có thể mở lại và nhận GeoJSON. Chọn hộp bao địa lý thăm dò `108.8,12.6,109.6,13.5` (lonMin,latMin,lonMax,latMax), điểm thăm dò `POINT(109.25 13.05)` và khoảng UTC `[2021-11-29T00:00:00Z, 2021-12-02T00:00:00Z]`. Đây là **AOI nghiên cứu**, không phải polygon xuất ảnh gốc của dự án.

**Q1 — Hai lát IW GRD HD giao hộp tìm kiếm:**

`https://api.daac.asf.alaska.edu/services/search/param?dataset=SENTINEL-1&processingLevel=GRD_HD&beamMode=IW&bbox=108.8,12.6,109.6,13.5&start=2021-11-29T00:00:00Z&end=2021-12-02T00:00:00Z&maxResults=100&output=geojson`

**Kết quả:** `features.Count = 2`. Cả hai: platform `Sentinel-1A`; `IW`; `GRD_HD`; VV+VH (`1SDV`); `DESCENDING`; ASF `pathNumber=120`; absolute orbit `040792`; datatake `04D7A0`.

| Nhãn chỉ dành cho nghiên cứu | Tên sản phẩm ASF đã xác minh | Acquisition UTC (start–stop) | Giờ Việt Nam ICT (start–stop) | Mức khớp địa lý |
|---|---|---|---|---|
| Cảnh A | `S1A_IW_GRDH_1SDV_20211129T223638_20211129T223703_040792_04D7A0_7891` | 29/11 22:36:38–22:37:03 | 30/11 05:36:38–05:37:03 | ASF trả về khi lọc đúng điểm hạ lưu thăm dò |
| Cảnh B | `S1A_IW_GRDH_1SDV_20211129T223703_20211129T223728_040792_04D7A0_E47F` | 29/11 22:37:03–22:37:28 | 30/11 05:37:03–05:37:28 | Giao bbox rộng; không có trong kết quả lọc điểm |

**Q2 — Xác nhận footprint tại điểm thăm dò:**

`https://api.daac.asf.alaska.edu/services/search/param?dataset=SENTINEL-1&processingLevel=GRD_HD&beamMode=IW&intersectsWith=POINT%28109.25%2013.05%29&start=2021-11-29T00:00:00Z&end=2021-12-02T00:00:00Z&maxResults=100&output=geojson`

**Kết quả:** `features.Count = 1`, chỉ cảnh **A**. Đây là kiểm tra bằng chỉ mục hình học của ASF; điểm đại diện không thay thế việc đối chiếu toàn bộ polygon vùng đánh giá.

**Q3 — Đối chứng không giới hạn processing level, vẫn chỉ IW trong bbox và khoảng UTC như trên:**

`https://api.daac.asf.alaska.edu/services/search/param?dataset=SENTINEL-1&beamMode=IW&bbox=108.8,12.6,109.6,13.5&start=2021-11-29T00:00:00Z&end=2021-12-02T00:00:00Z&maxResults=200&output=geojson`

**Kết quả:** 14 feature, gồm hai lát ở trên với các bản GRD, metadata GRD, SLC, RAW, OCN và metadata tương ứng; tất cả thuộc lần bay khoảng **22:36–22:37 UTC ngày 29/11**. **Không trả về một cảnh IW có thời gian thu nhận 05:36 UTC ngày 30/11** trong AOI/thời đoạn/bộ lọc này. Kết quả âm tính có phạm vi giới hạn: không khẳng định tất cả chế độ SAR hoặc mọi vùng ngoài bbox đều không có dữ liệu.

Các mốc UTC được kiểm tra trực tiếp ở thuộc tính `startTime` của JSON ASF (`2021-11-29T22:36:38Z` và `2021-11-29T22:37:03Z`); không suy ra UTC từ thiết lập múi giờ hiển thị của hệ điều hành.

## 3. Provenance nội bộ đã xem (read-only)

- `D:/VTP/V45_runs/20260928_engine_r1/results/V45_SAR_provenance.json` (tạo lúc 20:19 ICT, 28/09/2026) ghi nhận TIFF gốc `1911 × 2402` px, `EPSG:32649`, pixel `90 × 90 m`, band description `VV`, SHA-256 `74599050bcfa20aaddca4ea716bc83edba8715cdd829b6cc2f2a3b24182808b9`; `potential_scene_identity_or_time_fields` rỗng; `original_sentinel_product_id_verified=false`; `original_acquisition_utc_verified=false`. Bản TIFF trong `05-Du-lieu-GIS/DoAn_Flood_Data/DoAn_Flood_Data/` được JSON này báo là trùng byte. **SHA-256 TIFF gốc đã được kiểm tra lại bằng `Get-FileHash` và khớp**; bản sao chỉ được đối chiếu qua báo cáo provenance hiện có.
- `D:/VTP/05-Du-lieu-GIS/README-tro-den-du-lieu.md` ghi kế hoạch dùng Sentinel-1 GRD qua GEE và Otsu động + SNIC, **không** định danh cảnh hay chứng minh bộ lọc/thuật toán đã dùng khi xuất chính TIFF này. Danh sách tệp GIS tìm thấy TIFF, ASC và bản TIFF sao, không thấy metadata sidecar Sentinel-1 tương ứng.
- `D:/VTP/BG_Flood_Project/BG_Flood/eval_v44.py` dùng frame 33 = 102 h để so với SAR, và `D:/VTP/V45_Ke_hoach_trien_khai.md` mô tả cách hiểu GMT+7. Ngược lại, `D:/VTP/BG_Flood_Project/BG_Flood/Teamwork_Validation/compare_v39_multisource.py` và `D:/VTP/Bao_Cao_Tong_Ket_V38.md` ghi `05:36 UTC`. Đây là **các nhãn/giả định trong mã và báo cáo**, không phải chứng cứ gốc về giờ cảm biến.
- Quét nội dung mã/tài liệu văn bản (`*.py`, `*.js`, `*.json`, `*.md`, `*.txt`) trong `D:/VTP` tìm thấy nhiều tệp **đọc/sử dụng** raster Otsu nhưng chưa nhận diện được script GEE xuất ảnh hoặc manifest chứa image ID. Phạm vi rà soát này không bao gồm mọi archive, lịch sử GEE hay tài khoản Drive.

## 4. Diễn giải `05h36` và giới hạn

Giả sử epoch mô hình `2021-11-26 00:00:00+07:00` như hồ sơ V45 hiện có:

| Giả thuyết về chuỗi tên | Timestamp UTC tương ứng | Giờ từ epoch mô hình | Quan hệ với kết quả ASF |
|---|---|---:|---|
| `30/11/2021 05:36` là **ICT** | `2021-11-29T22:36:00Z` | `101.6 h` | Gần cảnh A: bắt đầu muộn hơn 38 giây (`101 h 36 m 38 s`) |
| `30/11/2021 05:36` là **UTC** | `2021-11-30T05:36:00Z` | `108.6 h` | Không có cảnh IW tương ứng trong ba truy vấn ASF có giới hạn trên |

Hai giả thuyết lệch **7 giờ**. Bằng chứng catalog ủng hộ mạnh việc **`05h36` là nhãn giờ địa phương của một lần bay có thật**, đặc biệt cảnh A. Tuy nhiên **không thể kết luận TIFF chính là cảnh A**: metadata raster không chứa ID; chưa có script xuất ảnh, GEE task, thông tin threshold/mask/resampling, hoặc dấu vết về mosaic/temporal composite. Ngay cả khi khớp đến phút, thời điểm quan sát của một pixel, lát/ảnh tổng hợp và thời gian đặt tên file vẫn có thể khác nhau. Vì vậy chưa khóa timestamp hiệu chuẩn V45 dựa trên nghiên cứu này.

## 5. Bước tiếp theo để đóng provenance (chưa thực hiện)

1. Khôi phục **GEE Code Editor script**, bản lưu asset hoặc lịch sử `Export.image.*`/Drive đã tạo TIFF. Ghi toàn bộ `COPERNICUS/S1_GRD` image ID, `system:time_start`/`system:time_end` nếu có, `orbitProperties_pass`, `relativeOrbitNumber_start`, `instrumentMode`, polarizations, polygon AOI, phép ghép và các tham số export (`scale`, `crs`, `region`). Đối chiếu mọi ID đó với ASF/ESA và dữ liệu source; **không** lấy tên TIFF thay image ID.
2. Tra cứu GEE **chỉ đọc** trong khoảng `[2021-11-29T00:00:00Z, 2021-12-02T00:00:00Z]` cho polygon đánh giá thực, sau đó lọc IW/VV và đối chiếu ID cảnh A/B. Ví dụ truy vấn metadata (chưa chạy):

   ```javascript
   var point = ee.Geometry.Point([109.25, 13.05]); // Điểm thăm dò; thay bằng AOI thực
   var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
     .filterBounds(point)
     .filterDate('2021-11-29T00:00:00Z', '2021-12-02T00:00:00Z')
     .filter(ee.Filter.eq('instrumentMode', 'IW'))
     .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
     .sort('system:time_start');
   var metadata = s1.toList(s1.size()).map(function(item) {
     var img = ee.Image(item);
     return ee.Feature(null, {
       id: img.id(),
       acquisition_utc: img.date().format("YYYY-MM-dd'T'HH:mm:ss'Z'", 'UTC'),
       acquisition_ict: img.date().format('YYYY-MM-dd HH:mm:ss', 'Asia/Ho_Chi_Minh'),
       orbit_pass: img.get('orbitProperties_pass'),
       relative_orbit: img.get('relativeOrbitNumber_start'),
       absolute_orbit: img.get('orbitNumber_start')
     });
   });
   print(ee.FeatureCollection(metadata));
   ```

3. Với script/manifest gốc, làm rõ ảnh đơn, ghép hai lát cùng datatake hay tổ hợp nhiều thời điểm; ghi phép Otsu/SNIC, các mặt nạ nước thường trực và thủ tục xuất/reproject. Nếu cần xác thực raster, so sánh pixel/footprint với output tái tạo **trong công việc riêng được cho phép**, không sửa ảnh hiện có trong lần nghiên cứu này.
4. Chỉ khi liên kết source → xử lý → TIFF được chứng minh mới chốt thời điểm quan sát và khung thời gian mô hình; nếu thiếu liên kết, tiếp tục ghi nhãn **UTC/ICT unresolved for TIFF**, giữ cả hai giả thuyết timeline và không dùng mức khớp CSI để chọn.
