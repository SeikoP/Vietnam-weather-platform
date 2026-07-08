# Hướng Dẫn Power BI

Power BI đọc schema `analyst` từ PostgreSQL.

## Bảng

- `dim_date`
- `dim_district`
- `fact_weather_daily`
- `fact_weather_hourly`
- `fact_aqi_hourly`

## Quan Hệ

- `fact_*.date_key` -> `dim_date.date_key`
- `fact_*.district_id` -> `dim_district.district_id`
