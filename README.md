# Nền tảng dữ liệu thời tiết và chất lượng không khí Hà Nội

## Tổng quan

Dự án xây dựng một nền tảng dữ liệu phục vụ thu thập, chuẩn hóa, lưu trữ, phân tích và cung cấp dữ liệu thời tiết cùng chất lượng không khí theo khu vực tại Hà Nội. Hệ thống được thiết kế theo hướng có thể vận hành định kỳ, mở rộng nguồn dữ liệu, kiểm soát chất lượng dữ liệu và cung cấp dữ liệu đã xử lý cho các lớp phân tích phía sau.

Trọng tâm của hệ thống không chỉ là hiển thị dữ liệu thời tiết, mà là hoàn thiện một quy trình dữ liệu có cấu trúc: từ nguồn dữ liệu bên ngoài, qua các bước kiểm tra và biến đổi, đến kho dữ liệu phân tích và giao diện truy xuất ổn định. Cách tiếp cận này giúp dữ liệu có khả năng tái sử dụng cho báo cáo, trực quan hóa, phân tích xu hướng, đối chiếu theo thời gian và đánh giá chất lượng môi trường đô thị.

## Mục tiêu

- Xây dựng quy trình dữ liệu đầy đủ từ thu thập, kiểm tra, chuẩn hóa, lưu trữ đến cung cấp dữ liệu.
- Tổ chức dữ liệu theo mô hình phù hợp cho phân tích thời gian, khu vực và chỉ số môi trường.
- Theo dõi được chất lượng dữ liệu, lỗi xử lý, trạng thái chạy và lịch sử vận hành.
- Cung cấp giao diện truy xuất rõ ràng để phục vụ ứng dụng, báo cáo hoặc công cụ phân tích.
- Thiết kế hệ thống theo hướng có thể bảo trì, kiểm thử và mở rộng.

## Phạm vi dữ liệu

Hệ thống tập trung vào địa bàn Hà Nội ở cấp quận, huyện và thị xã. Dữ liệu được chia thành ba nhóm chính:

- Dữ liệu thời tiết theo ngày: nhiệt độ trung bình, cao nhất, thấp nhất, mưa, gió, mây, bức xạ và các chỉ số liên quan.
- Dữ liệu thời tiết theo giờ: biến động ngắn hạn của nhiệt độ, độ ẩm, áp suất, gió, mưa và điều kiện khí tượng.
- Dữ liệu chất lượng không khí theo giờ: chỉ số chất lượng không khí, bụi mịn, khí ô nhiễm và các thông số môi trường liên quan.

Việc kết hợp dữ liệu theo ngày và theo giờ cho phép hệ thống vừa phục vụ phân tích tổng quan dài hạn, vừa hỗ trợ quan sát chi tiết theo từng thời điểm.

## Kiến trúc hệ thống

Hệ thống được tổ chức thành các lớp chức năng rõ ràng:

- Lớp thu thập dữ liệu: kết nối nguồn dữ liệu thời tiết và chất lượng không khí, có kiểm soát lỗi, thời gian chờ và khả năng thử lại.
- Lớp kiểm tra dữ liệu: đánh giá tính hợp lệ của tọa độ, thời gian và miền giá trị của từng chỉ số.
- Lớp biến đổi dữ liệu: chuẩn hóa dữ liệu thô thành các bản ghi có cấu trúc thống nhất.
- Lớp lưu trữ phân tích: tổ chức dữ liệu theo bảng chiều và bảng sự kiện để thuận lợi cho truy vấn, tổng hợp và trực quan hóa.
- Lớp cung cấp dữ liệu: mở các điểm truy xuất dữ liệu theo khu vực, khoảng thời gian và nhóm chỉ số.
- Lớp giám sát: ghi nhận lịch sử chạy, lỗi kiểm tra dữ liệu và thông tin truy cập.

Việc tách các lớp này giúp hệ thống dễ kiểm thử, dễ thay đổi từng phần và hạn chế ảnh hưởng dây chuyền khi cần mở rộng.

## Mô hình dữ liệu

Kho dữ liệu được thiết kế theo hướng phân tích, trong đó dữ liệu khu vực và thời gian đóng vai trò là chiều phân tích chính. Các bảng sự kiện lưu trữ chỉ số thời tiết và chất lượng không khí theo từng mốc thời gian.

Các nhóm dữ liệu cốt lõi gồm:

- Chiều thời gian: phục vụ lọc, nhóm và tổng hợp theo ngày, tháng, quý, năm hoặc cuối tuần.
- Chiều khu vực: mô tả các đơn vị hành chính tại Hà Nội cùng tọa độ đại diện.
- Sự kiện thời tiết theo ngày: phục vụ phân tích xu hướng và báo cáo tổng hợp.
- Sự kiện thời tiết theo giờ: phục vụ quan sát biến động chi tiết.
- Sự kiện chất lượng không khí theo giờ: phục vụ đánh giá ô nhiễm và đối chiếu với điều kiện khí tượng.
- Dữ liệu giám sát: lưu lịch sử xử lý, lỗi dữ liệu và thông tin truy cập hệ thống.

Cách tổ chức này giúp dữ liệu phù hợp cho cả truy vấn nghiệp vụ, báo cáo định kỳ và kết nối với công cụ trực quan hóa.

## Luồng xử lý dữ liệu

Quy trình xử lý được chia thành ba loại chính:

- Nạp lịch sử: thu thập dữ liệu trong một khoảng thời gian dài để hình thành nền dữ liệu ban đầu.
- Cập nhật định kỳ: bổ sung dữ liệu mới theo chu kỳ nhằm duy trì tính liên tục.
- Dự báo ngắn hạn: lấy dữ liệu dự báo để hỗ trợ quan sát và so sánh với dữ liệu thực tế sau này.

Mỗi lần xử lý đều đi qua các bước: lấy dữ liệu, chuẩn hóa, kiểm tra, loại bỏ bản ghi không hợp lệ, nạp vào kho dữ liệu và ghi nhận kết quả vận hành. Cách này giúp hệ thống không chỉ có dữ liệu đầu ra, mà còn có dấu vết để đánh giá quá trình tạo ra dữ liệu đó.

## Kiểm soát chất lượng dữ liệu

Dữ liệu môi trường có thể thiếu, sai miền giá trị hoặc không đồng nhất giữa các nguồn. Vì vậy hệ thống áp dụng kiểm tra theo quy tắc cho từng nhóm chỉ số:

- Tọa độ phải nằm trong vùng hợp lý của Hà Nội.
- Nhiệt độ, độ ẩm, áp suất, gió, mưa và bức xạ phải nằm trong ngưỡng có thể chấp nhận.
- Chỉ số bụi mịn, khí ô nhiễm và chất lượng không khí phải được kiểm tra theo miền giá trị phù hợp.
- Bản ghi lỗi không được nạp thẳng vào kho phân tích mà được ghi nhận để phục vụ truy vết.

Việc kiểm soát này làm tăng độ tin cậy của dữ liệu và giúp người phân tích hiểu rõ giới hạn của bộ dữ liệu.

## Giao diện truy xuất dữ liệu

Hệ thống cung cấp dữ liệu theo các hướng truy xuất chính:

- Danh sách khu vực tại Hà Nội.
- Dữ liệu thời tiết theo ngày của một hoặc nhiều khu vực.
- Dữ liệu thời tiết theo giờ của một hoặc nhiều khu vực.
- Dữ liệu chất lượng không khí theo giờ.
- Thống kê tổng hợp theo khoảng thời gian và khu vực.
- Trạng thái hoạt động của hệ thống.

Các điểm truy xuất được thiết kế để tách rõ dữ liệu tổng quan và dữ liệu theo khu vực cụ thể, giúp dễ tích hợp với giao diện người dùng, bảng điều khiển phân tích hoặc công cụ báo cáo.

## Giám sát và vận hành

Một hệ thống dữ liệu tốt cần trả lời được dữ liệu đến từ đâu, được xử lý khi nào và có lỗi gì trong quá trình xử lý. Vì vậy dự án có lớp giám sát riêng cho:

- Lịch sử các lần chạy quy trình dữ liệu.
- Số lượng bản ghi được xử lý, bỏ qua hoặc bị từ chối.
- Lỗi phát sinh khi lấy dữ liệu hoặc kiểm tra dữ liệu.
- Nhật ký truy cập vào giao diện cung cấp dữ liệu.

Những thông tin này hỗ trợ đánh giá độ ổn định của hệ thống và giúp phát hiện sớm vấn đề khi dữ liệu bất thường.

## Giá trị phân tích

Dữ liệu sau khi chuẩn hóa có thể phục vụ nhiều hướng phân tích:

- Theo dõi xu hướng nhiệt độ, lượng mưa và độ ẩm theo thời gian.
- So sánh điều kiện thời tiết giữa các khu vực trong Hà Nội.
- Quan sát biến động chất lượng không khí theo giờ.
- Đối chiếu mối liên hệ giữa điều kiện khí tượng và chỉ số ô nhiễm.
- Xây dựng bảng điều khiển theo ngày, tháng, khu vực hoặc nhóm chỉ số.
- Tạo nền dữ liệu cho các mô hình phân tích hoặc dự báo mở rộng.

Nhờ cấu trúc dữ liệu rõ ràng, hệ thống có thể được dùng như một nguồn dữ liệu trung tâm cho nhiều bài toán phân tích khác nhau.

## Khả năng mở rộng

Thiết kế hiện tại cho phép mở rộng theo nhiều hướng:

- Bổ sung thêm nguồn dữ liệu thời tiết hoặc môi trường khác.
- Mở rộng phạm vi địa lý ra ngoài Hà Nội.
- Thêm nhóm chỉ số mới như cảnh báo thời tiết, chỉ số sức khỏe hoặc dữ liệu dân cư.
- Tích hợp lớp trực quan hóa dữ liệu chuyên sâu.
- Bổ sung cơ chế đánh giá chất lượng dữ liệu nâng cao.
- Xây dựng mô hình dự báo hoặc phát hiện bất thường dựa trên dữ liệu lịch sử.

Các lớp thu thập, xử lý, lưu trữ và cung cấp dữ liệu được tách biệt để việc mở rộng không buộc phải thay đổi toàn bộ hệ thống.

## Định hướng hoàn thiện

Các hướng phát triển tiếp theo có thể tập trung vào:

- Chuẩn hóa thêm bộ quy tắc kiểm tra dữ liệu theo tài liệu khí tượng và môi trường.
- Bổ sung chỉ số đánh giá độ đầy đủ và độ tin cậy của dữ liệu theo từng khu vực.
- Tạo báo cáo phân tích định kỳ về thời tiết và chất lượng không khí.
- Xây dựng giao diện trực quan hóa cho người dùng cuối.
- Tăng cường kiểm thử tích hợp cho toàn bộ luồng xử lý dữ liệu.
- Tự động hóa cảnh báo khi quy trình dữ liệu lỗi hoặc dữ liệu vượt ngưỡng bất thường.

## Kết luận

Dự án thể hiện một quy trình xây dựng nền tảng dữ liệu hoàn chỉnh cho bài toán thời tiết và chất lượng không khí đô thị. Hệ thống có đầy đủ các thành phần quan trọng của một sản phẩm dữ liệu: nguồn dữ liệu, xử lý định kỳ, kiểm soát chất lượng, kho dữ liệu phân tích, giao diện truy xuất và giám sát vận hành.

Cách thiết kế này giúp dữ liệu không chỉ được lưu trữ, mà còn có khả năng phục vụ phân tích, kiểm chứng, mở rộng và vận hành lâu dài.
