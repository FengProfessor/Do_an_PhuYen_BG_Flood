# Research: DEM preprocessing và river carving tốt hơn V49

Ngày: 2026-10-13  
Phạm vi: Phú Yên, lưới 30 m, BG_Flood / V49  
Mục tiêu: đánh giá các phương pháp hydro-conditioning / stream burning / breaching có thể cải thiện V49 mà không biến DEM thoát nước thành bathymetry giả.

## 1. Baseline V49 hiện tại

V49 có một quyết định kiến trúc đúng về mặt khoa học: tách `DEM_HYDRO_CONDITIONED` dùng cho topology/routing khỏi `DEM_HYDRAULIC_BED` dùng cho BG_Flood. Hai sản phẩm không được phép dùng thay cho nhau.

HydroDEM hiện tại trong `v49_build_hydro_conditioned_dem.py` dùng Priority-Flood để **nâng** depression/flat và sau đó tính D8. Báo cáo `V49_HYDRO_validation_report.json` cho thấy:

- 4,410,000 ô hợp lệ;
- 1,177,695 ô bị thay đổi, tất cả đều bị nâng;
- 0 ô bị hạ;
- mức nâng lớn nhất khoảng 30.047 m;
- topology cuối cùng không còn internal unresolved/cycle.

Như vậy HydroDEM đã giải quyết tính liên tục D8, nhưng theo hướng fill-only. Với địa hình 30 m có đường, đường sắt, đê, cầu và cống không được phân giải, đây chưa phải chiến lược tối thiểu hóa biến dạng DEM.

Hydraulic-bed V49-E lại rất bảo thủ. `v49_synthesize_hydraulic_bed.py` hạ mỗi reach theo `depth_m` cục bộ và taper ngang bằng raised cosine. Các endpoint `preliminary_bed_upstream_m` / `preliminary_bed_downstream_m` hiện chủ yếu là QA; chúng không tạo thành một target thalweg grade line xuyên suốt reach. Vì vậy đáy cuối cùng về bản chất gần với:

`z_bed(x,y) = z_DEM(x,y) - depth_reach * lateral_weight`

Điểm mạnh là không khoét sâu tùy ý qua terrain thiếu bằng chứng. Điểm yếu là nhiễu/undulation của Copernicus ở dọc lòng sông vẫn có thể truyền xuống đáy.

## 2. Breach-first / fill-last phù hợp hơn fill-only cho HydroDEM

John Lindsay (2016) phân biệt rõ:

- filling: nâng các ô trong depression;
- breaching: hạ một hành lang xuyên qua blockage;
- hybrid: chọn breach/fill hoặc constrained breach để giảm mức can thiệp DEM.

Trong thử nghiệm của bài báo, complete breaching có thời gian xử lý khoảng 87% thời gian của filling; selective/constrained breach vẫn cùng bậc chi phí tính toán nhưng cho phép giảm tác động lên DEM. Tác giả kết luận breaching/hybrid thường phù hợp hơn với artifact depressions, đặc biệt các blockage do DEM không biểu diễn được breakline, culvert hoặc bridge.

Nguồn chính:

- Lindsay, J.B. (2016), *Efficient hybrid breaching-filling sink removal methods for flow path enforcement in digital elevation models*, Hydrological Processes 30(6), 846–857. DOI: https://doi.org/10.1002/hyp.10648
- Preprint: https://jblindsay.github.io/ghrg/pubs/Lindsay-HP-preprint.pdf
- WhiteboxTools manual: https://jblindsay.github.io/wbt_book/available_tools/hydrological_analysis.html

WhiteboxTools hiện khuyến nghị thử `BreachDepressionsLeastCost` trước depression filling; công cụ đặc biệt phù hợp với road embankments. Có thể giới hạn độ dài/độ sâu/cost của breach rồi fill các depression còn lại.

### Kết luận cho V49 HydroDEM

Không nên thay Priority-Flood bằng một lần burn sâu cố định. Nên chuyển thành **hybrid có mask và constraint**:

1. nhận diện/preserve true sinks, reservoir, wetland, dam/weir và các hydraulic controls;
2. topology-aware enforce mạng sông đã được V49-B/C/C.1 xác nhận;
3. breach có mục tiêu tại road/rail/embankment crossings nơi có bằng chứng sông/cống/cầu;
4. least-cost constrained breach cho artifact depressions còn lại;
5. Priority-Flood/fill chỉ cho residual micro-sinks không breach hợp lý;
6. D8/accumulation và audit lại từ raster được ghi ra đĩa.

## 3. Không nên dùng AGREE/FillBurn cổ điển như phương án chính

Stream burning cổ điển ép vector hydrography xuống raster. Vấn đề lớn ở lưới 30 m là mismatch scale: nhiều nhánh có thể rasterize vào cùng ô, line crossing/braid/lake/complex channel có thể tạo sai topology và “stream piracy”.

Lindsay (2016), *The practice of DEM stream burning revisited*, đề xuất `TopologicalBreachBurn` (TBB). Phương pháp dùng total upstream channel length để prune mạng vector theo độ chi tiết DEM và ưu tiên channel lớn hơn khi nhiều links chiếm cùng raster cell. Trong test của bài báo, độ khớp watershed của TBB gần như ổn định khi coarse grid, trong khi stream burn truyền thống suy giảm rõ rệt.

Nguồn chính:

- https://doi.org/10.1002/esp.3888
- https://jblindsay.github.io/ghrg/pubs/2016_Lindsay_ESPL.pdf

### Kết luận cho V49

Nếu buộc mạng hydrography vào DEM, TBB hoặc một implementation tương đương topology-aware đáng thử hơn AGREE/FillBurn đơn giản. Tuy nhiên V49 cần giữ structure/tidal/reservoir exceptions; không burn toàn bộ OSM/HydroRIVERS một cách mù quáng.

## 4. Cống/cầu/đường nên được xử lý như hydro-enforcement riêng

USGS định nghĩa hydro-conditioning và hydro-enforcement khác nhau:

- conditioning làm toàn bề mặt có flow liên tục và loại spurious sinks;
- enforcement sửa elevation trùng với hydrographic network/structures để nước đi qua road fills, rail grades, culvert/bridge thay vì bị DEM giữ lại như một đập giả.

USGS 3DHP còn yêu cầu downstream monotonicity ở hydrographic cells và connector/culvert phải thay terrain cản dòng; ngoài các feature cần enforce, source DEM nên được giữ nguyên tối đa.

Nguồn chính:

- USGS Fact Sheet 2014-3051: https://www.usgs.gov/publications/hydrologic-enforcement-lidar-dems
- 3DHP Hydrologically Conditioned and Enforced DEM specification: https://www.usgs.gov/ngp-standards-and-specifications/elevation-derived-hydrography-data-acquisition-specifications-15
- Culverts and Drainageways: https://www.usgs.gov/media/files/culverts-and-drainageways

WhiteboxTools có `BurnStreamsAtRoads`, chỉ hạ DEM tại giao stream-road theo bề rộng embankment. Đây là pattern phù hợp hơn việc hạ nguyên tuyến đường hoặc fill một vùng rất lớn phía thượng lưu.

## 5. MERIT Hydro cho một pattern tốt: water-guided + minimum modification

MERIT Hydro xây flow direction từ DEM kết hợp các bản đồ nước, tách actual inland basins khỏi dummy depressions, và tạo hydrologically adjusted elevation sao cho downstream không cao hơn upstream trong khi giảm tối đa sai khác so với DEM gốc.

Nguồn:

- MERIT Hydro project: https://global-hydrodynamics.github.io/MERIT_Hydro/
- Yamazaki et al. (2019), DOI: https://doi.org/10.1029/2019WR024873

MERIT Hydro có độ phân giải khoảng 90 m nên không nên dùng trực tiếp làm bed cho BG_Flood 30 m. Giá trị của nó ở đây là **design pattern**: water-guided network alignment + minimum modification + true-depression handling.

## 6. Cải thiện “đục sông” cho hydraulic bed: target thalweg thay vì DEM-depth

V49 hiện đã có inventory, graph, width/depth evidence, C.1 authorization, confluence QA và protected structures. Vì vậy bước tiếp theo không nên là khoét sâu hơn trên toàn mạng; nên thay đổi hình học đáy trong scope được phép.

Đề xuất tạo `target_thalweg_z(s)` theo chainage `s` cho mỗi reach:

1. lấy water-surface/bank elevation envelope từ các cross-section hợp lệ;
2. trừ depth LOW/CENTRAL/HIGH hoặc depth đã calibration;
3. fit longitudinal profile robust/smooth có giới hạn curvature;
4. ràng buộc junction continuity tại confluence;
5. cho phép discontinuity/control hợp lý ở dam/weir, reservoir, tidal/backwater;
6. chỉ hạ DEM khi target bed thấp hơn DEM và nằm trong authorized river mask;
7. blend target thalweg ra bank bằng cross-section shape phù hợp.

Với reach đủ rộng, nên thử trapezoid/compound cross-section hoặc asymmetric profile thay vì một cosine bowl duy nhất. Raised-cosine vẫn hữu ích như anti-cliff taper, nhất là sông hẹp chỉ chiếm 1–2 cell.

Điểm khác biệt quan trọng: target bed được xác định bởi **longitudinal hydraulics**, còn DEM chỉ cung cấp terrain/bank constraint. Như vậy speckle trên water surface của Copernicus không bị sao chép nguyên xi xuống đáy.

## 7. Dữ liệu nền: FABDEM nên là benchmark, không phải thay thế tự động

FABDEM là phiên bản 30 m từ Copernicus DEM đã loại ảnh hưởng forest/buildings bằng machine learning. Đây là candidate tốt để benchmark ở floodplain/urban/vegetated zones. Tuy nhiên nó vẫn không cung cấp measured river bathymetry và không giải quyết đầy đủ culvert/bridge/levee controls.

Do đó nên chạy A/B giữa Copernicus base và FABDEM cho terrain ngoài kênh, nhưng giữ cùng river/structure enforcement logic và cùng forcing. Không nên coi FABDEM là “đục sông sẵn”.

## 8. Pipeline ứng viên tốt nhất cho dự án

Tên đề xuất: `V49-HYBRID` hoặc `V50-HYDROBREACH`.

### Nhánh A — drainage DEM

`Base DEM`

→ preserve true sinks + protected hydraulic controls  
→ topology-aware burn của approved hydrograph  
→ explicit stream-road/culvert/bridge breach  
→ least-cost constrained breach  
→ fill residual micro-sinks  
→ D8 / accumulation / basin audit

### Nhánh B — BG_Flood hydraulic bed

`Base terrain`

→ authorized reach geometry  
→ target thalweg profile theo chainage  
→ confluence/structure/tidal constraints  
→ variable cross-section / lateral smooth blend  
→ LOW / CENTRAL / HIGH uncertainty surfaces  
→ matched BG_Flood runs

Hai nhánh vẫn phải độc lập. Drainage DEM không được dùng trực tiếp làm BG_Flood bed.

## 9. Thí nghiệm nên chạy trước khi đổi V49

Tạo candidate mới, giữ V49 hiện tại làm control. Không overwrite V49.

So sánh ít nhất các chỉ số:

### Terrain/topology

- số ô raise/lower;
- tổng `sum(|delta_z|)` và volume raise/lower;
- max raise / max lower;
- số depression dùng breach vs fill;
- số road/rail crossings được enforce;
- D8 cycle/unresolved;
- flow-path distance tới approved hydrograph;
- basin/outlet agreement;
- thay đổi ngoài authorized/preserve mask phải bằng 0.

### Hydraulic

- cùng forcing, same solver/config/hardware window;
- SAR CSI/F1/precision/recall và False Negative area;
- HWM/WSE residual nơi datum đủ tin cậy;
- arrival time;
- velocity outliers;
- mass/water-budget closure;
- sensitivity LOW/CENTRAL/HIGH.

Không nên chọn phương pháp chỉ vì D8 đẹp hơn. Candidate chỉ thắng V49 nếu vừa giảm biến dạng terrain, vừa cải thiện topology, và khi đưa vào BG_Flood không làm xấu independent hydraulic evidence.

## 10. Xếp hạng đề xuất

1. **Hybrid least-cost breaching + residual filling:** ưu tiên cao nhất cho HydroDEM.
2. **Explicit road/culvert/bridge hydro-enforcement:** ưu tiên rất cao ở Phú Yên vì barrier nhân tạo là lỗi đã biết của DEM 30 m.
3. **Topology-aware stream burning (TBB-like):** nên dùng nếu burn hydrography vào raster; tốt hơn AGREE/FillBurn cổ điển cho lưới thô.
4. **Target-thalweg longitudinal synthesis + cross-section blending:** ưu tiên cao nhất để cải thiện hydraulic-bed carving của V49-E.
5. **FABDEM benchmark/ensemble:** hữu ích để giảm building/forest artifacts nhưng không thay thế hydro-enforcement hay bathymetry.
6. **Blind fixed-depth burn / global monotonic carve:** không khuyến nghị vì dễ xóa hydraulic controls thật và tạo channel giả.

### Recommendation

Nếu chỉ chọn một nâng cấp có khả năng đem lại lợi ích rõ nhất so với V49 hiện tại, nên làm prototype **breach-first HydroDEM** trên một vùng test có QL1A/đường sắt/cống đã biết, rồi chạy matched metrics với fill-only V49. Sau khi topology chứng minh tốt hơn, mới nâng cấp hydraulic bed bằng target-thalweg profile. Hai thay đổi nên được đánh giá riêng để biết cải thiện đến từ drainage topology hay từ bathymetry geometry.
