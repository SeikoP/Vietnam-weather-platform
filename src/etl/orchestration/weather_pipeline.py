"""Weather + AQI ETL orchestration pipeline."""

from collections.abc import Callable, Iterable
from time import sleep
from typing import Any

from sqlalchemy.orm import Session

from src.database.models import DimDistrict
from src.etl.extractors.open_meteo import OpenMeteoClient
from src.etl.loaders.weather import WeatherWarehouseLoader
from src.etl.services.etl_run import EtlRunService
from src.etl.transformers.weather import WeatherTransformer
from src.etl.validators.weather import (
    AqiHourlyRecord,
    WeatherDailyRecord,
    WeatherHourlyRecord,
    WeatherValidator,
)
from src.monitoring.logging import get_logger

LOGGER = get_logger(__name__)
DEFAULT_DISTRICT_REQUEST_DELAY_SECONDS = 1.5


class WeatherPipeline:
    def __init__(
        self,
        session: Session,
        client: OpenMeteoClient,
        transformer: WeatherTransformer,
        validator: WeatherValidator,
        etl_run_service: EtlRunService | None = None,
        district_request_delay_seconds: float = DEFAULT_DISTRICT_REQUEST_DELAY_SECONDS,
    ) -> None:
        self._session = session
        self._client = client
        self._transformer = transformer
        self._validator = validator
        self._etl_run_service = etl_run_service
        self._district_request_delay_seconds = district_request_delay_seconds

    def _log_validation_error(
        self,
        etl_run_id: int | None,
        record: WeatherDailyRecord | WeatherHourlyRecord | AqiHourlyRecord,
        field_name: str,
        invalid_value: Any,
        reason: str,
        severity: str,
    ) -> None:
        if self._etl_run_service and etl_run_id:
            if isinstance(record, WeatherDailyRecord):
                source_table = "analyst.fact_weather_daily"
            elif isinstance(record, WeatherHourlyRecord):
                source_table = "analyst.fact_weather_hourly"
            elif isinstance(record, AqiHourlyRecord):
                source_table = "analyst.fact_aqi_hourly"
            else:
                source_table = "unknown"
            self._etl_run_service.store_validation_error(
                etl_run_id=etl_run_id,
                source_table=source_table,
                district_id=getattr(record, "district_id", None),
                field_name=field_name,
                invalid_value=str(invalid_value) if invalid_value is not None else None,
                reason=reason,
                severity=severity,
            )

    def _log_extract_error(
        self, etl_run_id: int | None, district: DimDistrict, exc: Exception
    ) -> None:
        if self._etl_run_service and etl_run_id:
            self._etl_run_service.log(
                etl_run_id=etl_run_id,
                level="ERROR",
                event_name="extract_failed",
                message=f"Failed to fetch data for district {district.district_name}",
                context={"district_id": district.district_id, "error": str(exc)},
            )
        LOGGER.error(
            "district_extract_failed",
            district_id=district.district_id,
            district_name=district.district_name,
            error=str(exc),
        )

    def _finish_log(
        self, etl_run_id: int | None, event: str, rows: int, skipped: int, rejected: int
    ) -> None:
        if self._etl_run_service and etl_run_id:
            self._etl_run_service.log(
                etl_run_id=etl_run_id,
                level="INFO",
                event_name=event,
                message=f"{event} completed",
                context={"rows_loaded": rows, "rows_skipped": skipped, "total_rejected": rejected},
            )
        LOGGER.info(event, rows_loaded=rows, rows_skipped=skipped, total_rejected=rejected)

    def _collect_valid_records(
        self,
        district: DimDistrict,
        payload: dict[str, Any],
        transform_payload: Callable[[DimDistrict, dict[str, Any]], list[Any]],
        validate_record: Callable[[Any], list[Any]],
        etl_run_id: int | None,
    ) -> tuple[list[Any], int, int]:
        valid: list[Any] = []
        skipped = 0
        rejected = 0

        for record in transform_payload(district, payload):
            errors = validate_record(record)
            if errors:
                skipped += 1
                rejected += len(errors)
                for error in errors:
                    self._log_validation_error(
                        etl_run_id,
                        record,
                        error.field_name,
                        error.invalid_value,
                        error.reason,
                        error.severity,
                    )
            else:
                valid.append(record)
        return valid, skipped, rejected

    def _run_district_pipeline(
        self,
        districts: Iterable[DimDistrict],
        fetch_payload: Callable[[DimDistrict], dict[str, Any]],
        transform_payload: Callable[[DimDistrict, dict[str, Any]], list[Any]],
        validate_record: Callable[[Any], list[Any]],
        load_records: Callable[[list[Any], int | None], int],
        event_name: str,
        etl_run_id: int | None,
    ) -> int:
        total_rows = 0
        total_skipped = 0
        total_rejected = 0

        for district in districts:
            try:
                payload = fetch_payload(district)
            except Exception as exc:
                self._log_extract_error(etl_run_id, district, exc)
                total_skipped += 1
                self._session.commit()
                sleep(self._district_request_delay_seconds)
                continue

            valid, skipped, rejected = self._collect_valid_records(
                district, payload, transform_payload, validate_record, etl_run_id
            )
            total_rows += load_records(valid, etl_run_id)
            total_skipped += skipped
            total_rejected += rejected
            self._session.commit()
            sleep(self._district_request_delay_seconds)

        self._finish_log(etl_run_id, event_name, total_rows, total_skipped, total_rejected)
        return total_rows

    def _run_batch_district_pipeline(
        self,
        districts: Iterable[DimDistrict],
        fetch_payloads: Callable[[list[DimDistrict]], dict[int, dict[str, Any]]],
        fetch_payload: Callable[[DimDistrict], dict[str, Any]],
        transform_payload: Callable[[DimDistrict, dict[str, Any]], list[Any]],
        validate_record: Callable[[Any], list[Any]],
        load_records: Callable[[list[Any], int | None], int],
        event_name: str,
        etl_run_id: int | None,
    ) -> int:
        district_list = list(districts)
        if not district_list:
            self._finish_log(etl_run_id, event_name, 0, 0, 0)
            return 0

        try:
            payloads = fetch_payloads(district_list)
        except Exception as exc:
            LOGGER.warning("district_batch_fetch_failed", event_name=event_name, error=str(exc))
            return self._run_district_pipeline(
                districts=district_list,
                fetch_payload=fetch_payload,
                transform_payload=transform_payload,
                validate_record=validate_record,
                load_records=load_records,
                event_name=event_name,
                etl_run_id=etl_run_id,
            )

        total_rows = 0
        total_skipped = 0
        total_rejected = 0
        for district in district_list:
            payload = payloads.get(district.district_id, {})
            valid, skipped, rejected = self._collect_valid_records(
                district, payload, transform_payload, validate_record, etl_run_id
            )
            total_rows += load_records(valid, etl_run_id)
            total_skipped += skipped
            total_rejected += rejected
            self._session.commit()

        self._finish_log(etl_run_id, event_name, total_rows, total_skipped, total_rejected)
        return total_rows

    def _transform_daily(self, district: DimDistrict, payload: dict[str, Any]):
        return self._transformer.daily_from_open_meteo(
            district.district_id, district.latitude, district.longitude, payload
        )

    def _transform_hourly(self, district: DimDistrict, payload: dict[str, Any]):
        return self._transformer.hourly_from_open_meteo(
            district.district_id, district.latitude, district.longitude, payload
        )

    def _transform_aqi_hourly(self, district: DimDistrict, payload: dict[str, Any]):
        return self._transformer.aqi_hourly_from_open_meteo(
            district.district_id, district.latitude, district.longitude, payload
        )

    # ------------------------------------------------------------------
    # Historical / incremental weather
    # ------------------------------------------------------------------

    def run_historical_daily(self, districts, start_date, end_date, etl_run_id=None):
        loader = WeatherWarehouseLoader(self._session)
        return self._run_batch_district_pipeline(
            districts=districts,
            fetch_payloads=lambda district_list: self._client.fetch_historical_daily_batch(
                [
                    (district.district_id, district.latitude, district.longitude)
                    for district in district_list
                ],
                start_date,
                end_date,
            ),
            fetch_payload=lambda district: self._client.fetch_historical_daily(
                district.latitude, district.longitude, start_date, end_date
            ),
            transform_payload=self._transform_daily,
            validate_record=self._validator.validate_daily,
            load_records=loader.upsert_daily,
            event_name="historical_daily_pipeline_complete",
            etl_run_id=etl_run_id,
        )

    def run_historical_hourly(self, districts, start_date, end_date, etl_run_id=None):
        loader = WeatherWarehouseLoader(self._session)
        return self._run_batch_district_pipeline(
            districts=districts,
            fetch_payloads=lambda district_list: self._client.fetch_historical_hourly_batch(
                [
                    (district.district_id, district.latitude, district.longitude)
                    for district in district_list
                ],
                start_date,
                end_date,
            ),
            fetch_payload=lambda district: self._client.fetch_historical_hourly(
                district.latitude, district.longitude, start_date, end_date
            ),
            transform_payload=self._transform_hourly,
            validate_record=self._validator.validate_hourly,
            load_records=loader.upsert_hourly,
            event_name="historical_hourly_pipeline_complete",
            etl_run_id=etl_run_id,
        )

    def run_forecast_daily(self, districts, forecast_days=7, etl_run_id=None):
        loader = WeatherWarehouseLoader(self._session)
        return self._run_district_pipeline(
            districts=districts,
            fetch_payload=lambda district: self._client.fetch_forecast_daily(
                district.latitude, district.longitude, forecast_days
            ),
            transform_payload=self._transform_daily,
            validate_record=self._validator.validate_daily,
            load_records=loader.upsert_daily,
            event_name="forecast_daily_pipeline_complete",
            etl_run_id=etl_run_id,
        )

    def run_forecast_hourly(self, districts, forecast_days=7, etl_run_id=None):
        loader = WeatherWarehouseLoader(self._session)
        return self._run_district_pipeline(
            districts=districts,
            fetch_payload=lambda district: self._client.fetch_forecast_hourly(
                district.latitude, district.longitude, forecast_days
            ),
            transform_payload=self._transform_hourly,
            validate_record=self._validator.validate_hourly,
            load_records=loader.upsert_hourly,
            event_name="forecast_hourly_pipeline_complete",
            etl_run_id=etl_run_id,
        )

    def run_historical_aqi_hourly(self, districts, start_date, end_date, etl_run_id=None):
        loader = WeatherWarehouseLoader(self._session)
        return self._run_batch_district_pipeline(
            districts=districts,
            fetch_payloads=lambda district_list: self._client.fetch_historical_aqi_hourly_batch(
                [
                    (district.district_id, district.latitude, district.longitude)
                    for district in district_list
                ],
                start_date,
                end_date,
            ),
            fetch_payload=lambda district: self._client.fetch_historical_aqi_hourly(
                district.latitude, district.longitude, start_date, end_date
            ),
            transform_payload=self._transform_aqi_hourly,
            validate_record=self._validator.validate_aqi_hourly,
            load_records=loader.upsert_aqi_hourly,
            event_name="historical_aqi_hourly_pipeline_complete",
            etl_run_id=etl_run_id,
        )

    def run_forecast_aqi_hourly(self, districts, forecast_days=7, etl_run_id=None):
        loader = WeatherWarehouseLoader(self._session)
        return self._run_district_pipeline(
            districts=districts,
            fetch_payload=lambda district: self._client.fetch_forecast_aqi_hourly(
                district.latitude, district.longitude, forecast_days
            ),
            transform_payload=self._transform_aqi_hourly,
            validate_record=self._validator.validate_aqi_hourly,
            load_records=loader.upsert_aqi_hourly,
            event_name="forecast_aqi_hourly_pipeline_complete",
            etl_run_id=etl_run_id,
        )
