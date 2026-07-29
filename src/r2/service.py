from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import Engine

from src.r2.exporter import ExportedTable, SnapshotMerger, WarehouseExporter
from src.r2.models import TABLE_SPECS, ReleaseManifest
from src.r2.publisher import R2Publisher

FACT_TABLE_NAMES = (
    "fact_weather_daily",
    "fact_weather_hourly",
    "fact_aqi_hourly",
)
FULL_REFRESH_DIMENSIONS = {"dim_district", "dim_date"}


def manifest_watermark(manifest: ReleaseManifest) -> date:
    values = []
    for name in FACT_TABLE_NAMES:
        table = manifest.tables.get(name)
        if table is None or table.max_date is None:
            raise ValueError(f"R2 manifest is missing watermark for {name}")
        values.append(table.max_date)
    if len(set(values)) != 1:
        raise ValueError("R2 fact table watermarks differ")
    return date.fromisoformat(values[0])


def resolve_publish_range(
    manifest: ReleaseManifest,
    *,
    target_date: date,
    start_date: date | None,
    end_date: date | None,
    force_republish: bool,
) -> tuple[date, date] | None:
    if start_date is not None or end_date is not None:
        if not force_republish:
            raise ValueError("bounded repair requires --force-republish")
        if start_date is None or end_date is None:
            raise ValueError("repair requires both --start-date and --end-date")
        if start_date > end_date:
            raise ValueError("start_date must not be after end_date")
        return start_date, end_date

    if force_republish:
        raise ValueError("--force-republish requires a bounded date range")
    watermark = manifest_watermark(manifest)
    if target_date <= watermark:
        return None
    return watermark + timedelta(days=1), target_date


class WarehouseReleaseService:
    def __init__(
        self,
        engine: Engine,
        publisher: R2Publisher,
        *,
        batch_size: int = 5_000,
    ) -> None:
        self.engine = engine
        self.publisher = publisher
        self.exporter = WarehouseExporter(batch_size=batch_size)
        self.merger = SnapshotMerger()

    def bootstrap(self) -> ReleaseManifest:
        return self._build_release(
            source="local-postgres",
            current_manifest=None,
            expected_latest_etag=None,
            start_date=None,
            end_date=None,
        )

    def publish_incremental(
        self,
        *,
        target_date: date,
        start_date: date | None = None,
        end_date: date | None = None,
        force_republish: bool = False,
    ) -> ReleaseManifest | None:
        _, current_manifest, etag = self.publisher.read_latest()
        publish_range = resolve_publish_range(
            current_manifest,
            target_date=target_date,
            start_date=start_date,
            end_date=end_date,
            force_republish=force_republish,
        )
        if publish_range is None:
            return None
        return self._build_release(
            source="supabase",
            current_manifest=current_manifest,
            expected_latest_etag=etag,
            start_date=publish_range[0],
            end_date=publish_range[1],
        )

    def _build_release(
        self,
        *,
        source: str,
        current_manifest: ReleaseManifest | None,
        expected_latest_etag: str | None,
        start_date: date | None,
        end_date: date | None,
    ) -> ReleaseManifest:
        generated_at = datetime.now(UTC)
        release_id = generated_at.strftime("%Y%m%dT%H%M%SZ")
        with TemporaryDirectory(prefix="vwdp-r2-") as temporary:
            root = Path(temporary)
            current_directory = root / "current"
            delta_directory = root / "delta"
            output_directory = root / "release"
            exported: dict[str, ExportedTable] = {}

            for spec in TABLE_SPECS:
                current_path: Path | None = None
                if current_manifest is not None:
                    current_path = current_directory / f"{spec.name}.parquet"
                    self.publisher.download_parquet(
                        current_manifest.tables[spec.name],
                        current_path,
                    )

                delta_path = delta_directory / f"{spec.name}.parquet"
                use_date_filter = (
                    start_date is not None
                    and end_date is not None
                    and spec.name not in FULL_REFRESH_DIMENSIONS
                )
                self.exporter.export_spec(
                    self.engine,
                    spec,
                    delta_path,
                    start_date=start_date if use_date_filter else None,
                    end_date=end_date if use_date_filter else None,
                )
                exported[spec.name] = self.merger.merge_table(
                    spec,
                    current_path,
                    delta_path,
                    output_directory,
                )

            hour_dates = exported["dim_hour"]
            for name in ("fact_weather_hourly", "fact_aqi_hourly"):
                exported[name] = replace(
                    exported[name],
                    min_date=hour_dates.min_date,
                    max_date=hour_dates.max_date,
                )
            self._validate_release(exported, expected_end_date=end_date)
            return self.publisher.publish_release(
                release_id=release_id,
                source=source,
                generated_at=generated_at,
                tables=exported,
                expected_latest_etag=expected_latest_etag,
            )

    @staticmethod
    def _validate_release(
        tables: dict[str, ExportedTable],
        *,
        expected_end_date: date | None,
    ) -> None:
        expected_names = {spec.name for spec in TABLE_SPECS}
        if set(tables) != expected_names:
            raise ValueError("R2 release does not contain all analyst tables")
        if any(table.row_count <= 0 for table in tables.values()):
            raise ValueError("R2 release contains an empty analyst table")
        max_dates = {tables[name].max_date for name in FACT_TABLE_NAMES}
        if len(max_dates) != 1 or None in max_dates:
            raise ValueError("R2 fact table max dates differ")
        if expected_end_date is not None:
            current_max = date.fromisoformat(next(iter(max_dates)))
            if current_max < expected_end_date:
                raise ValueError("Supabase does not contain the requested publish end date")

