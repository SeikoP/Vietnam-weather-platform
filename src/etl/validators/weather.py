"""Weather data validation module."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class ValidationErrorRecord:
    field_name: str
    invalid_value: Any
    reason: str
    severity: str = "error"


@dataclass(frozen=True)
class WeatherDailyRecord:
    district_id: int
    observed_date: date
    latitude: float
    longitude: float
    temperature_2m_mean: float | None
    temperature_2m_max: float | None
    temperature_2m_min: float | None
    apparent_temperature_mean: float | None
    relative_humidity_2m_mean: float | None
    dew_point_2m_mean: float | None
    surface_pressure_mean: float | None
    vapour_pressure_deficit_mean: float | None
    wind_speed_10m_max: float | None
    wind_gusts_10m_max: float | None
    cloud_cover_mean: float | None
    shortwave_radiation_sum: float | None
    precipitation_sum: float | None
    rain_sum: float | None
    weather_code: int | None
    soil_moisture_0_to_7cm_mean: float | None

    @property
    def date_key(self) -> int:
        return int(self.observed_date.strftime("%Y%m%d"))


@dataclass(frozen=True)
class WeatherHourlyRecord:
    district_id: int
    observed_at: datetime
    latitude: float
    longitude: float
    temperature_2m: float | None
    apparent_temperature: float | None
    relative_humidity_2m: float | None
    dew_point_2m: float | None
    surface_pressure: float | None
    vapour_pressure_deficit: float | None
    wind_speed_10m: float | None
    wind_gusts_10m: float | None
    cloud_cover: float | None
    shortwave_radiation: float | None
    precipitation: float | None
    rain: float | None
    weather_code: int | None
    soil_moisture_0_to_7cm: float | None

    @property
    def observed_date(self) -> date:
        return self.observed_at.date()

    @property
    def date_key(self) -> int:
        return int(self.observed_date.strftime("%Y%m%d"))


@dataclass(frozen=True)
class AqiHourlyRecord:
    district_id: int
    observed_at: datetime
    latitude: float
    longitude: float
    european_aqi: float | None
    us_aqi: float | None
    pm10: float | None
    pm2_5: float | None
    carbon_monoxide: float | None
    carbon_dioxide: float | None
    nitrogen_dioxide: float | None
    sulphur_dioxide: float | None
    ozone: float | None
    aerosol_optical_depth: float | None
    dust: float | None
    uv_index: float | None
    uv_index_clear_sky: float | None
    ammonia: float | None
    methane: float | None

    @property
    def observed_date(self) -> date:
        return self.observed_at.date()

    @property
    def date_key(self) -> int:
        return int(self.observed_date.strftime("%Y%m%d"))


class WeatherValidator:
    def validate_daily(self, record: WeatherDailyRecord) -> list[ValidationErrorRecord]:
        errors: list[ValidationErrorRecord] = []
        errors.extend(self._range("latitude", record.latitude, 20.5, 21.5))
        errors.extend(self._range("longitude", record.longitude, 105.2, 106.1))
        errors.extend(self._range("temperature_2m_mean", record.temperature_2m_mean, -5.0, 45.0))
        errors.extend(self._range("temperature_2m_max", record.temperature_2m_max, -5.0, 45.0))
        errors.extend(self._range("temperature_2m_min", record.temperature_2m_min, -5.0, 45.0))
        errors.extend(
            self._range("apparent_temperature_mean", record.apparent_temperature_mean, -10.0, 55.0)
        )
        errors.extend(
            self._range("relative_humidity_2m_mean", record.relative_humidity_2m_mean, 0, 100)
        )
        errors.extend(self._range("dew_point_2m_mean", record.dew_point_2m_mean, -10.0, 35.0))
        errors.extend(self._range("surface_pressure_mean", record.surface_pressure_mean, 950, 1050))
        errors.extend(
            self._range("vapour_pressure_deficit_mean", record.vapour_pressure_deficit_mean, 0, 8)
        )
        errors.extend(self._range("wind_speed_10m_max", record.wind_speed_10m_max, 0, 100))
        errors.extend(self._range("wind_gusts_10m_max", record.wind_gusts_10m_max, 0, 150))
        errors.extend(self._range("cloud_cover_mean", record.cloud_cover_mean, 0, 100))
        errors.extend(self._range("shortwave_radiation_sum", record.shortwave_radiation_sum, 0, 40))
        errors.extend(self._range("precipitation_sum", record.precipitation_sum, 0, 800))
        errors.extend(self._range("rain_sum", record.rain_sum, 0, 800))
        errors.extend(
            self._range("soil_moisture_0_to_7cm_mean", record.soil_moisture_0_to_7cm_mean, 0, 1)
        )
        return errors

    def validate_hourly(self, record: WeatherHourlyRecord) -> list[ValidationErrorRecord]:
        errors: list[ValidationErrorRecord] = []
        errors.extend(self._range("latitude", record.latitude, 20.5, 21.5))
        errors.extend(self._range("longitude", record.longitude, 105.2, 106.1))
        errors.extend(self._range("temperature_2m", record.temperature_2m, -5.0, 45.0))
        errors.extend(self._range("apparent_temperature", record.apparent_temperature, -10.0, 55.0))
        errors.extend(self._range("relative_humidity_2m", record.relative_humidity_2m, 0, 100))
        errors.extend(self._range("dew_point_2m", record.dew_point_2m, -10.0, 35.0))
        errors.extend(self._range("surface_pressure", record.surface_pressure, 950, 1050))
        errors.extend(self._range("vapour_pressure_deficit", record.vapour_pressure_deficit, 0, 8))
        errors.extend(self._range("wind_speed_10m", record.wind_speed_10m, 0, 100))
        errors.extend(self._range("wind_gusts_10m", record.wind_gusts_10m, 0, 150))
        errors.extend(self._range("cloud_cover", record.cloud_cover, 0, 100))
        errors.extend(self._range("shortwave_radiation", record.shortwave_radiation, 0, 1400))
        errors.extend(self._range("precipitation", record.precipitation, 0, 300))
        errors.extend(self._range("rain", record.rain, 0, 300))
        errors.extend(self._range("soil_moisture_0_to_7cm", record.soil_moisture_0_to_7cm, 0, 1))
        return errors

    def validate_aqi_hourly(self, record: AqiHourlyRecord) -> list[ValidationErrorRecord]:
        errors: list[ValidationErrorRecord] = []
        errors.extend(self._range("latitude", record.latitude, 20.5, 21.5))
        errors.extend(self._range("longitude", record.longitude, 105.2, 106.1))
        errors.extend(self._range("european_aqi", record.european_aqi, 0, 500))
        errors.extend(self._range("us_aqi", record.us_aqi, 0, 500))
        errors.extend(self._range("pm10", record.pm10, 0, 1000))
        errors.extend(self._range("pm2_5", record.pm2_5, 0, 500))
        errors.extend(self._range("carbon_monoxide", record.carbon_monoxide, 0, 100000))
        errors.extend(self._range("nitrogen_dioxide", record.nitrogen_dioxide, 0, 1000))
        errors.extend(self._range("sulphur_dioxide", record.sulphur_dioxide, 0, 1000))
        errors.extend(self._range("ozone", record.ozone, 0, 500))
        errors.extend(self._range("uv_index", record.uv_index, 0, 20))
        errors.extend(self._range("uv_index_clear_sky", record.uv_index_clear_sky, 0, 20))
        errors.extend(self._range("dust", record.dust, 0, 10000))
        return errors

    @staticmethod
    def _range(
        field_name: str,
        value: float | int | None,
        minimum: float,
        maximum: float,
    ) -> list[ValidationErrorRecord]:
        if value is None:
            return []
        if minimum <= value <= maximum:
            return []
        return [
            ValidationErrorRecord(
                field_name=field_name,
                invalid_value=value,
                reason=f"{field_name} must be between {minimum} and {maximum}",
            )
        ]
