"""Weather ETL orchestration pipeline."""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from src.database.models import DimProvince
from src.etl.extractors.open_meteo import OpenMeteoClient
from src.etl.loaders.weather import WeatherWarehouseLoader
from src.etl.services.etl_run import EtlRunService
from src.etl.transformers.weather import WeatherTransformer
from src.etl.validators.weather import WeatherDailyRecord, WeatherHourlyRecord, WeatherValidator
from src.monitoring.logging import get_logger

LOGGER = get_logger(__name__)


class WeatherPipeline:
    def __init__(
        self,
        session: Session,
        client: OpenMeteoClient,
        transformer: WeatherTransformer,
        validator: WeatherValidator,
        etl_run_service: EtlRunService | None = None,
    ) -> None:
        self._session = session
        self._client = client
        self._transformer = transformer
        self._validator = validator
        self._etl_run_service = etl_run_service

    def _log_validation_error(
        self,
        etl_run_id: int | None,
        record: WeatherDailyRecord | WeatherHourlyRecord,
        field_name: str,
        invalid_value: Any,
        reason: str,
        severity: str,
    ) -> None:
        """Log validation error to database if ETL run service is available."""
        if self._etl_run_service and etl_run_id:
            province_id = getattr(record, "province_id", None)
            if isinstance(record, WeatherDailyRecord):
                source_table = "warehouse.fact_weather_daily"
            elif isinstance(record, WeatherHourlyRecord):
                source_table = "warehouse.fact_weather_hourly"
            else:
                source_table = "unknown"
            self._etl_run_service.store_validation_error(
                etl_run_id=etl_run_id,
                source_table=source_table,
                province_id=province_id,
                field_name=field_name,
                invalid_value=str(invalid_value) if invalid_value is not None else None,
                reason=reason,
                severity=severity,
            )

    def run_historical_daily(
        self,
        provinces: list[DimProvince],
        start_date: date,
        end_date: date,
        etl_run_id: int | None = None,
    ) -> int:
        valid_records = []
        skipped = 0
        total_rejected = 0

        for province in provinces:
            try:
                payload = self._client.fetch_historical_daily(
                    province.latitude,
                    province.longitude,
                    start_date,
                    end_date,
                )
            except Exception as exc:
                if self._etl_run_service and etl_run_id:
                    self._etl_run_service.log(
                        etl_run_id=etl_run_id,
                        level="ERROR",
                        event_name="extract_failed",
                        message=f"Failed to fetch data for province {province.province_name}",
                        context={"province_id": province.province_id, "error": str(exc)},
                    )
                LOGGER.error(
                    "province_extract_failed",
                    province_id=province.province_id,
                    province_name=province.province_name,
                    error=str(exc),
                )
                skipped += 1
                continue

            records = self._transformer.daily_from_open_meteo(
                province.province_id,
                province.latitude,
                province.longitude,
                payload,
            )

            for record in records:
                errors = self._validator.validate_daily(record)
                if errors:
                    skipped += 1
                    total_rejected += len(errors)
                    LOGGER.warning(
                        "weather_record_rejected",
                        province_id=record.province_id,
                        date=record.observed_date.isoformat(),
                        errors=[error.__dict__ for error in errors],
                    )
                    for error in errors:
                        self._log_validation_error(
                            etl_run_id=etl_run_id,
                            record=record,
                            field_name=error.field_name,
                            invalid_value=error.invalid_value,
                            reason=error.reason,
                            severity=error.severity,
                        )
                    continue
                valid_records.append(record)

        affected_rows = WeatherWarehouseLoader(self._session).upsert_daily(
            valid_records, etl_run_id
        )

        if self._etl_run_service and etl_run_id:
            self._etl_run_service.log(
                etl_run_id=etl_run_id,
                level="INFO",
                event_name="pipeline_complete",
                message=f"Daily weather pipeline completed",
                context={
                    "rows_loaded": affected_rows,
                    "rows_skipped": skipped,
                    "total_rejected": total_rejected,
                },
            )

        LOGGER.info(
            "weather_pipeline_complete",
            rows_loaded=affected_rows,
            rows_skipped=skipped,
            total_rejected=total_rejected,
        )
        return affected_rows

    def run_historical_hourly(
        self,
        provinces: list[DimProvince],
        start_date: date,
        end_date: date,
        etl_run_id: int | None = None,
    ) -> int:
        valid_records = []
        skipped = 0
        total_rejected = 0

        for province in provinces:
            try:
                payload = self._client.fetch_historical_hourly(
                    province.latitude,
                    province.longitude,
                    start_date,
                    end_date,
                )
            except Exception as exc:
                if self._etl_run_service and etl_run_id:
                    self._etl_run_service.log(
                        etl_run_id=etl_run_id,
                        level="ERROR",
                        event_name="extract_failed",
                        message=f"Failed to fetch hourly data for province {province.province_name}",
                        context={"province_id": province.province_id, "error": str(exc)},
                    )
                LOGGER.error(
                    "province_hourly_extract_failed",
                    province_id=province.province_id,
                    province_name=province.province_name,
                    error=str(exc),
                )
                skipped += 1
                continue

            records = self._transformer.hourly_from_open_meteo(
                province.province_id,
                province.latitude,
                province.longitude,
                payload,
            )

            for record in records:
                errors = self._validator.validate_hourly(record)
                if errors:
                    skipped += 1
                    total_rejected += len(errors)
                    LOGGER.warning(
                        "weather_hourly_record_rejected",
                        province_id=record.province_id,
                        observed_at=record.observed_at.isoformat(),
                        errors=[error.__dict__ for error in errors],
                    )
                    for error in errors:
                        self._log_validation_error(
                            etl_run_id=etl_run_id,
                            record=record,
                            field_name=error.field_name,
                            invalid_value=error.invalid_value,
                            reason=error.reason,
                            severity=error.severity,
                        )
                    continue
                valid_records.append(record)

        affected_rows = WeatherWarehouseLoader(self._session).upsert_hourly(
            valid_records,
            etl_run_id,
        )

        if self._etl_run_service and etl_run_id:
            self._etl_run_service.log(
                etl_run_id=etl_run_id,
                level="INFO",
                event_name="hourly_pipeline_complete",
                message="Hourly weather pipeline completed",
                context={
                    "rows_loaded": affected_rows,
                    "rows_skipped": skipped,
                    "total_rejected": total_rejected,
                },
            )

        LOGGER.info(
            "weather_hourly_pipeline_complete",
            rows_loaded=affected_rows,
            rows_skipped=skipped,
            total_rejected=total_rejected,
        )
        return affected_rows

    def run_forecast_daily(
        self,
        provinces: list[DimProvince],
        forecast_days: int = 7,
        etl_run_id: int | None = None,
    ) -> int:
        valid_records = []
        skipped = 0
        total_rejected = 0

        for province in provinces:
            try:
                payload = self._client.fetch_forecast_daily(
                    province.latitude,
                    province.longitude,
                    forecast_days,
                )
            except Exception as exc:
                if self._etl_run_service and etl_run_id:
                    self._etl_run_service.log(
                        etl_run_id=etl_run_id,
                        level="ERROR",
                        event_name="extract_failed",
                        message=f"Failed to fetch forecast daily for province {province.province_name}",
                        context={"province_id": province.province_id, "error": str(exc)},
                    )
                LOGGER.error(
                    "province_forecast_daily_extract_failed",
                    province_id=province.province_id,
                    province_name=province.province_name,
                    error=str(exc),
                )
                skipped += 1
                continue

            records = self._transformer.daily_from_open_meteo(
                province.province_id,
                province.latitude,
                province.longitude,
                payload,
            )

            for record in records:
                errors = self._validator.validate_daily(record)
                if errors:
                    skipped += 1
                    total_rejected += len(errors)
                    LOGGER.warning(
                        "forecast_daily_record_rejected",
                        province_id=record.province_id,
                        date=record.observed_date.isoformat(),
                        errors=[error.__dict__ for error in errors],
                    )
                    for error in errors:
                        self._log_validation_error(
                            etl_run_id=etl_run_id,
                            record=record,
                            field_name=error.field_name,
                            invalid_value=error.invalid_value,
                            reason=error.reason,
                            severity=error.severity,
                        )
                    continue
                valid_records.append(record)

        from src.etl.loaders.weather import WeatherWarehouseLoader

        affected_rows = WeatherWarehouseLoader(self._session).upsert_daily(
            valid_records, etl_run_id
        )

        if self._etl_run_service and etl_run_id:
            self._etl_run_service.log(
                etl_run_id=etl_run_id,
                level="INFO",
                event_name="forecast_daily_pipeline_complete",
                message="Forecast daily pipeline completed",
                context={
                    "rows_loaded": affected_rows,
                    "rows_skipped": skipped,
                    "total_rejected": total_rejected,
                },
            )

        LOGGER.info(
            "forecast_daily_pipeline_complete",
            rows_loaded=affected_rows,
            rows_skipped=skipped,
            total_rejected=total_rejected,
        )
        return affected_rows

    def run_forecast_hourly(
        self,
        provinces: list[DimProvince],
        forecast_days: int = 7,
        etl_run_id: int | None = None,
    ) -> int:
        valid_records = []
        skipped = 0
        total_rejected = 0

        for province in provinces:
            try:
                payload = self._client.fetch_forecast_hourly(
                    province.latitude,
                    province.longitude,
                    forecast_days,
                )
            except Exception as exc:
                if self._etl_run_service and etl_run_id:
                    self._etl_run_service.log(
                        etl_run_id=etl_run_id,
                        level="ERROR",
                        event_name="extract_failed",
                        message=f"Failed to fetch forecast hourly for province {province.province_name}",
                        context={"province_id": province.province_id, "error": str(exc)},
                    )
                LOGGER.error(
                    "province_forecast_hourly_extract_failed",
                    province_id=province.province_id,
                    province_name=province.province_name,
                    error=str(exc),
                )
                skipped += 1
                continue

            records = self._transformer.hourly_from_open_meteo(
                province.province_id,
                province.latitude,
                province.longitude,
                payload,
            )

            for record in records:
                errors = self._validator.validate_hourly(record)
                if errors:
                    skipped += 1
                    total_rejected += len(errors)
                    LOGGER.warning(
                        "forecast_hourly_record_rejected",
                        province_id=record.province_id,
                        observed_at=record.observed_at.isoformat(),
                        errors=[error.__dict__ for error in errors],
                    )
                    for error in errors:
                        self._log_validation_error(
                            etl_run_id=etl_run_id,
                            record=record,
                            field_name=error.field_name,
                            invalid_value=error.invalid_value,
                            reason=error.reason,
                            severity=error.severity,
                        )
                    continue
                valid_records.append(record)

        from src.etl.loaders.weather import WeatherWarehouseLoader

        affected_rows = WeatherWarehouseLoader(self._session).upsert_hourly(
            valid_records, etl_run_id
        )

        if self._etl_run_service and etl_run_id:
            self._etl_run_service.log(
                etl_run_id=etl_run_id,
                level="INFO",
                event_name="forecast_hourly_pipeline_complete",
                message="Forecast hourly pipeline completed",
                context={
                    "rows_loaded": affected_rows,
                    "rows_skipped": skipped,
                    "total_rejected": total_rejected,
                },
            )

        LOGGER.info(
            "forecast_hourly_pipeline_complete",
            rows_loaded=affected_rows,
            rows_skipped=skipped,
            total_rejected=total_rejected,
        )
        return affected_rows