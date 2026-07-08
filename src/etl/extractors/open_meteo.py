from datetime import date
from time import monotonic, sleep
from typing import Any

import requests

from src.etl.exceptions import ExternalApiError
from src.monitoring.logging import get_logger

LOGGER = get_logger(__name__)


class OpenMeteoClient:
    DAILY_VARIABLES = [
        "temperature_2m_mean",
        "temperature_2m_max",
        "temperature_2m_min",
        "apparent_temperature_mean",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
        "shortwave_radiation_sum",
        "precipitation_sum",
        "rain_sum",
        "weather_code",
    ]

    HOURLY_VARIABLES = [
        "temperature_2m",
        "apparent_temperature",
        "relative_humidity_2m",
        "dew_point_2m",
        "surface_pressure",
        "vapour_pressure_deficit",
        "wind_speed_10m",
        "wind_gusts_10m",
        "cloud_cover",
        "shortwave_radiation",
        "precipitation",
        "rain",
        "weather_code",
        "soil_moisture_0_to_7cm",
    ]

    AQI_HOURLY_VARIABLES = [
        "pm10",
        "pm2_5",
        "carbon_monoxide",
        "carbon_dioxide",
        "nitrogen_dioxide",
        "sulphur_dioxide",
        "ozone",
        "aerosol_optical_depth",
        "dust",
        "uv_index",
        "uv_index_clear_sky",
        "ammonia",
        "methane",
    ]

    def __init__(
        self,
        archive_url: str,
        forecast_url: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        air_quality_url: str = "https://air-quality-api.open-meteo.com/v1/air-quality",
    ) -> None:
        self._archive_url = archive_url
        self._forecast_url = forecast_url
        self._air_quality_url = air_quality_url
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def fetch_historical_daily(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": ",".join(self.DAILY_VARIABLES),
            "timezone": "Asia/Bangkok",
        }
        return self._get_json(self._archive_url, params)

    def fetch_historical_hourly(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": ",".join(self.HOURLY_VARIABLES),
            "timezone": "Asia/Bangkok",
        }
        return self._get_json(self._archive_url, params)

    def fetch_forecast_daily(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7,
    ) -> dict[str, Any]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_days": forecast_days,
            "daily": ",".join(self.DAILY_VARIABLES),
            "timezone": "Asia/Bangkok",
        }
        return self._get_json(self._forecast_url, params)

    def fetch_forecast_hourly(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7,
    ) -> dict[str, Any]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_days": forecast_days,
            "hourly": ",".join(self.HOURLY_VARIABLES),
            "timezone": "Asia/Bangkok",
        }
        return self._get_json(self._forecast_url, params)

    def fetch_historical_aqi_hourly(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": ",".join(self.AQI_HOURLY_VARIABLES),
            "timezone": "Asia/Bangkok",
        }
        return self._get_json(self._air_quality_url, params)

    def fetch_forecast_aqi_hourly(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7,
    ) -> dict[str, Any]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "forecast_days": forecast_days,
            "hourly": ",".join(self.AQI_HOURLY_VARIABLES),
            "timezone": "Asia/Bangkok",
        }
        return self._get_json(self._air_quality_url, params)

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            started_at = monotonic()
            try:
                response = requests.get(url, params=params, timeout=self._timeout_seconds)
                latency_ms = round((monotonic() - started_at) * 1000, 2)
                LOGGER.info("open_meteo_request", url=url, latency_ms=latency_ms, attempt=attempt)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                LOGGER.warning("open_meteo_retry", url=url, attempt=attempt, error=str(exc))
                if attempt < self._max_retries:
                    sleep(min(2 ** (attempt - 1), 8))
        raise ExternalApiError(f"Open-Meteo request failed after retries: {last_error}")
