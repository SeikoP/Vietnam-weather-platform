from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DailyWeatherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    district_id: int
    observed_date: date
    temperature_2m_mean: float | None = None
    temperature_2m_max: float | None = None
    temperature_2m_min: float | None = None
    apparent_temperature_mean: float | None = None
    wind_speed_10m_max: float | None = None
    wind_gusts_10m_max: float | None = None
    shortwave_radiation_sum: float | None = None
    precipitation_sum: float | None = None
    rain_sum: float | None = None
    weather_code: int | None = None


class HourlyWeatherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    district_id: int
    observed_at: datetime
    temperature_2m: float | None = None
    apparent_temperature: float | None = None
    relative_humidity_2m: float | None = None
    dew_point_2m: float | None = None
    surface_pressure: float | None = None
    vapour_pressure_deficit: float | None = None
    wind_speed_10m: float | None = None
    wind_gusts_10m: float | None = None
    cloud_cover: float | None = None
    shortwave_radiation: float | None = None
    precipitation: float | None = None
    rain: float | None = None
    weather_code: int | None = None
    soil_moisture_0_to_7cm: float | None = None


class AqiHourlyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    district_id: int
    observed_at: datetime
    pm10: float | None = None
    pm2_5: float | None = None
    carbon_monoxide: float | None = None
    carbon_dioxide: float | None = None
    nitrogen_dioxide: float | None = None
    sulphur_dioxide: float | None = None
    ozone: float | None = None
    aerosol_optical_depth: float | None = None
    dust: float | None = None
    uv_index: float | None = None
    uv_index_clear_sky: float | None = None
    methane: float | None = None


class WeatherStatisticsResponse(BaseModel):
    district_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    avg_temperature_2m_mean: float | None = None
    max_temperature_2m_max: float | None = None
    min_temperature_2m_min: float | None = None
    total_precipitation_sum: float | None = None
