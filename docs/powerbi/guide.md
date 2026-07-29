# Hướng Dẫn Power BI

Power BI đọc các file CSV public từ Cloudflare R2, không kết nối trực tiếp Supabase
hoặc PostgreSQL local. Xem cấu hình `Web.Contents`, refresh và rollback tại
[`docs/r2-snapshots.md`](../r2-snapshots.md).

Chỉ cần khai báo `R2BaseUrl` và function `LoadR2Table` một lần. Sáu query bảng gọi
function này bằng tên bảng; không cần tạo sáu Web data source độc lập.

## Bảng

- `dim_hour`
- `dim_date`
- `dim_district`
- `fact_weather_daily`
- `fact_weather_hourly`
- `fact_aqi_hourly`

## Quan Hệ

- `fact_*.date_key` -> `dim_date.date_key`
- `fact_*.district_id` -> `dim_district.district_id`
