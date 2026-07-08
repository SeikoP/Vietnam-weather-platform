from datetime import date

from src.etl.validators.weather import WeatherDailyRecord, WeatherValidator


def _make_daily_record(**overrides) -> WeatherDailyRecord:
    defaults = dict(
        district_id=1,
        observed_date=date(2024, 1, 15),
        latitude=21.0278,
        longitude=105.8342,
        temperature_2m_mean=25.1,
        temperature_2m_max=30.0,
        temperature_2m_min=20.0,
        apparent_temperature_mean=26.0,
        relative_humidity_2m_mean=77.0,
        dew_point_2m_mean=18.0,
        surface_pressure_mean=1009.4,
        vapour_pressure_deficit_mean=1.2,
        wind_speed_10m_max=22.5,
        wind_gusts_10m_max=35.0,
        cloud_cover_mean=63.0,
        shortwave_radiation_sum=18.2,
        precipitation_sum=5.0,
        rain_sum=5.0,
        weather_code=61,
        soil_moisture_0_to_7cm_mean=0.3,
    )
    defaults.update(overrides)
    return WeatherDailyRecord(**defaults)


def test_validator_accepts_plausible_daily_record() -> None:
    record = _make_daily_record()
    errors = WeatherValidator().validate_daily(record)
    assert errors == []


def test_validator_rejects_impossible_temperature_and_coordinates() -> None:
    record = _make_daily_record(latitude=25.0, longitude=120.0, temperature_2m_mean=90.0)
    errors = WeatherValidator().validate_daily(record)
    assert {error.field_name for error in errors} == {
        "latitude",
        "longitude",
        "temperature_2m_mean",
    }
