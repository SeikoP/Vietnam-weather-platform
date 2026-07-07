from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from src.etl.validators.weather import WeatherDailyRecord, WeatherHourlyRecord

VIETNAM_TZ = ZoneInfo("Asia/Bangkok")


class WeatherTransformer:
    def daily_from_open_meteo(
        self,
        province_id: int,
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
                    province_id=province_id,
                    observed_date=date.fromisoformat(iso_date),
                    latitude=latitude,
                    longitude=longitude,
                    temperature_2m_mean=self._value(daily, "temperature_2m_mean", index),
                    temperature_2m_max=self._value(daily, "temperature_2m_max", index),
                    temperature_2m_min=self._value(daily, "temperature_2m_min", index),
                    relative_humidity_2m_mean=self._value(
                        daily,
                        "relative_humidity_2m_mean",
                        index,
                    ),
                    surface_pressure_mean=self._value(daily, "surface_pressure_mean", index),
                    wind_speed_10m_max=self._value(daily, "wind_speed_10m_max", index),
                    cloud_cover_mean=self._value(daily, "cloud_cover_mean", index),
                    shortwave_radiation_sum=self._value(
                        daily,
                        "shortwave_radiation_sum",
                        index,
                    ),
                    precipitation_sum=self._value(daily, "precipitation_sum", index),
                )
            )
        return records

    def hourly_from_open_meteo(
        self,
        province_id: int,
        latitude: float,
        longitude: float,
        payload: dict[str, Any],
    ) -> list[WeatherHourlyRecord]:
        hourly = payload.get("hourly") or {}
        timestamps = hourly.get("time") or []

        records: list[WeatherHourlyRecord] = []
        for index, iso_timestamp in enumerate(timestamps):
            observed_at = date_time_from_open_meteo(iso_timestamp)
            records.append(
                WeatherHourlyRecord(
                    province_id=province_id,
                    observed_at=observed_at,
                    latitude=latitude,
                    longitude=longitude,
                    temperature_2m=self._value(hourly, "temperature_2m", index),
                    relative_humidity_2m=self._value(hourly, "relative_humidity_2m", index),
                    surface_pressure=self._value(hourly, "surface_pressure", index),
                    wind_speed_10m=self._value(hourly, "wind_speed_10m", index),
                    cloud_cover=self._value(hourly, "cloud_cover", index),
                    shortwave_radiation=self._value(hourly, "shortwave_radiation", index),
                    precipitation=self._value(hourly, "precipitation", index),
                )
            )
        return records

    @staticmethod
    def _value(series: dict[str, list[Any]], key: str, index: int) -> float | None:
        values = series.get(key)
        if values is None or index >= len(values):
            return None
        value = values[index]
        return None if value is None else float(value)


def date_time_from_open_meteo(value: str):
    from datetime import datetime

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=VIETNAM_TZ)
    return parsed.astimezone(VIETNAM_TZ)
