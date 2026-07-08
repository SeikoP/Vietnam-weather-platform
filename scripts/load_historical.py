"""
One-off script to load full historical weather + AQI data for Hanoi districts.
Runs sequentially with a small delay to respect Open-Meteo free tier rate limits.

Usage:
    poetry run python scripts/load_historical.py
    poetry run python scripts/load_historical.py --run-type historical-hourly
    poetry run python scripts/load_historical.py --run-type historical-aqi-hourly
    poetry run python scripts/load_historical.py --start-date 2024-01-01 --end-date 2024-12-31
    poetry run python scripts/load_historical.py --delay 7
"""

import argparse
import datetime
import sys
import time
from datetime import date

from src.config.settings import get_settings
from src.database.seeds.districts import DISTRICTS
from src.database.session import SessionLocal
from src.etl.extractors.open_meteo import OpenMeteoClient
from src.etl.loaders.weather import WeatherWarehouseLoader
from src.etl.transformers.weather import WeatherTransformer
from src.etl.validators.weather import WeatherValidator
from src.monitoring.logging import configure_logging

HISTORICAL_START_DATE = date(2023, 6, 1)
DEFAULT_DELAY = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load historical weather/AQI data for Hanoi")
    parser.add_argument(
        "--run-type",
        choices=["historical-daily", "historical-hourly", "historical-aqi-hourly"],
        default="historical-daily",
    )
    parser.add_argument("--start-date", type=date.fromisoformat, default=None)
    parser.add_argument("--end-date", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Seconds between API requests (default {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip districts that already have data in the warehouse",
    )
    return parser.parse_args()


def ensure_dim_date(start: date, end: date) -> None:
    from datetime import timedelta

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from src.database.models import DimDate

    rows, current = [], start
    while current <= end:
        rows.append(
            {
                "date_key": int(current.strftime("%Y%m%d")),
                "date": current,
                "year": current.year,
                "quarter": ((current.month - 1) // 3) + 1,
                "month": current.month,
                "day": current.day,
                "day_of_week": current.isoweekday(),
                "is_weekend": current.isoweekday() in {6, 7},
            }
        )
        current += timedelta(days=1)

    with SessionLocal() as session:
        stmt = (
            pg_insert(DimDate)
            .values(rows)
            .on_conflict_do_nothing(index_elements=[DimDate.date_key])
        )
        session.execute(stmt)
        session.commit()
    print(f"  dim_date: {len(rows)} dates ensured ({start} to {end})")


def get_loaded_districts(run_type: str) -> set[int]:
    from sqlalchemy import text

    if "aqi" in run_type:
        table = "warehouse.fact_aqi_hourly"
    elif "hourly" in run_type:
        table = "warehouse.fact_weather_hourly"
    else:
        table = "warehouse.fact_weather_daily"
    with SessionLocal() as session:
        rows = session.execute(text(f"SELECT DISTINCT district_id FROM {table}")).fetchall()
    return {row[0] for row in rows}


def fetch_with_retry(client, run_type, latitude, longitude, start_date, end_date, max_wait=60):
    wait = 10
    while True:
        try:
            if run_type == "historical-hourly":
                return client.fetch_historical_hourly(latitude, longitude, start_date, end_date)
            elif run_type == "historical-aqi-hourly":
                return client.fetch_historical_aqi_hourly(latitude, longitude, start_date, end_date)
            else:
                return client.fetch_historical_daily(latitude, longitude, start_date, end_date)
        except Exception as exc:
            if "429" in str(exc) and wait <= max_wait:
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                wait = min(wait * 2, max_wait)
            else:
                raise


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging("WARNING")

    start_date = args.start_date or HISTORICAL_START_DATE
    end_date = args.end_date or (date.today() - datetime.timedelta(days=1))
    total = len(DISTRICTS)
    estimated = total * (args.delay + 6)

    print("\nHanoi Weather & AQI Historical Load")
    print(f"  run-type  : {args.run_type}")
    print(f"  date range: {start_date} -> {end_date}")
    print(f"  districts : {total}")
    print(f"  delay     : {args.delay}s between requests")
    print(f"  estimated : ~{estimated/60:.0f} minutes")
    print()

    print("Ensuring dim_date coverage...")
    ensure_dim_date(start_date, end_date)
    print()

    skip_ids: set[int] = set()
    if args.skip_existing:
        skip_ids = get_loaded_districts(args.run_type)
        print(f"Skipping {len(skip_ids)} districts already loaded.")
        print()

    client = OpenMeteoClient(
        archive_url=settings.open_meteo_archive_url,
        forecast_url=settings.open_meteo_forecast_url,
        timeout_seconds=60,
        max_retries=1,
    )
    transformer = WeatherTransformer()
    validator = WeatherValidator()

    total_loaded = 0
    total_rejected = 0
    errors: list[str] = []
    t0 = time.monotonic()

    for idx, (district_id, district_name, latitude, longitude) in enumerate(DISTRICTS, 1):
        if district_id in skip_ids:
            print(f"  [{idx:2d}/{total}] SKIP {district_name}")
            continue

        try:
            payload = fetch_with_retry(
                client, args.run_type, latitude, longitude, start_date, end_date
            )

            if args.run_type == "historical-hourly":
                records = transformer.hourly_from_open_meteo(
                    district_id, latitude, longitude, payload
                )
                validate_fn = validator.validate_hourly
            elif args.run_type == "historical-aqi-hourly":
                records = transformer.aqi_hourly_from_open_meteo(
                    district_id, latitude, longitude, payload
                )
                validate_fn = validator.validate_aqi_hourly
            else:
                records = transformer.daily_from_open_meteo(
                    district_id, latitude, longitude, payload
                )
                validate_fn = validator.validate_daily

            valid, rejected = [], 0
            for record in records:
                if not validate_fn(record):
                    valid.append(record)
                else:
                    rejected += 1

            if valid:
                with SessionLocal() as session:
                    loader = WeatherWarehouseLoader(session)
                    if args.run_type == "historical-hourly":
                        loaded = loader.upsert_hourly(valid, None)
                    elif args.run_type == "historical-aqi-hourly":
                        loaded = loader.upsert_aqi_hourly(valid, None)
                    else:
                        loaded = loader.upsert_daily(valid, None)
                    session.commit()
            else:
                loaded = 0

            total_loaded += loaded
            total_rejected += rejected
            elapsed = time.monotonic() - t0
            remaining = (total - idx) * (args.delay + 6)
            print(
                f"  [{idx:2d}/{total}] OK  {district_name:<30} {loaded:4d} records  "
                f"({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)"
            )

        except Exception as exc:
            errors.append(f"{district_name}: {exc}")
            print(f"  [{idx:2d}/{total}] FAILED  {district_name}: {exc}")

        if idx < total and district_id not in skip_ids:
            time.sleep(args.delay)

    total_time = time.monotonic() - t0
    print(f"\nDone in {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"  Loaded  : {total_loaded}")
    print(f"  Rejected: {total_rejected}")
    print(f"  Failed  : {len(errors)}")
    if errors:
        print("\nFailed districts:")
        for err in errors:
            print(f"  {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
