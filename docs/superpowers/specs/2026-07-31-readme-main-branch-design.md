# Thiết Kế README Tổng Quan Và Nhánh `main`

## Mục Tiêu

- Làm README gốc phản ánh đúng nền tảng dữ liệu thời tiết hiện tại.
- Ưu tiên mục tiêu, kiến trúc, dữ liệu, tự động hóa và đầu ra báo cáo.
- Không biến README thành hướng dẫn cài đặt hoặc danh sách lệnh vận hành.
- Đổi nhánh mặc định của repository từ `master` thành `main` trên GitHub, remote và local.

## Phạm Vi README

README mới gồm:

1. Mô tả ngắn bài toán và phạm vi dữ liệu Hà Nội.
2. Luồng `Open-Meteo -> ETL -> Supabase PostgreSQL -> Cloudflare R2 -> Reporting`.
3. Các khả năng chính: thu thập, chuẩn hóa, kiểm tra, upsert, giám sát và phát hành snapshot.
4. Nhóm dữ liệu `analyst` và mục đích của snapshot CSV/Parquet.
5. Tự động hóa bằng GitHub Actions và ranh giới giữa workflow với logic ETL.
6. Cấu trúc thư mục chính và liên kết đến tài liệu chuyên sâu.

README không chứa block lệnh cài đặt, seed, chạy ETL hoặc test. Các thao tác đó tiếp tục nằm
trong `docs/deployment.md` và `docs/etl.md`.

## Đổi Tên Nhánh

1. Xác minh `main` chưa tồn tại và `master` là nhánh mặc định hiện tại.
2. Đổi tên nhánh GitHub `master` thành `main` bằng API chính thức.
3. Fetch/prune để cập nhật remote-tracking refs và `origin/HEAD`.
4. Đổi tên hoặc tạo lại nhánh local `main` tại đúng commit remote.
5. Đưa hai commit tài liệu của thay đổi này lên `main` bằng fast-forward push.

Không force-push và không xóa nhánh chứa commit chưa được hợp nhất.

## Xác Minh

- Các đường dẫn tài liệu trong README tồn tại.
- `git diff --check` không có lỗi whitespace.
- SHA local và `origin/main` trùng nhau sau push.
- GitHub báo `defaultBranchRef.name` là `main`.
- Remote không còn nhánh `master`; `origin/HEAD` trỏ tới `origin/main`.
