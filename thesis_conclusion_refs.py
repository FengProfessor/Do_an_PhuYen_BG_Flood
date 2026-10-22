# -*- coding: utf-8 -*-
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

def build_conclusion_and_refs(doc, add_h, add_p):
    add_h("KẾT LUẬN VÀ KIẾN NGHỊ", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)

    add_h("1. Kết luận", level=2)
    add_p("Qua quá trình nghiên cứu lý thuyết, xây dựng thuật toán và thực nghiệm tính toán số trên chuỗi dữ liệu thực tế trận lũ lịch sử cuối tháng 11/2021 tại hạ lưu lưu vực sông Ba, tỉnh Phú Yên, đồ án đã hoàn thành các nội dung nghiên cứu và đạt được một số kết quả chính như sau:")
    add_p("1. Xây dựng quy trình tích hợp giữa mô hình thủy lực số hai chiều giải hệ phương trình nước nông trên GPU (BG_Flood), dữ liệu viễn thám radar Sentinel-1 SAR và hệ thống thông tin địa lý GIS. Quy trình cho phép mô phỏng động học ngập lụt chi tiết trên lưới phân giải 30m (hơn 4,4 triệu ô tính toán) với tốc độ tính toán nhanh hơn thời gian thực (đạt xấp xỉ 1.83x thời gian thực), hỗ trợ cung cấp thông tin kịp thời phục vụ công tác phòng chống thiên tai.")
    add_p("2. Nhận diện và xử lý các vấn đề kỹ thuật số học trong mô phỏng thủy lực hai chiều:")
    add_p("- Xác định và hiệu chỉnh lỗi xung đột cấu hình giữa tham số độ nhám đơn trị và bản đồ phân bố nhám không gian, qua đó nâng bước thời gian tính toán thích ứng dt từ 0.28s lên 3.8s - 4.1s, rút ngắn thời gian chạy mô phỏng từ khoảng 168 giờ xuống 14 giờ (kịch bản V23).")
    add_p("- Xác định nguyên nhân gây mất ổn định số học (lỗi phân kỳ) tại thời điểm t ≈ 160.000s trên lưới 30m xuất phát từ các điểm hố sụt vi địa hình (sinks) trên sườn dốc; ứng dụng thuật toán lấp hố sụt thủy văn Priority-Flood (kịch bản V41) để xử lý triệt để các bẫy trũng nhân tạo, đảm bảo tính ổn định theo điều kiện CFL trong suốt 120 giờ mô phỏng.")
    add_p("3. Cải thiện độ chính xác kiểm chuẩn với dữ liệu vệ tinh Sentinel-1 SAR:")
    add_p("- Phân tích ảnh hưởng của rào cản nhân tạo (đê bao, đường giao thông) trên lưới DEM 30m đối với dòng tràn; áp dụng kỹ thuật hiệu chỉnh địa hình cục bộ (Levee Breaching) hạ thấp 2m tại các vị trí cống tiêu thoát lũ ven sông Ba (kịch bản V44).")
    add_p("- Tại thời điểm đỉnh lũ ứng với ảnh chụp Sentinel-1 SAR (102 giờ mô phỏng), chỉ số thành công tới hạn CSI đạt 20.64%, độ phủ Recall đạt 24.97% và độ chuẩn xác Precision đạt 54.32%, cải thiện rõ rệt so với các kịch bản ban đầu (CSI đạt 3.29% ở V23 và 13.50% ở V43).")
    add_p("4. Kiểm chứng độc lập tính hợp lý hình thái học bằng chỉ số địa hình thủy văn HAND (Height Above Nearest Drainage): 90.43% tổng diện tích ngập của mô hình V44 tập trung trong vùng bãi bồi tự nhiên (HAND <= 3.5m) và chỉ có 1.00% diện tích ngập ở khu vực đồi dốc (dưới dạng các dòng tụ thủy hẹp), xác nhận tính phù hợp về mặt phân bố không gian dòng chảy trọng trường và hạn chế tối đa sai số ngập giả trên sườn dốc.")
    add_p("5. Làm rõ nguyên nhân bỏ sót thân đê chính ven hạ lưu sông Ba trong thuật toán V44 do đỉnh đê không ngập nước trên ảnh SAR; đề xuất giải pháp xử lý hình thái học (Morphological Carving) trong vùng đệm 150m ven sông trên 41.907 ô lưới, tạo cơ sở cho kịch bản V45 mở rộng không gian thoát lũ tự nhiên hai bên bờ hạ lưu sông Ba.")

    add_h("2. Kiến nghị", level=2)
    add_p("Để công trình nghiên cứu tiếp tục được hoàn thiện và chuyển giao hiệu quả vào thực tiễn quản lý rủi ro thiên tai tại tỉnh Phú Yên và các địa phương miền Trung, đồ án đề xuất một số định hướng nghiên cứu tiếp theo:")
    add_p("1. Về dữ liệu địa hình: Tiếp tục triển khai tính toán chi tiết kịch bản V45 với bản đồ địa hình `PhuYen_DEM_30m_V45.asc`; đồng thời khuyến nghị kết hợp dữ liệu quét độ cao LiDAR hoặc UAV để xây dựng mô hình địa hình số DTM độ phân giải cao (< 5m), tích hợp thông tin hệ thống cống ngầm và công trình thoát nước đô thị TP. Tuy Hòa.")
    add_p("2. Về dữ liệu thủy văn biên: Tăng cường lắp đặt các trạm đo lưu lượng và mực nước tự động tại hạ lưu đập Đồng Cam, sông Bàn Thạch và sông Kỳ Lộ để thay thế dữ liệu nội suy, giúp nâng cao độ chính xác của đường quá trình lưu lượng biên đầu vào.")
    add_p("3. Về ứng dụng Trí tuệ nhân tạo (GeoAI): Nghiên cứu mở rộng các cấu trúc mạng học sâu thay thế (như ConvLSTM, U-Net) từ nguồn dữ liệu lớn sinh ra bởi mô hình 2D BG_Flood, hướng tới công cụ dự báo ngập lụt hỗ trợ phản ứng nhanh khi tiếp nhận thông tin mưa dự báo.")
    add_p("4. Về ứng dụng thực tiễn: Hướng tới tích hợp mô hình vào Hệ thống Hỗ trợ Ra quyết định (Decision Support System - DSS) cảnh báo thiên tai của tỉnh Phú Yên, phục vụ công tác điều hành xả lũ an toàn của các hồ chứa thủy điện và hỗ trợ Ban Chỉ huy PCTT lập phương án ứng phó, sơ tán dân cư.")

    doc.add_page_break()

    # ==============================================================================
    # TÀI LIỆU THAM KHẢO
    # ==============================================================================
    add_h("TÀI LIỆU THAM KHẢO", level=1, align=WD_ALIGN_PARAGRAPH.CENTER)

    references = [
        ("[1]", "World Meteorological Organization (WMO) (2021). WMO Atlas of Mortality and Economic Losses from Weather, Climate and Water Extremes (1970–2019). WMO-No. 1267, Geneva, Switzerland. [Online]. Khả dụng: https://library.wmo.int/records/item/57608-wmo-atlas-of-mortality-and-economic-losses-from-weather-climate-and-water-extremes-1970-2019"),
        ("[2]", "Ban Chỉ đạo Quốc gia về Phòng chống thiên tai (2021). Báo cáo tổng kết công tác phòng, chống thiên tai năm 2021 và nhiệm vụ trọng tâm công tác năm 2022. Bộ Nông nghiệp và Phát triển Nông thôn, Hà Nội. [Online]. Khả dụng: http://phongchongthientai.mard.gov.vn/"),
        ("[3]", "Bosserelle, C., Sharma, S., & Popinet, S. (2020). BG_Flood: A GPU-accelerated 2D shallow water equation model for flood and inundation simulation. SoftwareX, 12, 100585. DOI: https://doi.org/10.1016/j.softx.2020.100585"),
        ("[4]", "Bates, P. D., Horritt, M. S., & Fewtrell, T. J. (2010). A simple inertial formulation of the shallow water equations for efficient two-dimensional flood inundation modelling. Journal of Hydrology, 387(1-2), 33-45. DOI: https://doi.org/10.1016/j.jhydrol.2010.03.027"),
        ("[5]", "Otsu, N. (1979). A threshold selection method from gray-level histograms. IEEE Transactions on Systems, Man, and Cybernetics, 9(1), 62-66. DOI: https://doi.org/10.1109/TSMC.1979.4310076"),
        ("[6]", "Nobre, A. D., Cuartas, L. A., Hodnett, M., Rennó, C. D., Rodrigues, G., Silveira, A., Waterloo, M., & Saleska, S. (2011). Height Above the Nearest Drainage – a hydrologically normalized Digital Elevation Model, comparison to shallow water table modeling. Remote Sensing of Environment, 115(2), 518-527. DOI: https://doi.org/10.1016/j.rse.2011.06.012"),
        ("[7]", "Yamazaki, D., Ikeshima, D., Tawatari, R., Yamaguchi, T., O'Loughlin, F., Neal, J. C., Sampson, C. C., Kanae, S., & Bates, P. D. (2017). A high-accuracy map of global terrain elevations (MERIT DEM). Geophysical Research Letters, 44(11), 5844-5853. DOI: https://doi.org/10.1002/2017GL072874"),
        ("[8]", "Hawker, L., Uhe, P., Paulo, L., Sosa, J., Savage, J., Sampson, C., & Neal, J. (2022). A 30 m global map of elevation with forests and buildings removed (FABDEM). Environmental Research Letters, 17(2), 024016. DOI: https://doi.org/10.1088/1748-9326/ac4d27"),
        ("[9]", "Torres, R., Snoeij, P., Geudtner, D., Bibby, D., Davidson, M., Attema, E., Potin, P., Rommen, B., Floury, N., Brown, M., Traver, I. N., Deghaye, P., Duesmann, B., Rosich, B., Miranda, N., Bruno, C., L'Abbate, M., Croci, R., Pietropaolo, A., ... & Rostan, F. (2012). GMES Sentinel-1 mission. Remote Sensing of Environment, 120, 9-24. DOI: https://doi.org/10.1016/j.rse.2011.05.028"),
        ("[10]", "Schumann, G. J., & Moller, D. K. (2015). Microwave remote sensing of flood inundation. Physics and Chemistry of the Earth, Parts A/B/C, 83-84, 84-95. DOI: https://doi.org/10.1016/j.pce.2015.02.005"),
        ("[11]", "Hersbach, H., Bell, B., Berrisford, P., Hirahara, S., Horányi, A., Muñoz-Sabater, J., Nicolas, J., Peubey, C., Radu, R., Schepers, D., Simmons, A., Soci, C., Abdalla, S., Abellan, X., Balsamo, G., Bechtold, P., Biavati, G., Bidlot, J., Bonavita, M., ... & Thépaut, J. N. (2020). The ERA5 global reanalysis. Quarterly Journal of the Royal Meteorological Society, 146(730), 1999-2049. DOI: https://doi.org/10.1002/qj.3803"),
        ("[12]", "Toro, E. F. (2001). Shock-Capturing Methods for Free-Surface Shallow Flows. John Wiley & Sons, New York. ISBN: 978-0-471-98766-6. DOI: https://doi.org/10.1002/0470845347"),
        ("[13]", "Harten, A., Lax, P. D., & van Leer, B. (1983). On upstream differencing and Godunov-type schemes for hyperbolic conservation laws. SIAM Review, 25(1), 35-61. DOI: https://doi.org/10.1137/1025002"),
        ("[14]", "Barnes, R., Lehman, C., & Mulla, D. (2014). Priority-flood: An optimal depression-filling and watershed-labeling algorithm for digital elevation models. Computers & Geosciences, 62, 117-127. DOI: https://doi.org/10.1016/j.cageo.2013.04.018"),
        ("[15]", "Callow, J. N., Van Niel, K. P., & Boggs, G. S. (2007). How does modifying a DEM to reflect known drainage affect calculated water flow paths?. Earth Surface Processes and Landforms, 32(5), 629-644. DOI: https://doi.org/10.1002/esp.1446"),
        ("[16]", "Saksena, S., & Merwade, V. (2015). Incorporating the effect of DEM resolution and accuracy for improved flood inundation mapping. Journal of Hydrology, 530, 180-194. DOI: https://doi.org/10.1016/j.jhydrol.2015.09.067"),
        ("[17]", "Trịnh Thu Phương, Nguyễn Ý Như, Bùi Chí Nam, & Trần Ngọc Anh (2020). Mô phỏng ngập lụt vùng hạ du lưu vực sông Ba dưới tác động của biến đổi khí hậu và vận hành hồ chứa. Tạp chí Khí tượng Thủy văn, 718, 45-56. [Online]. Khả dụng: http://tapchikttv.vn/article/629"),
        ("[18]", "Nguyễn Văn Tuấn (2019). Ứng dụng viễn thám radar trong giám sát ngập lụt tại khu vực miền Trung Việt Nam. Tạp chí Các Khoa học về Trái Đất, 41(3), 210-221. DOI: https://doi.org/10.15625/0866-7187/41/3/13845"),
        ("[19]", "Lê Văn Hưng, & Hà Minh Cường (2021). Đánh giá nguy cơ ngập lụt đô thị bằng mô hình thủy lực 2D kết hợp GIS. Tạp chí Khoa học ĐHQGHN: Các Khoa học Trái đất và Môi trường, 37(2), 15-28. DOI: https://doi.org/10.25073/2588-1094/vnuees.4628"),
        ("[20]", "Ủy ban Nhân dân Tỉnh Phú Yên (2021). Báo cáo tình hình thiệt hại và công tác khắc phục hậu quả thiên tai, mưa lũ lịch sử tháng 11 năm 2021 trên địa bàn tỉnh Phú Yên. UBND Tỉnh, Tuy Hòa. [Online]. Khả dụng: https://phuyen.gov.vn/"),
        ("[21]", "Zanaga, D., Van De Kerchove, R., De Keersmaecker, W., Souverijns, N., Brockmann, C., Quast, R., Wevers, J., Grosu, A., Paccini, A., Vergnaud, S., Cartus, O., Santoro, M., Fritz, S., Georgieva, I., Lesiv, M., Carter, S., Herold, M., Li, L., Tsendbazar, N. E., ... & Arino, O. (2021). ESA WorldCover 10 m 2020 v100. Zenodo. DOI: https://doi.org/10.5281/zenodo.5571936"),
        ("[22]", "Pekel, J. F., Cottam, A., Gorelick, N., & Belward, A. S. (2016). High-resolution mapping of global surface water and its long-term changes. Nature, 540(7633), 418-422. DOI: https://doi.org/10.1038/nature20584"),
        ("[23]", "Lee, J. S. (1980). Digital image enhancement and noise filtering by use of local statistics. IEEE Transactions on Pattern Analysis and Machine Intelligence, PAMI-2(2), 165-168. DOI: https://doi.org/10.1109/TPAMI.1980.4766994"),
        ("[24]", "Vacondio, R., Dal Palù, A., & Mignosa, P. (2014). GPU-accelerated shallow water flow simulation on unstructured grids. Environmental Modelling & Software, 58, 140-154. DOI: https://doi.org/10.1016/j.envsoft.2014.04.003"),
        ("[25]", "Neal, J., Schumann, G., & Bates, P. (2012). A subgrid channel model for simulating river hydraulics and floodplain inundation over large and data sparse areas. Water Resources Research, 48(11), W11506. DOI: https://doi.org/10.1029/2012WR012514"),
        ("[26]", "Sanders, B. F. (2007). Evaluation of on-line DEM products for flood inundation modeling. Advances in Water Resources, 30(8), 1831-1847. DOI: https://doi.org/10.1016/j.advwatres.2006.07.007"),
        ("[27]", "Pulvirenti, L., Pierdicca, N., Chini, M., & Guerriero, L. (2011). An algorithm for operational flood mapping from Synthetic Aperture Radar (SAR) data using fuzzy logic. IEEE Transactions on Geoscience and Remote Sensing, 49(12), 5229-5240. DOI: https://doi.org/10.1109/TGRS.2011.2114667"),
        ("[28]", "Martinis, S., Kuenzer, C., Wendleder, A., Huth, J., Twele, A., Roth, A., & Dech, S. (2015). Comparing four operational SAR-based water and flood detection approaches. International Journal of Remote Sensing, 36(13), 3519-3543. DOI: https://doi.org/10.1080/01431161.2015.1060647"),
        ("[29]", "Brivio, P. A., Colombo, R., Fasolini, F., & Smith, W. (2002). Integration of remote sensing data and GIS for accurate mapping of flooded areas. International Journal of Remote Sensing, 23(3), 429-441. DOI: https://doi.org/10.1080/01431160010014729"),
        ("[30]", "Huizinga, J., de Moel, H., & Szewczyk, W. (2017). Global flood depth-damage functions: Methodology and the database with guidelines. JRC Technical Reports, Publications Office of the European Union, Luxembourg. DOI: https://doi.org/10.2760/16510"),
        ("[31]", "LeVeque, R. J. (2002). Finite Volume Methods for Hyperbolic Problems. Cambridge University Press, Cambridge. DOI: https://doi.org/10.1017/CBO9780511791253"),
        ("[32]", "Cunge, J. A., Holly, F. M., & Verwey, A. (1980). Practical Aspects of Computational River Hydraulics. Pitman Publishing, London. ISBN: 0-273-08442-9. DOI: https://doi.org/10.1016/B978-0-273-08442-6.50005-0"),
        ("[33]", "Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. In Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (pp. 785-794). ACM. DOI: https://doi.org/10.1145/2939672.2939785"),
        ("[34]", "Hochreiter, S., & Schmidhuber, J. (1997). Long short-term memory. Neural Computation, 9(8), 1735-1780. DOI: https://doi.org/10.1162/neco.1997.9.8.1735"),
        ("[35]", "Copernicus Open Access Hub (2021). European Space Agency (ESA) Sentinel-1 Scientific Data Hub. [Online]. Khả dụng: https://dataspace.copernicus.eu/")
    ]

    for item in references:
        p_ref = doc.add_paragraph()
        p_ref.paragraph_format.first_line_indent = -Inches(0.4)
        p_ref.paragraph_format.left_indent = Inches(0.4)
        p_ref.paragraph_format.space_before = Pt(3)
        p_ref.paragraph_format.space_after = Pt(6)
        
        r_num = p_ref.add_run(item[0] + " ")
        r_num.bold = True
        r_num.font.name = 'Times New Roman'
        r_num.font.size = Pt(11.5)
        
        r_content = p_ref.add_run(item[1])
        r_content.font.name = 'Times New Roman'
        r_content.font.size = Pt(11.5)

    print("Xong phần Kết luận và Tài liệu tham khảo.")
