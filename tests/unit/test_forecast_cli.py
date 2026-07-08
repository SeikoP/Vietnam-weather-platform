"""Tests for forecast run types in ETL CLI."""

from datetime import date

from src.etl.cli import resolve_date_range


def test_forecast_daily_resolve_date_range_returns_yesterday() -> None:
    start_date, end_date = resolve_date_range("forecast-daily", today=date(2026, 7, 7))

    assert start_date == date(2026, 7, 6)
    assert end_date == date(2026, 7, 6)


def test_forecast_hourly_resolve_date_range_returns_yesterday() -> None:
    start_date, end_date = resolve_date_range("forecast-hourly", today=date(2026, 7, 7))

    assert start_date == date(2026, 7, 6)
    assert end_date == date(2026, 7, 6)
