# -*- coding: utf-8 -*-
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml

def build_front_matter(doc, add_h, add_p, set_cell_border, set_cell_shading):
    # ==============================================================================
    # 1. TRANG BÌA CHÍNH (COVER PAGE)
    # ==============================================================================
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_before = Pt(20)
    p_inst.paragraph_format.space_after = Pt(4)
    r1 = p_inst.add_run("ĐẠI HỌC QUỐC GIA HÀ NỘI\nTRƯỜNG ĐẠI HỌC CÔNG NGHỆ\n")
    r1.bold = True
    r1.font.name = 'Times New Roman'
    r1.font.size = Pt(13.5)
    r2 = p_inst.add_run("VIỆN CÔNG NGHỆ HÀNG KHÔNG VŨ TRỤ\n")
    r2.bold = True
    r2.font.name = 'Times New Roman'
    r2.font.size = Pt(14)
    r2.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    
    p_line = doc.add_paragraph()
    p_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_line.paragraph_format.space_after = Pt(50)
    r_l = p_line.add_run("-----------------------***-----------------------")
    r_l.bold = True

    p_deg = doc.add_paragraph()
    p_deg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_deg.paragraph_format.space_after = Pt(24)
    r_deg = p_deg.add_run("ĐỒ ÁN TỐT NGHIỆP ĐẠI HỌC HỆ CHÍNH QUY\nNGÀNH CÔNG NGHỆ HÀNG KHÔNG VŨ TRỤ")
    r_deg.bold = True
    r_deg.font.name = 'Times New Roman'
    r_deg.font.size = Pt(14.5)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(24)
    p_title.paragraph_format.space_after = Pt(40)
    r_t = p_title.add_run("ỨNG DỤNG VIỄN THÁM, GIS VÀ MÔ HÌNH THỦY LỰC SỐ\nĐỂ MÔ PHỎNG VÀ ĐÁNH GIÁ DIỄN BIẾN NGẬP LỤT\nTẠI HẠ LƯU LƯU VỰC SÔNG BA, TỈNH PHÚ YÊN")
    r_t.bold = True
    r_t.font.name = 'Times New Roman'
    r_t.font.size = Pt(17)
    r_t.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

    p_info = doc.add_paragraph()
    p_info.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_info.paragraph_format.first_line_indent = Inches(1.5)
    p_info.paragraph_format.space_before = Pt(60)
    p_info.paragraph_format.space_after = Pt(90)
    r_info = p_info.add_run(
        "Sinh viên thực hiện:\t\t[Họ và tên Sinh viên / CuongHM]\n"
        "Mã số sinh viên:\t\t[Mã số sinh viên]\n"
        "Khóa đào tạo:\t\t\tQH-2022-I/CQ\n"
        "Cán bộ hướng dẫn:\t\tTS. Hà Minh Cường\n"
        "Cơ quan công tác:\t\tViện Công nghệ Hàng không Vũ trụ"
    )
    r_info.font.name = 'Times New Roman'
    r_info.font.size = Pt(13)

    p_bot = doc.add_paragraph()
    p_bot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_b = p_bot.add_run("Hà Nội – Năm 2026")
    r_b.bold = True
    r_b.font.name = 'Times New Roman'
    r_b.font.size = Pt(13)

    doc.add_page_break()

    # ==============================================================================
    # 2. LỜI CAM ĐOAN & LỜI CẢM ƠN
    # ==============================================================================
    add_h("Lời cam đoan", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_p("Tôi xin cam đoan rằng công trình nghiên cứu trong đồ án tốt nghiệp này là do chính tôi thực hiện dưới sự định hướng và hướng dẫn khoa học trực tiếp của TS. Hà Minh Cường. Các số liệu, kết quả tính toán mô phỏng thủy lực và các phân tích viễn thám trình bày trong đồ án là hoàn toàn trung thực, khách quan và được đúc kết từ quá trình thực nghiệm nghiêm túc trên mô hình BG_Flood kết hợp dữ liệu ảnh vệ tinh Sentinel-1 SAR.")
    add_p("Các tài liệu tham khảo, số liệu trích dẫn kế thừa từ các công trình khoa học của các tác giả khác trong và ngoài nước đều được dẫn chiếu nguồn gốc rõ ràng, minh bạch theo đúng quy chuẩn học thuật quốc tế. Tôi xin chịu hoàn toàn trách nhiệm trước Hội đồng chấm đồ án và pháp luật về tính chính xác và liêm chính học thuật của công trình này.")
    add_p("Hà Nội, ngày … tháng … năm 2026\nSinh viên cam đoan\n\n\n[Họ và tên Sinh viên]", indent=False, align=WD_ALIGN_PARAGRAPH.RIGHT)

    doc.add_page_break()

    add_h("Lời cảm ơn", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_p("Đối với mỗi sinh viên ngành Công nghệ Hàng không Vũ trụ, đồ án tốt nghiệp không chỉ là dấu mốc quan trọng khép lại chặng đường học tập tại giảng đường đại học mà còn là công trình nghiên cứu khoa học độc lập đầu tay, đánh dấu sự trưởng thành về tư duy học thuật và năng lực thực hành chuyên môn. Trong suốt quá trình thực hiện đồ án, em đã nhận được sự quan tâm, chỉ dẫn tận tình từ các thầy cô, gia đình và bạn bè.")
    add_p("Trước hết, em xin bày tỏ lòng biết ơn sâu sắc và chân thành nhất tới TS. Hà Minh Cường – cán bộ giảng dạy tại Viện Công nghệ Hàng không Vũ trụ, Trường Đại học Công nghệ – ĐHQGHN. Thầy đã trực tiếp hướng dẫn, định hướng khoa học, truyền đạt cho em những kiến thức chuyên sâu về công nghệ viễn thám radar, xử lý dữ liệu địa không gian GIS và kỹ thuật mô hình hóa thủy lực số hai chiều. Sự nghiêm cẩn, tận tụy và những lời động viên quý báu của Thầy là động lực to lớn giúp em vượt qua nhiều rào cản kỹ thuật phức tạp trong quá trình nghiên cứu.")
    add_p("Em xin trân trọng cảm ơn các thầy cô giáo trong Ban Giám hiệu, Ban Chủ nhiệm Viện Công nghệ Hàng không Vũ trụ và toàn thể cán bộ, giảng viên Trường Đại học Công nghệ – ĐHQGHN đã tận tâm giảng dạy, trang bị cho em nền tảng kiến thức khoa học cơ bản và cơ sở ngành vững chắc trong suốt khóa học.")
    add_p("Em cũng xin gửi lời cảm ơn tới các chuyên gia và các bạn đồng môn tại phòng thí nghiệm đã luôn đồng hành, chia sẻ tài nguyên tính toán GPU, thảo luận chuyên môn và hỗ trợ em giải quyết bài toán tối ưu hóa thuật toán Godunov trên GPU.")
    add_p("Cuối cùng, em xin bày tỏ lòng biết ơn sâu sắc tới gia đình và người thân, những người luôn động viên, hỗ trợ và tạo mọi điều kiện thuận lợi nhất để em hoàn thành chương trình đào tạo và đồ án tốt nghiệp này.")
    add_p("Em xin chân thành cảm ơn!")
    add_p("Hà Nội, ngày … tháng … năm 2026\nSinh viên thực hiện\n\n\n[Họ và tên Sinh viên]", indent=False, align=WD_ALIGN_PARAGRAPH.RIGHT)

    doc.add_page_break()

    # ==============================================================================
    # 3. TÓM TẮT & ABSTRACT
    # ==============================================================================
    add_h("Tóm tắt", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_p("Lũ lụt là một trong những loại hình thiên tai nguy hiểm và có tần suất xuất hiện cao tại khu vực duyên hải miền Trung Việt Nam, đặc biệt tại các lưu vực sông có đặc điểm địa hình dốc, thời gian tập trung nước nhanh và chịu sự điều tiết xả lũ phức tạp từ hệ thống các hồ chứa thủy điện ở thượng nguồn. Trận lũ cuối tháng 11 năm 2021 tại tỉnh Phú Yên là một sự kiện ngập lụt quy mô lớn, xảy ra dưới tác động tổ hợp của mưa lớn diện rộng và vận hành xả lũ với lưu lượng đỉnh trên 9.000 m³/s từ thủy điện Sông Ba Hạ, gây ngập lụt diện rộng tại vùng hạ lưu sông Ba và đồng bằng Tuy Hòa. Mục tiêu trọng tâm của đồ án tốt nghiệp này là xây dựng, hiệu chỉnh và kiểm định một quy trình mô phỏng thủy lực số hai chiều (2D) độ phân giải 30m sử dụng mô hình mã nguồn mở BG_Flood gia tốc trên GPU, kết hợp chặt chẽ với công nghệ viễn thám radar khẩu độ tổng hợp Sentinel-1 (SAR) và hệ thống thông tin địa lý (GIS).")
    add_p("Nghiên cứu tập trung giải quyết bài toán cốt lõi về rào cản nhân tạo trên mô hình số độ cao (DEM) — nguyên nhân chính khiến các mô hình thủy lực quy mô lớn không thể tái hiện hiện tượng nước tràn bờ qua hệ thống đê điều, đường giao thông. Thông qua quá trình phân tích số học và thực nghiệm qua nhiều phiên bản nâng cấp (từ V1 đến V44), đồ án đã phát triển và ứng dụng các giải pháp kỹ thuật: chuẩn hóa cấu hình hệ số nhám Manning, thuật toán lấp hố sụt thủy văn (Priority-Flood Sink Filling) hạn chế sốc vận tốc, thuật toán mở đường tràn cục bộ (Levee Breaching) và san phẳng hình thái (Morphological Carving). Kết quả mô phỏng trận lũ 120 giờ cho thấy mô hình duy trì tính ổn định số học trong suốt chuỗi tính toán (không xảy ra lỗi phân kỳ NaN) với tốc độ tính toán nhanh gấp 1.75 - 1.83 lần thời gian thực trên GPU.")
    add_p("Kiểm định định lượng với vết ngập thực tế trích xuất từ ảnh vệ tinh Sentinel-1 SAR (tại thời điểm 05:36 ngày 30/11/2021, tức 102 giờ mô phỏng) cho thấy chỉ số thành công tới hạn (CSI) đạt 20.64%, độ phủ (Recall) đạt 24.97% và độ chính xác (Precision) đạt 54.32%, cải thiện đáng kể so với các phiên bản ban đầu (CSI đạt 3.29% ở V23 và 13.5% ở V43). Đồng thời, phương pháp kiểm chứng địa hình độc lập HAND (Height Above Nearest Drainage) xác nhận 90.43% tổng diện tích ngập mô phỏng phân bố phù hợp trong vùng bãi bồi tự nhiên (HAND <= 3.5m). Kết quả nghiên cứu cung cấp cơ sở khoa học và công cụ mô phỏng hỗ trợ công tác quy hoạch, cảnh báo sớm và giảm thiểu rủi ro thiên tai lũ lụt tại tỉnh Phú Yên.")
    add_p("Từ khóa: BG_Flood, Hệ phương trình nước nông 2D, Sentinel-1 SAR, GIS, Đục đê (Levee Breaching), Hạ lưu Sông Ba, Phú Yên, CSI, HAND.", bold_prefix="")

    doc.add_page_break()

    add_h("Abstract", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    add_p("Flooding is one of the most frequent and hazardous natural disasters in Central Vietnam, particularly in short and steep river basins governed by complex upstream reservoir operations. The flood event in late November 2021 in Phu Yen Province is a representative case study, caused by high-volume emergency discharge exceeding 9,000 m³/s from the Song Ba Ha hydropower reservoir combined with heavy monsoon rainfall, triggering widespread inundation across the Tuy Hoa plain. The primary objective of this graduation thesis is to establish, calibrate, and validate a high-resolution (30m) 2D hydrodynamic flood simulation framework using the GPU-accelerated open-source model BG_Flood, integrated with Sentinel-1 Synthetic Aperture Radar (SAR) remote sensing and Geographic Information Systems (GIS).")
    add_p("This study tackles a practical challenge in computational hydraulics: the presence of artificial barriers in digital elevation models (DEMs), which restrict floodwaters from expanding naturally across floodplains. Through systematic numerical experimentation across progressive versions (V1 to V44), targeted technical solutions were implemented: resolving spatial roughness parameterization, applying Priority-Flood sink filling to eliminate local shock instabilities, levee breaching, and morphological carving along river corridors. The 120-hour flood simulation maintained numerical stability throughout computation (zero NaN divergence) while achieving a real-time computational speedup of 1.75x to 1.83x on GPU architecture.")
    add_p("Quantitative validation against benchmark flood extents derived from Sentinel-1 SAR imagery (captured at simulation hour 102) demonstrated clear progress: the Critical Success Index (CSI) reached 20.64%, with a Recall of 24.97% and Precision of 54.32%, substantially improving upon earlier baseline setups (CSI of 3.29% in V23 and 13.5% in V43). Furthermore, independent topographic verification using the Height Above Nearest Drainage (HAND) index confirmed that 90.43% of simulated inundation appropriately settled within natural floodplains (HAND <= 3.5m). This research delivers a consistent numerical modeling workflow for flood hazard assessment and disaster mitigation in Phu Yen Province.")
    add_p("Keywords: BG_Flood, 2D Shallow Water Equations, Sentinel-1 SAR, GIS, Levee Breaching, Lower Ba River, Phu Yen, CSI, HAND index.", bold_prefix="")

    doc.add_page_break()

    # ==============================================================================
    # 4. DANH MỤC TỪ VIẾT TẮT
    # ==============================================================================
    add_h("Danh mục từ viết tắt", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)

    table_abbr = doc.add_table(rows=1, cols=3)
    table_abbr.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_abbr.autofit = False

    hdr_cells = table_abbr.rows[0].cells
    hdr_cells[0].text = "STT"
    hdr_cells[1].text = "Viết tắt"
    hdr_cells[2].text = "Thuật ngữ Tiếng Anh / Tiếng Việt"
    for c in hdr_cells:
        set_cell_shading(c, "1F4E79")
        set_cell_border(c, top="single", bottom="single", left="none", right="none")
        for p in c.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.bold = True
                r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                r.font.name = 'Times New Roman'
                r.font.size = Pt(12)

    abbr_list = [
        ("1", "2D SWE", "2D Shallow Water Equations (Phương trình nước nông hai chiều)"),
        ("2", "BG_Flood", "Block-Adaptive GPU-accelerated Flood Model (Mô hình ngập lụt GPU)"),
        ("3", "SAR", "Synthetic Aperture Radar (Radar khẩu độ tổng hợp)"),
        ("4", "GIS", "Geographic Information System (Hệ thống thông tin địa lý)"),
        ("5", "DEM", "Digital Elevation Model (Mô hình số độ cao)"),
        ("6", "DTM", "Digital Terrain Model (Mô hình địa hình số trần - Bare Earth)"),
        ("7", "DSM", "Digital Surface Model (Mô hình bề mặt số - có nhà và cây)"),
        ("8", "CSI", "Critical Success Index (Chỉ số thành công tới hạn)"),
        ("9", "POD / Recall", "Probability of Detection (Xác suất phát hiện / Độ phủ đúng)"),
        ("10", "FAR", "False Alarm Ratio (Tỷ lệ báo động sai / Dương tính giả)"),
        ("11", "Precision", "Độ chính xác mô phỏng (TP / (TP + FP))"),
        ("12", "HAND", "Height Above Nearest Drainage (Độ cao so với mạng thoát nước gần nhất)"),
        ("13", "FVM", "Finite Volume Method (Phương pháp thể tích hữu hạn)"),
        ("14", "CFL", "Courant–Friedrichs–Lewy condition (Điều kiện ổn định bước thời gian CFL)"),
        ("15", "HLL / HLLC", "Harten-Lax-van Leer Contact (Bộ giải sóng Riemann số học)"),
        ("16", "GPU", "Graphics Processing Unit (Bộ vi xử lý đồ họa chuyên dụng)"),
        ("17", "CUDA", "Compute Unified Device Architecture (Nền tảng tính toán song song NVIDIA)"),
        ("18", "ERA5", "ECMWF Reanalysis v5 (Dữ liệu tái phân tích khí quyển toàn cầu)"),
        ("19", "GEE", "Google Earth Engine (Nền tảng điện toán đám mây xử lý ảnh vệ tinh)"),
        ("20", "IW GRD", "Interferometric Wide Swath Ground Range Detected (Chế độ ảnh radar mặt đất)"),
        ("21", "GSW", "Global Surface Water (Cơ sở dữ liệu mặt nước toàn cầu JRC)"),
        ("22", "WMO", "World Meteorological Organization (Tổ chức Khí tượng Thế giới)"),
        ("23", "BĐKH", "Biến đổi khí hậu toàn cầu"),
        ("24", "PCTT", "Phòng chống thiên tai và Tìm kiếm cứu nạn"),
        ("25", "KTTV", "Khí tượng Thủy văn"),
        ("26", "TP / FP", "True Positive (Dương tính thật) / False Positive (Dương tính giả)"),
        ("27", "FN / TN", "False Negative (Âm tính giả) / True Negative (Âm tính thật)"),
        ("28", "MCC", "Matthews Correlation Coefficient (Hệ số tương quan Matthews)")
    ]

    for item in abbr_list:
        row_cells = table_abbr.add_row().cells
        row_cells[0].text = item[0]
        row_cells[1].text = item[1]
        row_cells[2].text = item[2]
        set_cell_border(row_cells[0])
        set_cell_border(row_cells[1])
        set_cell_border(row_cells[2])
        row_cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        row_cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
        row_cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
        for cell in row_cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.name = 'Times New Roman'
                    r.font.size = Pt(11)

    doc.add_page_break()

    # ==============================================================================
    # 5. DANH MỤC HÌNH ẢNH & DANH MỤC BẢNG BIỂU
    # ==============================================================================
    add_h("Danh mục hình ảnh", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    figures_list = [
        "Hình 1.1: Cơ chế hoạt động của Radar khẩu độ tổng hợp (SAR) và các dạng tán xạ sóng",
        "Hình 1.2: So sánh cấu trúc không gian giữa DSM, DEM và DTM trong mô phỏng dòng chảy bề mặt",
        "Hình 1.3: Nguyên lý phân định đới bãi bồi thủy văn dựa trên chỉ số địa hình HAND",
        "Hình 2.1: Lưới sai phân thể tích hữu hạn (FVM) và bộ giải Riemann HLLC trên mặt tiếp xúc ô lưới",
        "Hình 2.2: Quy trình tự động xử lý ảnh radar Sentinel-1 SAR và phân ngưỡng Otsu trích xuất vết lũ",
        "Hình 2.3: Minh họa cơ chế rào cản nhân tạo trên DEM 30m và thuật toán đục đê (Levee Breaching)",
        "Hình 2.4: Sơ đồ ma trận nhầm lẫn không gian Contingency (TP, FP, FN, TN) kiểm chuẩn với ảnh vệ tinh",
        "Hình 2.5: Sơ đồ khung quy trình nghiên cứu tổng thể của đồ án",
        "Hình 3.1: Bản đồ mạng lưới sông ngòi và lưu vực hạ lưu sông Ba, tỉnh Phú Yên",
        "Hình 3.2: Chuỗi thời gian lưu lượng xả lũ đập Sông Ba Hạ và Sông Hinh trong trận lũ tháng 11/2021",
        "Hình 3.3: Bản đồ phân bố hệ số nhám Manning không gian 30m khu vực hạ lưu Phú Yên",
        "Hình 3.4: Diễn biến lan tỏa của sóng lũ qua các khung hình thời gian (t = 3h, 24h, 54h, 102h)",
        "Hình 3.5: Bản đồ kiểm chuẩn không gian 4 màu mô phỏng V44 so với ảnh SAR tại mốc 102 giờ",
        "Hình 3.6: Mặt cắt ngang địa hình (DEM) và mực nước sông Ba tại X=314955 minh chứng thân đê cản lũ",
        "Hình 3.7: Bản đồ phân bố diện tích ngập lụt theo các cấp địa hình thủy văn HAND"
    ]
    for fig in figures_list:
        p_fig = doc.add_paragraph()
        p_fig.paragraph_format.space_before = Pt(2)
        p_fig.paragraph_format.space_after = Pt(4)
        r = p_fig.add_run(fig)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)

    doc.add_page_break()

    add_h("Danh mục bảng biểu", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)
    tables_list = [
        "Bảng 2.1: Ma trận nhầm lẫn không gian (Contingency Matrix) đánh giá độ khớp vết ngập",
        "Bảng 3.1: Các thông số cấu hình vật lý và số học của mô hình thủy lực BG_Flood",
        "Bảng 3.2: Hệ số nhám Manning quy đổi từ bản đồ lớp phủ đất ESA WorldCover 10m",
        "Bảng 3.3: Lịch sử tiến hóa và so sánh hiệu quả các thế hệ kịch bản mô phỏng từ V1 đến V45",
        "Bảng 3.4: Tiến trình diễn biến các chỉ số kiểm chuẩn theo chuỗi thời gian mô phỏng V44 (40 khung hình)",
        "Bảng 3.5: Bảng thống kê chi tiết các chỉ số định lượng tại thời điểm đỉnh lũ 102 giờ (Khung hình 33)",
        "Bảng 3.6: Phân bố diện tích ngập của mô hình V44 theo các đới thủy văn địa hình HAND",
        "Bảng 3.7: Kết quả thử nghiệm sơ bộ mô hình học máy (Surrogate Model) dự báo độ sâu ngập"
    ]
    for tab in tables_list:
        p_tab = doc.add_paragraph()
        p_tab.paragraph_format.space_before = Pt(2)
        p_tab.paragraph_format.space_after = Pt(4)
        r = p_tab.add_run(tab)
        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)

    doc.add_page_break()
    print("Xong phần Front Matter.")
