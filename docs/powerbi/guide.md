# Power BI Guide

Power BI connects directly to Supabase PostgreSQL.

Recommended tables:

- `warehouse.dim_date`
- `warehouse.dim_province`
- `warehouse.fact_weather_daily`

Relationships:

- `fact_weather_daily.date_key` to `dim_date.date_key`
- `fact_weather_daily.province_id` to `dim_province.province_id`

Use `dim_date` for calendar slicers and `dim_province` for geographic filtering.
