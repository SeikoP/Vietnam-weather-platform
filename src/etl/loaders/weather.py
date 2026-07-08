from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database.models import FactAqiHourly, FactWeatherDaily, FactWeatherHourly
from src.etl.validators.weather import AqiHourlyRecord, WeatherDailyRecord, WeatherHourlyRecord


class WeatherWarehouseLoader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_daily(self, records: list[WeatherDailyRecord], etl_run_id: int | None) -> int:
        if not records:
            return 0
        payload = [
            {
                "district_id": r.district_id,
                "date_key": r.date_key,
                "observed_date": r.observed_date,
                "temperature_2m_mean": r.temperature_2m_mean,
                "temperature_2m_max": r.temperature_2m_max,
                "temperature_2m_min": r.temperature_2m_min,
                "apparent_temperature_mean": r.apparent_temperature_mean,
                "relative_humidity_2m_mean": r.relative_humidity_2m_mean,
                "dew_point_2m_mean": r.dew_point_2m_mean,
                "surface_pressure_mean": r.surface_pressure_mean,
                "vapour_pressure_deficit_mean": r.vapour_pressure_deficit_mean,
                "wind_speed_10m_max": r.wind_speed_10m_max,
                "wind_gusts_10m_max": r.wind_gusts_10m_max,
                "cloud_cover_mean": r.cloud_cover_mean,
                "shortwave_radiation_sum": r.shortwave_radiation_sum,
                "precipitation_sum": r.precipitation_sum,
                "rain_sum": r.rain_sum,
                "weather_code": r.weather_code,
                "soil_moisture_0_to_7cm_mean": r.soil_moisture_0_to_7cm_mean,
                "etl_run_id": etl_run_id,
            }
            for r in records
        ]
        stmt = insert(FactWeatherDaily).values(payload)
        update_cols = {
            col.name: getattr(stmt.excluded, col.name)
            for col in FactWeatherDaily.__table__.columns
            if col.name not in {"weather_daily_id", "district_id", "date_key", "created_at"}
        }
        stmt = stmt.on_conflict_do_update(
            constraint="uq_fact_weather_daily_district_date", set_=update_cols
        )
        self._session.execute(stmt)
        return len(records)

    def upsert_hourly(self, records: list[WeatherHourlyRecord], etl_run_id: int | None) -> int:
        if not records:
            return 0
        payload = [
            {
                "district_id": r.district_id,
                "date_key": r.date_key,
                "observed_date": r.observed_date,
                "observed_at": r.observed_at,
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
                "etl_run_id": etl_run_id,
            }
            for r in records
        ]
        stmt = insert(FactWeatherHourly).values(payload)
        update_cols = {
            col.name: getattr(stmt.excluded, col.name)
            for col in FactWeatherHourly.__table__.columns
            if col.name not in {"weather_hourly_id", "district_id", "observed_at", "created_at"}
        }
        stmt = stmt.on_conflict_do_update(
            constraint="uq_fact_weather_hourly_district_time", set_=update_cols
        )
        self._session.execute(stmt)
        return len(records)

    def upsert_aqi_hourly(self, records: list[AqiHourlyRecord], etl_run_id: int | None) -> int:
        if not records:
            return 0
        payload = [
            {
                "district_id": r.district_id,
                "date_key": r.date_key,
                "observed_date": r.observed_date,
                "observed_at": r.observed_at,
                "european_aqi": r.european_aqi,
                "us_aqi": r.us_aqi,
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
                "ammonia": r.ammonia,
                "methane": r.methane,
                "etl_run_id": etl_run_id,
            }
            for r in records
        ]
        stmt = insert(FactAqiHourly).values(payload)
        update_cols = {
            col.name: getattr(stmt.excluded, col.name)
            for col in FactAqiHourly.__table__.columns
            if col.name not in {"aqi_hourly_id", "district_id", "observed_at", "created_at"}
        }
        stmt = stmt.on_conflict_do_update(
            constraint="uq_fact_aqi_hourly_district_time", set_=update_cols
        )
        self._session.execute(stmt)
        return len(records)
