from datetime import datetime
from zoneinfo import ZoneInfo

from src.etl.transformers.weather import WeatherTransformer
from src.etl.validators.weather import WeatherValidator


def test_transformer_builds_hourly_records_from_open_meteo_payload() -> None:
    payload = {
        "hourly": {
            "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
            "temperature_2m": [21.4, 21.1],
            "relative_humidity_2m": [88, 89],
            "surface_pressure": [1011.2, 1010.9],
            "wind_speed_10m": [5.5, 6.1],
            "wind_direction_10m": [45.0, 225.0],
            "cloud_cover": [72, 76],
            "shortwave_radiation": [0.0, 0.0],
            "precipitation": [0.0, 0.2],
        }
    }

    records = WeatherTransformer().hourly_from_open_meteo(
        district_id=1,
        latitude=21.0278,
        longitude=105.8342,
        payload=payload,
    )

    assert len(records) == 2
    assert records[0].observed_at == datetime(
        2024,
        1,
        1,
        0,
        0,
        tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"),
    )
    assert records[0].date_key == 20240101
    assert records[0].wind_direction_10m == 45.0
    assert records[1].precipitation == 0.2


def test_validator_rejects_wind_direction_outside_degrees_range() -> None:
    payload = {
        "hourly": {
            "time": ["2024-01-01T00:00"],
            "wind_direction_10m": [361.0],
        }
    }
    record = WeatherTransformer().hourly_from_open_meteo(
        district_id=1,
        latitude=21.0278,
        longitude=105.8342,
        payload=payload,
    )[0]

    errors = WeatherValidator().validate_hourly(record)

    assert {error.field_name for error in errors} == {"wind_direction_10m"}
