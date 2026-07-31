# Triển Khai

## Yêu Cầu

- Python `>=3.13,<3.14`.
- Poetry để cài dependency và chạy entry point.
- Supabase PostgreSQL cho ETL và warehouse.
- Cloudflare R2 dùng để phân phối snapshot cho các công cụ xây dựng báo cáo.

## Cấu Hình

```powershell
Copy-Item .env.example .env
poetry install
```

Thay toàn bộ giá trị mẫu trong `.env`; không commit file này. Các nhóm biến:

| Nhóm | Biến |
| --- | --- |
| Ứng dụng | `APP_ENV`, `LOG_LEVEL` |
| Database chính | `DATABASE_URL`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` |
| Open-Meteo | `OPEN_METEO_ARCHIVE_URL`, `OPEN_METEO_FORECAST_URL`, `OPEN_METEO_TIMEOUT_SECONDS`, `OPEN_METEO_MAX_RETRIES` |
| Discord | `DISCORD_NOTIFICATIONS_ENABLED`, `DISCORD_WEBHOOK_URL` |
| R2 | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_BASE_URL` |

Mẫu hiện tại dùng Supabase Shared Pooler ở Session mode, cổng `5432`, để tương
thích mạng IPv4. Lấy connection string hiện tại từ nút **Connect** của Supabase;
URL-encode phần mật khẩu nếu có ký tự đặc biệt. Direct connection phù hợp migration
khi máy có IPv6 hoặc IPv4 add-on, nhưng không bắt buộc cho checkout này.

## Khởi Tạo Database

```powershell
poetry run alembic upgrade head
poetry run python scripts/seed_provinces.py
poetry run python scripts/seed_dim_date.py
```

Các seed dùng upsert/do-nothing nên chạy lại được. `seed_provinces.py` nạp 30
quận/huyện; `seed_dim_date.py` bổ sung dimension ngày từ mốc dự án đến hiện tại.

## GitHub Actions

Repository cần các GitHub Secrets:

```text
DATABASE_URL
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
DISCORD_WEBHOOK_URL
```

Và GitHub Variables:

```text
R2_ACCOUNT_ID
R2_BUCKET_NAME
R2_PUBLIC_BASE_URL
DISCORD_NOTIFICATIONS_ENABLED
```

`DATABASE_URL` phải truy cập được từ runner; với project không có IPv4 add-on,
dùng Shared Pooler thay vì direct IPv6 host. Workflow tự chạy test, Ruff, migration
và seed trước collector. Chi tiết lịch/preset nằm trong [ETL và tự động hóa](etl.md).

## An Toàn Và Xử Lý Lỗi

- `.env`, URL, token và mật khẩu không được commit hoặc dán vào log/issue.
- Nếu migration qua direct host lỗi `Network is unreachable`, kiểm tra IPv6 và đổi
  sang Session Pooler IPv4 trước khi sửa ETL.
- Sau timeout migration hoặc ETL, kiểm tra process, transaction và row count hiện tại
  trước khi chạy lại.
- Kiểm tra database bằng Alembic head, row count, min/max date, khóa ngoại mồ côi và
  `pg_database_size`.
