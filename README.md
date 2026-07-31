# Nền Tảng Dữ Liệu Thời Tiết Hà Nội

Nền tảng thu thập thời tiết và chất lượng không khí cho 30 quận/huyện Hà Nội,
lưu dữ liệu phân tích trong Supabase PostgreSQL và xuất snapshot CSV/Parquet lên
Cloudflare R2 để các công cụ báo cáo truy cập qua HTTP.

## Luồng Dữ Liệu

```text
Open-Meteo -> ETL -> Supabase PostgreSQL -> Cloudflare R2 -> Công cụ báo cáo
```

## Thành Phần Chính

- `src/etl/`: extract, transform, validate và upsert dữ liệu.
- `src/database/`: sáu bảng `analyst`, bốn bảng `monitoring` và Alembic.
- `src/r2/`: tạo, xác minh và kích hoạt release CSV/Parquet.
- `.github/workflows/etl.yml`: lịch chạy và điều phối ETL hằng ngày.

## Bắt Đầu Nhanh

Yêu cầu Python 3.13 và Poetry. Sao chép `.env.example` thành `.env`, sau đó thay
các giá trị mẫu; không commit `.env`.

```powershell
poetry install
poetry run alembic upgrade head
poetry run python scripts/seed_provinces.py
poetry run python scripts/seed_dim_date.py
```

## Lệnh Thường Dùng

```powershell
# ETL cho ngày hôm qua
poetry run vwdp-etl --run-type incremental-daily

# Demo hai quận/huyện
poetry run vwdp-etl --run-type incremental-daily --max-districts 2 --request-delay-seconds 0

# Kiểm tra mã nguồn
poetry run pytest
poetry run ruff check .
```

Nếu Poetry không có trên `PATH`, dùng các executable trong `.venv\Scripts\` như
được ghi trong tài liệu vận hành.

## Tài Liệu

- [Kiến trúc hệ thống](docs/architecture.md)
- [Mô hình dữ liệu](docs/data-model.md)
- [ETL và tự động hóa](docs/etl.md)
- [Triển khai](docs/deployment.md)
- [Cloudflare R2 và công cụ báo cáo](docs/r2-reporting.md)
