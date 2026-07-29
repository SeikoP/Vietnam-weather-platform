from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.r2.config import R2Config
from src.r2.models import (
    TABLE_SPECS,
    LatestPointer,
    ReleaseManifest,
    TableManifest,
)


def test_table_specs_match_analyst_schema_primary_keys() -> None:
    assert {spec.name: spec.primary_key for spec in TABLE_SPECS} == {
        "dim_district": ("district_id",),
        "dim_date": ("date_key",),
        "dim_hour": ("hour_key",),
        "fact_weather_daily": ("district_id", "date_key"),
        "fact_weather_hourly": ("district_id", "hour_key"),
        "fact_aqi_hourly": ("district_id", "hour_key"),
    }

    assert next(spec for spec in TABLE_SPECS if spec.name == "dim_hour").columns == (
        "hour_key",
        "date_key",
        "observed_date",
        "observed_at",
    )


def test_release_manifest_round_trip_preserves_vietnam_timestamp() -> None:
    generated_at = datetime(2026, 7, 29, 18, 15, tzinfo=UTC)
    table = TableManifest(
        name="fact_weather_daily",
        row_count=34_616,
        parquet_key="v1/releases/20260729T181500Z/analyst/fact_weather_daily.parquet",
        parquet_bytes=123,
        parquet_sha256="a" * 64,
        csv_key="v1/releases/20260729T181500Z/analyst/fact_weather_daily.csv",
        csv_bytes=456,
        csv_sha256="b" * 64,
        min_date="2023-06-01",
        max_date="2026-07-29",
    )
    manifest = ReleaseManifest.create(
        release_id="20260729T181500Z",
        source="local-postgres",
        generated_at=generated_at,
        tables={"fact_weather_daily": table},
    )

    payload = json.loads(manifest.to_json())
    restored = ReleaseManifest.from_json(manifest.to_json())

    assert payload["generated_at_utc"] == "2026-07-29T18:15:00+00:00"
    assert payload["generated_at_vietnam"] == "2026-07-30T01:15:00+07:00"
    assert restored == manifest


def test_latest_pointer_uses_release_manifest_key() -> None:
    pointer = LatestPointer.create(
        release_id="20260729T181500Z",
        generated_at=datetime(2026, 7, 29, 18, 15, tzinfo=UTC),
    )

    assert pointer.manifest_key == "v1/releases/20260729T181500Z/manifest.json"
    assert LatestPointer.from_json(pointer.to_json()) == pointer


def test_r2_config_requires_all_credential_names_without_exposing_values() -> None:
    with pytest.raises(ValueError, match="R2_BUCKET_NAME"):
        R2Config.from_env(
            {
                "R2_ACCOUNT_ID": "account",
                "R2_ACCESS_KEY_ID": "access",
                "R2_SECRET_ACCESS_KEY": "secret",
            }
        )


def test_r2_config_builds_s3_endpoint() -> None:
    config = R2Config.from_env(
        {
            "R2_ACCOUNT_ID": "account",
            "R2_ACCESS_KEY_ID": "access",
            "R2_SECRET_ACCESS_KEY": "secret",
            "R2_BUCKET_NAME": "weather",
            "R2_PUBLIC_BASE_URL": "https://data.example.com/",
        }
    )

    assert config.endpoint_url == "https://account.r2.cloudflarestorage.com"
    assert config.public_base_url == "https://data.example.com"
    assert "secret_access_key='secret'" not in repr(config)


def test_r2_config_accepts_existing_legacy_access_key_names() -> None:
    config = R2Config.from_env(
        {
            "R2_ACCOUNT_ID": "account",
            "ACCESS_KEY_ID": "legacy-access",
            "SECRET_ACCESS_KEY": "legacy-secret",
            "R2_BUCKET_NAME": "vwdp",
        }
    )

    assert config.access_key_id == "legacy-access"
    assert config.secret_access_key == "legacy-secret"
