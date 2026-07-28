from datetime import UTC, datetime

import pytest
from sqlalchemy.dialects import postgresql

from src.sync.cloud_to_local import (
    AQI_SPEC,
    DAILY_SPEC,
    HOURLY_SPEC,
    TABLE_SPECS,
    CloudToLocalSync,
    SyncOptions,
    SyncTableResult,
    build_source_statement,
    build_upsert_statement,
    load_local_district_ids,
    load_watermarks,
    validate_distinct_databases,
)


def test_sync_options_reject_negative_lookback() -> None:
    with pytest.raises(ValueError, match="lookback_days"):
        SyncOptions(lookback_days=-1)


def test_sync_options_reject_non_positive_batch_size() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        SyncOptions(batch_size=0)


def test_validate_distinct_databases_rejects_same_database_without_leaking_password() -> None:
    cloud_url = "postgresql+psycopg://cloud:one@localhost:5433/vwdp"
    local_url = "postgresql+psycopg://local:two@localhost:5433/vwdp"

    with pytest.raises(ValueError) as exc_info:
        validate_distinct_databases(cloud_url, local_url)

    assert "one" not in str(exc_info.value)
    assert "two" not in str(exc_info.value)


def test_table_specs_preserve_foreign_key_order_and_conflict_keys() -> None:
    assert [spec.name for spec in TABLE_SPECS] == [
        "dim_district",
        "dim_date",
        "dim_hour",
        "fact_weather_daily",
        "fact_weather_hourly",
        "fact_aqi_hourly",
    ]
    conflicts = {spec.name: spec.conflict_columns for spec in TABLE_SPECS}
    assert conflicts["fact_weather_daily"] == ("district_id", "date_key")
    assert conflicts["fact_weather_hourly"] == ("district_id", "hour_key")
    assert conflicts["fact_aqi_hourly"] == ("district_id", "hour_key")
    assert DAILY_SPEC.name == "fact_weather_daily"
    assert HOURLY_SPEC.name == "fact_weather_hourly"
    assert AQI_SPEC.name == "fact_aqi_hourly"


class RecordingResult:
    def __init__(self, rows: list[dict[str, int]] | None = None, scalar: int | None = None) -> None:
        self.rows = rows or []
        self.scalar = scalar

    def mappings(self) -> "RecordingResult":
        return self

    def all(self) -> list[dict[str, int]]:
        return self.rows

    def scalar_one_or_none(self) -> int | None:
        return self.scalar

    def scalars(self) -> "RecordingResult":
        return self


class RecordingConnection:
    def __init__(self, result: RecordingResult) -> None:
        self.result = result
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return self.result


def test_load_watermarks_returns_max_key_per_district() -> None:
    connection = RecordingConnection(
        RecordingResult(
            rows=[
                {"district_id": 1, "last_key": 2026072801},
                {"district_id": 2, "last_key": 2026072802},
            ]
        )
    )

    result = load_watermarks(connection, HOURLY_SPEC)

    assert result == {1: 2026072801, 2: 2026072802}
    sql = str(connection.statement.compile(dialect=postgresql.dialect()))
    assert "max" in sql.lower()
    assert "group by" in sql.lower()


def test_load_local_district_ids_returns_stable_ids() -> None:
    connection = RecordingConnection(RecordingResult(rows=[1, 2, 5]))

    assert load_local_district_ids(connection) == (1, 2, 5)


def test_hourly_statement_combines_district_watermarks_and_lookback() -> None:
    statement = build_source_statement(
        HOURLY_SPEC,
        watermarks={1: 2026072500, 2: 2026072400},
        district_ids=(1, 2, 3),
        cutoff=datetime(2026, 7, 25, tzinfo=UTC),
        full=False,
    )

    sql = str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "fact_weather_hourly.district_id" in sql
    assert "fact_weather_hourly.hour_key" in sql
    assert "dim_hour.observed_at" in sql
    assert "fact_weather_hourly.hour_key > -1" in sql
    assert " OR " in sql


def test_empty_target_statement_reads_all_source_rows() -> None:
    statement = build_source_statement(
        HOURLY_SPEC,
        watermarks={},
        district_ids=(1, 2),
        cutoff=datetime(2026, 7, 25, tzinfo=UTC),
        full=False,
    )

    assert "WHERE" not in str(statement.compile(dialect=postgresql.dialect()))


def test_full_statement_has_no_incremental_where_clause() -> None:
    statement = build_source_statement(
        DAILY_SPEC,
        watermarks={1: 123},
        district_ids=(1,),
        cutoff=datetime(2026, 7, 25, tzinfo=UTC),
        full=True,
    )

    assert "WHERE" not in str(statement.compile(dialect=postgresql.dialect()))


def test_upsert_statement_updates_daily_row_on_composite_conflict() -> None:
    statement = build_upsert_statement(
        DAILY_SPEC,
        [
            {
                "district_id": 1,
                "date_key": 20260728,
                "observed_date": datetime(2026, 7, 28, tzinfo=UTC).date(),
                "temperature_2m_mean": 30.5,
            }
        ],
    )

    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (district_id, date_key) DO UPDATE" in sql
    assert "temperature_2m_mean" in sql


def test_sync_service_runs_tables_in_order_and_uses_utc_cutoff() -> None:
    observed: list[tuple[str, datetime]] = []
    now = datetime(2026, 7, 28, 12, tzinfo=UTC)

    class RecordingSync(CloudToLocalSync):
        def _sync_table(self, spec, cutoff):
            observed.append((spec.name, cutoff))
            return SyncTableResult(spec.name, 0, 0)

    service = RecordingSync(
        cloud_engine=object(),
        local_engine=object(),
        options=SyncOptions(lookback_days=3),
        now_fn=lambda: now,
    )

    results = service.run()

    assert [result.table_name for result in results] == [spec.name for spec in TABLE_SPECS]
    assert observed == [
        (spec.name, datetime(2026, 7, 25, 12, tzinfo=UTC)) for spec in TABLE_SPECS
    ]
