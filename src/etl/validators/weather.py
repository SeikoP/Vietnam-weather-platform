"""Weather data validation module."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class ValidationErrorRecord:
    """Represents a validation error for a weather record."""
    field_name: str
    invalid_value: Any
    reason: str
    severity: str = "error"


@dataclass(frozen=True)
class WeatherDailyRecord:
    """Daily weather observation record."""
    province_id: int
    observed_date: date
    latitude: float
    longitude: float
    temperature_2m_mean: float | None
    relative_humidity_2m_mean: float | None
    surface_pressure_mean: float | None
    wind_speed_10m_max: float | None
    cloud_cover_mean: float | None
    shortwave_radiation_sum: float | None
    temperature_2m_max: float | None = None
    temperature_2m_min: float | None = None
    precipitation_sum: float | None = None

    @property
    def date_key(self) -> int:
        """Return date key in YYYYMMDD format."""
        return int(self.observed_date.strftime("%Y%m%d"))


@dataclass(frozen=True)
class WeatherHourlyRecord:
    """Hourly weather observation record."""
    province_id: int
    observed_at: datetime
    latitude: float
    longitude: float
    temperature_2m: float | None
    relative_humidity_2m: float | None
    surface_pressure: float | None
    wind_speed_10m: float | None
    cloud_cover: float | None
    shortwave_radiation: float | None
    precipitation: float | None

    @property
    def observed_date(self) -> date:
        """Return the date of this observation."""
        return self.observed_at.date()

    @property
    def date_key(self) -> int:
        """Return date key in YYYYMMDD format."""
        return int(self.observed_date.strftime("%Y%m%d"))


class WeatherValidator:
    """Validates weather records against business rules."""

    def validate_daily(self, record: WeatherDailyRecord) -> list[ValidationErrorRecord]:
        """Validate a daily weather record."""
        errors: list[ValidationErrorRecord] = []
        errors.extend(self._range("latitude", record.latitude, 8.0, 24.5))
        errors.extend(self._range("longitude", record.longitude, 102.0, 110.5))
        errors.extend(self._range("temperature_2m_mean", record.temperature_2m_mean, -10.0, 55.0))
        errors.extend(self._range("temperature_2m_max", record.temperature_2m_max, -10.0, 60.0))
        errors.extend(self._range("temperature_2m_min", record.temperature_2m_min, -20.0, 50.0))
        errors.extend(
            self._range("relative_humidity_2m_mean", record.relative_humidity_2m_mean, 0, 100)
        )
        errors.extend(self._range("surface_pressure_mean", record.surface_pressure_mean, 850, 1100))
        errors.extend(self._range("wind_speed_10m_max", record.wind_speed_10m_max, 0, 120))
        errors.extend(self._range("cloud_cover_mean", record.cloud_cover_mean, 0, 100))
        errors.extend(self._range("shortwave_radiation_sum", record.shortwave_radiation_sum, 0, 45))
        errors.extend(self._range("precipitation_sum", record.precipitation_sum, 0, 2000))
        return errors

    def validate_hourly(self, record: WeatherHourlyRecord) -> list[ValidationErrorRecord]:
        """Validate an hourly weather record."""
        errors: list[ValidationErrorRecord] = []
        errors.extend(self._range("latitude", record.latitude, 8.0, 24.5))
        errors.extend(self._range("longitude", record.longitude, 102.0, 110.5))
        errors.extend(self._range("temperature_2m", record.temperature_2m, -10.0, 55.0))
        errors.extend(self._range("relative_humidity_2m", record.relative_humidity_2m, 0, 100))
        errors.extend(self._range("surface_pressure", record.surface_pressure, 850, 1100))
        errors.extend(self._range("wind_speed_10m", record.wind_speed_10m, 0, 120))
        errors.extend(self._range("cloud_cover", record.cloud_cover, 0, 100))
        errors.extend(self._range("shortwave_radiation", record.shortwave_radiation, 0, 1400))
        errors.extend(self._range("precipitation", record.precipitation, 0, 500))
        return errors

    @staticmethod
    def _range(
        field_name: str,
        value: float | int | None,
        minimum: float,
        maximum: float,
    ) -> list[ValidationErrorRecord]:
        """Check if a value is within the valid range."""
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
