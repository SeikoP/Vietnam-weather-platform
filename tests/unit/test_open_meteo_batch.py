from datetime import date
from unittest.mock import MagicMock, patch

from src.etl.exceptions import ExternalApiError
from src.etl.extractors.open_meteo import OpenMeteoClient


def _make_client() -> OpenMeteoClient:
    return OpenMeteoClient(
        archive_url="https://archive.example.com",
        forecast_url="https://forecast.example.com",
        timeout_seconds=5,
        max_retries=1,
    )


def test_fetch_historical_daily_batch_uses_comma_separated_coordinates() -> None:
    client = _make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"daily": {"time": ["2026-07-06"]}},
        {"daily": {"time": ["2026-07-06"]}},
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response) as mock_get:
        result = client.fetch_historical_daily_batch(
            [(1, 21.0333, 105.8333), (2, 21.0285, 105.8542)],
            start_date=date(2026, 7, 6),
            end_date=date(2026, 7, 6),
        )

    call_url = mock_get.call_args[0][0]
    call_params = mock_get.call_args[1]["params"]
    assert call_url == "https://archive.example.com"
    assert call_params["latitude"] == "21.0333,21.0285"
    assert call_params["longitude"] == "105.8333,105.8542"
    assert call_params["start_date"] == "2026-07-06"
    assert call_params["end_date"] == "2026-07-06"
    assert "daily" in call_params
    assert result == {
        1: {"daily": {"time": ["2026-07-06"]}},
        2: {"daily": {"time": ["2026-07-06"]}},
    }


def test_fetch_historical_daily_batch_rejects_response_count_mismatch() -> None:
    client = _make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = [{"daily": {"time": ["2026-07-06"]}}]
    mock_response.raise_for_status = MagicMock()

    try:
        with patch("requests.get", return_value=mock_response):
            client.fetch_historical_daily_batch(
                [(1, 21.0333, 105.8333), (2, 21.0285, 105.8542)],
                start_date=date(2026, 7, 6),
                end_date=date(2026, 7, 6),
            )
    except ExternalApiError as exc:
        assert "returned 1 payloads for 2 districts" in str(exc)
    else:
        raise AssertionError("Expected mismatched batch response to fail")


def test_fetch_historical_hourly_batch_maps_response_by_district_order() -> None:
    client = _make_client()
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"hourly": {"time": ["2026-07-06T00:00"], "temperature_2m": [28.0]}},
        {"hourly": {"time": ["2026-07-06T00:00"], "temperature_2m": [29.0]}},
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response):
        result = client.fetch_historical_hourly_batch(
            [(1, 21.0333, 105.8333), (2, 21.0285, 105.8542)],
            start_date=date(2026, 7, 6),
            end_date=date(2026, 7, 6),
        )

    assert result[1]["hourly"]["temperature_2m"] == [28.0]
    assert result[2]["hourly"]["temperature_2m"] == [29.0]
