# Warehouse Design

The warehouse schema follows a star-schema model.

## Dimensions

- `warehouse.dim_date`: calendar dimension keyed by `date_key`.
- `warehouse.dim_province`: historical 63-province Vietnam model with coordinates.

## Facts

- `warehouse.fact_weather_daily`: one row per province per date.
- `warehouse.fact_weather_hourly`: one row per province per timestamp.

## Monitoring

- `monitoring.etl_runs`
- `monitoring.etl_logs`
- `monitoring.validation_errors`
- `monitoring.api_requests`

Power BI should connect directly to Supabase PostgreSQL and import or DirectQuery the warehouse schema. CSV intermediates are intentionally avoided.
