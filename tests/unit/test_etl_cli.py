from datetime import date

from src.etl.cli import resolve_date_range


def test_incremental_date_range_loads_yesterday_only() -> None:
    start_date, end_date = resolve_date_range("incremental-daily", today=date(2026, 7, 7))

    assert start_date == date(2026, 7, 6)
    assert end_date == date(2026, 7, 6)


def test_historical_date_range_starts_from_project_start_date() -> None:
    start_date, end_date = resolve_date_range("historical-daily", today=date(2026, 7, 7))

    assert start_date == date(2023, 6, 1)
    assert end_date == date(2026, 7, 6)
