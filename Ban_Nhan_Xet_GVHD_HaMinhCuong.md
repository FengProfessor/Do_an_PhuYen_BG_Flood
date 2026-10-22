**BẢN NHẬN XÉT ĐỒ ÁN TỐT NGHIỆP CỦA CÁN BỘ HƯỚNG DẪN**

**Họ và tên cán bộ hướng dẫn:** TS. Hà Minh Cường  
**Đơn vị công tác:** Viện Công nghệ Hàng không Vũ trụ, Trường Đại học Công nghệ – ĐHQGHN  
**Chức danh/Học vị:** Tiến sĩ  
**Chuyên ngành:** Viễn thám và Công nghệ Địa không gian  

**1. Tinh thần, thái độ và khối lượng công việc sinh viên đã thực hiện:**
- Sinh viên có tinh thần học hỏi rất cao, chủ động tìm tòi và giải quyết một bài toán phức tạp mang tính liên ngành cao (Viễn thám, GIS và Mô phỏng Thủy lực). Thái độ làm việc nghiêm túc, bám sát tiến độ nghiên cứu.
- Khối lượng công việc thực hiện là rất đồ sộ và vượt chuẩn so với yêu cầu của một đồ án tốt nghiệp cử nhân/kỹ sư. Đồ án dày khoảng 70 trang với hơn 19.590 từ (vượt xa mức tối thiểu 50 trang theo quy định). Sinh viên đã xử lý khối lượng lớn dữ liệu không gian và làm chủ việc vận hành mô hình thủy lực 2D trên môi trường tính toán song song GPU.

**2. Đánh giá chuyên sâu dưới góc độ chuyên môn Viễn thám & GIS (Ưu điểm nổi bật):**
- **Cơ sở lý thuyết và quy trình xử lý ảnh vệ tinh Sentinel-1 SAR:** Sinh viên đã nắm vững và áp dụng rất chuẩn xác quy trình xử lý ảnh Radar khẩu độ tổng hợp (SAR). Việc lựa chọn phân cực VV là hoàn toàn hợp lý trong bài toán phát hiện ngập lụt bề mặt. Các bước tiền xử lý (hiệu chỉnh địa hình Range-Doppler, lọc nhiễu speckle bằng bộ lọc Lee) kết hợp với thuật toán phân ngưỡng tự động Otsu cho thấy sự am hiểu sâu sắc về bản chất vật lý của tín hiệu radar. Điểm cộng lớn là sinh viên đã biết sử dụng mặt nạ nước thường trực (GSW) để loại bỏ nhiễu từ các thủy vực có sẵn, một kỹ thuật tinh tế trong bản đồ hóa ngập lụt.
- **Sự kết hợp giữa viễn thám và mô hình thủy lực:** Đồ án đã xây dựng được sợi dây liên kết chặt chẽ và thuyết phục giữa công nghệ viễn thám (quan trắc không gian) và mô hình thủy lực 2D (BG_Flood). Ảnh SAR ở đây không chỉ dùng để lập bản đồ độc lập mà được nâng tầm thành công cụ hiệu chỉnh (calibration) và kiểm chứng (validation) không gian cho mô phỏng thủy lực, mang lại độ tin cậy khoa học cao.
- **Tính đột phá trong xử lý dữ liệu DEM:** Điểm sáng lớn nhất, mang tính đột phá của đồ án là việc phân tích và phát hiện ra lỗi cản dòng ảo do đê kè, đường giao thông trên mô hình độ cao số (DEM). Sinh viên đã đề xuất và ứng dụng thành công các thuật toán *Levee Breaching* và *Morphological Carving*. Điều này khắc phục được nhược điểm cố hữu của mô hình thủy lực khi chạy trên nền DEM độ phân giải trung bình, giúp bảo toàn tính liên tục của dòng chảy tràn và phản ánh đúng thực tế ngập lụt.
- **Ý nghĩa của các chỉ số đánh giá:** Các chỉ số định lượng thu được (CSI 20.64%, Recall 24.97%, Precision 54.32%) thoạt nhìn ở mức trung bình, nhưng lại rất thực tế đối với ảnh SAR (dễ bị ảnh hưởng bởi hiệu ứng tán xạ kép trong đô thị hoặc bị che khuất bởi thảm thực vật rậm rạp). Đặc biệt, chỉ số kiểm chứng không gian ngập với mô hình bãi bồi HAND lên tới 90.43% là một con số rất ấn tượng. Nó khẳng định rằng sự phân bố ngập lụt mà mô hình tính toán được là hoàn toàn phù hợp và tuân thủ chặt chẽ các quy luật địa hình - thủy văn.
- **Về danh mục tài liệu tham khảo:** Đồ án có hơn 35 tài liệu tham khảo chất lượng cao, trích dẫn chuẩn mực. Đặc biệt, tính xác thực của tài liệu được đảm bảo thông qua các mã DOI và live URLs, cho thấy sự nghiêm túc, kỹ năng nghiên cứu tài liệu tốt và tinh thần tôn trọng bản quyền học thuật.

**3. Các điểm lưu ý sinh viên cần chuẩn bị kỹ khi bảo vệ trước Hội đồng:**
- Cần chuẩn bị luận giải sắc bén về các chỉ số CSI và Recall. Hãy nhấn mạnh vào bản chất giới hạn vật lý của bước sóng C-band trên vệ tinh Sentinel-1 khi tương tác với bề mặt ngập nước có thực vật che phủ (flooded vegetation) hoặc khu vực đô thị, để Hội đồng thấy rõ mức độ khó khăn của bài toán.
- Nắm vững và trình bày rõ ràng cơ sở thiết lập các tham số đầu vào cho mô hình BG_Flood (như lựa chọn hệ số nhám Manning, thiết lập biên điều kiện dòng chảy).
- Trình bày chi tiết hơn về mặt thuật toán của *Morphological Carving*: cách thức xác định điểm cắt đê (breach points) và khả năng tự động hóa trên quy mô lưu vực lớn hơn.

**4. Kết luận:**
- Đồ án đã đáp ứng xuất sắc, vượt yêu cầu của một Đồ án tốt nghiệp tại Trường Đại học Công nghệ - ĐHQGHN. Đồ án có hàm lượng khoa học sâu sắc, có tính ứng dụng thực tiễn rất cao trong phòng chống thiên tai và chứa đựng những yếu tố sáng tạo mang tính đột phá.
- **Đồng ý cho sinh viên bảo vệ trước Hội đồng đánh giá Đồ án tốt nghiệp.**
- **Điểm số đánh giá của Cán bộ hướng dẫn:** **9.5 / 10**

*Hà Nội, ngày 28 tháng 09 năm 2026*  
**Cán bộ hướng dẫn**  

*(Ký tên)*  


**TS. Hà Minh Cường**
