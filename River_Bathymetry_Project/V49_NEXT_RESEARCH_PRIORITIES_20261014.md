# V49 — nghiên cứu có thể làm trước lần chạy dài tiếp theo

Ngày: 14/10/2026. Run hiện hành đã bị ngắt do mất điện; đây là kế hoạch ưu tiên nghiên cứu/kiểm thử, không phải các hạng mục đã triển khai hay một quyết định Gate G.

**Ưu tiên:** kiểm tra hai hotspot từ dữ liệu cứu được và chuẩn bị checkpoint có kiểm thử; đồng thời tiếp tục bằng chứng forcing/geometry/quan trắc. Có thể làm phần lớn trên CPU, dữ liệu tĩnh và thí nghiệm ngắn.

| Thứ tự | Câu hỏi cần giải quyết | Công việc độc lập với run 120 giờ | Sản phẩm và điều kiện kết thúc |
|---|---|---|---|
| 1 | Vì sao nghiệm CENTRAL/BASE tách mạnh ở điểm ngoài vùng carving? | Trích cửa sổ DEM/độ dốc, h/zs/u/v và ngữ cảnh thủy vực tại hai hotspot; xác định các transition đã ghi; thiết kế phép thử ngắn về timestep/wet-dry với biên và trạng thái đủ xác định | Hồ sơ từng địa điểm, các giả thuyết có thể kiểm tra, trace thí nghiệm ngắn. Không kết luận nguyên nhân từ 11 snapshot thưa |
| 1 | Làm sao bảo toàn tiến độ khi process/nguồn điện bị ngắt? | Thiết kế loader/checkpoint ở ranh giới full-step; giữ đúng precision, cả hai cum_infilt, loop/mesh/observer và hash; thử tiến trình bị ngắt sau commit | Một release riêng có checkpoint và phép so interrupted/restarted với uninterrupted. Chưa gọi exact nếu chỉ đạt tolerance; chưa có implementation hiện hành |
| 2 | Mưa x2 và bốn Q đầu vào đại diện đúng vùng/thời gian nào? | Đối chiếu epoch/interval từng nguồn; footprint trung bình diện tích; lập sơ đồ vùng góp nước của Q so với rain-on-grid; thu raw trạm hoặc dữ liệu nhà cung cấp có provenance | Forcing register với nguồn/units/timing/footprint và bảng bất định; không tự đổi x2 thành x1 từ một tổng đối chứng |
| 2 | Các phase C/C.1/B/D/F còn thiếu bằng chứng ở đâu? | Xếp hạng 29 UNKNOWN, 43 mục review, 7 object thiếu graph support và 9 major persistent omissions; nghiên cứu tại chính object; đối chiếu bridge/culvert, reservoir controls, ảnh có ngày và khảo sát | Hồ sơ object/reach có nguồn, geometry, niên đại, datum khi cần. Không tự cấp quyền carve từ việc nhận dạng một polygon nước |
| 3 | Thuật toán drainage/terrain nào tốt hơn tại các vùng đã xác định? | Benchmark breach/fill trên khu vực nhỏ; đánh giá outlet, sink tự nhiên, độ biến dạng và crossing đã xác minh; so DEM ứng viên trong nhánh riêng | Bảng benchmark và candidate có mask/giới hạn/provenance rõ. Thay drainage DEM không tự cải thiện BG_Flood nếu hydraulic input không đổi |
| 3 | Làm sao kiểm định mô hình ngoài một ảnh ngập đã từng xem? | Chuẩn bị bằng chứng H/Q/HWM nối datum và ảnh chưa dùng phát triển; giữ phép so Sentinel chính, bổ sung vùng quanh reach theo ranh khai báo trước | Observation register, quy tắc ghép thời gian/miền quan sát và báo cáo đánh giá nhiều đại lượng; không chỉ dùng CSI hoặc tổng diện tích |

## Dữ liệu đã có để bắt đầu ngay

- [11 frame đã cứu và phân tích so với BASE](D:/VTP/River_Bathymetry_Project/V49_POWERLOSS_RECOVERY_AND_FINDINGS_20261014.md): tới giờ 33, chưa có frame ở giờ SAR 101,614. Max speed 20,45 m/s xuất hiện trong cả hai arm; max khác biệt mực nước khung cuối khoảng 0,55 m nằm cách reach chỉnh gần nhất khoảng 16,72 km. Đây là mục tiêu chẩn đoán, chưa chứng minh lỗi hoặc lợi ích carving.
- [Kiểm toán restart từ source](D:/VTP/River_Bathymetry_Project/V49_POWERLOSS_RESTART_FEASIBILITY_20261014.md): parser có hotstartfile nhưng đường khởi tạo không nạp checkpoint; output float32 thiếu trạng thái solver float64 và hai bản đồ thấm.
- [Forcing/CHIRPS/mask nghiên cứu ngày 14/10](D:/VTP/River_Bathymetry_Project/V49_CONTINUED_RESEARCH_20261014.md): phép đối chiếu ERA5 cùng UTC và dữ liệu CHIRPS pentad có provenance; CHIRPS pentad chưa được xác minh trùng cửa sổ giờ của model.
- [Tồn đọng R3 từng phase](D:/VTP/River_Bathymetry_Project/V49_R3_UNPASSED_REMEDIATION_20261013.md): các count object/reach giữ nguyên; phần progress RUNNING trong tài liệu đó là snapshot cũ ngày 13/10, không phải trạng thái hiện hành.

## Cơ sở khoa học và giới hạn

[USACE về khởi tạo 2D](https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.6/boundary-and-initial-conditions-for-2d-flow-areas/initial-conditions) phân biệt initial WSE, restart và ramp-up/warm-up. Đây là tham khảo phương pháp, không chứng minh BG_Flood cục bộ đã có những chức năng đó. Kiểm toán mã cục bộ mới xác định khả năng thực thi hiện tại.

[CHC mô tả CHIRPS v3](https://www.chc.ucsb.edu/data/chirps3) cho biết daily rnl dùng ERA5 phân bố tổng pentad, daily sat dùng IMERG Late và daily date labels không đồng nhất cửa sổ đo của mọi trạm. Vì vậy phải kiểm dependence/time support trước khi gọi một sản phẩm đối chứng độc lập hoặc dùng làm forcing giờ.

[Stephens et al. 2014](https://research-information.bris.ac.uk/en/publications/problems-with-binary-pattern-measures-for-flood-model-evaluation/) cho thấy binary flood metrics phụ thuộc quy mô trận/địa hình và có thể thiên lệch. Suy luận áp dụng cho V49: đọc CSI cùng FP/FN, timing, coverage và quan trắc cao độ phù hợp; tổng diện tích gần nhau chưa đủ chứng minh đúng vị trí hay đúng đáy.

Chưa cần chạy thêm một bộ 120 giờ để làm các việc trên. Các thí nghiệm mới phải giữ nguồn, ranh vùng, điều kiện biên, biến thay đổi và trạng thái đủ xác định; không ghép budget ở giờ 35,4 thành checkpoint không gian ở giờ 33. Những hạng mục trong bảng là công việc tiếp theo được đề xuất, chưa thực hiện trong lượt lập ưu tiên này.
