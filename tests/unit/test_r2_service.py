from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.r2.models import ReleaseManifest, TableManifest
from src.r2.service import manifest_watermark, resolve_publish_range


def _manifest(max_date: str) -> ReleaseManifest:
    tables = {}
    for name in (
        "fact_weather_daily",
        "fact_weather_hourly",
        "fact_aqi_hourly",
    ):
        tables[name] = TableManifest(
            name=name,
            row_count=1,
            parquet_key=f"{name}.parquet",
            parquet_bytes=1,
            parquet_sha256="a" * 64,
            csv_key=f"{name}.csv",
            csv_bytes=1,
            csv_sha256="b" * 64,
            min_date="2023-06-01",
            max_date=max_date,
        )
    return ReleaseManifest.create(
        release_id="20260728T181500Z",
        source="supabase",
        generated_at=datetime(2026, 7, 28, 18, 15, tzinfo=UTC),
        tables=tables,
    )


def test_watermark_requires_three_fact_tables_to_match() -> None:
    manifest = _manifest("2026-07-28")
    manifest.tables["fact_aqi_hourly"] = TableManifest(
        **{
            **manifest.tables["fact_aqi_hourly"].__dict__,
            "max_date": "2026-07-27",
        }
    )

    with pytest.raises(ValueError, match="watermarks differ"):
        manifest_watermark(manifest)


def test_normal_publish_range_fills_every_gap_after_watermark() -> None:
    publish_range = resolve_publish_range(
        _manifest("2026-07-26"),
        target_date=date(2026, 7, 29),
        start_date=None,
        end_date=None,
        force_republish=False,
    )

    assert publish_range == (date(2026, 7, 27), date(2026, 7, 29))


def test_normal_publish_is_noop_when_release_is_current() -> None:
    assert (
        resolve_publish_range(
            _manifest("2026-07-29"),
            target_date=date(2026, 7, 29),
            start_date=None,
            end_date=None,
            force_republish=False,
        )
        is None
    )


def test_repair_requires_bounded_range_and_force() -> None:
    with pytest.raises(ValueError, match="force-republish"):
        resolve_publish_range(
            _manifest("2026-07-29"),
            target_date=date(2026, 7, 29),
            start_date=date(2026, 7, 28),
            end_date=date(2026, 7, 28),
            force_republish=False,
        )

    assert resolve_publish_range(
        _manifest("2026-07-29"),
        target_date=date(2026, 7, 29),
        start_date=date(2026, 7, 28),
        end_date=date(2026, 7, 28),
        force_republish=True,
    ) == (date(2026, 7, 28), date(2026, 7, 28))

