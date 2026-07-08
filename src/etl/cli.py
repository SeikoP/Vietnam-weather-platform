"""ETL command-line interface."""

import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

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
INCREMENTAL_LOOKBACK_DAYS = 3
HISTORICAL_REQUEST_DELAY_SECONDS = 10.0
STANDARD_REQUEST_DELAY_SECONDS = 1.5
VIETNAM_TZ = ZoneInfo("Asia/Bangkok")
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
    current_date = today or datetime.now(VIETNAM_TZ).date()
    end_date = current_date - timedelta(days=1)
    if run_type.startswith("historical"):
        return HISTORICAL_START_DATE, end_date
    if run_type.startswith("incremental"):
        start_date = end_date - timedelta(days=INCREMENTAL_LOOKBACK_DAYS - 1)
        return start_date, end_date
    return end_date, end_date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Hanoi weather/AQI ETL")
    parser.add_argument("--run-type", choices=sorted(RUN_TYPES), default="incremental-daily")
    parser.add_argument("--start-date", type=date.fromisoformat, default=None)
    parser.add_argument("--end-date", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--district-id",
        action="append",
        type=int,
        default=None,
        help="Limit ETL to one district id. Repeat for multiple districts.",
    )
    parser.add_argument(
        "--max-districts",
        type=int,
        default=None,
        help="Limit ETL to the first N districts after district filters. Useful for demos.",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=None,
        help="Override seconds to wait between district API requests.",
    )
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
            if args.start_date and args.end_date:
                start_date, end_date = args.start_date, args.end_date
            else:
                start_date, end_date = resolve_date_range(args.run_type)

            pipeline, etl_run_id = _create_pipeline(
                session, args.run_type, args.request_delay_seconds
            )
            session.commit()
            districts = _get_districts(session, args.district_id, args.max_districts)
            etl_run_service = EtlRunService(session)

            try:
                affected_rows = _run_pipeline(
                    pipeline=pipeline,
                    run_type=args.run_type,
                    districts=districts,
                    start_date=start_date,
                    end_date=end_date,
                    etl_run_id=etl_run_id,
                )
            except Exception as exc:
                session.rollback()
                etl_run_service.complete_run(
                    etl_run_id=etl_run_id,
                    status="failed",
                    rows_inserted=0,
                    rows_updated=0,
                    rows_skipped=0,
                    error_summary=str(exc),
                )
                session.commit()
                raise

            _log_summary(session, args.run_type, affected_rows, etl_run_id, start_date, end_date)
            etl_run_service.complete_run(
                etl_run_id=etl_run_id,
                status="completed",
                rows_inserted=affected_rows,
                rows_updated=0,
                rows_skipped=0,
            )
            session.commit()
            return 0

    except VwdpError as exc:
        LOGGER.error("etl_failed", error=str(exc))
        return 1
    except Exception as exc:
        LOGGER.error("unexpected_error", error=str(exc))
        return 1


def _get_districts(
    session: Session, district_ids: list[int] | None = None, max_districts: int | None = None
) -> list:
    from src.repositories.district_repository import DistrictRepository

    districts = DistrictRepository(session).list_all()
    if district_ids:
        requested_ids = set(district_ids)
        districts = [district for district in districts if district.district_id in requested_ids]
        found_ids = {district.district_id for district in districts}
        missing_ids = sorted(requested_ids - found_ids)
        if missing_ids:
            raise ValueError(f"Unknown district id(s): {missing_ids}")

    if max_districts is not None:
        if max_districts < 1:
            raise ValueError("--max-districts must be greater than 0")
        districts = districts[:max_districts]
    return districts


def _create_pipeline(
    session: Session, run_type: str, request_delay_seconds: float | None = None
) -> tuple[WeatherPipeline, int]:
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
        district_request_delay_seconds=_request_delay_seconds(run_type, request_delay_seconds),
    )
    return pipeline, etl_run_id


def _request_delay_seconds(run_type: str, override: float | None = None) -> float:
    if override is not None:
        if override < 0:
            raise ValueError("--request-delay-seconds must be 0 or greater")
        return override
    if run_type.startswith("historical"):
        return HISTORICAL_REQUEST_DELAY_SECONDS
    return STANDARD_REQUEST_DELAY_SECONDS


def _run_pipeline(
    pipeline: WeatherPipeline,
    run_type: str,
    districts: list,
    start_date: date,
    end_date: date,
    etl_run_id: int,
) -> int:
    if run_type == "forecast-daily":
        return pipeline.run_forecast_daily(districts, etl_run_id=etl_run_id)
    if run_type == "forecast-hourly":
        return pipeline.run_forecast_hourly(districts, etl_run_id=etl_run_id)
    if run_type == "forecast-aqi-hourly":
        return pipeline.run_forecast_aqi_hourly(districts, etl_run_id=etl_run_id)
    if run_type in ("historical-aqi-hourly", "incremental-aqi-hourly"):
        return pipeline.run_historical_aqi_hourly(districts, start_date, end_date, etl_run_id)
    if run_type.endswith("hourly"):
        return pipeline.run_historical_hourly(districts, start_date, end_date, etl_run_id)
    return pipeline.run_historical_daily(districts, start_date, end_date, etl_run_id)


def _log_summary(
    session: Session,
    run_type: str,
    affected_rows: int,
    etl_run_id: int,
    start_date: date,
    end_date: date,
) -> None:
    EtlRunService(session).log(
        etl_run_id=etl_run_id,
        level="INFO",
        event_name="etl_summary",
        message=f"ETL run {run_type} completed",
        context={
            "affected_rows": affected_rows,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )
    LOGGER.info(
        "etl_run_complete",
        run_type=run_type,
        rows_loaded=affected_rows,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )
