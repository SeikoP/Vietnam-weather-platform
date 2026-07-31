# Thiết Kế Đồng Bộ Link R2 Vào `.env`

## Mục tiêu

Tạo một script Python lấy manifest của release R2 đang hoạt động, dựng đủ sáu URL CSV
ổn định cho các công cụ xây dựng báo cáo và cập nhật `.env` mà không làm thay đổi các
biến khác.

## Luồng xử lý

1. Đọc `R2_PUBLIC_BASE_URL` từ `.env`, bỏ dấu `/` cuối URL.
2. Tải `v1/latest.json`, lấy `manifest_key`, sau đó tải manifest release.
3. Chỉ chấp nhận đúng sáu bảng `analyst` chuẩn của dự án.
4. Dựng URL theo `v1/current/analyst/<table>.csv` và kiểm tra từng URL truy cập được.
5. Ghi lại một block có marker trong `.env`: `R2_ANALYST_<TABLE>_URL` cho từng bảng.
6. In danh sách biến đã cập nhật; không in credential hoặc toàn bộ nội dung `.env`.

## Xử lý lỗi

- Dừng mà không sửa `.env` nếu pointer, manifest hoặc một CSV không truy cập được.
- Dừng nếu manifest thiếu hoặc thừa bảng so với sáu bảng chuẩn.
- Ghi `.env` theo kiểu idempotent: cập nhật block cũ thay vì nối trùng lặp.

## Kiểm chứng

- Unit test dùng HTTP server giả lập để kiểm tra luồng pointer → manifest → sáu CSV.
- Unit test xác nhận `.env` giữ nguyên biến ngoài block và lần chạy thứ hai không tạo bản sao.
- Chạy script với endpoint thật, kiểm tra sáu URL trả HTTP thành công và chỉ báo tên biến.

## Ngoài phạm vi

- Không dùng R2 credentials để list bucket.
- Không khởi động Streamlit sau khi cập nhật `.env`.
- Không sửa các thay đổi không liên quan đang tồn tại trong working tree.
