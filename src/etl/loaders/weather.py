from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models import DimHour, FactAqiHourly, FactWeatherDaily, FactWeatherHourly
from src.etl.validators.weather import AqiHourlyRecord, WeatherDailyRecord, WeatherHourlyRecord

BATCH_SIZE = 500


class WeatherWarehouseLoader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_daily(self, records: list[WeatherDailyRecord], etl_run_id: int | None) -> int:
        if not records:
            return 0
        for batch in _chunks(records):
            payload = [
                {
                    "district_id": r.district_id,
                    "date_key": r.date_key,
                    "observed_date": r.observed_date,
                    "temperature_2m_mean": r.temperature_2m_mean,
                    "temperature_2m_max": r.temperature_2m_max,
                    "temperature_2m_min": r.temperature_2m_min,
                    "apparent_temperature_mean": r.apparent_temperature_mean,
                    "wind_speed_10m_max": r.wind_speed_10m_max,
                    "wind_gusts_10m_max": r.wind_gusts_10m_max,
                    "shortwave_radiation_sum": r.shortwave_radiation_sum,
                    "precipitation_sum": r.precipitation_sum,
                    "rain_sum": r.rain_sum,
                    "weather_code": r.weather_code,
                }
                for r in batch
            ]
            stmt = insert(FactWeatherDaily).values(payload)
            update_cols = {
                col.name: getattr(stmt.excluded, col.name)
                for col in FactWeatherDaily.__table__.columns
                if col.name not in {"district_id", "date_key"}
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["district_id", "date_key"], set_=update_cols
            )
            self._session.execute(stmt)
        return len(records)

    def upsert_hourly(self, records: list[WeatherHourlyRecord], etl_run_id: int | None) -> int:
        if not records:
            return 0
        for batch in _chunks(records):
            hour_keys = self._upsert_dim_hours(batch)
            payload = [
                {
                    "district_id": r.district_id,
                    "hour_key": hour_keys[r.observed_at],
                    "temperature_2m": r.temperature_2m,
                    "apparent_temperature": r.apparent_temperature,
                    "relative_humidity_2m": r.relative_humidity_2m,
                    "dew_point_2m": r.dew_point_2m,
                    "surface_pressure": r.surface_pressure,
                    "vapour_pressure_deficit": r.vapour_pressure_deficit,
                    "wind_speed_10m": r.wind_speed_10m,
                    "wind_gusts_10m": r.wind_gusts_10m,
                    "cloud_cover": r.cloud_cover,
                    "shortwave_radiation": r.shortwave_radiation,
                    "precipitation": r.precipitation,
                    "rain": r.rain,
                    "weather_code": r.weather_code,
                    "soil_moisture_0_to_7cm": r.soil_moisture_0_to_7cm,
                }
                for r in batch
            ]
            stmt = insert(FactWeatherHourly).values(payload)
            update_cols = {
                col.name: getattr(stmt.excluded, col.name)
                for col in FactWeatherHourly.__table__.columns
                if col.name not in {"district_id", "hour_key"}
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["district_id", "hour_key"], set_=update_cols
            )
            self._session.execute(stmt)
        return len(records)

    def upsert_aqi_hourly(self, records: list[AqiHourlyRecord], etl_run_id: int | None) -> int:
        if not records:
            return 0
        for batch in _chunks(records):
            hour_keys = self._upsert_dim_hours(batch)
            payload = [
                {
                    "district_id": r.district_id,
                    "hour_key": hour_keys[r.observed_at],
                    "pm10": r.pm10,
                    "pm2_5": r.pm2_5,
                    "carbon_monoxide": r.carbon_monoxide,
                    "carbon_dioxide": r.carbon_dioxide,
                    "nitrogen_dioxide": r.nitrogen_dioxide,
                    "sulphur_dioxide": r.sulphur_dioxide,
                    "ozone": r.ozone,
                    "aerosol_optical_depth": r.aerosol_optical_depth,
                    "dust": r.dust,
                    "uv_index": r.uv_index,
                    "uv_index_clear_sky": r.uv_index_clear_sky,
                    "methane": r.methane,
                }
                for r in batch
            ]
            stmt = insert(FactAqiHourly).values(payload)
            update_cols = {
                col.name: getattr(stmt.excluded, col.name)
                for col in FactAqiHourly.__table__.columns
                if col.name not in {"district_id", "hour_key"}
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["district_id", "hour_key"], set_=update_cols
            )
            self._session.execute(stmt)
        return len(records)

    def _upsert_dim_hours(self, records: list[WeatherHourlyRecord | AqiHourlyRecord]) -> dict:
        hours = {
            r.observed_at: {
                "date_key": r.date_key,
                "observed_date": r.observed_date,
                "observed_at": r.observed_at,
            }
            for r in records
        }
        stmt = insert(DimHour).values(list(hours.values()))
        stmt = stmt.on_conflict_do_update(
            index_elements=["observed_at"],
            set_={
                "date_key": stmt.excluded.date_key,
                "observed_date": stmt.excluded.observed_date,
            },
        )
        self._session.execute(stmt)

        rows = self._session.execute(
            DimHour.__table__.select()
            .with_only_columns(DimHour.observed_at, DimHour.hour_key)
            .where(DimHour.observed_at.in_(hours))
        )
        return {observed_at: hour_key for observed_at, hour_key in rows}


def _chunks(records: list, size: int = BATCH_SIZE):
    for index in range(0, len(records), size):
        yield records[index : index + size]
