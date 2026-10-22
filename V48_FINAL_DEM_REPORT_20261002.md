# V48 — DEM chuẩn đã khóa trước Sentinel-1

**Ngày khóa:** 02/10/2026  
**Trạng thái:** `V48_CONDITIONED_FROZEN_PRE_SAR_RELEASE`

## Kết quả cuối

- Base chính thức: `PhuYen_DEM_30m_V48_BASE_COPERNICUS.tif`, byte-identical với `PhuYen_DEM_30m.tif` gốc Copernicus.
- DEM dùng cho mô hình: `PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.tif`.
- Bản ASC cho BG_Flood: `PhuYen_DEM_30m_V48_CONDITIONED_FROZEN.asc`.
- Final conditioning: **40 components / 55 cells**.
- Cut depth: min **0.005 m**, median **0.586 m**, max **0.974 m**.
- Cut volume raster: **25565.4 m³**.

## Rule chọn cuối

Một component chỉ được vào V48 nếu đồng thời:

1. baseline topology class = `AUTO_APPROVE_STRICT`;
2. vẫn strict trong cả **7/7 topology-cap configurations**;
3. vẫn strict khi **JRC bị hold out hoàn toàn khỏi topology gate**;
4. mọi Tier-A candidate cell của component sống **>=9/11 candidate sensitivity configurations**;
5. không dùng Sentinel-1 2021 trong candidate, topology, threshold hay cut selection.

Từ 47 strict baseline, giao cuối còn **40 components**.

## Các phép biến đổi không có trong V48 frozen

- Không global Priority-Flood trên DEM cuối.
- Không epsilon eastward ramp.
- Không clip các cao độ âm của Copernicus.
- Không kế thừa V39 Safe, V41, V44, V45 hoặc 38 cut V46.
- Không tune theo CSI/Recall/Precision của Sentinel-1.

## Verification

Independent verifier: **PASS**.

- Changed mask exact: `True` (55/55 cells).
- Grid/CRS/nodata preserved: `True`.
- All changes lowering: `True`.
- Max final cut: **0.974 m**.
- All frozen cell values match selected proposals: `True`.
- ASC vs frozen GeoTIFF max abs diff: **0.000000 m**.

## SHA-256 khóa release

- Base: `0c3c6ca6f299b00dd22a91a26c66e8c784f0e70c445412216f01efdd76504508`
- Frozen GeoTIFF: `f47dfc68bdc70d7f2107b11e538832ca3e4f9788c92667e6fbb761cbfec8ad0e`
- Frozen ASC: `e323dc1fc6e24dcc28c59e8d118c0814a644e39769edcaf0596dcf9cac0b9aa9`

## Quy tắc sau freeze

Sentinel-1 2021 từ đây chỉ được dùng để **validation**. Không sửa lại `V48_CONDITIONED_FROZEN` dựa trên kết quả SAR. Nếu cần thử chỉnh theo SAR, phải tạo một nhánh exploratory/version khác để không phá independent validation.
