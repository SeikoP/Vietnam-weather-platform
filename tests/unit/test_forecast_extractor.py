"""Tests for OpenMeteoClient forecast methods."""

from unittest.mock import MagicMock, patch

from src.etl.extractors.open_meteo import OpenMeteoClient


def _make_client() -> OpenMeteoClient:
    return OpenMeteoClient(
        archive_url="https://archive.example.com",
        forecast_url="https://forecast.example.com",
        timeout_seconds=5,
        max_retries=1,
    )


def test_fetch_forecast_daily_calls_forecast_url() -> None:
    client = _make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = {"daily": {"time": []}}
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response) as mock_get:
        result = client.fetch_forecast_daily(21.0278, 105.8342, forecast_days=3)

    call_url = mock_get.call_args[0][0]
    call_params = mock_get.call_args[1]["params"]
    assert call_url == "https://forecast.example.com"
    assert call_params["forecast_days"] == 3
    assert "daily" in call_params
    assert result == {"daily": {"time": []}}


def test_fetch_forecast_hourly_calls_forecast_url() -> None:
    client = _make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = {"hourly": {"time": []}}
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response) as mock_get:
        result = client.fetch_forecast_hourly(10.8231, 106.6297, forecast_days=5)

    call_url = mock_get.call_args[0][0]
    call_params = mock_get.call_args[1]["params"]
    assert call_url == "https://forecast.example.com"
    assert call_params["forecast_days"] == 5
    assert "hourly" in call_params
    assert result == {"hourly": {"time": []}}