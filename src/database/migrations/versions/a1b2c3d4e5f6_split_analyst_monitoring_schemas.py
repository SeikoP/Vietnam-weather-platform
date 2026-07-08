"""Split public into analyst and monitoring schemas

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-07-08
"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create schemas
    # ------------------------------------------------------------------
    op.execute("create schema if not exists analyst")
    op.execute("create schema if not exists monitoring")

    # ------------------------------------------------------------------
    # analyst.dim_district
    # ------------------------------------------------------------------
    op.execute(
        """
        create table analyst.dim_district (
            district_id integer primary key,
            district_name varchar(120) not null unique,
            latitude double precision not null check (latitude between 20.5 and 21.5),
            longitude double precision not null check (longitude between 105.2 and 106.1)
        )
    """
    )

    # ------------------------------------------------------------------
    # analyst.dim_date
    # ------------------------------------------------------------------
    op.execute(
        """
        create table analyst.dim_date (
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

    # ------------------------------------------------------------------
    # analyst.fact_weather_daily
    # ------------------------------------------------------------------
    op.execute(
        """
        create table analyst.fact_weather_daily (
            weather_daily_id bigserial primary key,
            district_id integer not null references analyst.dim_district(district_id),
            date_key integer not null references analyst.dim_date(date_key),
            observed_date date not null,
            temperature_2m_mean double precision,
            temperature_2m_max double precision,
            temperature_2m_min double precision,
            apparent_temperature_mean double precision,
            relative_humidity_2m_mean double precision,
            dew_point_2m_mean double precision,
            surface_pressure_mean double precision,
            vapour_pressure_deficit_mean double precision,
            wind_speed_10m_max double precision,
            wind_gusts_10m_max double precision,
            cloud_cover_mean double precision,
            shortwave_radiation_sum double precision,
            precipitation_sum double precision,
            rain_sum double precision,
            weather_code smallint,
            soil_moisture_0_to_7cm_mean double precision,
            source varchar(50) not null default 'open-meteo',
            etl_run_id bigint,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            constraint uq_fact_weather_daily_district_date unique (district_id, date_key)
        )
    """
    )

    # ------------------------------------------------------------------
    # analyst.fact_weather_hourly
    # ------------------------------------------------------------------
    op.execute(
        """
        create table analyst.fact_weather_hourly (
            weather_hourly_id bigserial primary key,
            district_id integer not null references analyst.dim_district(district_id),
            date_key integer not null references analyst.dim_date(date_key),
            observed_date date not null,
            observed_at timestamptz not null,
            temperature_2m double precision,
            apparent_temperature double precision,
            relative_humidity_2m double precision,
            dew_point_2m double precision,
            surface_pressure double precision,
            vapour_pressure_deficit double precision,
            wind_speed_10m double precision,
            wind_gusts_10m double precision,
            cloud_cover double precision,
            shortwave_radiation double precision,
            precipitation double precision,
            rain double precision,
            weather_code smallint,
            soil_moisture_0_to_7cm double precision,
            source varchar(50) not null default 'open-meteo',
            etl_run_id bigint,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            constraint uq_fact_weather_hourly_district_time unique (district_id, observed_at)
        )
    """
    )

    # ------------------------------------------------------------------
    # analyst.fact_aqi_hourly
    # ------------------------------------------------------------------
    op.execute(
        """
        create table analyst.fact_aqi_hourly (
            aqi_hourly_id bigserial primary key,
            district_id integer not null references analyst.dim_district(district_id),
            date_key integer not null references analyst.dim_date(date_key),
            observed_date date not null,
            observed_at timestamptz not null,
            european_aqi double precision,
            us_aqi double precision,
            pm10 double precision,
            pm2_5 double precision,
            carbon_monoxide double precision,
            carbon_dioxide double precision,
            nitrogen_dioxide double precision,
            sulphur_dioxide double precision,
            ozone double precision,
            aerosol_optical_depth double precision,
            dust double precision,
            uv_index double precision,
            uv_index_clear_sky double precision,
            ammonia double precision,
            methane double precision,
            source varchar(50) not null default 'open-meteo-air-quality',
            etl_run_id bigint,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now(),
            constraint uq_fact_aqi_hourly_district_time unique (district_id, observed_at)
        )
    """
    )

    # ------------------------------------------------------------------
    # monitoring.etl_runs
    # ------------------------------------------------------------------
    op.execute(
        """
        create table monitoring.etl_runs (
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
        create table monitoring.etl_logs (
            etl_log_id bigserial primary key,
            etl_run_id bigint references monitoring.etl_runs(etl_run_id),
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
        create table monitoring.validation_errors (
            validation_error_id bigserial primary key,
            etl_run_id bigint references monitoring.etl_runs(etl_run_id),
            source_table varchar(120) not null,
            district_id integer,
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
        create table monitoring.api_requests (
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

    # ------------------------------------------------------------------
    # Indexes — analyst
    # ------------------------------------------------------------------
    op.execute(
        "create index if not exists ix_fact_weather_daily_date_key "
        "on analyst.fact_weather_daily(date_key)"
    )
    op.execute(
        "create index if not exists ix_fact_weather_daily_district_id "
        "on analyst.fact_weather_daily(district_id)"
    )
    op.execute(
        "create index if not exists ix_fact_weather_hourly_observed_at "
        "on analyst.fact_weather_hourly(observed_at)"
    )
    op.execute(
        "create index if not exists ix_fact_weather_hourly_district_id "
        "on analyst.fact_weather_hourly(district_id)"
    )
    op.execute(
        "create index if not exists ix_fact_aqi_hourly_observed_at "
        "on analyst.fact_aqi_hourly(observed_at)"
    )
    op.execute(
        "create index if not exists ix_fact_aqi_hourly_district_id "
        "on analyst.fact_aqi_hourly(district_id)"
    )

    # Indexes — monitoring
    op.execute(
        "create index if not exists ix_etl_logs_etl_run_id on monitoring.etl_logs(etl_run_id)"
    )
    op.execute(
        "create index if not exists ix_validation_errors_etl_run_id "
        "on monitoring.validation_errors(etl_run_id)"
    )


def downgrade() -> None:
    op.execute("drop schema if exists analyst cascade")
    op.execute("drop schema if exists monitoring cascade")
