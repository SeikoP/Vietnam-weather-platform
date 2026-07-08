from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from src.etl.validators.weather import AqiHourlyRecord, WeatherDailyRecord, WeatherHourlyRecord

VIETNAM_TZ = ZoneInfo("Asia/Bangkok")


class WeatherTransformer:
    def daily_from_open_meteo(
        self,
        district_id: int,
        latitude: float,
        longitude: float,
        payload: dict[str, Any],
    ) -> list[WeatherDailyRecord]:
        daily = payload.get("daily") or {}
        dates = daily.get("time") or []
        records: list[WeatherDailyRecord] = []
        for index, iso_date in enumerate(dates):
            records.append(
                WeatherDailyRecord(
                    district_id=district_id,
                    observed_date=date.fromisoformat(iso_date),
                    latitude=latitude,
                    longitude=longitude,
                    temperature_2m_mean=self._val(daily, "temperature_2m_mean", index),
                    temperature_2m_max=self._val(daily, "temperature_2m_max", index),
                    temperature_2m_min=self._val(daily, "temperature_2m_min", index),
                    apparent_temperature_mean=self._val(daily, "apparent_temperature_mean", index),
                    relative_humidity_2m_mean=self._val(daily, "relative_humidity_2m_mean", index),
                    dew_point_2m_mean=self._val(daily, "dew_point_2m_mean", index),
                    surface_pressure_mean=self._val(daily, "surface_pressure_mean", index),
                    vapour_pressure_deficit_mean=self._val(
                        daily, "vapour_pressure_deficit_mean", index
                    ),
                    wind_speed_10m_max=self._val(daily, "wind_speed_10m_max", index),
                    wind_gusts_10m_max=self._val(daily, "wind_gusts_10m_max", index),
                    cloud_cover_mean=self._val(daily, "cloud_cover_mean", index),
                    shortwave_radiation_sum=self._val(daily, "shortwave_radiation_sum", index),
                    precipitation_sum=self._val(daily, "precipitation_sum", index),
                    rain_sum=self._val(daily, "rain_sum", index),
                    weather_code=self._int_val(daily, "weather_code", index),
                    soil_moisture_0_to_7cm_mean=self._val(
                        daily, "soil_moisture_0_to_7cm_mean", index
                    ),
                )
            )
        return records

    def hourly_from_open_meteo(
        self,
        district_id: int,
        latitude: float,
        longitude: float,
        payload: dict[str, Any],
    ) -> list[WeatherHourlyRecord]:
        hourly = payload.get("hourly") or {}
        timestamps = hourly.get("time") or []
        records: list[WeatherHourlyRecord] = []
        for index, iso_timestamp in enumerate(timestamps):
            records.append(
                WeatherHourlyRecord(
                    district_id=district_id,
                    observed_at=_parse_datetime(iso_timestamp),
                    latitude=latitude,
                    longitude=longitude,
                    temperature_2m=self._val(hourly, "temperature_2m", index),
                    apparent_temperature=self._val(hourly, "apparent_temperature", index),
                    relative_humidity_2m=self._val(hourly, "relative_humidity_2m", index),
                    dew_point_2m=self._val(hourly, "dew_point_2m", index),
                    surface_pressure=self._val(hourly, "surface_pressure", index),
                    vapour_pressure_deficit=self._val(hourly, "vapour_pressure_deficit", index),
                    wind_speed_10m=self._val(hourly, "wind_speed_10m", index),
                    wind_gusts_10m=self._val(hourly, "wind_gusts_10m", index),
                    cloud_cover=self._val(hourly, "cloud_cover", index),
                    shortwave_radiation=self._val(hourly, "shortwave_radiation", index),
                    precipitation=self._val(hourly, "precipitation", index),
                    rain=self._val(hourly, "rain", index),
                    weather_code=self._int_val(hourly, "weather_code", index),
                    soil_moisture_0_to_7cm=self._val(hourly, "soil_moisture_0_to_7cm", index),
                )
            )
        return records

    def aqi_hourly_from_open_meteo(
        self,
        district_id: int,
        latitude: float,
        longitude: float,
        payload: dict[str, Any],
    ) -> list[AqiHourlyRecord]:
        hourly = payload.get("hourly") or {}
        timestamps = hourly.get("time") or []
        records: list[AqiHourlyRecord] = []
        for index, iso_timestamp in enumerate(timestamps):
            records.append(
                AqiHourlyRecord(
                    district_id=district_id,
                    observed_at=_parse_datetime(iso_timestamp),
                    latitude=latitude,
                    longitude=longitude,
                    european_aqi=self._val(hourly, "european_aqi", index),
                    us_aqi=self._val(hourly, "us_aqi", index),
                    pm10=self._val(hourly, "pm10", index),
                    pm2_5=self._val(hourly, "pm2_5", index),
                    carbon_monoxide=self._val(hourly, "carbon_monoxide", index),
                    carbon_dioxide=self._val(hourly, "carbon_dioxide", index),
                    nitrogen_dioxide=self._val(hourly, "nitrogen_dioxide", index),
                    sulphur_dioxide=self._val(hourly, "sulphur_dioxide", index),
                    ozone=self._val(hourly, "ozone", index),
                    aerosol_optical_depth=self._val(hourly, "aerosol_optical_depth", index),
                    dust=self._val(hourly, "dust", index),
                    uv_index=self._val(hourly, "uv_index", index),
                    uv_index_clear_sky=self._val(hourly, "uv_index_clear_sky", index),
                    ammonia=self._val(hourly, "ammonia", index),
                    methane=self._val(hourly, "methane", index),
                )
            )
        return records

    @staticmethod
    def _val(series: dict[str, list[Any]], key: str, index: int) -> float | None:
        values = series.get(key)
        if values is None or index >= len(values):
            return None
        value = values[index]
        return None if value is None else float(value)

    @staticmethod
    def _int_val(series: dict[str, list[Any]], key: str, index: int) -> int | None:
        values = series.get(key)
        if values is None or index >= len(values):
            return None
        value = values[index]
        return None if value is None else int(value)


def _parse_datetime(value: str):
    from datetime import datetime

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=VIETNAM_TZ)
    return parsed.astimezone(VIETNAM_TZ)


def date_time_from_open_meteo(value: str):
    return _parse_datetime(value)
