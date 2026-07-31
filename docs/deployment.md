# Triển Khai Và Đồng Bộ Local

## Yêu Cầu

- Python `>=3.13,<3.14`.
- Poetry để cài dependency và chạy entry point.
- PostgreSQL/Supabase cho API và ETL.
- Docker chỉ cần khi dùng PostgreSQL local hoặc chạy API bằng Compose.
- Cloudflare R2 chỉ cần cho snapshot/Power BI.

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
| Đồng bộ local | `CLOUD_DATABASE_URL`, `LOCAL_DATABASE_URL`, `VWDP_POSTGRES_PASSWORD` |
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

## Chạy API

```powershell
# Entry point đóng gói, host 0.0.0.0:8000
poetry run vwdp-api

# Chế độ phát triển
poetry run uvicorn src.api.app:app --reload
```

Chạy bằng Docker:

```powershell
docker compose --env-file .env -f ops/local/compose.yml up -d api
docker compose --env-file .env -f ops/local/compose.yml ps api
```

Docker image dùng Python 3.13, Poetry 2.1.4 và mở API ở cổng `8000`.

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

## PostgreSQL Docker Local

PostgreSQL tùy chọn dùng container `vwdp-postgres`, database/user `vwdp` và ánh xạ
`localhost:5433 -> 5432`. Nó độc lập với các container dự án khác.

```powershell
$env:VWDP_POSTGRES_PASSWORD = "<local-secret>"
docker compose --env-file .env -f ops/local/compose.yml up -d postgres
docker compose --env-file .env -f ops/local/compose.yml ps postgres
```

Volume có tên `vietnam-weather-platform_vwdp_postgres_data`. Đổi biến môi trường
sau khi volume đã tạo không tự đổi mật khẩu trong PostgreSQL. Đổi tương tác để tránh
lộ mật khẩu trong command history:

```powershell
docker exec -it vwdp-postgres psql -U vwdp -d vwdp
```

Tại `psql`, chạy `\password vwdp`, sau đó `\q`. Không mở cổng `5433` trực tiếp ra
Internet; máy thành viên nên đi qua mạng nội bộ/VPN và dùng role chỉ đọc.

## Đồng Bộ Supabase Về Local

Dùng tài khoản cloud chỉ đọc nếu có thể:

```powershell
$env:CLOUD_DATABASE_URL = "<read-only-supabase-url>"
$env:LOCAL_DATABASE_URL = "postgresql+psycopg://vwdp:<url-encoded-password>@localhost:5433/vwdp"
.\.venv\Scripts\python.exe scripts\sync_cloud_to_local.py
```

Script thực hiện theo thứ tự:

1. Yêu cầu đủ hai URL và từ chối nếu chúng trỏ cùng database.
2. Chạy Alembic trên local bằng `LOCAL_DATABASE_URL`.
3. Mở transaction cloud ở chế độ `READ ONLY` và stream theo batch.
4. Upsert từng bảng trong transaction local riêng.
5. In `read`/`upserted` theo bảng mà không in URL hoặc credential.

Mặc định `--lookback-days 0 --batch-size 1000`. Giá trị `0` lấy mọi khóa mới hơn
watermark local, nên vẫn lấp toàn bộ khoảng trống nếu nhiều ngày chưa chạy; nó chỉ
không đọc lại row cũ. Dùng cửa sổ dương khi dữ liệu có thể sửa muộn:

```powershell
.\.venv\Scripts\python.exe scripts\sync_cloud_to_local.py --lookback-days 7
```

Chỉ dùng `--full` khi cần rebuild vì lệnh đọc lại toàn bộ và tăng Supabase egress:

```powershell
.\.venv\Scripts\python.exe scripts\sync_cloud_to_local.py --full --batch-size 1000
```

## An Toàn Và Xử Lý Lỗi

- `.env`, URL, token và mật khẩu không được commit hoặc dán vào log/issue.
- Nếu sync lỗi, chỉ transaction của bảng hiện tại rollback; bảng đã hoàn tất được
  giữ lại. Chạy lại an toàn vì dùng upsert.
- Nếu migration qua direct host lỗi `Network is unreachable`, kiểm tra IPv6 và đổi
  sang Session Pooler IPv4 trước khi sửa ETL.
- Sau timeout restore/sync, kiểm tra process, transaction và row count hiện tại trước
  khi chạy lại.
- Kiểm tra local bằng Alembic head, row count, min/max date, khóa ngoại mồ côi và
  `pg_database_size`.
