from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Engine,
    Float,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    inspect,
    text,
)

from src.r2.models import TableSpec

SQL_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True)
class ExportedTable:
    name: str
    parquet_path: Path
    csv_path: Path
    row_count: int
    parquet_bytes: int
    parquet_sha256: str
    csv_bytes: int
    csv_sha256: str
    min_date: str | None
    max_date: str | None


class WarehouseExporter:
    def __init__(self, batch_size: int = 5_000) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size

    def export_spec(
        self,
        engine: Engine,
        spec: TableSpec,
        output_path: Path,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        if (start_date is None) != (end_date is None):
            raise ValueError("start_date and end_date must be provided together")
        _validate_spec_identifiers(spec)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        columns = ", ".join(f"source.{_quote_identifier(column)}" for column in spec.columns)
        query = (
            f"select {columns} "
            f"from analyst.{_quote_identifier(spec.name)} as source"
        )
        parameters: dict[str, date] = {}
        if start_date is not None and end_date is not None:
            if spec.date_via_hour:
                query += (
                    " join analyst.dim_hour as hour "
                    "on hour.hour_key = source.hour_key "
                    "where hour.observed_date between :start_date and :end_date"
                )
            elif spec.date_column is not None:
                query += (
                    f" where source.{_quote_identifier(spec.date_column)} "
                    "between :start_date and :end_date"
                )
            else:
                raise ValueError(f"{spec.name} does not support date filtering")
            parameters = {"start_date": start_date, "end_date": end_date}
        order_by = ", ".join(
            f"source.{_quote_identifier(column)}" for column in spec.primary_key
        )
        query += f" order by {order_by}"

        writer: pq.ParquetWriter | None = None
        row_count = 0
        try:
            with engine.connect() as connection:
                arrow_schema = _arrow_schema(connection, spec)
                result = (
                    connection.execution_options(stream_results=True)
                    .execute(text(query), parameters)
                    .mappings()
                )
                while rows := result.fetchmany(self.batch_size):
                    records = [dict(row) for row in rows]
                    table = pa.Table.from_pylist(records, schema=arrow_schema)
                    if writer is None:
                        writer = pq.ParquetWriter(output_path, table.schema, compression="zstd")
                    writer.write_table(table)
                    row_count += len(records)
        finally:
            if writer is not None:
                writer.close()

        if writer is None:
            raise ValueError(f"{spec.name} export returned zero rows")
        return row_count


class SnapshotMerger:
    def merge_table(
        self,
        spec: TableSpec,
        current_parquet: Path | None,
        delta_parquet: Path,
        output_directory: Path,
    ) -> ExportedTable:
        _validate_spec_identifiers(spec)
        output_directory.mkdir(parents=True, exist_ok=True)
        parquet_path = output_directory / f"{spec.name}.parquet"
        csv_path = output_directory / f"{spec.name}.csv"
        columns = ", ".join(_quote_identifier(column) for column in spec.columns)
        keys = ", ".join(_quote_identifier(column) for column in spec.primary_key)

        connection = duckdb.connect()
        try:
            # DuckDB parameters bind values, not SQL identifiers. TableSpec identifiers
            # are allowlisted above; every file path remains a prepared parameter.
            duplicate_query = f"""
                select count(*)
                from (
                    select {keys}
                    from read_parquet(?)
                    group by {keys}
                    having count(*) > 1
                )
                """
            duplicate_count = connection.execute(
                duplicate_query,
                [str(delta_parquet)],
            ).fetchone()[0]
            if duplicate_count:
                raise ValueError(f"{spec.name} delta contains duplicate primary keys")

            if current_parquet is None:
                current_sql = (
                    f"select {columns}, 0 as _source_priority "
                    "from read_parquet(?) where false"
                )
                parameters = [str(delta_parquet), str(delta_parquet)]
            else:
                current_sql = f"select {columns}, 0 as _source_priority from read_parquet(?)"
                parameters = [str(current_parquet), str(delta_parquet)]

            merge_query = f"""
                create temp table merged as
                select {columns}
                from (
                    select *, row_number() over (
                        partition by {keys}
                        order by _source_priority desc
                    ) as _row_number
                    from (
                        {current_sql}
                        union all
                        select {columns}, 1 as _source_priority
                        from read_parquet(?)
                    )
                )
                where _row_number = 1
                """
            connection.execute(
                merge_query,
                parameters,
            )
            row_count = connection.execute("select count(*) from merged").fetchone()[0]
            min_date, max_date = self._date_range(connection, spec)
            parquet_query = (
                f"copy (select {columns} from merged order by {keys}) "
                "to ? (format parquet, compression zstd)"
            )
            connection.execute(
                parquet_query,
                [str(parquet_path)],
            )
            csv_query = (
                f"copy (select {columns} from merged order by {keys}) "
                "to ? (format csv, header true, null '')"
            )
            connection.execute(
                csv_query,
                [str(csv_path)],
            )
        finally:
            connection.close()

        return ExportedTable(
            name=spec.name,
            parquet_path=parquet_path,
            csv_path=csv_path,
            row_count=row_count,
            parquet_bytes=parquet_path.stat().st_size,
            parquet_sha256=_sha256(parquet_path),
            csv_bytes=csv_path.stat().st_size,
            csv_sha256=_sha256(csv_path),
            min_date=min_date,
            max_date=max_date,
        )

    @staticmethod
    def _date_range(
        connection: duckdb.DuckDBPyConnection,
        spec: TableSpec,
    ) -> tuple[str | None, str | None]:
        if spec.date_column is None:
            return None, None
        column = _quote_identifier(spec.date_column)
        date_range_query = (
            f"select min({column})::varchar, max({column})::varchar from merged"
        )
        row = connection.execute(date_range_query).fetchone()
        return row[0], row[1]


def _quote_identifier(value: str) -> str:
    if SQL_IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return f'"{value}"'


def _validate_spec_identifiers(spec: TableSpec) -> None:
    identifiers = (
        spec.name,
        *spec.columns,
        *spec.primary_key,
        *((spec.date_column,) if spec.date_column is not None else ()),
    )
    for identifier in identifiers:
        _quote_identifier(identifier)


def _arrow_schema(connection, spec: TableSpec) -> pa.Schema:
    database_columns = {
        column["name"]: column["type"]
        for column in inspect(connection).get_columns(spec.name, schema="analyst")
    }
    return pa.schema(
        [
            pa.field(column, _arrow_type(database_columns[column]))
            for column in spec.columns
        ]
    )


def _arrow_type(column_type) -> pa.DataType:
    if isinstance(column_type, Boolean):
        return pa.bool_()
    # Tuple syntax is intentional for compatibility with review/security tooling.
    if isinstance(column_type, (SmallInteger, Integer, BigInteger)):  # noqa: UP038
        return pa.int64()
    if isinstance(column_type, (Float, Numeric)):  # noqa: UP038
        return pa.float64()
    if isinstance(column_type, DateTime):
        return pa.timestamp("us", tz="UTC" if column_type.timezone else None)
    if isinstance(column_type, Date):
        return pa.date32()
    if isinstance(column_type, (String, Text)):  # noqa: UP038
        return pa.string()
    raise TypeError(f"Unsupported warehouse column type: {type(column_type).__name__}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
