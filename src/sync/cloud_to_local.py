from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, Select, Table, and_, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, make_url

from src.database.models import (
    DimDate,
    DimDistrict,
    DimHour,
    FactAqiHourly,
    FactWeatherDaily,
    FactWeatherHourly,
)


@dataclass(frozen=True)
class SyncOptions:
    lookback_days: int = 0
    batch_size: int = 1000
    full: bool = False

    def __post_init__(self) -> None:
        if self.lookback_days < 0:
            raise ValueError("lookback_days must be non-negative")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")

    @property
    def lookback(self) -> timedelta:
        return timedelta(days=self.lookback_days)


@dataclass(frozen=True)
class TableSpec:
    name: str
    table: Table
    conflict_columns: tuple[str, ...]
    key_column: str | None
    district_column: str | None = None
    cutoff_column: str | None = None
    cutoff_join: Table | None = None
    always_full: bool = False

    def __post_init__(self) -> None:
        if self.cutoff_join is not None and self.key_column is None:
            raise ValueError("cutoff_join requires key_column")


@dataclass(frozen=True)
class SyncTableResult:
    table_name: str
    rows_read: int
    rows_upserted: int


TABLE_SPECS = (
    TableSpec(
        "dim_district",
        DimDistrict.__table__,
        ("district_id",),
        "district_id",
        always_full=True,
    ),
    TableSpec("dim_date", DimDate.__table__, ("date_key",), "date_key", cutoff_column="date"),
    TableSpec(
        "dim_hour",
        DimHour.__table__,
        ("hour_key",),
        "hour_key",
        cutoff_column="observed_at",
    ),
    TableSpec(
        "fact_weather_daily",
        FactWeatherDaily.__table__,
        ("district_id", "date_key"),
        "date_key",
        district_column="district_id",
        cutoff_column="observed_date",
    ),
    TableSpec(
        "fact_weather_hourly",
        FactWeatherHourly.__table__,
        ("district_id", "hour_key"),
        "hour_key",
        district_column="district_id",
        cutoff_column="observed_at",
        cutoff_join=DimHour.__table__,
    ),
    TableSpec(
        "fact_aqi_hourly",
        FactAqiHourly.__table__,
        ("district_id", "hour_key"),
        "hour_key",
        district_column="district_id",
        cutoff_column="observed_at",
        cutoff_join=DimHour.__table__,
    ),
)

_SPECS_BY_NAME = {spec.name: spec for spec in TABLE_SPECS}
DAILY_SPEC = _SPECS_BY_NAME["fact_weather_daily"]
HOURLY_SPEC = _SPECS_BY_NAME["fact_weather_hourly"]
AQI_SPEC = _SPECS_BY_NAME["fact_aqi_hourly"]

type Watermarks = dict[int, int] | int | None


def _database_identity(url: str) -> tuple[str | None, int | None, str | None]:
    parsed = make_url(url)
    return parsed.host, parsed.port, parsed.database


def validate_distinct_databases(cloud_url: str, local_url: str) -> None:
    if _database_identity(cloud_url) == _database_identity(local_url):
        raise ValueError("cloud and local database endpoints must be different")


def load_watermarks(connection: Connection, spec: TableSpec) -> Watermarks:
    if spec.always_full or spec.key_column is None:
        return None

    key = spec.table.c[spec.key_column]
    if spec.district_column is None:
        return connection.execute(select(func.max(key))).scalar_one_or_none()

    district = spec.table.c[spec.district_column]
    statement = (
        select(district.label("district_id"), func.max(key).label("last_key"))
        .group_by(district)
        .order_by(district)
    )
    rows = connection.execute(statement).mappings().all()
    return {row["district_id"]: row["last_key"] for row in rows}


def load_local_district_ids(connection: Connection) -> tuple[int, ...]:
    district_id = DimDistrict.__table__.c.district_id
    result = connection.execute(select(district_id).order_by(district_id))
    return tuple(result.scalars().all())


def build_source_statement(
    spec: TableSpec,
    watermarks: Watermarks,
    district_ids: tuple[int, ...],
    cutoff: datetime,
    full: bool,
) -> Select:
    table = spec.table
    statement = select(*table.c)

    cutoff_table = table
    if spec.cutoff_join is not None:
        join_table = spec.cutoff_join
        statement = statement.select_from(
            table.join(join_table, table.c[spec.key_column] == join_table.c[spec.key_column])
        )
        cutoff_table = join_table

    conditions = []
    target_is_empty = watermarks is None or watermarks == {}
    if not full and not spec.always_full and not target_is_empty:
        if spec.district_column is not None:
            if not isinstance(watermarks, dict):
                raise ValueError("fact table watermarks must be grouped by district")
            district = table.c[spec.district_column]
            key = table.c[spec.key_column]
            conditions.extend(
                and_(district == district_id, key > watermarks.get(district_id, -1))
                for district_id in district_ids
            )
        else:
            key = table.c[spec.key_column]
            conditions.append(key > watermarks)

        if spec.cutoff_column is not None:
            cutoff_column = cutoff_table.c[spec.cutoff_column]
            cutoff_value = (
                cutoff.date()
                if spec.cutoff_column in {"date", "observed_date"}
                else cutoff
            )
            conditions.append(cutoff_column >= cutoff_value)

    if conditions:
        statement = statement.where(or_(*conditions))

    order_columns = []
    if spec.district_column is not None:
        order_columns.append(table.c[spec.district_column])
    if spec.key_column is not None:
        order_columns.append(table.c[spec.key_column])
    return statement.order_by(*order_columns)


def build_upsert_statement(spec: TableSpec, rows: list[dict[str, Any]]):
    if not rows:
        raise ValueError("rows must not be empty")

    provided_names = set().union(*(row.keys() for row in rows))
    table_names = {column.name for column in spec.table.columns}
    unknown_names = provided_names - table_names
    if unknown_names:
        raise ValueError(f"unknown columns for {spec.name}: {sorted(unknown_names)}")

    ordered_names = [
        column.name for column in spec.table.columns if column.name in provided_names
    ]
    normalized_rows = [{name: row.get(name) for name in ordered_names} for row in rows]
    statement = insert(spec.table).values(normalized_rows)
    update_columns = {
        name: getattr(statement.excluded, name)
        for name in ordered_names
        if name not in spec.conflict_columns
    }
    return statement.on_conflict_do_update(
        index_elements=[spec.table.c[name] for name in spec.conflict_columns],
        set_=update_columns,
    )


class CloudToLocalSync:
    def __init__(
        self,
        cloud_engine: Engine,
        local_engine: Engine,
        options: SyncOptions | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.cloud_engine = cloud_engine
        self.local_engine = local_engine
        self.options = options or SyncOptions()
        self.now_fn = now_fn or (lambda: datetime.now(UTC))

    def run(self) -> list[SyncTableResult]:
        now = self.now_fn()
        if now.tzinfo is None:
            raise ValueError("now_fn must return a timezone-aware datetime")
        cutoff = now - self.options.lookback
        return [self._sync_table(spec, cutoff) for spec in TABLE_SPECS]

    def _sync_table(self, spec: TableSpec, cutoff: datetime) -> SyncTableResult:
        with self.local_engine.connect() as state_connection:
            watermarks = load_watermarks(state_connection, spec)
            district_ids = (
                load_local_district_ids(state_connection)
                if spec.district_column is not None
                else ()
            )

        source_statement = build_source_statement(
            spec,
            watermarks=watermarks,
            district_ids=district_ids,
            cutoff=cutoff,
            full=self.options.full,
        )
        rows_read = 0
        rows_upserted = 0

        with self.cloud_engine.connect() as cloud_connection, cloud_connection.begin():
            cloud_connection.execute(text("SET TRANSACTION READ ONLY"))
            source_result = cloud_connection.execution_options(stream_results=True).execute(
                source_statement
            )

            with self.local_engine.begin() as local_connection:
                for partition in source_result.mappings().partitions(self.options.batch_size):
                    rows = [dict(row) for row in partition]
                    if not rows:
                        continue
                    rows_read += len(rows)
                    local_connection.execute(build_upsert_statement(spec, rows))
                    rows_upserted += len(rows)

        return SyncTableResult(spec.name, rows_read, rows_upserted)
