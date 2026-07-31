# Nền Tảng Dữ Liệu Thời Tiết Hà Nội

## Tổng Quan

Nền tảng thu thập và chuẩn hóa dữ liệu thời tiết, chất lượng không khí cho 30
quận/huyện Hà Nội. Dữ liệu được lưu trong Supabase PostgreSQL, theo dõi chất lượng
qua schema giám sát và phát hành thành snapshot trên Cloudflare R2 cho các công cụ
phân tích, báo cáo.

## Kiến Trúc Dữ Liệu

```text
Open-Meteo -> ETL Python -> Supabase PostgreSQL -> Cloudflare R2 -> Reporting tools
```

Supabase là nguồn dữ liệu chuẩn. ETL chịu trách nhiệm thu thập, biến đổi, kiểm tra và
upsert; R2 là lớp phân phối chỉ đọc qua CSV/Parquet, không thay thế warehouse.

## Khả Năng Chính

- Thu thập weather daily, weather hourly và AQI hourly từ Open-Meteo.
- Chuẩn hóa dữ liệu theo quận/huyện và dimension thời gian dùng chung.
- Kiểm tra dữ liệu trước khi nạp, upsert idempotent và ghi nhận trạng thái ETL.
- Quản lý schema bằng SQLAlchemy/Alembic và tách dữ liệu phân tích khỏi monitoring.
- Phát hành release R2 có manifest, checksum và alias ổn định cho công cụ báo cáo.

## Dữ Liệu Phân Tích

Schema `analyst` tổ chức theo mô hình fact/dimension:

- `dim_district`, `dim_date`, `dim_hour` cung cấp ngữ cảnh địa lý và thời gian.
- `fact_weather_daily`, `fact_weather_hourly`, `fact_aqi_hourly` lưu các chỉ số quan sát.

Snapshot CSV/Parquet giữ cùng cấu trúc bảng để Power BI hoặc công cụ tương thích HTTP
có thể tải dữ liệu mà không truy vấn trực tiếp Supabase.

## Tự Động Hóa Và Phân Phối

GitHub Actions điều phối migration, seed, ba collector và bước publish R2 theo lịch.
Workflow chỉ làm nhiệm vụ orchestration; logic nghiệp vụ nằm trong mã nguồn ETL và R2.
Release chỉ được kích hoạt sau khi dữ liệu vượt qua kiểm tra, sau đó được xuất qua
`v1/current/analyst/` và mô tả bởi manifest phiên bản.

## Cấu Trúc Dự Án

- `src/etl/`: extract, transform, validate, load và orchestration.
- `src/database/`: model, session và Alembic migrations.
- `src/monitoring/`: structured logging và thông báo vận hành.
- `src/r2/`: export, merge, manifest, publish và verify snapshot.
- `scripts/`: seed, catch-up, báo cáo và thao tác vận hành.
- `tests/unit/`: kiểm thử ETL, database, workflow và R2.

## Tài Liệu

- [Kiến trúc hệ thống](docs/architecture.md)
- [Mô hình dữ liệu](docs/data-model.md)
- [ETL và tự động hóa](docs/etl.md)
- [Triển khai](docs/deployment.md)
- [Cloudflare R2 và công cụ báo cáo](docs/r2-reporting.md)
