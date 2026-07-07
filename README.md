# Vietnam Weather Data Platform

VWDP is a production-oriented graduation data platform for Vietnam weather analytics. It uses Open-Meteo as the source, Supabase PostgreSQL as the warehouse, Python ETL for ingestion and validation, FastAPI for REST access, and Power BI through direct PostgreSQL connectivity.

## Architecture

- Extract: Open-Meteo archive and forecast clients with retry, timeout, and structured logs.
- Validate: rule-based checks for coordinates, date, temperature, humidity, pressure, wind, cloud cover, radiation, and precipitation.
- Transform: normalized daily/hourly weather records.
- Load: idempotent PostgreSQL upserts into warehouse fact tables.
- Serve: FastAPI endpoints for health, provinces, daily/hourly weather, statistics, and province-scoped weather.
- Monitor: automatic API request logging to `monitoring.api_requests` on every request.
- Automate: GitHub Actions daily schedule. Discord notification is present but disabled by default.

## Local Setup

```powershell
poetry install
Copy-Item .env.example .env
poetry run pytest
poetry run uvicorn src.api.app:app --reload
```

## Required Environment

- `DATABASE_URL`: Supabase PostgreSQL direct connection string.
- `DISCORD_NOTIFICATIONS_ENABLED`: defaults to `false`.
- `DISCORD_WEBHOOK_URL`: only required when Discord notification is enabled.

## Database

Schemas:

- `raw`
- `staging`
- `warehouse`
- `analytics`
- `monitoring`

Core warehouse tables:

- `warehouse.dim_date`
- `warehouse.dim_province`
- `warehouse.fact_weather_daily`
- `warehouse.fact_weather_hourly`

Run migrations:

```powershell
poetry run alembic upgrade head
poetry run python scripts/seed_provinces.py
poetry run python scripts/seed_dim_date.py
```

## ETL

```powershell
# Historical load
poetry run vwdp-etl --run-type historical-daily
poetry run vwdp-etl --run-type historical-hourly

# Incremental (yesterday only)
poetry run vwdp-etl --run-type incremental-daily
poetry run vwdp-etl --run-type incremental-hourly

# Forecast (next 7 days from Open-Meteo forecast API)
poetry run vwdp-etl --run-type forecast-daily
poetry run vwdp-etl --run-type forecast-hourly

# Custom date range override
poetry run vwdp-etl --run-type historical-daily --start-date 2024-01-01 --end-date 2024-12-31
```

## API

```powershell
poetry run uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health`
- `GET /provinces`
- `GET /provinces/{province_id}`
- `GET /provinces/{province_id}/daily` — daily weather for one province
- `GET /provinces/{province_id}/hourly` — hourly weather for one province
- `GET /daily`
- `GET /hourly`
- `GET /weather`
- `GET /statistics`
- `GET /docs`

All weather endpoints accept optional `start_date`, `end_date` (YYYY-MM-DD) and `province_id` query parameters.