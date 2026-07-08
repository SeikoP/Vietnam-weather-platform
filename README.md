# Nền Tảng Dữ Liệu Thời Tiết Hà Nội

Nền tảng ETL, warehouse, API và reporting cho dữ liệu thời tiết/AQI cấp quận/huyện tại Hà Nội.

## Thành Phần

- ETL lấy dữ liệu từ Open-Meteo weather/AQI.
- PostgreSQL lưu dữ liệu phân tích trong schema `analyst`.
- FastAPI cung cấp dữ liệu đã xử lý.
- Monitoring lưu ETL run, log, validation errors và API requests.
- Power BI đọc trực tiếp warehouse.

## Lệnh Chính

```powershell
poetry install
poetry run pytest
poetry run alembic upgrade head
poetry run uvicorn src.api.app:app --reload
```

## Chạy ETL

ETL được expose dưới dạng CLI `vwdp-etl` trong `pyproject.toml`:

```toml
vwdp-etl = "src.etl.cli:main"
```

```powershell
poetry run vwdp-etl --run-type incremental-daily
```

Demo tiết kiệm quota:

```powershell
poetry run vwdp-etl --run-type incremental-daily --district-id 1 --district-id 2 --request-delay-seconds 0
```

Historical demo ngắn:

```powershell
poetry run vwdp-etl --run-type historical-daily --start-date 2026-07-01 --end-date 2026-07-03 --max-districts 2 --request-delay-seconds 0
```

## Tài Liệu

- `docs/architecture/overview.md`: kiến trúc tổng quan.
- `docs/etl/flow.md`: luồng ETL.
- `docs/etl/automation.md`: GitHub Actions và demo mode.
- `docs/etl/demo-runbook.md`: kịch bản demo.
- `docs/database/warehouse-design.md`: mô hình warehouse.
- `docs/database/data-cleanup.md`: cleanup dữ liệu warehouse.
- `docs/powerbi/guide.md`: kết nối Power BI.
