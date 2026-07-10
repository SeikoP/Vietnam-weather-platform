from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app


def _client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=True)


def test_district_daily_returns_404_for_unknown_district() -> None:
    with patch(
        "src.repositories.district_repository.DistrictRepository.get_by_id", return_value=None
    ):
        response = _client().get("/districts/9999/daily")
    assert response.status_code == 404


def test_district_hourly_returns_404_for_unknown_district() -> None:
    with patch(
        "src.repositories.district_repository.DistrictRepository.get_by_id", return_value=None
    ):
        response = _client().get("/districts/9999/hourly")
    assert response.status_code == 404


def test_district_daily_returns_empty_list_when_no_data() -> None:
    mock_district = MagicMock()
    mock_district.district_id = 1
    with (
        patch(
            "src.repositories.district_repository.DistrictRepository.get_by_id",
            return_value=mock_district,
        ),
        patch("src.repositories.weather_repository.WeatherRepository.list_daily", return_value=[]),
    ):
        response = _client().get("/districts/1/daily")
    assert response.status_code == 200
    assert response.json() == []


def test_district_hourly_returns_empty_list_when_no_data() -> None:
    mock_district = MagicMock()
    mock_district.district_id = 1
    with (
        patch(
            "src.repositories.district_repository.DistrictRepository.get_by_id",
            return_value=mock_district,
        ),
        patch("src.repositories.weather_repository.WeatherRepository.list_hourly", return_value=[]),
    ):
        response = _client().get("/districts/1/hourly")
    assert response.status_code == 200
    assert response.json() == []


def test_district_hourly_uses_default_pagination() -> None:
    mock_district = MagicMock()
    mock_district.district_id = 1
    with (
        patch(
            "src.repositories.district_repository.DistrictRepository.get_by_id",
            return_value=mock_district,
        ),
        patch(
            "src.repositories.weather_repository.WeatherRepository.list_hourly", return_value=[]
        ) as list_hourly,
    ):
        response = _client().get("/districts/1/hourly")

    assert response.status_code == 200
    list_hourly.assert_called_once()
    assert list_hourly.call_args.args == (1, None, None, 100, 0)


def test_district_aqi_accepts_custom_pagination() -> None:
    mock_district = MagicMock()
    mock_district.district_id = 1
    with (
        patch(
            "src.repositories.district_repository.DistrictRepository.get_by_id",
            return_value=mock_district,
        ),
        patch(
            "src.repositories.weather_repository.WeatherRepository.list_aqi_hourly", return_value=[]
        ) as list_aqi,
    ):
        response = _client().get("/districts/1/aqi?limit=25&offset=50")

    assert response.status_code == 200
    list_aqi.assert_called_once()
    assert list_aqi.call_args.args == (1, None, None, 25, 50)
