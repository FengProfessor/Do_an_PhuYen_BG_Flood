# V45: cơ sở khoa học, nguồn chính và thực nghiệm cần làm

Ngày kiểm tra: 28/09/2026. Phạm vi: tài liệu chính thức và nghiên cứu gốc; đối chiếu có chọn lọc với Python fork đang có trong kho mã. Chưa chạy mô phỏng, chưa thay đổi DEM hoặc solver. Các đề xuất dưới đây là thiết kế thực nghiệm, chưa phải kết quả xác nhận V45.

## Kết luận phục vụ kế hoạch

V45 cần xác định **ngưỡng kết nối từ lòng sông sang từng vùng trũng**, lượng nước đi qua và thời điểm đi qua. Hạ một tập pixel 2 m chưa cho biết cửa thông có đủ chiều dài tràn, cao trình hay khả năng truyền nước. Cần kiểm tra thời gian SAR, hệ cao độ, lượng nước đầu vào và bảo toàn thể tích trước khi tăng mức khoét. SAR phù hợp để ràng buộc phạm vi ngập; chứng minh độ sâu cần thêm mực nước/vết lũ/đo thực địa độc lập.

## 1. Nguồn chính và ý nghĩa cho hạ lưu sông Ba

### 1.1 Copernicus GLO30 là DSM

Copernicus xác nhận sản phẩm là mô hình bề mặt gồm cây, công trình và hạ tầng, đã chỉnh một số mặt nước và sông. Điều này không bảo đảm mọi bờ sông, đê hay cống được mô tả đúng địa hình trần. [Copernicus: mô tả COP-DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM).

Handbook quy định cao độ theo EGM2008, đơn vị mét; GLO30 có bước lưới vĩ độ 1 giây cung. Sai số đứng tuyệt đối <4 m LE90 là thống kê tổng thể và có thể sai khác địa phương. Không được coi ±4 m là sai số bảo đảm tại từng điểm. [Copernicus DEM Product Handbook v5.0, mục 1.1](https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf).

**Áp dụng đề xuất:** lập bảng hệ cao độ của DEM, mực nước trạm, triều/biên biển, bathymetry và vết lũ. Xác minh dữ liệu DEM thực tế có phải GLO30 hay sản phẩm dẫn xuất. Nếu thiếu chuyển đổi về cùng datum, chưa được diễn giải chênh cao là sai số đê. Tách sai số do cây/công trình khỏi đê/đường có thật; lưu cao độ gốc, hiệu chỉnh và nguồn bằng chứng cho mỗi đoạn.

### 1.2 Một đối chứng DEM có ích

FABDEM v1.2 do nhóm Bristol phát hành, dùng phương pháp học máy để giảm thiên lệch do cây và nhà trong Copernicus GLO30, vẫn ở bước lưới khoảng 30 m. Dataset có điều kiện sử dụng CC BY-NC-SA 4.0. [Dataset của University of Bristol](https://research-information.bris.ac.uk/en/datasets/fabdem-v1-2/); [bài báo gốc Hawker và cộng sự, 2022](https://research-information.bris.ac.uk/ws/portalfiles/portal/314496213/Hawker_2022_Environ._Res._Lett._17_024016.pdf).

**Áp dụng đề xuất:** dùng FABDEM làm nhánh đối chứng nếu phù hợp điều kiện sử dụng, không mặc định đó là địa hình đúng tại Phú Yên. So sánh profile ngang sông, đất trống, khu dân cư và ruộng với điểm đo độc lập. Nó không tự cung cấp số đo đỉnh đê hay đáy sông.

### 1.3 SAR có vùng không quan sát tin cậy

GFM phân biệt phạm vi nước quan sát được, nước thường xuyên và vùng loại trừ. Rừng rậm, khu đô thị, bóng radar và bề mặt có tín hiệu giống nước có thể gây bỏ sót hoặc nhận nhầm. No-data cần được giữ là không quan sát được; không tự gán thành khô. [GFM Product Definition Document, các lớp đầu ra](https://extwiki.eodc.eu/en/GFM/PDD/GFM_Product_Output_Layers).

GFM cũng có cờ cảnh báo cho tác động thời tiết và các lớp loại trừ do bề mặt. [GFM: Recommendations](https://extwiki.eodc.eu/GFM/PUM/Recommendations).

**Áp dụng đề xuất:** nếu SAR nội bộ không phải GFM, các giới hạn vật lý này vẫn cần kiểm tra, nhưng không được áp mã lớp GFM lên dữ liệu nội bộ. Ghi rõ thuật toán tạo mask, ngày giờ từng scene, ảnh tham chiếu, orbit, ngưỡng phân lớp và phép ghép ảnh. Báo cáo phần diện tích có quan sát hợp lệ riêng. Không dùng một ngưỡng HAND để âm thầm loại các vùng mô hình dự báo sai.

### 1.4 Thời gian chụp quyết định phép đối chiếu

Nghiên cứu gốc Gobeyn và cộng sự cho thấy thời điểm SAR ảnh hưởng rõ đến hiệu chỉnh mô hình và độ bất định tham số; trong thiết lập tổng hợp của nghiên cứu, ảnh trước đỉnh cho ràng buộc tốt hơn ảnh gần/sau đỉnh. Đây không phải quy luật rằng mọi lưu vực nên dùng ảnh trước đỉnh. [Bài báo 2016, hồ sơ NASA NTRS](https://ntrs.nasa.gov/citations/20170001442).

**Áp dụng đề xuất:** đối chiếu `h(t_SAR)` với mỗi scene. Nếu sản phẩm SAR là hợp của nhiều ngày, đối chiếu riêng từng thời điểm trước, rồi mới lập phép hợp tương ứng. Bản đồ cực đại mô phỏng `hmax` là một sản phẩm khác. Gọi ảnh là “đỉnh lũ” chỉ sau khi đối chiếu thời gian với hydrograph tại hạ lưu; đỉnh ở thượng lưu không tự là đỉnh đồng thời ở mọi ô.

## 2. Đê: cần hình học và cơ chế truyền nước

HEC-RAS hướng dẫn căn mặt ô theo đê/đường bằng breakline để mô tả đúng rào cản. Đây là bằng chứng về vai trò mặt ô, không phải hướng dẫn API BG Flood. [HEC-RAS 2D Flow Areas, breaklines](https://www.hec.usace.army.mil/confluence/rasdocs/rasum/6.4/entering-and-editing-geometric-data/2d-flow-areas).

Tài liệu HEC phân biệt tràn tự do qua công trình và dòng ngập chìm: phương trình đập tràn thường phù hợp khi có dòng qua tới hạn/rơi tự do; SWE phù hợp hơn khi ngập chìm. Đặt ô hạ lưu ngay trên thân đê có thể tạo mực nước đuôi giả và làm giảm lượng tràn. [HEC: Modeling Weirs in 2D Areas](https://www.hec.usace.army.mil/confluence/rasdocs/hgt/latest/guides/modeling-weirs-in-2d-areas).

Quan hệ đơn giản để kiểm tra thứ nguyên là `Q = C L H^(3/2)`, với `L` là chiều dài đoạn tràn hữu hiệu, `H` là cột nước năng lượng trên đỉnh. Hệ số `C` phụ thuộc hệ đơn vị và hình học; không chép một hệ số từ tài liệu hệ feet vào mô hình SI. [HEC Hydraulic Reference: Weir Flow Coefficient](https://www.hec.usace.army.mil/confluence/rasdocs/ras1dtechref/latest/modeling-culverts/culvert-data-and-coefficients/weir-flow-coefficient).

**Suy luận kỹ thuật cho V45:** phải phân biệt ba đại lượng đang dễ gọi chung là “độ rộng”:

- Chiều dài cửa tràn/cửa mở dọc bờ, quyết định `L`.
- Chiều dày thân đê hoặc chiều dài đường đi nước cắt ngang đê.
- Chiều rộng raster được hạ, đang bị lượng tử hóa theo ô 30 m.

Một cửa thực rộng 5 m được biến thành ô hạ toàn bộ 30 m có thể tạo tiết diện truyền nước lớn hơn thực tế. Ngược lại, hạ một ô nhưng còn một mặt ô cao ở đầu/đuôi thì đường truyền vẫn bị chặn. Không thể chọn độ rộng tốt nhất chỉ từ diện tích SAR cuối cùng.

### 2.1 Subgrid nghĩa là gì và giới hạn áp dụng

HEC mô tả subgrid bằng quan hệ cao độ–thể tích trong ô và bảng hình học/thủy lực ở từng mặt ô lấy từ địa hình chi tiết. [HEC-HMS Technical Reference: 2D Diffusion Wave Model](https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/transform/2d-diffusion-wave-model).

**Áp dụng đề xuất:** nếu cần cửa nhỏ hơn 30 m, cân nhắc cấu trúc tại mặt ô với chiều dài hữu hiệu và crest, hoặc lưới tinh cục bộ đã kiểm chứng. Nội suy DEM 30 m xuống 5 m không bổ sung thông tin đo địa hình. Chỉ thêm một cờ `subgrid=true` không tạo ra các quan hệ hình học còn thiếu.

## 3. BG Flood upstream và Python fork phải được kiểm chứng riêng

Tài liệu upstream mô tả solver SWE dựa trên Saint-Venant/Basilisk và cấu trúc Block Uniform Quadtree trên GPU. Upstream vẫn ghi tài liệu đang hoàn thiện và có lộ trình adaptive. [Tài liệu BG Flood](https://aliceharang.github.io/); [kho mã upstream](https://github.com/CyprienBosserelle/BG_Flood).

Không suy luận rằng Python fork hiện có đầy đủ adaptivity, cấu trúc đê/cống, hay bộ kiểm chứng của upstream. Các nhận xét sau chỉ dựa vào file local đã đọc:

| Quan sát mã local | Ý nghĩa cần kiểm tra |
|---|---|
| `python/bg_flood/flow_gpu.py:152,255` lấy `zlr=max(zl,zr)` để tái dựng mặt ô | Dòng qua bờ phụ thuộc nền tại giao diện. Cần xuất crest tái dựng mà solver thực sự thấy, không chỉ ảnh DEM ở tâm ô. |
| `flow_gpu.py:343,363` chặn `h` vào [0,100] m | Nếu giới hạn hoạt động, thể tích có thể thay đổi ngoài thông lượng vật lý. Cần đếm số lần, thể tích thêm/bớt, vị trí và thời điểm; chưa chứng minh nó đã tác động đáng kể trong V44. |
| `flow_gpu.py:351-352,366-367` chặn vận tốc ±20 m/s | Cần kiểm tra việc chặn có hoạt động tại cửa khoét hay không; chưa thể coi nghiệm đã ổn định chỉ vì không NaN. |
| `flow_gpu.py:345` dùng ngưỡng vận tốc khi `h>=0.001`, trong khi `param.py` mặc định `eps=0.0001` | Kiểm chứng lan truyền mặt ướt với các ngưỡng đang dùng thực tế, nhất là gần ô mới ngập. |
| `flow_gpu.py:388,404` dùng tối thiểu `h_fric=0.01` m khi tính ma sát | Đây là thay đổi của fork cần thử độ nhạy; không phải bằng chứng phải giảm Manning toàn miền. |
| `breach_levees_v44.py:390` yêu cầu pixel thuộc `sar_flood`; dòng 403 hạ đều `breach_depth` | Có thể bỏ sót đỉnh đê đang khô, trong khi đỉnh đó lại chặn đường vào vùng SAR ngập ở phía sau. Đây là giả thuyết trực tiếp cần kiểm tra profile. |

Đường dẫn thư mục nguồn local: [Python fork](D:/VTP/BG_Flood_Project/BG_Flood/python/bg_flood/flow_gpu.py), [khoét V44](D:/VTP/BG_Flood_Project/BG_Flood/breach_levees_v44.py).

Nếu một ảnh SAR đã dùng chọn ô sửa DEM rồi lại dùng chấm điểm, kết quả đó là **độ khớp hiệu chỉnh**, chưa phải kiểm định độc lập. Giữ riêng sự kiện/ngày SAR/vết lũ khác để kiểm định; nếu chưa có, công bố rõ giới hạn này.

## 4. Thực nghiệm đề xuất theo thứ tự

Các phép thử dưới đây do báo cáo đề xuất, không phải ngưỡng chuẩn bắt buộc từ tài liệu. Chưa thực hiện.

### A. Khóa bộ dữ liệu và phép so sánh

1. Lưu manifest gồm hash DEM, SAR, Q, mưa, ma sát, biên biển, code và cấu hình; ghi thời gian bắt đầu, timezone và đơn vị.
2. Chia vùng hạ lưu bờ trái/bờ phải theo hướng dòng chảy, rồi chia các khoang trũng theo đê/đường/kênh; không chia trái/phải theo hướng người nhìn màn hình.
3. Khóa mask quan sát hợp lệ trước khi thử mô hình. Báo cáo CSI/IoU, precision, recall, diện tích false positive/false negative cho từng khoang và từng thời điểm.

### B. Chẩn đoán ngưỡng kết nối mà chưa sửa solver

1. Vẽ các profile từ lòng sông qua bờ/đê đến từng khoang SAR ngập nhưng mô hình khô. Chồng DEM gốc/V41/V44, đường/kênh và `zs` mô phỏng.
2. Tìm đường nối có cao trình nút thắt thấp nhất từ sông đến khoang trũng; ghi chuỗi mặt ô chắn, không chỉ một pixel cao cục bộ. Đây là công cụ sàng lọc tĩnh, không thay thế động lực hay lưu lượng.
3. Phân biệt bốn giả thuyết: mực nước sông chưa đủ cao; crest giả quá cao; đường vào bị đứt/tiết diện quá nhỏ; thiếu nguồn nước từ mưa/nhánh bên. Chọn thí nghiệm tương ứng với từng giả thuyết.

### C. Kiểm chứng số học trước hiệu chỉnh diện rộng

1. Hồ tĩnh trên địa hình gồ ghề, có mặt ướt/khô: kiểm tra vận tốc giả và thay đổi thể tích.
2. Dam break đơn giản và mặt ướt lan qua bậc nền: kiểm tra đối xứng X/Y, lan truyền, tính không âm và sai số theo bước lưới/thời gian.
3. Đê kín rồi tăng mực nước qua crest; cửa có chiều dài đã biết; tràn tự do và ngập chìm: kiểm tra lưu lượng, chiều dòng, bảo toàn giữa hai phía.
4. Cùng bài toán chạy đường CPU và GPU đang dùng, đối chiếu thể tích, WSE và mặt ngập. Nếu khác đáng kể, tìm nguyên nhân trước khi chỉnh DEM.
5. Lập cân bằng `ΔV = inflow - outflow + rain - infiltration + numerical_correction`; ghi riêng ảnh hưởng mọi phép clamp/reset. Chọn ngưỡng chấp nhận sau baseline và hội tụ, không lấy một tỷ lệ đẹp làm chuẩn mặc định.

### D. Nhánh hiệu chỉnh V45

- **D0:** DEM baseline với bộ đánh giá đã sửa; giữ nguyên forcing để có mốc so sánh.
- **D1:** hiệu chỉnh địa hình có bằng chứng theo từng hành lang, giữ các đê/đường có thật, phục hồi kênh/cống biết tồn tại. Mỗi thay đổi có chiều dài hữu hiệu, cao trình đáy/crest, chiều dài cắt ngang, nguồn và khoảng bất định.
- **D2:** nếu cần cửa dưới kích thước ô, thử module truyền nước tại mặt ô trong miền nhỏ; phải qua C trước khi đưa toàn miền.
- **D3:** nhánh đối chứng DEM trần như FABDEM, có căn chỉnh datum và giữ công trình có thật từ nguồn riêng.

Trước mọi hiệu chỉnh hình học, sửa và kiểm thử các lỗi đơn vị/forcing/timing đã được audit xác nhận, rồi tạo baseline mới với DEM chưa khoét thêm. Sau đó mới thử từng nhóm: crest/hình học, Q và timing, triều, Manning/mưa/thấm. Không tối ưu đồng thời tất cả theo một ảnh SAR vì nhiều tổ hợp có thể cho cùng phạm vi nhưng khác độ sâu. Phần này chỉ là tư vấn phương pháp; thứ tự triển khai cụ thể theo báo cáo audit V45.

### E. Quyết định chọn V45

V45 được chấp nhận khi cải thiện theo bờ/khoang và đúng thời gian SAR, không làm xấu mực nước độc lập, không tạo mất/thêm nước không giải thích được, và không phụ thuộc mạnh vào một bước lưới hoặc ngưỡng ướt/khô. Độ sâu báo cáo cần khoảng bất định phản ánh sai số DEM và đầu vào. Nếu mới có SAR extent, mô tả đúng là “đã đánh giá phạm vi ngập”; chưa tuyên bố “độ sâu chuẩn nhất”.

## 5. Bổ sung: dữ liệu công khai cho trận 29–30/11/2021

### 5.1 Những mốc đã tìm được từ nguồn chính

| Mốc | Giá trị | Loại bằng chứng và nguồn |
|---|---:|---|
| Phú Lâm, 13h 29/11 | 1,24 m | Thực đo trong bảng mục 6.1, [bản tin NCHMF 30/11/2021 lưu tại EVN](https://www.evn.com.vn/userfile/User/tcdl/files/2021/11/HNnambo301121.pdf) |
| Phú Lâm, 19h 29/11 | 1,46 m | Cùng bản tin, thực đo |
| Phú Lâm, 01h 30/11 | 1,33 m | Cùng bản tin, thực đo |
| Phú Lâm, 07h 30/11 | 1,55 m | Cùng bản tin, thực đo |
| Phú Lâm, 15h 30/11 | BĐ3 + 0,37 m | [Công điện 7618/CĐ-PCTT của Bộ Công Thương, 01/12/2021](https://www.evn.com.vn/userfile/User/tcdl/files/2021/12/PCTTBCTChudongungphomualu.pdf) |
| Sông Ba Hạ, 15h 30/11 | Xả 9.400 m³/s | [Thiên tai Việt Nam 2021, trang 156](https://chinhsach.dmptc.gov.vn/Uploads/Thu%20vien%20tai%20lieu/Tai%20lieu%20truyen%20thong/Thien%20tai%20Viet%20Nam%202021%20fix%203.pdf) |
| Phú Lâm, đỉnh trận lũ | 4,63 m | Cùng báo cáo quốc gia, trang 150 |
| Phú Lâm, giờ đỉnh | 23h 30/11/2021 | [Báo cáo UBND Đắk Lắk về hiện trạng môi trường 2021–2025](https://vpubnd.daklak.gov.vn/CMS/Content/VanBan/2026/4.2026/1123_QD-UBND%20BC.pdf), trang in 196 / trang PDF 212, mục năm 2021 |
| Củng Sơn, đỉnh trận lũ | 38,72 m lúc 19h 30/11/2021 | Cùng báo cáo UBND, trang in 195 / trang PDF 211 |

Bản tin ngày 30/11 còn có các mức 2,90 / 4,50 / 4,20 / 3,70 m ở các cột sau: đây là **dự báo**, không được nhập như số đo. Các mốc giờ Việt Nam phải được gắn UTC+7 trước khi đổi sang UTC; tương ứng mốc 23h là 16:00 UTC cùng ngày. Cần giữ ghi chú rằng tài liệu hành chính không khai báo timezone bằng chuỗi ISO.

**Hệ quả cho dữ liệu hiện có:** nhóm audit xác nhận tên SAR có ngày `20211130`; tên này chưa xác định giờ chụp. Phải đọc timestamp scene và timezone gốc. Một ảnh sáng 30/11 vẫn có thể nằm trước đỉnh Phú Lâm lúc 23h nhiều giờ. Nếu có ảnh 29/11 trong sản phẩm ghép thì ảnh đó chỉ ràng buộc giai đoạn trước đỉnh. Không dịch chuỗi Q/SAR chỉ để tăng CSI. Mực nước trạm trên đây cũng chưa tự động cùng datum với EGM2008; chỉ dùng giá trị tuyệt đối khi xác minh mốc trạm.

### 5.2 Có nghiên cứu gốc rất sát khu vực

[Lương Hữu Dũng và cộng sự, 2024, HEC-RAS hạ lưu sông Ba](https://imh.ac.vn/wp-content/uploads/2024/07/30.bai-6.pdf) có hydrograph thực đo Phú Lâm 2021 (Hình 10), khảo sát 46 vết lũ và bảng 20 điểm. Bài mô tả 59 mặt cắt sông Ba kế thừa, bổ sung 20 mặt cắt năm 2023; dùng nhập lưu khu giữa và triều cửa Đà Diễn/Đà Nông. Đây là đầu mối dữ liệu có thật, chưa tìm thấy bộ mặt cắt số mở tải trực tiếp.

Đã tải [PDF gốc](/D:/VTP/V45_IMH_SongBa_2024.pdf) và xem trang 71–72. Bảng tọa độ chỉ in hai chữ số thập phân; nhiều điểm cùng tọa độ nhưng khác cao trình. Một số kinh độ cần kiểm tra lại trên bản đồ. Không dùng nguyên bảng làm chuẩn điểm cho ô 30 m. Chỉ số hóa hydrograph dưới nhãn “đọc từ đồ thị”, kèm bất định, nếu không lấy được chuỗi gốc.

**Đề xuất khi chưa có dữ liệu ngoài:** dùng các mốc bản tin để ràng buộc timing; đọc đồ thị làm đối chứng thô; dùng SAR nhiều ngày và không gian giữ lại để kiểm định; giữ hình học đê chưa biết dưới dạng các kịch bản có khoảng bất định. Không lấy tổng lưu lượng xả của hồ thượng nguồn nối tiếp rồi cộng thêm lần nữa tại biên Sông Ba Hạ. Cần lập sơ đồ mạng trước để tránh đếm trùng nguồn nước.

Tài liệu quốc gia đã lưu [PDF](/D:/VTP/V45_ThienTaiVietNam2021.pdf) và [bản trích xuất văn bản](/D:/VTP/V45_ThienTaiVietNam2021.txt). Có thể dùng trang 150, 156–157 để kiểm tra nguồn từng con số, không dựa vào tiêu đề báo chí.
