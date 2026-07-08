"""Optimize fact table storage

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-08
"""

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


WEATHER_DAILY_REAL_COLUMNS = [
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_mean",
    "relative_humidity_2m_mean",
    "dew_point_2m_mean",
    "surface_pressure_mean",
    "vapour_pressure_deficit_mean",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "cloud_cover_mean",
    "shortwave_radiation_sum",
    "precipitation_sum",
    "rain_sum",
    "soil_moisture_0_to_7cm_mean",
]

WEATHER_HOURLY_REAL_COLUMNS = [
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
    "soil_moisture_0_to_7cm",
]

AQI_HOURLY_REAL_COLUMNS = [
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
]


def upgrade() -> None:
    _drop_legacy_public_tables()

    op.execute("drop index if exists analyst.ix_fact_weather_daily_district_id")
    op.execute("alter table analyst.fact_weather_daily drop constraint fact_weather_daily_pkey")
    op.execute(
        "alter table analyst.fact_weather_daily "
        "drop constraint uq_fact_weather_daily_district_date"
    )
    op.execute("alter table analyst.fact_weather_daily drop column weather_daily_id")
    _alter_columns_type("analyst.fact_weather_daily", WEATHER_DAILY_REAL_COLUMNS, "real")
    op.execute(
        "alter table analyst.fact_weather_daily "
        "add constraint fact_weather_daily_pkey primary key (district_id, date_key)"
    )

    op.execute("drop index if exists analyst.ix_fact_weather_hourly_district_id")
    op.execute("alter table analyst.fact_weather_hourly drop constraint fact_weather_hourly_pkey")
    op.execute(
        "alter table analyst.fact_weather_hourly "
        "drop constraint uq_fact_weather_hourly_district_time"
    )
    op.execute("alter table analyst.fact_weather_hourly drop column weather_hourly_id")
    _alter_columns_type("analyst.fact_weather_hourly", WEATHER_HOURLY_REAL_COLUMNS, "real")
    op.execute(
        "alter table analyst.fact_weather_hourly "
        "add constraint fact_weather_hourly_pkey primary key (district_id, observed_at)"
    )

    op.execute("drop index if exists analyst.ix_fact_aqi_hourly_district_id")
    op.execute("alter table analyst.fact_aqi_hourly drop constraint fact_aqi_hourly_pkey")
    op.execute(
        "alter table analyst.fact_aqi_hourly drop constraint uq_fact_aqi_hourly_district_time"
    )
    op.execute("alter table analyst.fact_aqi_hourly drop column aqi_hourly_id")
    _alter_columns_type("analyst.fact_aqi_hourly", AQI_HOURLY_REAL_COLUMNS, "real")
    op.execute(
        "alter table analyst.fact_aqi_hourly "
        "add constraint fact_aqi_hourly_pkey primary key (district_id, observed_at)"
    )


def downgrade() -> None:
    op.execute("alter table analyst.fact_aqi_hourly drop constraint fact_aqi_hourly_pkey")
    _alter_columns_type("analyst.fact_aqi_hourly", AQI_HOURLY_REAL_COLUMNS, "double precision")
    op.execute("alter table analyst.fact_aqi_hourly add column aqi_hourly_id bigserial")
    op.execute(
        "alter table analyst.fact_aqi_hourly "
        "add constraint fact_aqi_hourly_pkey primary key (aqi_hourly_id)"
    )
    op.execute(
        "alter table analyst.fact_aqi_hourly "
        "add constraint uq_fact_aqi_hourly_district_time unique (district_id, observed_at)"
    )
    op.execute(
        "create index if not exists ix_fact_aqi_hourly_district_id "
        "on analyst.fact_aqi_hourly(district_id)"
    )

    op.execute("alter table analyst.fact_weather_hourly drop constraint fact_weather_hourly_pkey")
    _alter_columns_type(
        "analyst.fact_weather_hourly", WEATHER_HOURLY_REAL_COLUMNS, "double precision"
    )
    op.execute("alter table analyst.fact_weather_hourly add column weather_hourly_id bigserial")
    op.execute(
        "alter table analyst.fact_weather_hourly "
        "add constraint fact_weather_hourly_pkey primary key (weather_hourly_id)"
    )
    op.execute(
        "alter table analyst.fact_weather_hourly "
        "add constraint uq_fact_weather_hourly_district_time unique (district_id, observed_at)"
    )
    op.execute(
        "create index if not exists ix_fact_weather_hourly_district_id "
        "on analyst.fact_weather_hourly(district_id)"
    )

    op.execute("alter table analyst.fact_weather_daily drop constraint fact_weather_daily_pkey")
    _alter_columns_type(
        "analyst.fact_weather_daily", WEATHER_DAILY_REAL_COLUMNS, "double precision"
    )
    op.execute("alter table analyst.fact_weather_daily add column weather_daily_id bigserial")
    op.execute(
        "alter table analyst.fact_weather_daily "
        "add constraint fact_weather_daily_pkey primary key (weather_daily_id)"
    )
    op.execute(
        "alter table analyst.fact_weather_daily "
        "add constraint uq_fact_weather_daily_district_date unique (district_id, date_key)"
    )
    op.execute(
        "create index if not exists ix_fact_weather_daily_district_id "
        "on analyst.fact_weather_daily(district_id)"
    )


def _alter_columns_type(table_name: str, columns: list[str], target_type: str) -> None:
    clauses = [
        f"alter column {column} type {target_type} using {column}::{target_type}"
        for column in columns
    ]
    op.execute(f"alter table {table_name} {', '.join(clauses)}")


def _drop_legacy_public_tables() -> None:
    for table_name in [
        "fact_weather_hourly",
        "fact_aqi_hourly",
        "fact_weather_daily",
        "etl_runs",
        "etl_logs",
        "validation_errors",
        "api_requests",
    ]:
        op.execute(f"drop table if exists public.{table_name} cascade")
