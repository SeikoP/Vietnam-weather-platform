from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.app import create_app


def _client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=True)


def test_hourly_weather_uses_default_pagination() -> None:
    with patch(
        "src.repositories.weather_repository.WeatherRepository.list_hourly", return_value=[]
    ) as list_hourly:
        response = _client().get("/hourly")

    assert response.status_code == 200
    list_hourly.assert_called_once()
    assert list_hourly.call_args.args == (None, None, None, 100, 0)


def test_aqi_weather_accepts_custom_pagination() -> None:
    with patch(
        "src.repositories.weather_repository.WeatherRepository.list_aqi_hourly", return_value=[]
    ) as list_aqi:
        response = _client().get("/aqi?limit=25&offset=50")

    assert response.status_code == 200
    list_aqi.assert_called_once()
    assert list_aqi.call_args.args == (None, None, None, 25, 50)


def test_hourly_weather_rejects_too_large_limit() -> None:
    response = _client().get("/hourly?limit=1001")

    assert response.status_code == 422
