# Nền Tảng Dữ Liệu Thời Tiết Hà Nội

Nền tảng thu thập thời tiết và chất lượng không khí cho 30 quận/huyện Hà Nội,
lưu dữ liệu phân tích trong PostgreSQL, cung cấp FastAPI và xuất snapshot lên
Cloudflare R2 cho Power BI.

## Luồng Dữ Liệu

```text
Open-Meteo -> ETL -> Supabase PostgreSQL -> FastAPI
                                      \-> Cloudflare R2 -> Power BI
                                      \-> PostgreSQL local (tùy chọn)
```

## Thành Phần Chính

- `src/etl/`: extract, transform, validate và upsert dữ liệu.
- `src/database/`: sáu bảng `analyst`, bốn bảng `monitoring` và Alembic.
- `src/api/`: API đọc dữ liệu warehouse.
- `src/r2/`: tạo, xác minh và kích hoạt release CSV/Parquet.
- `src/sync/`: đồng bộ Supabase về PostgreSQL local theo watermark.
- `.github/workflows/etl.yml`: lịch chạy và điều phối ETL hằng ngày.

## Bắt Đầu Nhanh

Yêu cầu Python 3.13 và Poetry. Sao chép `.env.example` thành `.env`, sau đó thay
các giá trị mẫu; không commit `.env`.

```powershell
poetry install
poetry run alembic upgrade head
poetry run python scripts/seed_provinces.py
poetry run python scripts/seed_dim_date.py
poetry run vwdp-api
```

API mặc định chạy tại `http://localhost:8000`; Swagger UI ở `/docs`.

## Lệnh Thường Dùng

```powershell
# ETL cho ngày hôm qua
poetry run vwdp-etl --run-type incremental-daily

# Demo hai quận/huyện
poetry run vwdp-etl --run-type incremental-daily --max-districts 2 --request-delay-seconds 0

# Kiểm tra mã nguồn
poetry run pytest
poetry run ruff check .

# API có auto-reload khi phát triển
poetry run uvicorn src.api.app:app --reload
```

Nếu Poetry không có trên `PATH`, dùng các executable trong `.venv\Scripts\` như
được ghi trong tài liệu vận hành.

## Tài Liệu

- [Kiến trúc và API](docs/architecture.md)
- [Mô hình dữ liệu](docs/data-model.md)
- [ETL và tự động hóa](docs/etl.md)
- [Triển khai và đồng bộ local](docs/deployment.md)
- [Cloudflare R2 và Power BI](docs/r2-powerbi.md)
