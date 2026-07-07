from datetime import date

from src.etl.validators.weather import WeatherDailyRecord, WeatherValidator


def test_validator_accepts_plausible_daily_record() -> None:
    record = WeatherDailyRecord(
        province_id=1,
        observed_date=date(2024, 1, 15),
        latitude=21.0278,
        longitude=105.8342,
        temperature_2m_mean=25.1,
        relative_humidity_2m_mean=77.0,
        surface_pressure_mean=1009.4,
        wind_speed_10m_max=22.5,
        cloud_cover_mean=63.0,
        shortwave_radiation_sum=18.2,
    )

    errors = WeatherValidator().validate_daily(record)

    assert errors == []


def test_validator_rejects_impossible_temperature_and_coordinates() -> None:
    record = WeatherDailyRecord(
        province_id=1,
        observed_date=date(2024, 1, 15),
        latitude=99.0,
        longitude=250.0,
        temperature_2m_mean=90.0,
        relative_humidity_2m_mean=77.0,
        surface_pressure_mean=1009.4,
        wind_speed_10m_max=22.5,
        cloud_cover_mean=63.0,
        shortwave_radiation_sum=18.2,
    )

    errors = WeatherValidator().validate_daily(record)

    assert {error.field_name for error in errors} == {
        "latitude",
        "longitude",
        "temperature_2m_mean",
    }
