import docx
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = docx.Document()

# Title
title = doc.add_heading('Báo cáo Chi tiết Tiến độ Dự án Mô phỏng Lũ lụt', 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# Mở bài + Bối cảnh
doc.add_heading('Bối cảnh: Tại sao chúng ta làm dự án này?', level=1)
doc.add_paragraph('Mục tiêu của dự án là xây dựng một hệ thống có khả năng dự báo ngập lụt nhanh chóng và chính xác. Tuy nhiên, các phần mềm mô phỏng thủy lực truyền thống (như BG_Flood) chạy rất chậm, đôi khi mất đến 24 giờ để tính toán xong một kịch bản ngập lụt. Khi có bão lũ thực tế, chúng ta không thể chờ 24 giờ để đưa ra quyết định sơ tán.')
doc.add_paragraph('Giải pháp của chúng ta là ứng dụng Trí tuệ nhân tạo (GeoAI) kết hợp với mô hình vật lý (Hybrid). Cụ thể:')
doc.add_paragraph('Bước 1 (Giai đoạn hiện tại): Chúng ta sẽ dùng phần mềm BG_Flood chạy trước hàng trăm kịch bản bão lũ khác nhau. Kết quả sinh ra là một kho tàng khổng lồ các "bản đồ ngập lụt mẫu" (Training Set).', style='List Bullet')
doc.add_paragraph('Bước 2 (Giai đoạn AI): Đưa kho bản đồ mẫu này cho mạng nơ-ron nhân tạo (AI) học hỏi quy luật nước chảy.', style='List Bullet')
doc.add_paragraph('Bước 3 (Thực tế): Khi bão đổ bộ, AI sẽ tự suy luận và vẽ ra bản đồ ngập lụt chỉ trong 1-2 phút thay vì 24 giờ.', style='List Bullet')
doc.add_paragraph('Báo cáo dưới đây trình bày chi tiết từng bước chúng ta đã làm trong những tuần qua để xây dựng nền móng cho giai đoạn 1.')

# Tiến độ
doc.add_heading('Chi tiết Tiến độ Dự án theo Tuần', level=1)

# Week 0
doc.add_heading('Tuần 0: Gom nhặt tài nguyên và xây dựng nền móng', level=2)
doc.add_picture(r'D:\VTP\img_week0.png', width=Inches(5.5))
doc.add_paragraph('Mục tiêu tuần này: Chuẩn bị mọi thứ cần thiết trước khi bắt đầu chạy mô phỏng.')
doc.add_paragraph('Những việc chúng ta đã làm:', style='List Bullet')
doc.add_paragraph('Xác định khu vực nghiên cứu: Chúng ta chọn lưu vực rộng 18.000 km2 bao gồm tỉnh Đắk Lắk và Phú Yên. Tại sao lại ghép 2 tỉnh? Vì Đắk Lắk là vùng đồi núi cao, nơi hứng chịu mưa bão. Nước mưa từ Đắk Lắk sẽ dồn hết vào hệ thống sông Ba và đổ ập xuống Phú Yên. Do đó, phải tính toán cả Đắk Lắk thì mới biết được lượng nước đổ về Phú Yên là bao nhiêu.', style='List Bullet 2')
doc.add_paragraph('Tải bản đồ địa hình (DEM): Chúng ta đã thu thập bản đồ độ cao vệ tinh (DEM) với độ phân giải 90m cho toàn bộ khu vực này. Đây là "khuôn đúc" để phần mềm biết chỗ nào cao, chỗ nào trũng để cho nước chảy.', style='List Bullet 2')
doc.add_paragraph('Cài đặt phần mềm: Đã tải và cài đặt thành công phần mềm BG_Flood. Đây là phần mềm chuyên dụng tính toán dòng chảy bằng card đồ họa máy tính (GPU).', style='List Bullet 2')
doc.add_paragraph('Khó khăn:', style='List Bullet')
doc.add_paragraph('Việc khai báo các thông số toán học phức tạp vào phần mềm (như độ nhám của đất, lượng mưa, lưu lượng nước xả từ đập) ban đầu khá lúng túng.', style='List Bullet 2')

# Week 1
doc.add_heading('Tuần 1: Chạy thử nghiệm mô phỏng toàn vùng (Kịch bản V22)', level=2)
doc.add_picture(r'D:\VTP\img_week1.png', width=Inches(5.5))
doc.add_paragraph('Mục tiêu tuần này: Bấm nút chạy thử kịch bản lũ lụt đầu tiên trên diện rộng.')
doc.add_paragraph('Những việc chúng ta đã làm:', style='List Bullet')
doc.add_paragraph('Thiết lập Kịch bản V22: Chúng ta đặt tên kịch bản thử nghiệm này là V22. Kịch bản này mô phỏng nước chảy liên tục trong 5 ngày (120 giờ). Thời gian 5 ngày là đủ để chúng ta quan sát toàn bộ quá trình: từ lúc mưa bắt đầu rơi, nước trên sông dâng cao tạo thành đỉnh lũ, và cuối cùng là nước rút đi.', style='List Bullet 2')
doc.add_paragraph('Chạy phần mềm thành công: Phần mềm đã tính toán xong và xuất ra kết quả.', style='List Bullet 2')
doc.add_paragraph('Khó khăn:', style='List Bullet')
doc.add_paragraph('Phần mềm xuất ra một file kết quả có đuôi là ".nc" (NetCDF). Đây là một định dạng file dữ liệu khoa học cực kỳ nặng và phức tạp, chứa toàn bộ thông tin nước chảy từng giây một. Chúng ta không thể mở nó ra xem bình thường được, dẫn đến việc không biết kết quả bên trong hình thù ra sao.', style='List Bullet 2')

# Week 2
doc.add_heading('Tuần 2: Chuyển hóa dữ liệu thô thành Bản đồ có thể nhìn thấy', level=2)
doc.add_picture(r'D:\VTP\img_week2.png', width=Inches(5.5))
doc.add_paragraph('Mục tiêu tuần này: Phải tìm cách "nhìn thấy" được vùng bị ngập từ cái file .nc khổng lồ kia.')
doc.add_paragraph('Những việc chúng ta đã làm:', style='List Bullet')
doc.add_paragraph('Viết công cụ trích xuất ảnh: Chúng ta đã viết một đoạn code Python tự động mổ xẻ file .nc. Nó quét qua dữ liệu của từng ngày, tìm ra "mức ngập sâu nhất" của ngày hôm đó, và chụp lại thành một tấm ảnh bản đồ (file .tif). Kết quả là chúng ta có 5 tấm ảnh .tif nhẹ nhàng đại diện cho 5 ngày lũ.', style='List Bullet 2')
doc.add_paragraph('Lợi ích của file .tif: Những tấm ảnh .tif này cực kỳ dễ mở trên các phần mềm bản đồ thông dụng (như QGIS). Hơn nữa, những tấm ảnh tĩnh này chính là "sách giáo khoa" mà sau này AI sẽ dùng để học.', style='List Bullet 2')
doc.add_paragraph('Phát hiện và sửa lỗi lệch tọa độ:', style='List Bullet')
doc.add_paragraph('Vấn đề: Khi mở ảnh ngập lụt lên bản đồ thực tế, chúng ta phát hiện vệt nước bị lệch khoảng 45 mét so với dòng sông thực sự, và bản đồ bị lộn ngược.', style='List Bullet 2')
doc.add_paragraph('Nguyên nhân: Khác biệt về chuẩn đo đạc. Bản đồ địa hình đo từ "Góc" của mỗi ô vuông, còn phần mềm tính toán lại đo từ "Tâm" của ô vuông.', style='List Bullet 2')
doc.add_paragraph('Cách sửa: Chúng ta đã chèn thêm một lệnh toán học để lật ngược tấm ảnh lại và kéo tịnh tiến tấm ảnh khớp vào đúng hệ tọa độ chuẩn (EPSG:32648). Giờ đây ảnh ngập lụt đã khớp 100% với thực địa.', style='List Bullet 2')

# Week 3
doc.add_heading('Tuần 3: So sánh kết quả mô phỏng với ảnh Vệ tinh thực tế (Bản Cập Nhật)', level=2)
doc.add_paragraph('Mục tiêu tuần này: Kiểm tra xem phần mềm chúng ta tính toán có đúng với sự thật đã xảy ra trong quá khứ hay không.')
doc.add_paragraph('Cách kiểm tra: Chúng ta lấy bản đồ ngập lụt mà phần mềm vừa tính ra (mô phỏng), đem đặt cạnh một bức ảnh vệ tinh radar (SAR) chụp thực tế khu vực Phú Yên vào đúng lúc đỉnh lũ sáng ngày 30/11/2021.')
doc.add_picture(r'D:\VTP\BG_Flood_Project\BG_Flood\results\SAR_vs_Sim.png', width=Inches(5.5))
doc.add_paragraph('Phát hiện Lỗi Chồng lấp (Sự cố lật trục):', style='List Bullet')
doc.add_paragraph('Trước đây, khi chồng hai bức ảnh lên nhau, chúng ta thấy tỷ lệ khớp nhau cực kỳ thấp (chỉ 3%). Tuy nhiên, nhờ sự tinh ý quan sát, chúng ta phát hiện ảnh mô phỏng bị "lộn ngược" (flipped) theo trục dọc so với ảnh vệ tinh!', style='List Bullet 2')
doc.add_paragraph('Kỹ thuật viên đã ngay lập tức can thiệp vào code (thêm lệnh np.flipud) để lật lại mảng dữ liệu. Thật bất ngờ, hai bản đồ đã ăn khớp với nhau hơn rất nhiều, làm thay đổi hoàn toàn cục diện đánh giá.', style='List Bullet 2')
doc.add_paragraph('Phân tích Dữ liệu Kỹ thuật mới (Sau khi lật đúng chiều ảnh):', style='List Bullet')
doc.add_paragraph('Đúng dương tính (True Positive - Cả hai đều báo ngập): Tăng vọt lên 21,187 điểm ảnh (so với 5.000 lúc chưa lật). Sự trùng khớp đã cao gấp 4 lần!', style='List Bullet 2')
doc.add_paragraph('Sai âm tính (False Negative - Bỏ sót): Vẫn còn 95,267 điểm ảnh thực tế ngập nhưng phần mềm báo khô.', style='List Bullet 2')
doc.add_paragraph('Chỉ số CSI (Critical Success Index): Tăng vọt lên 15% (trước đó chỉ là 3.3%).', style='List Bullet 2')
doc.add_paragraph('Độ nhạy (Recall): Đạt 18.2% (trước đó chỉ là 4.5%). Nghĩa là phần mềm đã bắt được gần 20% diện tích lõi ngập sâu.', style='List Bullet 2')
doc.add_paragraph('Bài học và Hướng đi tiếp theo:', style='List Bullet')
doc.add_paragraph('Mặc dù chỉ số đã tăng mạnh nhờ lật đúng bản đồ, mô hình vẫn đang bị lỗi "Dự báo hụt" (Under-prediction). Nước trên mô phỏng vẫn hẹp hơn thực tế.', style='List Bullet 2')
doc.add_paragraph('Việc đang làm: Chúng ta đang nâng cấp từ lưới 90m lên lưới 30m siêu nét để mô phỏng chính xác hơn địa hình hạ lưu Phú Yên. Đồng thời, tinh chỉnh lại lượng mưa và độ ma sát của đất để nước dâng cao hơn.', style='List Bullet 2')

doc.save(r'D:\VTP\Bao_cao_Tien_do_v6.docx')
