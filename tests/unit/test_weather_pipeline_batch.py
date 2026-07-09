from dataclasses import dataclass
from datetime import date
from unittest.mock import MagicMock, patch

from src.etl.orchestration.weather_pipeline import WeatherPipeline
from src.etl.transformers.weather import WeatherTransformer
from src.etl.validators.weather import WeatherValidator


@dataclass(frozen=True)
class District:
    district_id: int
    district_name: str
    latitude: float
    longitude: float


def _make_pipeline(client) -> WeatherPipeline:
    session = MagicMock()
    return WeatherPipeline(
        session=session,
        client=client,
        transformer=WeatherTransformer(),
        validator=WeatherValidator(),
        district_request_delay_seconds=0,
    )


def test_historical_daily_uses_batch_fetch_and_loads_each_district_payload() -> None:
    districts = [
        District(1, "Ba Dinh", 21.0333, 105.8333),
        District(2, "Hoan Kiem", 21.0285, 105.8542),
    ]
    client = MagicMock()
    client.fetch_historical_daily_batch.return_value = {
        1: {
            "daily": {
                "time": ["2026-07-06"],
                "temperature_2m_mean": [28.0],
            }
        },
        2: {
            "daily": {
                "time": ["2026-07-06"],
                "temperature_2m_mean": [29.0],
            }
        },
    }
    pipeline = _make_pipeline(client)

    with patch("src.etl.orchestration.weather_pipeline.WeatherWarehouseLoader") as loader_cls:
        loader = loader_cls.return_value
        loader.upsert_daily.side_effect = lambda records, etl_run_id: len(records)

        rows = pipeline.run_historical_daily(
            districts,
            start_date=date(2026, 7, 6),
            end_date=date(2026, 7, 6),
        )

    assert rows == 2
    client.fetch_historical_daily_batch.assert_called_once()
    assert client.fetch_historical_daily.call_count == 0


def test_historical_daily_falls_back_to_per_district_fetch_when_batch_fails() -> None:
    districts = [
        District(1, "Ba Dinh", 21.0333, 105.8333),
        District(2, "Hoan Kiem", 21.0285, 105.8542),
    ]
    client = MagicMock()
    client.fetch_historical_daily_batch.side_effect = RuntimeError("batch failed")
    client.fetch_historical_daily.side_effect = [
        {"daily": {"time": ["2026-07-06"], "temperature_2m_mean": [28.0]}},
        {"daily": {"time": ["2026-07-06"], "temperature_2m_mean": [29.0]}},
    ]
    pipeline = _make_pipeline(client)

    with patch("src.etl.orchestration.weather_pipeline.WeatherWarehouseLoader") as loader_cls:
        loader = loader_cls.return_value
        loader.upsert_daily.side_effect = lambda records, etl_run_id: len(records)

        rows = pipeline.run_historical_daily(
            districts,
            start_date=date(2026, 7, 6),
            end_date=date(2026, 7, 6),
        )

    assert rows == 2
    client.fetch_historical_daily_batch.assert_called_once()
    assert client.fetch_historical_daily.call_count == 2
