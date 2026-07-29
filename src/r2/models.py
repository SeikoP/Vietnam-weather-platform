from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class TableSpec:
    name: str
    primary_key: tuple[str, ...]
    columns: tuple[str, ...]
    date_column: str | None
    date_via_hour: bool = False


TABLE_SPECS = (
    TableSpec(
        "dim_district",
        ("district_id",),
        ("district_id", "district_name", "latitude", "longitude"),
        None,
    ),
    TableSpec(
        "dim_date",
        ("date_key",),
        ("date_key", "date", "year", "quarter", "month", "day", "day_of_week", "is_weekend"),
        "date",
    ),
    TableSpec(
        "dim_hour",
        ("hour_key",),
        ("hour_key", "date_key", "observed_date", "observed_at"),
        "observed_date",
    ),
    TableSpec(
        "fact_weather_daily",
        ("district_id", "date_key"),
        (
            "district_id",
            "date_key",
            "observed_date",
            "temperature_2m_mean",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_mean",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "shortwave_radiation_sum",
            "precipitation_sum",
            "rain_sum",
            "weather_code",
        ),
        "observed_date",
    ),
    TableSpec(
        "fact_weather_hourly",
        ("district_id", "hour_key"),
        (
            "district_id",
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "dew_point_2m",
            "surface_pressure",
            "vapour_pressure_deficit",
            "wind_speed_10m",
            "wind_gusts_10m",
            "cloud_cover",
            "shortwave_radiation",
            "precipitation",
            "rain",
            "weather_code",
            "soil_moisture_0_to_7cm",
            "hour_key",
        ),
        None,
        True,
    ),
    TableSpec(
        "fact_aqi_hourly",
        ("district_id", "hour_key"),
        (
            "district_id",
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "carbon_dioxide",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "aerosol_optical_depth",
            "dust",
            "uv_index",
            "uv_index_clear_sky",
            "methane",
            "hour_key",
        ),
        None,
        True,
    ),
)


@dataclass(frozen=True)
class TableManifest:
    name: str
    row_count: int
    parquet_key: str
    parquet_bytes: int
    parquet_sha256: str
    csv_key: str
    csv_bytes: int
    csv_sha256: str
    min_date: str | None
    max_date: str | None


@dataclass(frozen=True)
class ReleaseManifest:
    schema_version: int
    release_id: str
    source: str
    generated_at_utc: str
    generated_at_vietnam: str
    tables: dict[str, TableManifest]

    @classmethod
    def create(
        cls,
        *,
        release_id: str,
        source: str,
        generated_at: datetime,
        tables: dict[str, TableManifest],
    ) -> ReleaseManifest:
        utc_value = generated_at.astimezone(UTC)
        return cls(
            schema_version=1,
            release_id=release_id,
            source=source,
            generated_at_utc=utc_value.isoformat(),
            generated_at_vietnam=utc_value.astimezone(VIETNAM_TZ).isoformat(),
            tables=tables,
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, value: str | bytes) -> ReleaseManifest:
        payload = json.loads(value)
        payload["tables"] = {
            name: TableManifest(**table) for name, table in payload["tables"].items()
        }
        return cls(**payload)


@dataclass(frozen=True)
class LatestPointer:
    schema_version: int
    release_id: str
    manifest_key: str
    published_at_utc: str
    published_at_vietnam: str

    @classmethod
    def create(cls, *, release_id: str, generated_at: datetime) -> LatestPointer:
        utc_value = generated_at.astimezone(UTC)
        return cls(
            schema_version=1,
            release_id=release_id,
            manifest_key=f"v1/releases/{release_id}/manifest.json",
            published_at_utc=utc_value.isoformat(),
            published_at_vietnam=utc_value.astimezone(VIETNAM_TZ).isoformat(),
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, value: str | bytes) -> LatestPointer:
        return cls(**json.loads(value))
