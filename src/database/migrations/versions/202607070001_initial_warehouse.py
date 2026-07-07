"""initial warehouse

Revision ID: 202607070001
Revises:
Create Date: 2026-07-07
"""

from alembic import op

revision = "202607070001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create schema if not exists raw")
    op.execute("create schema if not exists staging")
    op.execute("create schema if not exists warehouse")
    op.execute("create schema if not exists analytics")
    op.execute("create schema if not exists monitoring")

    op.execute(
        """
        create table if not exists raw.weather_api_responses (
            raw_response_id bigserial primary key,
            etl_run_id bigint,
            source_api varchar(80) not null,
            province_id integer not null,
            request_url text not null,
            request_params jsonb not null,
            response_payload jsonb not null,
            status_code integer not null,
            latency_ms double precision not null,
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        """
        create table if not exists staging.weather_daily (
            staging_weather_daily_id bigserial primary key,
            etl_run_id bigint,
            province_id integer not null,
            observed_date date not null,
            payload jsonb not null,
            is_valid boolean not null default true,
            created_at timestamptz not null default now(),
            constraint uq_staging_weather_daily unique (province_id, observed_date)
        )
        """
    )
    op.execute(
        """
        create table if not exists staging.weather_hourly (
            staging_weather_hourly_id bigserial primary key,
            etl_run_id bigint,
            province_id integer not null,
            observed_at timestamptz not null,
            payload jsonb not null,
            is_valid boolean not null default true,
            created_at timestamptz not null default now(),
            constraint uq_staging_weather_hourly unique (province_id, observed_at)
        )
        """
    )
    op.execute(
        """
        create table if not exists warehouse.dim_date (
            date_key integer primary key,
            date date not null unique,
            year integer not null,
            quarter integer not null,
            month integer not null,
            day integer not null,
            day_of_week integer not null,
            is_weekend boolean not null
        )
        """
    )
    op.execute(
        """
        create table if not exists warehouse.dim_province (
            province_id integer primary key,
            province_name varchar(120) not null unique,
            latitude double precision not null check (latitude between 8.0 and 24.5),
            longitude double precision not null check (longitude between 102.0 and 110.5)
        )
        """
    )
    op.execute(
        """
        create table if not exists warehouse.fact_weather_daily (
            weather_daily_id bigserial primary key,
            province_id integer not null references warehouse.dim_province(province_id),
            date_key integer not null references warehouse.dim_date(date_key),
            observed_date date not null,
            temperature_2m_mean double precision,
            temperature_2m_max double precision,
            temperature_2m_min double precision,
            relative_humidity_2m_mean double precision,
            surface_pressure_mean double precision,
            wind_speed_10m_max double precision,
            cloud_cover_mean double precision,
            shortwave_radiation_sum double precision,
            precipitation_sum double precision,
            source varchar(50) not null default 'open-meteo',
            etl_run_id bigint,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            constraint uq_fact_weather_daily_province_date unique (province_id, date_key)
        )
        """
    )
    op.execute(
        """
        create table if not exists warehouse.fact_weather_hourly (
            weather_hourly_id bigserial primary key,
            province_id integer not null references warehouse.dim_province(province_id),
            date_key integer not null references warehouse.dim_date(date_key),
            observed_date date not null,
            observed_at timestamptz not null,
            temperature_2m double precision,
            relative_humidity_2m double precision,
            surface_pressure double precision,
            wind_speed_10m double precision,
            cloud_cover double precision,
            shortwave_radiation double precision,
            precipitation double precision,
            source varchar(50) not null default 'open-meteo',
            etl_run_id bigint,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            constraint uq_fact_weather_hourly_province_time unique (province_id, observed_at)
        )
        """
    )
    op.execute(
        """
        create table if not exists monitoring.etl_runs (
            etl_run_id bigserial primary key,
            run_type varchar(40) not null,
            status varchar(30) not null,
            started_at timestamptz not null,
            finished_at timestamptz,
            rows_inserted integer not null default 0,
            rows_updated integer not null default 0,
            rows_skipped integer not null default 0,
            error_summary text
        )
        """
    )
    op.execute(
        """
        create table if not exists monitoring.etl_logs (
            etl_log_id bigserial primary key,
            etl_run_id bigint,
            level varchar(20) not null,
            event_name varchar(120) not null,
            message text not null,
            context jsonb,
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        """
        create table if not exists monitoring.validation_errors (
            validation_error_id bigserial primary key,
            etl_run_id bigint,
            source_table varchar(120) not null,
            province_id integer,
            field_name varchar(120) not null,
            invalid_value text,
            reason text not null,
            severity varchar(20) not null,
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        """
        create table if not exists monitoring.api_requests (
            api_request_id bigserial primary key,
            endpoint varchar(200) not null,
            method varchar(20) not null,
            status_code integer not null,
            latency_ms double precision not null,
            request_time timestamptz not null default now(),
            context jsonb
        )
        """
    )
    op.execute(
        """
        create index if not exists ix_fact_weather_daily_date_key
        on warehouse.fact_weather_daily(date_key)
        """
    )
    op.execute(
        """
        create index if not exists ix_fact_weather_daily_province_id
        on warehouse.fact_weather_daily(province_id)
        """
    )
    op.execute(
        """
        create index if not exists ix_fact_weather_hourly_observed_at
        on warehouse.fact_weather_hourly(observed_at)
        """
    )
    op.execute(
        """
        create index if not exists ix_fact_weather_hourly_province_id
        on warehouse.fact_weather_hourly(province_id)
        """
    )
    op.execute(
        """
        create index if not exists ix_raw_weather_api_responses_etl_run_id
        on raw.weather_api_responses(etl_run_id)
        """
    )
    op.execute(
        "create index if not exists ix_etl_logs_etl_run_id on monitoring.etl_logs(etl_run_id)"
    )
    op.execute(
        """
        create index if not exists ix_validation_errors_etl_run_id
        on monitoring.validation_errors(etl_run_id)
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists monitoring.api_requests")
    op.execute("drop table if exists monitoring.validation_errors")
    op.execute("drop table if exists monitoring.etl_logs")
    op.execute("drop table if exists monitoring.etl_runs")
    op.execute("drop table if exists warehouse.fact_weather_hourly")
    op.execute("drop table if exists warehouse.fact_weather_daily")
    op.execute("drop table if exists warehouse.dim_province")
    op.execute("drop table if exists warehouse.dim_date")
    op.execute("drop table if exists staging.weather_hourly")
    op.execute("drop table if exists staging.weather_daily")
    op.execute("drop table if exists raw.weather_api_responses")
