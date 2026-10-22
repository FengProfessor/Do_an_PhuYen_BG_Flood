# Kiểm tra độc lập nguồn primary: river carving V49, mục 2–3

Ngày kiểm tra: 2026-10-13. Miền cần đánh giá: Phú Yên, lưới 30 m.

Tài liệu được review: `D:\VTP\River_Bathymetry_Project\V49_DEM_RIVER_CARVING_RESEARCH_20261013.md`, mục 2–3 và các claim liên quan tới ba công cụ Whitebox. Đây là review nguồn và API; không chạy benchmark, không kiểm tra riêng USGS/MERIT/FABDEM, không xác nhận lại số liệu V49 trong mục 1.

Đã đọc research skill theo yêu cầu; làm việc như agent background, không spawn agent hoặc gửi tin sang chat khác. Chỉ tạo báo cáo này bằng `apply_patch`.

## 1. Claim verdict

| Claim trong tài liệu gốc / cách diễn giải có thể phát sinh | Verdict | Căn cứ và vị trí phân tích |
|---|---|---|
| Complete breaching mất khoảng 87% thời gian filling | **Đúng trong thử nghiệm được trích dẫn** | Chi tiết thống kê, đối chứng và điều kiện ở §2; không phải tỷ lệ cải thiện độ chính xác. |
| Selective/constrained breach có chi phí tương tự filling | **Đúng có điều kiện** | Phụ thuộc mode và constraint; không được bỏ qua trường hợp CB2 chậm hơn rõ rệt (§2). |
| Breach-first phù hợp hơn fill-only cho HydroDEM Phú Yên | **Có cơ sở để đặt giả thuyết; chưa chứng minh thắng tại miền này** | Khuyến nghị tác giả/phần mềm không thay thế bằng chứng tại Phú Yên (§2, §4, §7). |
| TBB prune theo TUCL, ưu tiên sông lớn khi collision | **Được nguồn primary xác nhận** | Tài liệu TBB chính thức; cần giữ cả ý nghĩa D8 pointer (§5). |
| TBB tốt hơn AGREE/FillBurn ở Phú Yên 30 m | **Suy rộng quá mức nếu viết như kết quả đã xác lập** | Đối chứng thực nghiệm là FillBurn; kết quả gần 30 m không cho thấy TBB thắng (§3). |
| Least-cost breach có thể giới hạn trực tiếp độ sâu bằng `max_depth` | **Sai API nếu gán cho BreachDepressionsLeastCost** | `max_depth` thuộc công cụ khác; `max_cost` không phải độ sâu cực đại (§4). |
| BurnStreamsAtRoads chỉ hạ giao sông–đường, tự bảo đảm thông dòng | **Đúng về mục đích; không có bảo đảm vô điều kiện** | Cần hình học, raster và bề rộng phù hợp; có nhánh mã cần lưu ý (§6). |

## 2. DOI 10.1002/hyp.10648: kiểm tra 87% và phạm vi thực nghiệm

Wiley xác nhận Lindsay, *Hydrological Processes* 30(6), 846–857 (2016); online lần đầu 14-08-2015. Abstract nêu **87% thời gian filling**, tức tiết kiệm khoảng 13%, không phải nhanh hơn 87%. [Wiley][hp-wiley]

Trong preprint tác giả, §4/Bảng 2: trung bình **nhân** của tỷ lệ thời gian từng DEM; mỗi thời gian là trung bình 10 lượt, **loại I/O**; đối chứng Wang–Liu, implementation cố gắng tương đồng. [Preprint, PDF tr.15][hp-pdf]

| Mode | Constraint | Thời gian / filling |
|---|---|---:|
| B: complete | Không ràng buộc depth/length | 86,6% |
| SB1 | Depth 20 m | 108,3% |
| SB2 | Depth 20 m, length 100 cells | 107,1% |
| CB1 | Depth 20 m | 127,2% |
| CB2 | Depth 20 m, length 100 cells | 203,2% |

Bộ thử: sáu SRTM DEM, 1/3 arc-second (~30/90 m): Alps, Quebec, British Isles, Amazon, Iberia, Nile; khoảng 52 triệu–938 triệu cells. Máy 3 GHz/8-core, RAM 64 GB; chương trình Go. §2.3 lưu ý isolated pits có thể phù hợp filling; depression thật/sâu cần tránh breach dài/sâu hoặc giữ lại. [§2.3, §3–4, Bảng 1–2][hp-pdf]

**Giới hạn review:** đây chủ yếu là bằng chứng về hiệu năng sink removal. Từ phép thử này không suy ra thời gian chạy V49, độ chính xác BG_Flood, hay bathymetry tại Phú Yên. Các mức 20 m/100 cells là cấu hình thí nghiệm, không phải tham số đã hiệu chỉnh cho dự án. Nhận định “ít biến dạng hơn nên đáng thử” là giả thuyết thiết kế có cơ sở; nhận định “đã tốt hơn V49” thiếu đối chứng địa phương.

## 3. DOI 10.1002/esp.3888: TBB so với FillBurn, không phải phép thử AGREE

Wiley xác nhận Lindsay, *Earth Surface Processes and Landforms* 41(5), 658–668 (2016). [Wiley][esp-wiley]

Case study: một miền 4° × 4° tây nam Ontario; hydrography 1:10.000; bốn watershed; năm DEM từ khoảng 27–800 m. Mạng có sửa thủ công lỗi nối channel heads. Bảng III so sánh **TBB với FillBurn** bằng watershed Kappa/overall accuracy. [PDF, tr.6–8][esp-pdf]

| DEM / độ phân giải tại miền thử | Kappa TBB | Kappa FillBurn | Accuracy TBB / FillBurn (%) |
|---|---:|---:|---:|
| SRTM-1 / ~27 m | 0,952 | 0,953 | 96,51 / 96,59 |
| SRTM-3 / ~80 m | 0,949 | 0,940 | 96,30 / 95,62 |
| GMTED-7.5 / ~200 m | 0,948 | 0,536 | 96,23 / 63,84 |
| GMTED-15 / ~400 m | 0,935 | 0,724 | 95,22 / 79,72 |
| GTOPO-30 / ~800 m | 0,921 | 0,490 | 94,19 / 60,04 |

TBB ổn định hơn khi lưới thô; tại ~27 m, FillBurn nhỉnh rất nhẹ. SRTM-1: TBB 16,64 phút, FillBurn 2,10 phút. Discussion: pruning hữu ích khi hydrography chi tiết hơn DEM. [Bảng III/Discussion][esp-pdf]

**Giới hạn review:** không có benchmark trực tiếp AGREE trong bảng này. Không có kết quả Phú Yên/Copernicus/BG_Flood. Vì vậy, “TBB đáng xem xét khi có collision/adjacency” hợp lý; “TBB tốt hơn AGREE/FillBurn cho Phú Yên 30 m” chưa được chứng minh. Chênh lệch rất nhỏ ở ~27 m cũng không đủ để tuyên bố FillBurn tốt hơn tại Phú Yên.

## 4. BreachDepressionsLeastCost: tham số và các nhầm lẫn cần tránh

Đối chiếu WhiteboxTools open-core ở commit **`3d7c73cf562b6c58d2649c37f570e3e9a90322f2`**, không suy đoán phiên bản đang cài tại V49. Nguồn chính thức khuyến nghị thử least-cost trước filling, đồng thời thừa nhận có trường hợp full filling phù hợp. [Manual][wbt-manual]

### 4.1. Phân biệt hai thuật toán

`BreachDepressions` dẫn Lindsay 2016/hyp.10648; API có `max_depth` (đơn vị z, mặc định vô hạn), `max_length` (cells, vô hạn), `fill_pits`. `BreachDepressionsLeastCost` dẫn Lindsay–Dhun 2015 và các cải tiến sau đó. Không chuyển con số 87% sang least-cost hiện hành. [Nguồn BreachDepressions][wbt-b], [nguồn least-cost][wbt-lc]

### 4.2. Ý nghĩa API

| Tham số | Xác minh / verdict |
|---|---|
| `max_depth` | **Không có** trong signature/parameter parser của least-cost; không dùng như giới hạn độ sâu của công cụ này. |
| `dist` | Số nguyên **cells**, phải cung cấp theo API; không phải mét. Rust đếm bước 8-neighbour, kể cả diagonal. |
| `max_cost` | Tùy chọn; mặc định vô hạn. Ngưỡng **cost tích lũy**, không phải max độ sâu một cell. |
| `min_dist` | Thay đổi công thức cost, do đó thay đổi ý nghĩa số `max_cost`. |
| `flat_increment` | Đơn vị z; bỏ trống sẽ tính tự động. Output least-cost là F64. |
| `fill` | Fill depression chưa giải được; không có ngưỡng “chỉ micro-sinks” trong flag này. |

Các tên/kiểu và `flat_increment`/F64 được kiểm tra trong [Rust least-cost][wbt-lc]; ý nghĩa cost/fill trong [manual, mục BreachDepressionsLeastCost][wbt-manual].

Trong mã thực thi, với độ hạ cần thiết `c` và khoảng cách cạnh `g`: không `min_dist`, cost cộng `c`; có `min_dist`, cộng `g × (c_trước + c_sau)/2`. Nhãn “z units” của `max_cost` không thể hiểu như depth: chế độ sau có cả map-distance, tương ứng z × map-unit. [Công thức manual][wbt-manual], [Rust `new_cost`][wbt-lc]

**Diễn giải cho lưới 30 m:** một bước diagonal dài khoảng 42,4 m; `dist=N` không tương đương trần chiều dài vật lý `N×30 m`. Rust chỉ chặn enqueue ở `length_n <= max_length`; nhánh gặp đích thấp/NoData ở ô kế tiếp không kiểm tra này, nên có thể thêm một bước tới đích. Đây là đọc mã, chưa tái hiện thực nghiệm. [Rust `path_length`, vòng tìm đường][wbt-lc]

### 4.3. Default của Python khác CLI trực tiếp

Python wrapper: `dist` bắt buộc, `max_cost=None`, `min_dist=True`, `fill=True`; wrapper chủ động thêm `--min_dist` và `--fill`. [Signature và dựng args][wbt-py]

Rust CLI: `max_dist=20`, `max_cost=Inf`, `fill_deps=false`, `minimize_dist=false` nếu thiếu flag, dù metadata boolean ghi true. Muốn fill residual khi gọi executable trực tiếp phải truyền `--fill`; không lấy default wrapper làm default CLI. [Rust `run()`][wbt-lc]

**Hệ quả thiết kế:** `fill=False` không đồng nghĩa chỉ hạ DEM: bước đầu least-cost có thể nâng pit về gần láng giềng thấp nhất. Ba công cụ được review không có input preserve-mask trong API đã xem. Vì vậy không thể coi `dist/max_cost/fill` là cơ chế sẵn có bảo vệ reservoir, true sinks, đập/đê hoặc authorized mask. [Rust least-cost][wbt-lc], [các signature][wbt-py]

## 5. TopologicalBreachBurn: tài liệu chính thức và giới hạn tích hợp

Manual GitHub Pages trong tài liệu gốc không có mục TBB. Mã `FillBurn` chính thức chỉ TBB thuộc **Whitebox Toolset Extension (WTE)**; bản bài báo dùng Whitebox GAT. Tài liệu **Whitebox Workflows legacy Pro** truy cập được xác nhận TUCL pruning, ưu tiên tributary lớn và hạn chế nối dòng giữa tributaries. [Mã FillBurn][wbt-fillburn], [manual TBB][tbb-doc]

Theo manual TBB: DEM/vector cùng projection; `snap_distance` phục vụ nối endpoints. Bốn output: stream IDs, DEM, D8 pointer, accumulation. DEM breach giảm dần dọc tributary, đồng thời fill depression ngoài kênh; không dùng decrement cố định. **Chỉ DEM không chứa đủ ràng buộc tributary ID**; tính lại D8/accumulation từ DEM không tái tạo cùng routing. [Manual TBB, outputs][tbb-doc]

**Đánh giá riêng cho V49:** bước “burn → ghi DEM → tính lại D8 chuẩn” không đủ để mặc nhiên kế thừa ưu thế topology được báo cáo cho TBB. Nếu đánh giá implementation tương đương, phải kiểm tra cách lưu/truyền routing constraints và phần mạng bị prune. Độ đúng routing không chứng minh độ đúng cao độ đáy thủy lực.

Ghi chú phiên bản: các URL cũ `whiteboxgeo.com/manual/wbt_book/...` trả lỗi/404 trong lần kiểm tra. Tài liệu legacy Pro dùng ở trên không phải bằng chứng về giấy phép hay API của mọi phiên bản hiện hành; website Whitebox hiện đã giới thiệu Next Gen. Không xác minh executable/extension cài trên máy dự án. [Website chính thức][whitebox-home]

## 6. BurnStreamsAtRoads: preconditions và giới hạn ở 30 m

### 6.1. Hành vi được mô tả chính thức

Input: DEM, vector streams, vector roads, output và `width` (map units). Mô tả thuật toán: đi dọc stream raster khoảng nửa width mỗi phía giao đường, lấy cao độ nhỏ nhất, rồi hạ đoạn cần sửa về mức đó. `width` là bề rộng embankment dùng để xác định **chiều dài burn dọc sông**, không phải độ sâu hay buffer ngang sông. [Manual WhiteboxTools][wbt-manual], [manual Workflows][road-doc]

Không có yêu cầu chính thức trong các mục đã đọc rằng DEM phải depression-free trước; cũng không có cam kết tạo monotonic grade line hay xử lý mọi depression. Mô tả bằng mức minimum có thể để lại flat. [Manual Workflows][road-doc]

### 6.2. Điều kiện xác minh từ source, không gán thành câu của manual

| Điều kiện / chi tiết | Căn cứ primary và hệ quả |
|---|---|
| DEM đọc được; hai Shapefile có base type PolyLine | Source kiểm tra; có vòng xử lý parts, không có yêu cầu singlepart. |
| Cùng CRS/toạ độ, overlap đúng DEM | Source dùng tọa độ vector trực tiếp, không reproject. Đây là tiền điều kiện suy ra từ implementation. |
| Giao đường–sông phải tồn tại trong rasterization | Sự kiện burn dựa ô/adjacency; ở 30 m giao hình học chưa bảo đảm nhận diện đúng. |
| Cung cấp width phù hợp và hữu hạn, dương | Wrapper cho `None`; Rust mặc định 0. Không nên coi đó là bề rộng thiết kế. |
| Đoạn stream lân cận phải có cao độ hợp lệ | Vòng tìm minimum không loại NoData. `minz` khởi tạo bằng DEM maximum. |

Source còn tính `width_in_cells = floor(ceil(width/grid_res)/2)`, với `grid_res` trung bình x/y: bề rộng bị lượng tử hóa. Nếu giao cô lập không có stream-neighbour phù hợp, nhánh gán ô giao có thể giữ `minz=maximum` và **nâng** ô đó. Đây là suy luận tĩnh, không phải lỗi đã tái hiện tại V49. [Source BurnStreamsAtRoads][wbt-road]

**Điều kiện dùng ở Phú Yên — đánh giá của reviewer:** cần crossing được xác minh là đường cản giả/cầu/cống có đường thông nước, stream geometry đủ chính xác, mẫu cao độ hai bên embankment, tránh NoData/biên raster trong vùng truy vết. Source không biết invert cống, khẩu độ, đập thật hoặc quy trình vận hành. Do đó việc hạ một ô giao không xác nhận capacity hay bathymetry. Một đê/đập thật không được hợp thức hóa thành passage chỉ vì giao một polyline sông.

## 7. Cách diễn đạt kết luận phù hợp bằng chứng

Đề nghị khi sử dụng nội dung mục 2–3 trong quyết định dự án:

- **HydroDEM:** “Breach-first có constraint là ứng viên có cơ sở khoa học để so sánh với fill-only V49; lợi ích tại Phú Yên chưa xác lập.”
- **TBB:** “Có bằng chứng về độ ổn định watershed qua nhiều độ phân giải trong case Ontario, đặc biệt ở lưới thô; chưa đủ để kết luận tốt hơn AGREE/FillBurn ở Phú Yên 30 m.”
- **Tham số:** “Least-cost dùng dist/cost; giới hạn độ sâu tuyệt đối và bảo vệ hydraulic controls cần cơ chế bổ sung được kiểm chứng.”
- **Road burning:** “Chỉ xem xét ở crossing được xác minh và kiểm tra output/routing; không suy ra đường thông nước thật từ giao vector.”

Đây là kết luận review nguồn, không phải phê duyệt thay DEM hay đề xuất giá trị tham số chạy mới. Tài liệu gốc không bị sửa; code, DEM, configs, môi trường và jobs không bị thay đổi.

## Nguồn primary và khả năng tái kiểm tra

- **HP:** [DOI 10.1002/hyp.10648](https://doi.org/10.1002/hyp.10648); abstract Wiley và submitted preprint của tác giả đọc độc lập. Phần chi tiết timing dựa preprint, không giả định đã đọc full text Wiley sau paywall.
- **ESP:** [DOI 10.1002/esp.3888](https://doi.org/10.1002/esp.3888); PDF do tác giả lưu, Bảng III trang in 665/PDF tr.8.
- **WhiteboxTools:** manual tác giả và source repo của tác giả, pin commit nêu ở §4; wrapper/source được đối chiếu riêng.
- **TBB/Burn:** manual legacy trên domain nhà phát triển, ghi rõ khác sản phẩm/API so với WhiteboxTools open-core.
- SHA256 tài liệu gốc lúc kiểm tra: `603A945164642D8BDE097290777EB865B40E31EEA35F1BFC74E021E1AEA2FE20`.

[hp-wiley]: https://onlinelibrary.wiley.com/doi/abs/10.1002/hyp.10648
[hp-pdf]: https://jblindsay.github.io/ghrg/pubs/Lindsay-HP-preprint.pdf
[esp-wiley]: https://onlinelibrary.wiley.com/doi/abs/10.1002/esp.3888
[esp-pdf]: https://jblindsay.github.io/ghrg/pubs/2016_Lindsay_ESPL.pdf
[wbt-manual]: https://jblindsay.github.io/wbt_book/available_tools/hydrological_analysis.html
[wbt-b]: https://raw.githubusercontent.com/jblindsay/whitebox-tools/3d7c73cf562b6c58d2649c37f570e3e9a90322f2/whitebox-tools-app/src/tools/hydro_analysis/breach_depressions.rs
[wbt-lc]: https://raw.githubusercontent.com/jblindsay/whitebox-tools/3d7c73cf562b6c58d2649c37f570e3e9a90322f2/whitebox-tools-app/src/tools/hydro_analysis/breach_depressions_least_cost.rs
[wbt-py]: https://raw.githubusercontent.com/jblindsay/whitebox-tools/3d7c73cf562b6c58d2649c37f570e3e9a90322f2/whitebox_tools.py
[wbt-road]: https://raw.githubusercontent.com/jblindsay/whitebox-tools/3d7c73cf562b6c58d2649c37f570e3e9a90322f2/whitebox-tools-app/src/tools/hydro_analysis/burn_streams_at_roads.rs
[wbt-fillburn]: https://raw.githubusercontent.com/jblindsay/whitebox-tools/3d7c73cf562b6c58d2649c37f570e3e9a90322f2/whitebox-tools-app/src/tools/hydro_analysis/fill_burn.rs
[tbb-doc]: https://www.whiteboxgeo.com/manuals/legacy/tool_help_wbwpro.html#topological_breach_burn
[road-doc]: https://www.whiteboxgeo.com/manuals/legacy/tool_help.html#burn_streams_at_roads
[whitebox-home]: https://www.whiteboxgeo.com/
