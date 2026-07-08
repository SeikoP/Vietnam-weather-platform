from datetime import date

from src.etl.transformers.weather import WeatherTransformer


def test_transformer_builds_daily_records_from_open_meteo_payload() -> None:
    payload = {
        "daily": {
            "time": ["2024-01-01", "2024-01-02"],
            "temperature_2m_mean": [24.4, 25.2],
            "temperature_2m_max": [29.0, 30.1],
            "temperature_2m_min": [20.8, 21.3],
            "relative_humidity_2m_mean": [82, 78],
            "surface_pressure_mean": [1010.5, 1009.2],
            "wind_speed_10m_max": [18.0, 20.5],
            "cloud_cover_mean": [70, 61],
            "shortwave_radiation_sum": [16.5, 18.1],
            "precipitation_sum": [1.2, 0.0],
        }
    }

    records = WeatherTransformer().daily_from_open_meteo(
        district_id=1,
        latitude=21.0278,
        longitude=105.8342,
        payload=payload,
    )

    assert len(records) == 2
    assert records[0].observed_date == date(2024, 1, 1)
    assert records[0].date_key == 20240101
    assert records[1].temperature_2m_mean == 25.2
