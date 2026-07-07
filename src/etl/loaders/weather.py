from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models import FactWeatherDaily, FactWeatherHourly
from src.etl.validators.weather import WeatherDailyRecord, WeatherHourlyRecord


class WeatherWarehouseLoader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_daily(self, records: list[WeatherDailyRecord], etl_run_id: int | None) -> int:
        if not records:
            return 0

        payload = [
            {
                "province_id": record.province_id,
                "date_key": record.date_key,
                "observed_date": record.observed_date,
                "temperature_2m_mean": record.temperature_2m_mean,
                "temperature_2m_max": record.temperature_2m_max,
                "temperature_2m_min": record.temperature_2m_min,
                "relative_humidity_2m_mean": record.relative_humidity_2m_mean,
                "surface_pressure_mean": record.surface_pressure_mean,
                "wind_speed_10m_max": record.wind_speed_10m_max,
                "cloud_cover_mean": record.cloud_cover_mean,
                "shortwave_radiation_sum": record.shortwave_radiation_sum,
                "precipitation_sum": record.precipitation_sum,
                "etl_run_id": etl_run_id,
            }
            for record in records
        ]
        statement = insert(FactWeatherDaily).values(payload)
        update_columns = {
            column.name: getattr(statement.excluded, column.name)
            for column in FactWeatherDaily.__table__.columns
            if column.name not in {"weather_daily_id", "province_id", "date_key", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            constraint="uq_fact_weather_daily_province_date",
            set_=update_columns,
        )
        self._session.execute(statement)
        return len(records)

    def upsert_hourly(self, records: list[WeatherHourlyRecord], etl_run_id: int | None) -> int:
        if not records:
            return 0

        payload = [
            {
                "province_id": record.province_id,
                "date_key": record.date_key,
                "observed_date": record.observed_date,
                "observed_at": record.observed_at,
                "temperature_2m": record.temperature_2m,
                "relative_humidity_2m": record.relative_humidity_2m,
                "surface_pressure": record.surface_pressure,
                "wind_speed_10m": record.wind_speed_10m,
                "cloud_cover": record.cloud_cover,
                "shortwave_radiation": record.shortwave_radiation,
                "precipitation": record.precipitation,
                "etl_run_id": etl_run_id,
            }
            for record in records
        ]
        statement = insert(FactWeatherHourly).values(payload)
        update_columns = {
            column.name: getattr(statement.excluded, column.name)
            for column in FactWeatherHourly.__table__.columns
            if column.name not in {"weather_hourly_id", "province_id", "observed_at", "created_at"}
        }
        statement = statement.on_conflict_do_update(
            constraint="uq_fact_weather_hourly_province_time",
            set_=update_columns,
        )
        self._session.execute(statement)
        return len(records)
