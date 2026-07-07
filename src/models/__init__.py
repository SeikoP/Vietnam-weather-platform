"""Domain and API models."""

from .schemas.health import HealthResponse
from .schemas.province import ProvinceResponse
from .schemas.weather import DailyWeatherResponse, HourlyWeatherResponse, WeatherStatisticsResponse

__all__ = [
    "HealthResponse",
    "ProvinceResponse",
    "DailyWeatherResponse",
    "HourlyWeatherResponse",
    "WeatherStatisticsResponse",
]
