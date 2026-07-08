from datetime import date

from src.etl.cli import _request_delay_seconds, resolve_date_range


def test_incremental_date_range_loads_recent_rolling_window() -> None:
    start_date, end_date = resolve_date_range("incremental-daily", today=date(2026, 7, 7))

    assert start_date == date(2026, 7, 4)
    assert end_date == date(2026, 7, 6)


def test_incremental_aqi_date_range_uses_same_rolling_window() -> None:
    start_date, end_date = resolve_date_range("incremental-aqi-hourly", today=date(2026, 7, 7))

    assert start_date == date(2026, 7, 4)
    assert end_date == date(2026, 7, 6)


def test_historical_date_range_starts_from_project_start_date() -> None:
    start_date, end_date = resolve_date_range("historical-daily", today=date(2026, 7, 7))

    assert start_date == date(2023, 6, 1)
    assert end_date == date(2026, 7, 6)


def test_historical_runs_use_longer_request_delay() -> None:
    assert _request_delay_seconds("historical-hourly") > _request_delay_seconds(
        "incremental-hourly"
    )
