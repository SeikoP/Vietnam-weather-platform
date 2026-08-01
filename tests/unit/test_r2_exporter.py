from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from src.r2.exporter import (
    SnapshotMerger,
    WarehouseExporter,
    _execute_validated_query,
)
from src.r2.models import TableSpec

pytestmark = pytest.mark.filterwarnings(
    "ignore:The default date adapter is deprecated.*:DeprecationWarning"
)

SAMPLE_SPEC = TableSpec(
    name="sample",
    primary_key=("id",),
    columns=("id", "observed_date", "value"),
    date_column="observed_date",
)


def _write_parquet(path: Path, rows: list[tuple[int, str, str]]) -> None:
    import duckdb

    connection = duckdb.connect()
    connection.execute("create table source(id integer, observed_date date, value varchar)")
    connection.executemany("insert into source values (?, ?, ?)", rows)
    connection.execute("copy source to ? (format parquet)", [str(path)])
    connection.close()


def _read_rows(path: Path) -> list[tuple[int, str, str]]:
    import duckdb

    connection = duckdb.connect()
    rows = connection.execute(
        "select id, observed_date::varchar, value from read_parquet(?) order by id",
        [str(path)],
    ).fetchall()
    connection.close()
    return rows


def test_merge_replaces_matching_keys_and_inserts_new_rows(tmp_path: Path) -> None:
    current = tmp_path / "current.parquet"
    delta = tmp_path / "delta.parquet"
    _write_parquet(current, [(1, "2026-07-28", "old"), (2, "2026-07-28", "keep")])
    _write_parquet(delta, [(1, "2026-07-28", "new"), (3, "2026-07-29", "insert")])

    result = SnapshotMerger().merge_table(SAMPLE_SPEC, current, delta, tmp_path / "out")

    assert result.row_count == 3
    assert result.min_date == "2026-07-28"
    assert result.max_date == "2026-07-29"
    assert _read_rows(result.parquet_path) == [
        (1, "2026-07-28", "new"),
        (2, "2026-07-28", "keep"),
        (3, "2026-07-29", "insert"),
    ]


def test_merge_is_idempotent_and_csv_header_is_stable(tmp_path: Path) -> None:
    delta = tmp_path / "delta.parquet"
    _write_parquet(delta, [(1, "2026-07-29", "value")])
    merger = SnapshotMerger()

    first = merger.merge_table(SAMPLE_SPEC, None, delta, tmp_path / "first")
    second = merger.merge_table(SAMPLE_SPEC, first.parquet_path, delta, tmp_path / "second")

    assert second.row_count == 1
    with second.csv_path.open(encoding="utf-8", newline="") as handle:
        assert next(csv.reader(handle)) == ["id", "observed_date", "value"]


def test_merge_fills_new_nullable_column_when_current_snapshot_uses_old_schema(
    tmp_path: Path,
) -> None:
    import duckdb

    current = tmp_path / "current.parquet"
    delta = tmp_path / "delta.parquet"
    connection = duckdb.connect()
    connection.execute(
        "copy (select 1 as district_id, 10 as hour_key, 5.0::real as wind_speed_10m) "
        "to ? (format parquet)",
        [str(current)],
    )
    connection.execute(
        "copy (select 1 as district_id, 11 as hour_key, 6.0::real as wind_speed_10m, "
        "90.0::real as wind_direction_10m) to ? (format parquet)",
        [str(delta)],
    )
    connection.close()
    spec = TableSpec(
        name="fact_weather_hourly",
        primary_key=("district_id", "hour_key"),
        columns=(
            "district_id",
            "hour_key",
            "wind_speed_10m",
            "wind_direction_10m",
        ),
        date_column=None,
    )

    result = SnapshotMerger().merge_table(spec, current, delta, tmp_path / "out")

    connection = duckdb.connect()
    rows = connection.execute(
        "select district_id, hour_key, wind_speed_10m, wind_direction_10m "
        "from read_parquet(?) order by hour_key",
        [str(result.parquet_path)],
    ).fetchall()
    connection.close()
    assert rows == [(1, 10, 5.0, None), (1, 11, 6.0, 90.0)]


def test_merge_rejects_duplicate_keys_inside_delta(tmp_path: Path) -> None:
    delta = tmp_path / "delta.parquet"
    _write_parquet(delta, [(1, "2026-07-29", "first"), (1, "2026-07-29", "second")])

    try:
        SnapshotMerger().merge_table(SAMPLE_SPEC, None, delta, tmp_path / "out")
    except ValueError as exc:
        assert "duplicate primary keys" in str(exc)
    else:
        raise AssertionError("duplicate delta keys must be rejected")


def test_merge_rejects_unsafe_sql_identifiers(tmp_path: Path) -> None:
    delta = tmp_path / "delta.parquet"
    _write_parquet(delta, [(1, "2026-07-29", "value")])
    unsafe_spec = TableSpec(
        name="sample",
        primary_key=("id",),
        columns=("id", "value); drop table merged; --"),
        date_column=None,
    )

    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        SnapshotMerger().merge_table(unsafe_spec, None, delta, tmp_path / "out")


def test_validated_query_rejects_multiple_statements() -> None:
    import duckdb

    connection = duckdb.connect()
    try:
        with pytest.raises(ValueError, match="exactly one statement"):
            _execute_validated_query(connection, "select 1; select 2")
    finally:
        connection.close()


def test_warehouse_exporter_reads_only_requested_date_range(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as connection:
        connection.execute(text("attach database ':memory:' as analyst"))
        connection.execute(
            text(
                "create table analyst.sample("
                "id integer primary key, observed_date text not null, value text)"
            )
        )
        connection.execute(
            text(
                "insert into analyst.sample values "
                "(1, '2026-07-27', 'old'), "
                "(2, '2026-07-28', 'first'), "
                "(3, '2026-07-29', 'second')"
            )
        )
    output = tmp_path / "delta.parquet"

    count = WarehouseExporter(batch_size=1).export_spec(
        engine,
        SAMPLE_SPEC,
        output,
        start_date=date(2026, 7, 28),
        end_date=date(2026, 7, 29),
    )

    assert count == 2
    assert _read_rows(output) == [
        (2, "2026-07-28", "first"),
        (3, "2026-07-29", "second"),
    ]


def test_warehouse_exporter_filters_hourly_fact_through_dim_hour(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as connection:
        connection.execute(text("attach database ':memory:' as analyst"))
        connection.execute(
            text(
                "create table analyst.dim_hour("
                "hour_key integer primary key, observed_date text not null)"
            )
        )
        connection.execute(
            text("insert into analyst.dim_hour values (1, '2026-07-28'), (2, '2026-07-29')")
        )
        connection.execute(
            text(
                "create table analyst.sample_hourly("
                "district_id integer, hour_key integer, value text)"
            )
        )
        connection.execute(
            text("insert into analyst.sample_hourly values (1, 1, 'old'), (1, 2, 'target')")
        )
    spec = TableSpec(
        name="sample_hourly",
        primary_key=("district_id", "hour_key"),
        columns=("district_id", "hour_key", "value"),
        date_column=None,
        date_via_hour=True,
    )
    output = tmp_path / "hourly.parquet"

    count = WarehouseExporter().export_spec(
        engine,
        spec,
        output,
        start_date=date(2026, 7, 29),
        end_date=date(2026, 7, 29),
    )

    import duckdb

    connection = duckdb.connect()
    rows = connection.execute(
        "select district_id, hour_key, value from read_parquet(?)",
        [str(output)],
    ).fetchall()
    connection.close()
    assert count == 1
    assert rows == [(1, 2, "target")]


def test_warehouse_exporter_handles_null_only_first_batch(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as connection:
        connection.execute(text("attach database ':memory:' as analyst"))
        connection.execute(
            text(
                "create table analyst.nullable_sample("
                "id integer primary key, value real null)"
            )
        )
        connection.execute(
            text("insert into analyst.nullable_sample values (1, null), (2, 2.5)")
        )
    spec = TableSpec(
        name="nullable_sample",
        primary_key=("id",),
        columns=("id", "value"),
        date_column=None,
    )
    output = tmp_path / "nullable.parquet"

    count = WarehouseExporter(batch_size=1).export_spec(engine, spec, output)

    import duckdb

    connection = duckdb.connect()
    rows = connection.execute(
        "select id, value from read_parquet(?) order by id",
        [str(output)],
    ).fetchall()
    connection.close()
    assert count == 2
    assert rows == [(1, None), (2, 2.5)]
