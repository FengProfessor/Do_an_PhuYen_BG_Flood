# V45 — Nhật ký bằng chứng và quyết định triển khai

**Thời điểm:** 28/09/2026, 20:24 ICT  
**Phạm vi:** workspace R1 cô lập `D:/VTP/V45_runs/20260928_engine_r1`; chỉ tóm tắt bằng chứng đã đo, giả định và lý do chọn bước tiếp theo. Đây là nhật ký kiểm toán có thể kiểm tra, không phải nội dung suy nghĩ nội bộ.

## Câu hỏi và phương pháp

1. Raster SAR xuất cục bộ có chứng minh thời điểm quan trắc không? Đọc rasterio metadata/namespaces, so hai SHA256 và kiểm scene/time tags bằng `tests/audit_v45_sar_metadata.py`.
2. Nguồn khí tượng/thủy văn có thể khóa cho ca khoa học 120 giờ chưa? Đăng ký các bằng chứng gốc cần có trong `work/V45_science_evidence.json`, dùng `tests/science_gate_v45.py --profile r1a_120h` để tổng hợp trạng thái.
3. Bản mã/input kỹ thuật hiện tại có dấu mốc tái lập nào? Chạy `tests/preflight_v45.py` trên workspace R1, ghi manifest nguồn/config/test/ASC.

## Quan sát, giả định và quyết định

| Quan sát hoặc giả định | Giới hạn bằng chứng | Quyết định có thể kiểm tra |
|---|---|---|
| Hai TIFF SAR 1911 × 2402, 90 m, EPSG:32649, band `VV` trùng SHA256 `74599050bcfa20aaddca4ea716bc83edba8715cdd829b6cc2f2a3b24182808b9` | Không có scene ID hoặc acquisition UTC trong metadata xuất | Truy Sentinel-1 product gốc và lineage trước khi cố định observation time. |
| `t0=2021-11-26 00:00 ICT` chỉ là giả định; tên `20211130_05h36` có thể cho 101,6 h nếu ICT, 108,6 h nếu UTC | Không biết giờ trong tên file, t0 forcing hay cách ghép mask | Chưa chọn frame hay tính CSI theo hai số này. |
| Mưa V34 = 2 × V23 theo file và mã cục bộ; header Q V43 ghi `Real Data x1.25` nhưng chưa có nguồn gốc | Biến đổi nội bộ chưa chứng minh hiệu chỉnh vật lý/quan trắc | Chỉ dùng forcing hiện có cho smoke đã báo cáo, chưa chốt R1a khoa học. |
| DEM V45 nháp hạ 41.907 ô, hạ cực đại 171,669 m; SAR 90 m | Thiếu khảo sát crest/cửa/mặt cắt, datum; ảnh 90 m không phân giải chi tiết công trình | Giữ V45 ở trạng thái nháp; chỉ thiết kế địa hình sau khảo sát độc lập. |
| Checkpoint GPU toàn miền 20 s đã được kiểm; tiếp tục 20→60 s chưa chạy | Thao tác tương đương bị xét duyệt tự động từ chối trước đó | Giữ blocker restart mở; không suy từ nghiệm synthetic sang toàn miền. |
| Science gate R1a báo 11 blocker | Sổ bằng chứng chủ yếu `missing`/`unverified`; cờ `ready` không thay thẩm định khoa học | Hoàn thiện A2/B5 và restart trước khi chạy R1a 120 giờ. |

## Trạng thái và các tệp kiểm toán

- Technical preflight: exit 0; 81 tệp phân biệt/89 mục; năm ASC cùng grid 2100 × 2100. `results/manifest_preflight.json` SHA256 `ae08d4ac9ab894d79348df4f640d85922183206365ad1fb66b83e070d58cfda9`.
- SAR audit: `results/V45_SAR_provenance.json` SHA256 `b1b1b4f19c06bc865e3380b7b1579c2132637aa145f5bc89164b1975032979dc`.
- Evidence registry: `work/V45_science_evidence.json` SHA256 `b4b4e2cb85c287f2e2ba7bc37a97e1ea6a4c11524317dafddfc68ccd28ec523c`.
- Science gate: `results/V45_science_gate_status.json` SHA256 `1036ed458b1b95db749f4d9a88bf287f85e37e22cfd09f21cfc32b2817e52685`; `ready=false`, 11 blocker.

### Danh sách blocker R1a

`era5_raw_16points`, `rain_x2_justification`, `rain_interval_and_epoch`, `banthach_q_original`, `river_epoch_and_network`, `infiltration_il_cl_units`, `initial_stage_and_datum`, `dem_gauge_tide_vertical_datum`, `sar_scene_id_and_acquisition_utc`, `tailwater_and_open_boundary`, `fullgrid_resume_20_to_60`.

**Giới hạn kết luận:** chưa chạy R1a 120 giờ; chưa có CSI V45 được xác minh; chưa chứng minh chính xác vật lý của DEM V45 nháp. Những bước đã chạy và số liệu lịch sử nằm trong báo cáo R1 mục 7.1–7.15; thay đổi Markdown lần này không được tính vào technical manifest.

## Bổ sung 20:43 ICT — nguồn Q V42/V43 và cảnh Sentinel-1 ứng viên

**Cách thu thập.** Đọc AST `D:/VTP/BG_Flood_Project/BG_Flood/generate_banthach_v42.py` bằng `tests/audit_v45_banthach_generator.py`, băm trạng thái file hiện tại, không thực thi generator hoặc phân tích chuỗi số Q. Đối chiếu kết quả truy vấn catalog ASF từ nghiên cứu độc lập trong `D:/VTP/V45_Sentinel1_scene_research_20260928.md`. Cập nhật registry và chạy lại technical preflight, science gate. Nhật ký này ghi các chứng cứ và lý do quyết định triển khai, không thay thế hồ sơ nguồn hoặc kết quả solver.

| Chứng cứ mới | Điều đã chứng minh | Điều chưa chứng minh | Quyết định triển khai |
|---|---|---|---|
| AST generator V42, 6/6 kiểm tra đạt | Hai nhánh nguồn Sông Hinh/Bàn Thạch có fallback Q giả định nếu thiếu file; trục thời gian 0..432000 s bước 3600 s; nội suy giữ endpoint; cộng hai dòng; Q tối thiểu 10 m³/s. | File có tồn tại ở thời điểm tạo V42 hay không, lần chạy nào đã tạo sản phẩm, tính độc lập của hai dòng trong lưu vực. | Truy dữ liệu quan trắc/log và sơ đồ mạng sông; không coi nhãn `Real Data` là xác nhận nguồn. |
| Cả hai file đầu vào và V42/V43 hiện diện, SHA trong audit JSON | Có thể định danh các bản đang lưu. | V43 có được tạo trực tiếp từ V42 hay không, lý do `x1.25`, epoch, phép quy đổi hoặc việc Q Bàn Thạch đã bao gồm Sông Hinh. | Giữ hai cổng `banthach_q_original`, `river_epoch_and_network` chưa đạt. |
| `prep_v34.py` nhân V23 ×2 | Xác nhận quy tắc biến đổi bằng mã nguồn. | Nguồn ERA5/CDS gốc, khoảng tích lũy, 16 điểm, cơ sở khí tượng cho hệ số 2. | Giữ cổng rain x2 và ERA5 mở cho đến khi có chứng từ nguồn. |
| ASF trả về cảnh Sentinel-1A `S1A_IW_GRDH_1SDV_20211129T223638_20211129T223703_040792_04D7A0_7891` cho điểm 109.25E, 13.05N | Cảnh có acquisition 29/11/2021 22:36:38 UTC = 30/11 05:36:38 ICT, phù hợp phút trong tên TIFF nếu tên ghi giờ Việt Nam. | TIFF Otsu có được tạo từ cảnh này hay không; ảnh đơn/ghép/tổ hợp, AOI và workflow GEE, timezone tên file, model t0 đã đối chiếu nguồn hay chưa. | Ghi là ứng viên catalog; truy GEE script/task và image ID trước khi khóa timestamp/mask hay tính CSI. |
| Preflight 86 tệp/94 mục, 5 ASC cùng lưới, exit 0; science gate exit 0 với `ready=false` | Cấu hình/input đã liệt kê có thể băm và kiểm một phần hợp đồng kỹ thuật; 11 blocker được ghi. | Độ đúng vật lý, provenance nguồn, hình học đê, restart GPU toàn miền và hiệu lực mô phỏng 120 giờ. | Tiếp tục A2/B5/restart theo chứng từ; giữ R1a 120 giờ và CSI ở trạng thái chưa hoàn tất. |

**Dấu vết sau cập nhật:** audit generator JSON SHA256 `ec1d3ef4f09f1068e1ca86a112a9642d34009b8ffaf2b9fc3ec4ab51551fa9c7`; ghi chú ASF SHA256 `3802c3b897395183d4f4483b666b37c11fa055084a2f159ab223f215943aa8d2`; registry SHA256 `3c02e80364b4a1fc0124f8ad3d2421e36f2696588d59c764f8b73306aad932a8`; manifest SHA256 `feabe7722be28ff33366af545c0078733335fd59f0f853e7c1a1620ca4449793`; science gate SHA256 `73301bf0ef05db3d597023b787f943898ad9f35055be9e58b07fabca42e164d0`. Báo cáo R1 mục 7.16 và kế hoạch mục 21 chứa diễn giải đầy đủ; các hash cũ ở phần trên là dấu mốc lịch sử.

**Trạng thái mục tiêu:** V45 nháp đã chạy 60 s để xác minh kỹ thuật, nhưng DEM hạ 41.907 ô với độ sâu lớn chưa có hình học đo độc lập. Restart GPU toàn miền 20→60 s trước đó bị hệ thống xét duyệt từ chối, chưa có kết quả. Không tự chạy lại thao tác bị từ chối. Chưa chạy V45/R1a 120 giờ; chưa có CSI V45 được kiểm định. V44 production và toàn bộ raster/forcing hiện có được giữ nguyên.

## Bổ sung sau 21:09 ICT — thử loader forcing và làm mới cổng R1

**Chứng cứ chạy trực tiếp:** bản vá `read_uni_forcing_file` chỉ nằm trong R1 và có hồi quy mới; 16/16 bài riêng và 22/22 bài unit toàn nhóm đạt (CPU, exit 0). Loader nhận hai chuỗi V23/V34, mỗi chuỗi 144 mẫu 0..514800 s; từ chối `rain_v23_era5land.txt` tại dòng 148 vì thời gian giảm từ 514800 xuống 432000 s. Cấu hình R1 V44/V45 đều dùng rainfile V34 x2 có một chuỗi mưa (uniform). Endtime 120 giờ nằm trong trục mẫu, nhưng nguồn, epoch/UTC, tích lũy và hiệu chỉnh ×2 chưa có chứng từ.

**Cổng kiểm soát:** preflight exit 0, 87 file/95 mục, năm ASC 2100×2100; science gate `r1a_120h` exit 0, `ready=false` với 11 blocker. File manifest và gate mới ở R1/results; kiểm toán rain metadata hiện vẫn exit 1 do check tổng bao gồm tệp ERA5-Land lịch sử không hoạt động. Một lệnh chỉ đọc để tìm đường dẫn Q trong manifest bị hệ thống xét duyệt tự động chặn, không có kết quả mới về bốn thủy đồ. Không làm lại thao tác tương đương.

**Quyết định:** giữ bản gốc forcing/DEM và V44 production; phân biệt kiểm thử parser/độ phủ trục mẫu với chứng minh chất lượng dữ liệu và đúng vật lý. Thu CDS request/file ERA5, Q quan trắc và sơ đồ nhánh, chứng từ cao độ/thấm, lineage SAR và khảo sát đê/biên; đối chứng resume GPU toàn miền khi được phép. Mục 7.17 báo cáo R1 chứa lệnh và giới hạn. R1a 120 giờ và CSI V45 vẫn chưa được thực hiện/kiểm định.

## Bổ sung sau 21:33 ICT — đối soát kết quả và quyết định checkpoint

**Quan sát trực tiếp:** verifier V44 và V45 nháp 60 s đều exit 0, mỗi ca ba frame 2100×2100 và 18 bước ledger; residual lớn nhất lần lượt 1,1920928955078125×10^-7 và 2,384185791015625×10^-7 m³. Checkpoint synthetic CPU/GPU và smoke mưa/Q GPU đạt. Preflight exit 0, 87 file/95 mục; science gate R1a exit 0 nhưng `ready=false` với 11 blocker.

**Phân biệt bằng chứng:** verifier checkpoint 20 s theo mã hiện tại exit 1 đúng tại `Code changed: bg_flood/read_forcing.py`. Đối chiếu độc lập xác nhận trong 34 hash mã chỉ một file đổi, cả 10 hash input/config và ba artifact `.npz`/NetCDF/ledger không đổi so metadata. Kết quả kiểm chứng checkpoint trước sửa loader là bằng chứng lịch sử; trạng thái tương thích với mã mới chưa kiểm định. Resume GPU toàn miền 20→60 s chưa thực hiện vì lần yêu cầu trước bị xét duyệt tự động từ chối.

**Quyết định:** lưu nguyên checkpoint; không bypass fingerprint. Giữ 120 h và CSI ở trạng thái chưa chạy/chưa kiểm định, chờ provenance nguồn, hình học/datum/biên, lineage SAR và chứng minh restart. Hai lệnh bổ sung đọc phần cuối tài liệu và hash report trong lượt này bị xét duyệt tự động từ chối; không ghi các hash chưa xác nhận. Báo cáo đối soát đầy đủ: `D:/VTP/V45_runs/20260928_engine_r1/results/V45_R1_Doi_soat_20260928_v6.md`.
