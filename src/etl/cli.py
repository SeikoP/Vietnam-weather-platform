"""ETL command-line interface."""

import argparse
from datetime import date, timedelta

from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.database.session import SessionLocal
from src.etl.exceptions import VwdpError
from src.etl.extractors.open_meteo import OpenMeteoClient
from src.etl.orchestration.weather_pipeline import WeatherPipeline
from src.etl.services.etl_run import EtlRunService
from src.etl.transformers.weather import WeatherTransformer
from src.etl.validators.weather import WeatherValidator
from src.monitoring.logging import configure_logging, get_logger

HISTORICAL_START_DATE = date(2023, 6, 1)
RUN_TYPES = {
    "historical-daily",
    "historical-hourly",
    "historical-aqi-hourly",
    "incremental-daily",
    "incremental-hourly",
    "incremental-aqi-hourly",
    "forecast-daily",
    "forecast-hourly",
    "forecast-aqi-hourly",
}

LOGGER = get_logger(__name__)


def resolve_date_range(run_type: str, today: date | None = None) -> tuple[date, date]:
    if run_type not in RUN_TYPES:
        raise ValueError(f"Unsupported run type: {run_type}")
    current_date = today or date.today()
    end_date = current_date - timedelta(days=1)
    if run_type.startswith("historical"):
        return HISTORICAL_START_DATE, end_date
    return end_date, end_date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Hanoi weather/AQI ETL")
    parser.add_argument("--run-type", choices=sorted(RUN_TYPES), default="incremental-daily")
    parser.add_argument("--start-date", type=date.fromisoformat, default=None)
    parser.add_argument("--end-date", type=date.fromisoformat, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    try:
        configure_logging(settings.log_level)
    except Exception:
        configure_logging("INFO")

    try:
        with SessionLocal() as session:
            districts = _get_districts(session)
            if args.start_date and args.end_date:
                start_date, end_date = args.start_date, args.end_date
            else:
                start_date, end_date = resolve_date_range(args.run_type)

            pipeline, etl_run_id = _create_pipeline(session, args.run_type)

            if args.run_type == "forecast-daily":
                affected_rows = pipeline.run_forecast_daily(districts, etl_run_id=etl_run_id)
            elif args.run_type == "forecast-hourly":
                affected_rows = pipeline.run_forecast_hourly(districts, etl_run_id=etl_run_id)
            elif args.run_type == "forecast-aqi-hourly":
                affected_rows = pipeline.run_forecast_aqi_hourly(districts, etl_run_id=etl_run_id)
            elif args.run_type in ("historical-aqi-hourly", "incremental-aqi-hourly"):
                affected_rows = pipeline.run_historical_aqi_hourly(
                    districts, start_date, end_date, etl_run_id
                )
            elif args.run_type.endswith("hourly"):
                affected_rows = pipeline.run_historical_hourly(
                    districts, start_date, end_date, etl_run_id
                )
            else:
                affected_rows = pipeline.run_historical_daily(
                    districts, start_date, end_date, etl_run_id
                )

            _log_summary(session, args.run_type, affected_rows, etl_run_id)
            session.commit()
            return 0

    except VwdpError as exc:
        LOGGER.error("etl_failed", error=str(exc))
        return 1
    except Exception as exc:
        LOGGER.error("unexpected_error", error=str(exc))
        return 1


def _get_districts(session: Session) -> list:
    from src.repositories.district_repository import DistrictRepository

    return DistrictRepository(session).list_all()


def _create_pipeline(session: Session, run_type: str) -> tuple[WeatherPipeline, int]:
    settings = get_settings()
    client = OpenMeteoClient(
        archive_url=settings.open_meteo_archive_url,
        forecast_url=settings.open_meteo_forecast_url,
        timeout_seconds=settings.open_meteo_timeout_seconds,
        max_retries=settings.open_meteo_max_retries,
    )
    etl_run_service = EtlRunService(session)
    etl_run_id = etl_run_service.start_run(run_type)
    pipeline = WeatherPipeline(
        session=session,
        client=client,
        transformer=WeatherTransformer(),
        validator=WeatherValidator(),
        etl_run_service=etl_run_service,
    )
    return pipeline, etl_run_id


def _log_summary(session: Session, run_type: str, affected_rows: int, etl_run_id: int) -> None:
    EtlRunService(session).log(
        etl_run_id=etl_run_id,
        level="INFO",
        event_name="etl_summary",
        message=f"ETL run {run_type} completed",
        context={"affected_rows": affected_rows},
    )
    LOGGER.info("etl_run_complete", run_type=run_type, rows_loaded=affected_rows)
