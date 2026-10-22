# -*- coding: utf-8 -*-
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

def build_chapter2(doc, add_h, add_p, add_formula, add_fig, add_caption=None, set_cell_border=None, set_cell_shading=None):
    add_h("CHƯƠNG 2: PHƯƠNG PHÁP NGHIÊN CỨU VÀ CÔNG NGHỆ ÁP DỤNG", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)

    add_h("2.1. Cơ sở toán học của mô hình thủy lực 2 chiều (BG_Flood)", level=2)
    add_h("2.1.1. Hệ phương trình nước nông 2 chiều đầy đủ (2D SWE)", level=3)
    add_p("Hệ phương trình nước nông hai chiều (2D Shallow Water Equations - SWE), hay hệ phương trình Saint-Venant 2 chiều, là mô hình toán học cơ sở mô tả chuyển động của khối chất lỏng có bề mặt tự do khi chiều sâu dòng chảy nhỏ hơn rất nhiều so với quy mô chiều dài ngang của sóng lũ [4], [12]. Hệ phương trình này được thiết lập thông qua việc tích phân theo phương thẳng đứng (từ đáy z = zb(x,y) lên mặt tự do z = zs(x,y,t) = zb + h) của phương trình liên tục và hệ phương trình động lượng Navier-Stokes đối với chất lưu không nén được, dưới giả thiết phân bố áp suất tuân theo định luật thủy tĩnh (Hydrostatic Pressure Distribution) và bỏ qua gia tốc thẳng đứng:")
    add_p("Hệ phương trình bảo toàn dưới dạng vector bảo toàn phi tuyến trong hệ tọa độ Descartes (x, y) được viết như sau:")
    add_formula("∂U/∂t + ∂F(U)/∂x + ∂G(U)/∂y = S(U)", "2.1")
    add_p("Trong đó, U là vector các biến bảo toàn (Conserved Variables); F(U) và G(U) lần lượt là các vector thông lượng đối lưu (Convective Fluxes) theo phương x và phương y; S(U) là vector các số hạng nguồn (Source Terms) bao gồm độ dốc đáy địa hình, ứng suất ma sát đáy và các nguồn gia nhập/thất thoát nước:")
    add_formula("U = [ h ,  hu ,  hv ]^T", "2.2")
    add_formula("F(U) = [ hu ,  hu² + ½gh² ,  huv ]^T", "2.3")
    add_formula("G(U) = [ hv ,  huv ,  hv² + ½gh² ]^T", "2.4")
    add_formula("S(U) = [ R - I ,  -gh(∂zb/∂x) - τbx/ρ ,  -gh(∂zb/∂y) - τby/ρ ]^T", "2.5")
    add_p("Ý nghĩa vật lý của các đại lượng:")
    add_p("- h(x,y,t) = zs - zb là độ sâu cột nước cục bộ (m).")
    add_p("- u(x,y,t) và v(x,y,t) là các thành phần vận tốc dòng chảy trung bình theo chiều sâu dọc theo trục x và y (m/s).")
    add_p("- hu và hv là lưu lượng dòng chảy trên một đơn vị chiều rộng theo phương x và y (m²/s).")
    add_p("- g là gia tốc trọng trường chuẩn (g = 9.81 m/s²).")
    add_p("- zb(x,y) là cao trình đáy địa hình so với mực chuẩn mốc trắc địa (m).")
    add_p("- R(x,y,t) là cường độ mưa hữu hiệu rơi trực tiếp trên bề mặt ô lưới (m/s).")
    add_p("- I(x,y,t) là tốc độ ngấm/thấm nước qua lớp phủ mặt đất vào tầng ngậm nước (m/s).")
    add_p("- ρ là khối lượng riêng của nước ngọt (ρ ≈ 1.000 kg/m³).")
    add_p("- τbx và τby là các thành phần ứng suất ma sát đáy tác dụng lên khối chất lỏng theo phương x và phương y (N/m²).")

    add_h("2.1.2. Mô hình ứng suất ma sát đáy Manning-Strickler", level=3)
    add_p("Ứng suất cắt tại đáy (bed shear stress) mô tả lực cản tiêu tán năng lượng của dòng chảy khi di chuyển qua các bề mặt lớp phủ có độ nhám khác nhau (lòng sông, bãi cỏ, đất canh tác lúa, đường giao thông, khu dân cư đô thị). Trong mô hình BG_Flood, thành phần ma sát đáy được tham số hóa thông qua định luật bán thực nghiệm Manning-Strickler [4]:")
    add_formula("τbx / ρ = g · n² · u · √(u² + v²) / h^(1/3)", "2.6")
    add_formula("τby / ρ = g · n² · v · √(u² + v²) / h^(1/3)", "2.7")
    add_p("Trong đó, n là hệ số độ nhám Manning (đơn vị: s / m^(1/3)). Hệ số n phụ thuộc trực tiếp vào loại hình lớp phủ bề mặt và độ gồ ghề của lòng dẫn. Trong đồ án này, nhằm phản ánh tính không đồng nhất về mặt thủy lực của các dạng thảm phủ trên lưu vực, hệ số nhám Manning được thiết lập dưới dạng trường dữ liệu raster phân bố không gian n(x,y) xây dựng từ dữ liệu sử dụng đất ESA WorldCover 10m.")

    add_h("2.1.3. Phương pháp thể tích hữu hạn (FVM) dạng Godunov và bộ giải Riemann HLLC", level=3)
    add_p("Hệ phương trình nước nông 2 chiều là hệ phương trình vi phân đạo hàm riêng phi tuyến thuộc lớp hyperbolic. Khi dòng lũ chuyển động với vận tốc lớn hoặc khi xuất hiện sóng xung kích (sóng tràn bờ, sóng vỡ đập), nghiệm của phương trình có thể xuất hiện các điểm gián đoạn mạnh (Discontinuities / Shock waves). Các phương pháp giải số truyền thống (như sai phân trung tâm) thường xuất hiện hiện tượng dao động số học phi vật lý (Spurious Numerical Oscillations) tại các vùng gián đoạn, dẫn đến mất ổn định số học và làm gián đoạn quá trình tính toán.")
    add_p("Để khắc phục hạn chế trên, mô hình BG_Flood sử dụng phương pháp thể tích hữu hạn (Finite Volume Method - FVM) dạng Godunov với độ chính xác bậc 2 thông qua kỹ thuật tái tạo không gian MUSCL kết hợp bước thời gian thích nghi [12], [13]. Miền tính toán được rời rạc hóa thành lưới các ô thể tích kiểm soát (Control Volume) hình vuông kích thước Δx x Δy. Tích phân phương trình (2.1) trên ô thể tích (i, j) trong khoảng thời gian từ t đến t + dt dẫn đến phương thức cập nhật các biến bảo toàn trung bình ô:")
    add_formula("U_{i,j}^{n+1} = U_{i,j}^n - (dt/Δx) · [ F_{i+1/2, j} - F_{i-1/2, j} ] - (dt/Δy) · [ G_{i, j+1/2} - G_{i, j-1/2} ] + dt · S_{i,j}", "2.8")
    add_p("Trong đó, F_{i±1/2, j} và G_{i, j±1/2} là các thông lượng số (Numerical Fluxes) đi qua các mặt tiếp xúc biên giữa ô (i, j) với các ô láng giềng. Các thông lượng số này được xác định thông qua việc giải bài toán Riemann tại từng mặt phân cách ô lưới bằng bộ giải Riemann xấp xỉ HLLC (Harten-Lax-van Leer with Contact wave restoration) [12], [13]. Trong khi bộ giải HLL gốc của Harten, Lax và van Leer (1983) [13] chỉ giả định cấu trúc hai sóng biên và bỏ qua sóng trượt tiếp xúc (Contact/Shear wave), bộ giải HLLC được hoàn thiện bởi Toro (2001) [12] đã khôi phục thành công sóng tiếp xúc ở trạng thái trung gian. Cấu trúc 3 sóng này cho phép mô tả chính xác sự gián đoạn của thành phần vận tốc tiếp tuyến và mặt phân giới ướt/khô, đồng thời bảo toàn tính không âm của cột nước h (Positivity-preserving) và tái hiện trung thực các hiện tượng sóng kích bề mặt.")

    add_h("2.1.4. Điều kiện ổn định Courant-Friedrichs-Lewy (CFL) thích nghi", level=3)
    add_p("Để đảm bảo tính ổn định số học của lược đồ hiện số (Explicit scheme), bước thời gian tính toán dt cần thỏa mãn điều kiện ổn định Courant–Friedrichs–Lewy (CFL) [12]:")
    add_formula("dt ≤ CFL · min_{i,j} [ Δx / ( |u_{i,j}| + c_{i,j} ) , Δy / ( |v_{i,j}| + c_{i,j} ) ]", "2.9")
    add_p("Trong đó: c_{i,j} = √(g · h_{i,j}) là vận tốc truyền sóng trọng trường tự do trong cột nước nông; |u| + c và |v| + c là vận tốc truyền thông tin lớn nhất của sóng nước; hệ số Courant (CFL) là tham số ổn định không thứ nguyên (0 < CFL ≤ 1).")
    add_p("Trong mô hình BG_Flood, thuật toán tự động kiểm tra vận tốc dòng chảy trên toàn bộ 4.4 triệu ô lưới tại mỗi bước tính và điều chỉnh thích nghi bước thời gian dt (Adaptive Time-stepping). Khi nước dâng nhanh tại các vị trí có độ sâu lớn h hoặc vận tốc dòng chảy u, v cao, dt tự động giảm xuống (khoảng 0.7s) nhằm thỏa mãn điều kiện ổn định CFL; trong các giai đoạn dòng chảy biến đổi chậm, bước thời gian tự động tăng lên để nâng cao hiệu suất tính toán.")

    add_h("2.1.5. Kỹ thuật xử lý ranh giới ướt/khô (Wet-Dry Treatment) và kiểm soát lỗi NaN", level=3)
    add_p("Một trong những thách thức của mô phỏng ngập lụt trên đồng bằng là xử lý ranh giới di động giữa vùng đất khô (h = 0) và vùng ngập nước (h > 0). Tại mép nước tràn bờ, khi độ sâu h tiến dần về 0, các số hạng ma sát đáy τb ∝ 1/h^(1/3) và phép tính vận tốc u = (hu)/h xuất hiện điểm kỳ dị do chia cho 0, làm phát sinh giá trị không xác định NaN (Not-a-Number) và gây phân kỳ trường tính toán.")
    add_p("Mô hình BG_Flood xử lý vấn đề trên bằng kỹ thuật kiểm soát ngưỡng ướt/khô cục bộ:")
    add_p("- Ngưỡng độ sâu tối thiểu h_eps = 0.001 m (1 mm).")
    add_p("- Nếu h_{i,j} < h_eps: Ô lưới được xác định là ô khô. Mô hình thiết lập các thành phần động lượng hu = 0, hv = 0 và vận tốc u = 0, v = 0; đồng thời cô lập các số hạng ma sát đáy và gradient áp suất nhằm loại bỏ hiện tượng kỳ dị toán học.")
    add_p("- Đồng thời, cơ chế cân bằng thủy tĩnh (Well-Balanced Property) được cài đặt để đảm bảo rằng tại trạng thái 'hồ nước tĩnh' (Lake at rest: zs = const, u = v = 0 trên địa hình đáy biến đổi), thông lượng gradient áp suất thủy tĩnh cân bằng chính xác với số hạng nguồn độ dốc đáy ở mức sai số làm tròn máy tính.")

    add_h("2.2. Quy trình xử lý và trích xuất vết ngập từ ảnh viễn thám Sentinel-1 SAR", level=2)
    add_p("Để tạo ra bộ dữ liệu kiểm định mặt đất (Ground-truth benchmark) khách quan, đồ án đã xây dựng quy trình tự động hóa xử lý ảnh radar Sentinel-1 SAR bao gồm 6 giai đoạn kỹ thuật:")
    add_p("Giai đoạn 1: Thu nhận và nạp siêu dữ liệu (Data Ingestion): Thu thập tệp ảnh Sentinel-1 IW GRD chụp lúc 05:36 ngày 30/11/2021 (thời điểm đỉnh lũ trận lụt tại Phú Yên). Trích xuất kênh phân cực đồng VV (Vertical-Vertical) với kích thước ma trận ảnh thô 1.911 hàng x 2.402 cột.")
    add_p("Giai đoạn 2: Cập nhật quỹ đạo vệ tinh chính xác (Precise Orbit Ephemerides): Nạp tệp quỹ đạo chính xác (Sentinel-1 Precise Orbit Determination - POD) do ESA công bố sau 20 ngày kể từ khi vệ tinh chụp, hiệu chỉnh sai số vị trí tâm khối của vệ tinh xuống dưới 5 cm.")
    add_p("Giai đoạn 3: Hiệu chuẩn bức xạ (Radiometric Calibration): Chuyển đổi giá trị số số học (Digital Number - DN) của các pixel ảnh sang hệ số tán xạ ngược radar chuẩn Sigma Nought (σ⁰) theo công thức:")
    add_formula("σ⁰ (dB) = 10 · log10( DN² / A_i² )", "2.10")
    add_p("với A_i là hệ số hiệu chuẩn được cung cấp trong bảng tra cứu (Calibration LUT) của siêu dữ liệu ảnh.")
    add_p("Giai đoạn 4: Hiệu chỉnh địa hình bằng mô hình Range-Doppler (Terrain Correction): Sóng radar chiếu xiên tạo ra các biến dạng hình học trên địa hình đồi núi (co ngắn dốc - Foreshortening, chồng bóng - Layover, bóng radar - Shadowing). Sử dụng mô hình số độ cao SRTM/Copernicus 30m tích hợp trong thuật toán Range-Doppler để nắn chỉnh hình học, chuyển đổi ảnh từ hệ tọa độ Slant Range sang hệ tọa độ không gian địa lý phẳng UTM Zone 49N (WGS84) với kích thước pixel 30m x 30m, đối chiếu đồng bộ với mô hình số độ cao FABDEM 30m.")
    add_p("Giai đoạn 5: Lọc nhiễu đốm thích nghi (Adaptive Speckle Filtering): Nhiễu đốm (Speckle Noise) là hiện tượng giao thoa ngẫu nhiên của các sóng radar phản xạ từ các bộ tán xạ nhỏ trong ô phân giải. Áp dụng bộ lọc thích nghi Refined Lee Filter kích thước cửa sổ 5x5 pixel nhằm triệt tiêu nhiễu đốm nhân tính trên các vùng mặt nước đồng nhất, đồng thời duy trì độ sắc nét của ranh giới tiếp xúc giữa bờ và mép nước.")
    add_p("Giai đoạn 6: Phân ngưỡng tự động Otsu và Lọc nước thường trực:")
    add_p("Áp dụng thuật toán tối ưu hóa phương sai giữa hai lớp của Otsu [5] trên toàn bộ biểu đồ tần số σ⁰. Ngưỡng phân tách tối ưu được xác định tự động ở mức T* = -14.85 dB. Các pixel có giá trị σ⁰ < -14.85 dB được gắn nhãn là nước (Water = 1), các pixel còn lại là cạn (Non-water = 0).")
    add_p("Cuối cùng, nạp lớp bản đồ mật độ nước thường trực (Permanent Water Mask) trích xuất từ bộ dữ liệu Global Surface Water của Trung tâm Nghiên cứu Chung Châu Âu (JRC) [14] để loại bỏ các thủy vực cố định (lòng sông Ba mùa cạn, đầm Ô Loan, biển Đông), thu được duy nhất lớp nhãn nhị phân thể hiện vết ngập lũ thực tế (Flood Extent Benchmark).")

    add_h("2.3. Các phương pháp tiền xử lý và giải quyết rào cản nhân tạo trên địa hình", level=2)
    add_h("2.3.1. Thuật toán lấp hố sụt thủy văn Priority-Flood", level=3)
    add_p("Mô hình số độ cao FABDEM 30m sau khi loại bỏ công trình và tán cây thường xuất hiện các điểm trũng giả tạo (Sinks / Pits) cục bộ có diện tích 1 đến vài pixel, đặc biệt tại các sườn dốc đồi núi bao quanh đồng bằng Tuy Hòa. Khi mô hình thủy lực tính toán, nước mưa dồn vào các hố sụt này tạo thành các điểm tập trung dòng chảy với độ dốc địa hình cục bộ ∂zb/∂x rất lớn, làm tăng vận tốc dòng chảy tính toán, vi phạm điều kiện ổn định CFL và dẫn đến phân kỳ số học (lỗi NaN) tại bước thời gian t ≈ 160.000s trong kịch bản V40.")
    add_p("Để khắc phục hiện tượng này, đồ án đã triển khai thuật toán lấp hố sụt thủy văn tối ưu Priority-Flood đề xuất bởi Barnes et al. (2014) [14]. Thuật toán sử dụng cấu trúc hàng đợi ưu tiên (Priority Queue):")
    add_p("- Bước 1: Khởi tạo hàng đợi với tất cả các ô lưới nằm trên đường biên ngoài của lưu vực (vùng thoát nước ra biển có cao độ 0m).")
    add_p("- Bước 2: Liên tục lấy ô có cao độ thấp nhất trong hàng đợi ra xử lý. Xét 8 ô láng giềng xung quanh; nếu cao độ của ô láng giềng thấp hơn cao độ của ô hiện tại, điều đó chứng tỏ ô láng giềng là một hố sụt nội lục không có lối thoát. Thuật toán sẽ ngay lập tức 'nâng' cao độ của ô láng giềng lên bằng đúng cao độ của ô hiện tại.")
    add_p("- Bước 3: Thêm ô láng giềng đã hiệu chỉnh vào hàng đợi và lặp lại cho đến khi toàn bộ các hố trũng trên lưu vực được xử lý.")
    add_p("Việc áp dụng Priority-Flood thiết lập tính liên tục của hướng thoát nước trên bề mặt địa hình, loại bỏ các vùng trũng cục bộ gây mất ổn định vận tốc tính toán.")

    add_h("2.3.2. Thuật toán Đục đê và hạ đường giao thông (Levee & Road Breaching)", level=3)
    add_p("Để khắc phục hiện tượng thân đê và đường giao thông tạo thành rào cản nhân tạo ngăn dòng chảy tràn từ sông Ba ra bãi tràn trên lưới DEM 30m, nghiên cứu đã xây dựng thuật toán mở đường tràn cục bộ (Levee Breaching) [15]:")
    add_p("- Bước 1: Xác định mạng lưới các dải cản trở địa hình (Barriers) thông qua việc tính toán độ nhô cao cục bộ (Local Relief) so với bãi bồi lân cận: Relief(x,y) = DEM(x,y) - FocalMean(DEM, r=150m).")
    add_p("- Bước 2: Xác định các vị trí đê bao và đường giao thông nằm trong vùng có khả năng tràn lũ (HAND <= 3.5m).")
    add_p("- Bước 3: Thực hiện can thiệp hạ cao độ địa hình cục bộ: Tại các vị trí cầu cống tiêu thoát nước thực tế, cao độ ô lưới DEM được hạ thấp cục bộ một khoảng delta_z = 2.0m (bảo đảm không làm âm cao độ đáy so với mực nước biển), tạo thành các khe xả tràn nhân tạo có khẩu độ tương đương chiều rộng 1 đến 2 ô lưới (30m - 60m), cho phép nước lũ từ lòng sông thoát qua đê để tràn vào đồng bằng.")

    add_h("2.3.3. Thuật toán San phẳng hình thái (Morphological Carving) hai bên bờ sông", level=3)
    add_p("Phân tích kết quả thực nghiệm kịch bản V44 cho thấy: Thuật toán mở đường tràn ban đầu phụ thuộc vào mặt nạ ngập lụt trích xuất từ ảnh SAR. Do đỉnh đê có cao trình cao hơn mực nước nên ảnh SAR phân loại là bề mặt cạn (SAR = 0), dẫn đến việc thuật toán không xử lý các đoạn đê chính ven sông Ba. Nhằm khắc phục hạn chế này, phương pháp san phẳng hình thái (Morphological Carving) được đề xuất:")
    add_p("- Bước 1: Dùng phép toán hình thái học GIS tạo một vùng đệm (Buffer Zone) mở rộng từ 90m đến 150m (tương ứng 3 đến 5 ô lưới) chạy dọc song song hai bên mép bờ sông Ba.")
    add_p("- Bước 2: Quét toàn bộ các ô lưới nằm trong vùng đệm; bất kỳ ô lưới nào có cao trình nhô cao hơn cao trình trung bình của mặt bãi bồi phía sau đê (ngưỡng z_cut = 3.5m) đều được hạ thấp đồng mức về 3.5m.")
    add_p("Phương pháp này tương đương với giải pháp hạ thấp đồng mức dải đê nhân tạo cản dòng dọc hành lang sông, mở rộng tiết diện thoát lũ và tạo điều kiện cho dòng chảy tràn vào đồng bằng.")

    add_h("2.4. Phương pháp đánh giá và kiểm chuẩn mô hình", level=2)
    add_h("2.4.1. Ma trận nhầm lẫn không gian (Spatial Contingency Matrix)", level=3)
    add_p("Để kiểm định độ chính xác của mô hình thủy lực so với ảnh vệ tinh radar Sentinel-1 SAR một cách định lượng và khách quan, toàn bộ miền tính toán được chồng xếp không gian ở mức từng ô pixel 30m x 30m. Ma trận nhầm lẫn không gian 2x2 được thiết lập bao gồm 4 trạng thái nhị phân (Bảng 2.1):")
    if add_caption:
        add_caption("Bảng 2.1: Ma trận nhầm lẫn không gian (Contingency Matrix) đánh giá độ khớp vết ngập", is_table=True)
    table_contingency = doc.add_table(rows=3, cols=3)
    table_contingency.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_contingency.autofit = False

    c_data = [
        ("Phân loại trạng thái", "Vệ tinh SAR: Ngập (1)", "Vệ tinh SAR: Cạn (0)"),
        ("Mô phỏng: Ngập (h >= 0.3m)", "True Positive (TP)\nDương tính thật (Khớp đúng)", "False Positive (FP)\nDương tính giả (Báo động sai)"),
        ("Mô phỏng: Cạn (h < 0.3m)", "False Negative (FN)\nÂm tính giả (Bỏ sót ngập)", "True Negative (TN)\nÂm tính thật (Khô ráo)")
    ]
    for r_i, row in enumerate(c_data):
        for c_i, val in enumerate(row):
            c = table_contingency.rows[r_i].cells[c_i]
            c.text = val
            if set_cell_border:
                set_cell_border(c)
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            if r_i == 0:
                if set_cell_shading:
                    set_cell_shading(c, "1F4E79")
                for r in c.paragraphs[0].runs:
                    r.bold = True
                    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            else:
                for r in c.paragraphs[0].runs:
                    r.font.name = 'Times New Roman'
                    r.font.size = Pt(10.5)

    add_p("Ý nghĩa và cơ chế xác định từng trạng thái trong ma trận:")
    add_p("- True Positive (TP - Dương tính thật, hiển thị màu Xanh lá cây): Số ô lưới mà cả mô hình mô phỏng lẫn ảnh vệ tinh SAR đều xác nhận bị ngập nước (h_sim > 0.3m và SAR_flood = 1). Đây là vùng mô hình dự báo trùng khớp với vết nước trên ảnh vệ tinh.")
    add_p("- False Positive (FP - Dương tính giả / Báo động sai, hiển thị màu Đỏ): Số ô lưới mô hình báo ngập nhưng ảnh vệ tinh SAR xác nhận không ngập (h_sim > 0.3m và SAR_flood = 0). Phản ánh xu hướng mô hình dự báo ngập diện rộng ngoài thực tế.")
    add_p("- False Negative (FN - Âm tính giả / Bỏ sót, hiển thị màu Xanh dương): Số ô lưới ảnh vệ tinh SAR ghi nhận ngập nhưng mô hình không có nước (h_sim <= 0.3m và SAR_flood = 1). Phản ánh sự thiếu hụt nước của mô hình do cản trở địa hình hoặc thiếu nguồn lưu lượng biên.")
    add_p("- True Negative (TN - Âm tính thật, hiển thị màu Xám sáng): Số ô lưới cả mô hình và vệ tinh đều xác nhận khô ráo (h_sim <= 0.3m và SAR_flood = 0).")

    add_h("2.4.2. Hệ thống các chỉ số định lượng đánh giá", level=3)
    add_p("Từ các giá trị TP, FP, FN, TN, đồ án áp dụng hệ thống các chỉ số kiểm chuẩn thống kê tiêu chuẩn quốc tế:")
    add_p("1. Chỉ số thành công tới hạn (Critical Success Index - CSI / Threat Score):")
    add_formula("CSI = TP / (TP + FP + FN) · 100%", "2.11")
    add_p("CSI là chỉ số đánh giá toàn diện trong mô hình hóa ngập lụt bề mặt. Chỉ số này dao động từ 0% (hoàn toàn không trùng khớp) đến 100% (trùng khớp hoàn hảo giữa mô phỏng và quan trắc). Khác với độ chính xác tổng thể (Overall Accuracy) thường bị ảnh hưởng bởi số lượng lớn các ô không ngập TN, CSI chỉ tập trung đánh giá trên tổng diện tích có liên quan đến ngập lụt và xử phạt đồng thời cả sai số báo động sai FP lẫn sai số bỏ sót FN.")
    add_p("2. Xác suất phát hiện đúng hay Độ phủ thực (Probability of Detection - POD / Recall):")
    add_formula("Recall = TP / (TP + FN) · 100%", "2.12")
    add_p("Recall đo lường tỷ lệ phần trăm diện tích ngập thực tế trên ảnh vệ tinh được mô hình phản ánh thành công. Giá trị Recall càng cao chứng tỏ sóng lũ của mô hình đã lan tỏa tới hầu hết các vùng bị ngập.")
    add_p("3. Độ chính xác dự báo (Precision):")
    add_formula("Precision = TP / (TP + FP) · 100%", "2.13")
    add_p("Precision phản ánh mức độ tin cậy của các vùng mà mô hình báo ngập: Trong số các ô lưới mà mô hình dự báo có nước ngập, có bao nhiêu phần trăm là thực sự ngập ngoài thực địa.")
    add_p("4. Tỷ lệ báo động sai (False Alarm Ratio - FAR):")
    add_formula("FAR = FP / (TP + FP) · 100% = 100% - Precision", "2.14")
    add_p("5. Chỉ số F1-Score (Trung bình điều hòa giữa Precision và Recall):")
    add_formula("F1 = 2 · (Precision · Recall) / (Precision + Recall)", "2.15")
    add_p("6. Hệ số tương quan Matthews (Matthews Correlation Coefficient - MCC):")
    add_formula("MCC = (TP · TN - FP · FN) / √[ (TP + FP)(TP + FN)(TN + FP)(TN + FN) ]", "2.16")
    add_p("MCC là thước đo tương quan nhị phân cân bằng, có giá trị từ -1 (hoàn toàn nghịch đảo) qua 0 (dự báo ngẫu nhiên) đến +1 (dự báo hoàn hảo).")

    add_h("2.4.3. Phương pháp kiểm chứng địa hình bãi bồi độc lập (HAND Assessment)", level=3)
    add_p("Do ảnh vệ tinh radar Sentinel-1 chỉ chụp được tại một thời điểm duy nhất trong suốt 5 ngày lũ (lúc 05:36 ngày 30/11/2021) và có thể gặp phải các sai số che khuất tán cây (Radar Shadowing/Vegetation attenuation), việc chỉ dựa vào ảnh SAR là chưa đủ để khẳng định tính chân thực vật lý của toàn bộ quá trình mô phỏng.")
    add_p("Đồ án áp dụng phương pháp kiểm chứng địa hình bãi bồi độc lập thông qua việc chồng xếp lớp nước ngập mô phỏng lên bản đồ chỉ số thủy văn HAND (Height Above Nearest Drainage) [6]:")
    add_p("- Tính toán tỷ lệ diện tích nước ngập nằm trong đới bãi bồi tự nhiên (HAND <= 3.5m): P_HAND = (Diện tích ngập tại HAND <= 3.5m) / (Tổng diện tích ngập trên đất liền) · 100%.")
    add_p("Một mô hình thủy lực đạt tính hợp lý vật lý cao cần có P_HAND >= 85 - 90%. Nếu P_HAND thấp và xuất hiện diện tích ngập lớn ở đới HAND > 10m, điều đó chứng tỏ mô hình đang bị hiện tượng ngập lụt phi lý do lỗi tích lũy mưa hoặc tắc nghẽn dòng chảy sườn dốc.")

    add_h("2.5. Sơ đồ quy trình nghiên cứu tổng thể", level=2)
    add_p("Toàn bộ các nội dung nghiên cứu lý thuyết, thu thập dữ liệu, xử lý thuật toán số học và quy trình kiểm định được tích hợp thành một sơ đồ khung công nghệ hoàn chỉnh:")
    add_p("1. Dữ liệu đầu vào: Ảnh vệ tinh Sentinel-1 IW GRD, DEM FABDEM 30m, Sử dụng đất ESA WorldCover 10m, Mưa giờ ERA5 (145 trạm ảo), Lưu lượng xả lũ hồ Sông Ba Hạ, Sông Hinh.")
    add_p("2. Tiền xử lý dữ liệu: Nắn chỉnh địa hình Range-Doppler ảnh SAR, Lọc nhiễu Lee Filter, Phân ngưỡng Otsu -> Bản đồ ngập vệ tinh Benchmark; Xử lý địa hình: Priority-Flood Sink Filling, Levee Breaching -> Bản đồ DEM V44/V45; Xây dựng bản đồ độ nhám Manning không gian và thấm đất.")
    add_p("3. Mô phỏng thủy lực số 2D GPU: Nạp tham số vào BG_Flood, giải phương trình nước nông 2D Godunov, tự thích nghi bước thời gian dt theo điều kiện CFL, kiểm soát ranh giới ướt/khô chống NaN.")
    add_p("4. Đầu ra mô hình: Xuất tệp NetCDF4 chứa các trường dữ liệu h, zs, u, v định kỳ mỗi 3 giờ mô phỏng (tổng cộng 40 khung hình trong 120 giờ).")
    add_p("5. Kiểm định và Đánh giá: Đối chiếu không gian với ảnh SAR tại mốc 102 giờ (tính ma trận Contingency: CSI, Recall, Precision, F1, MCC); Chồng xếp bản đồ HAND kiểm chứng tính hợp lý bãi bồi tự nhiên.")

    doc.add_page_break()
    print("Xong Chương 2.")
