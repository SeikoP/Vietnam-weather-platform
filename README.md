# Hanoi Weather & AQI Data Platform

VWDP is a production-oriented graduation data platform for Hanoi weather and air quality analytics. It uses Open-Meteo as the source, Supabase PostgreSQL as the warehouse, Python ETL for ingestion and validation, FastAPI for REST access, and Power BI through direct PostgreSQL connectivity.

## Architecture

- Extract: Open-Meteo archive and forecast clients with retry, timeout, and structured logs.
- Validate: rule-based checks for coordinates, date, temperature, humidity, pressure, wind, cloud cover, radiation, and precipitation.
- Transform: normalized daily/hourly weather and hourly AQI records.
- Load: idempotent PostgreSQL upserts into warehouse fact tables.
- Serve: FastAPI endpoints for health, districts, daily/hourly weather, hourly AQI, statistics, and district-scoped weather.
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
- `analytics`
- `analyst`
- `monitoring`

Core warehouse tables:

- `analyst.dim_date`
- `analyst.dim_district`
- `analyst.fact_weather_daily`
- `analyst.fact_weather_hourly`
- `analyst.fact_aqi_hourly`

Run migrations:

```powershell
poetry run alembic upgrade head
poetry run python scripts/seed_dim_date.py
poetry run python scripts/seed_provinces.py
```

## ETL

```powershell
# Historical load
poetry run vwdp-etl --run-type historical-daily
poetry run vwdp-etl --run-type historical-hourly
poetry run vwdp-etl --run-type historical-aqi-hourly

# Incremental (yesterday only)
poetry run vwdp-etl --run-type incremental-daily
poetry run vwdp-etl --run-type incremental-hourly
poetry run vwdp-etl --run-type incremental-aqi-hourly

# Forecast (next 7 days from Open-Meteo forecast API)
poetry run vwdp-etl --run-type forecast-daily
poetry run vwdp-etl --run-type forecast-hourly
poetry run vwdp-etl --run-type forecast-aqi-hourly

# Custom date range override
poetry run vwdp-etl --run-type historical-daily --start-date 2024-01-01 --end-date 2024-12-31
```

## API

```powershell
poetry run uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health`
- `GET /districts`
- `GET /districts/{district_id}`
- `GET /districts/{district_id}/daily` — daily weather for one district
- `GET /districts/{district_id}/hourly` — hourly weather for one district
- `GET /districts/{district_id}/aqi` — hourly AQI for one district
- `GET /daily`
- `GET /hourly`
- `GET /aqi`
- `GET /statistics`
- `GET /docs`

Weather and AQI endpoints accept optional `start_date`, `end_date` (YYYY-MM-DD) and `district_id` query parameters.
