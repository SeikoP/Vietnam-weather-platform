from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DailyWeatherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    province_id: int
    observed_date: date
    temperature_2m_mean: float | None = None
    temperature_2m_max: float | None = None
    temperature_2m_min: float | None = None
    relative_humidity_2m_mean: float | None = None
    surface_pressure_mean: float | None = None
    wind_speed_10m_max: float | None = None
    cloud_cover_mean: float | None = None
    shortwave_radiation_sum: float | None = None
    precipitation_sum: float | None = None


class HourlyWeatherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    province_id: int
    observed_at: datetime
    temperature_2m: float | None = None
    relative_humidity_2m: float | None = None
    surface_pressure: float | None = None
    wind_speed_10m: float | None = None
    cloud_cover: float | None = None
    shortwave_radiation: float | None = None
    precipitation: float | None = None


class WeatherStatisticsResponse(BaseModel):
    province_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    avg_temperature_2m_mean: float | None = None
    max_temperature_2m_max: float | None = None
    min_temperature_2m_min: float | None = None
    total_precipitation_sum: float | None = None
