"""Tests for dim_date seed script."""

from datetime import date

from scripts.seed_dim_date import build_rows, date_key


def test_date_key_format() -> None:
    assert date_key(date(2024, 1, 15)) == 20240115


def test_build_rows_contains_start_and_end() -> None:
    rows = build_rows(date(2024, 1, 1), date(2024, 1, 3))

    assert len(rows) == 3
    assert rows[0]["date_key"] == 20240101
    assert rows[2]["date_key"] == 20240103


def test_build_rows_weekend_flag() -> None:
    rows = build_rows(date(2024, 1, 6), date(2024, 1, 7))

    assert rows[0]["is_weekend"] is True
    assert rows[1]["is_weekend"] is True


def test_build_rows_weekday_flag() -> None:
    rows = build_rows(date(2024, 1, 1), date(2024, 1, 1))

    assert rows[0]["is_weekend"] is False


def test_build_rows_quarter_calculation() -> None:
    rows = build_rows(date(2024, 4, 1), date(2024, 4, 1))

    assert rows[0]["quarter"] == 2


def test_build_rows_defaults_to_today() -> None:
    rows = build_rows()

    assert len(rows) >= 1
    assert rows[-1]["date"] <= date.today()
