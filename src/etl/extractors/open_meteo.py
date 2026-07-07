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
        "relative_humidity_2m_mean",
        "surface_pressure_mean",
        "wind_speed_10m_max",
        "cloud_cover_mean",
        "shortwave_radiation_sum",
        "precipitation_sum",
    ]

    HOURLY_VARIABLES = [
        "temperature_2m",
        "relative_humidity_2m",
        "surface_pressure",
        "wind_speed_10m",
        "cloud_cover",
        "shortwave_radiation",
        "precipitation",
    ]

    def __init__(
        self,
        archive_url: str,
        forecast_url: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        self._archive_url = archive_url
        self._forecast_url = forecast_url
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
