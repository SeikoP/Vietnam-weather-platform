from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DimDate(Base):
    __tablename__ = "dim_date"
    __table_args__ = {"schema": "warehouse"}

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    is_weekend: Mapped[bool] = mapped_column(nullable=False)


class DimProvince(Base):
    __tablename__ = "dim_province"
    __table_args__ = (
        CheckConstraint("latitude between 8.0 and 24.5", name="ck_dim_province_latitude_vn"),
        CheckConstraint("longitude between 102.0 and 110.5", name="ck_dim_province_longitude_vn"),
        {"schema": "warehouse"},
    )

    province_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    province_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    daily_weather: Mapped[list["FactWeatherDaily"]] = relationship(back_populates="province")


class FactWeatherDaily(Base):
    __tablename__ = "fact_weather_daily"
    __table_args__ = (
        UniqueConstraint("province_id", "date_key", name="uq_fact_weather_daily_province_date"),
        {"schema": "warehouse"},
    )

    weather_daily_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    province_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.dim_province.province_id"),
        nullable=False,
    )
    date_key: Mapped[int] = mapped_column(ForeignKey("warehouse.dim_date.date_key"), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    temperature_2m_mean: Mapped[float | None] = mapped_column(Float)
    temperature_2m_max: Mapped[float | None] = mapped_column(Float)
    temperature_2m_min: Mapped[float | None] = mapped_column(Float)
    relative_humidity_2m_mean: Mapped[float | None] = mapped_column(Float)
    surface_pressure_mean: Mapped[float | None] = mapped_column(Float)
    wind_speed_10m_max: Mapped[float | None] = mapped_column(Float)
    cloud_cover_mean: Mapped[float | None] = mapped_column(Float)
    shortwave_radiation_sum: Mapped[float | None] = mapped_column(Float)
    precipitation_sum: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(50), default="open-meteo", nullable=False)
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    province: Mapped[DimProvince] = relationship(back_populates="daily_weather")


class FactWeatherHourly(Base):
    __tablename__ = "fact_weather_hourly"
    __table_args__ = (
        UniqueConstraint("province_id", "observed_at", name="uq_fact_weather_hourly_province_time"),
        {"schema": "warehouse"},
    )

    weather_hourly_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    province_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.dim_province.province_id"),
        nullable=False,
    )
    date_key: Mapped[int] = mapped_column(ForeignKey("warehouse.dim_date.date_key"), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature_2m: Mapped[float | None] = mapped_column(Float)
    relative_humidity_2m: Mapped[float | None] = mapped_column(Float)
    surface_pressure: Mapped[float | None] = mapped_column(Float)
    wind_speed_10m: Mapped[float | None] = mapped_column(Float)
    cloud_cover: Mapped[float | None] = mapped_column(Float)
    shortwave_radiation: Mapped[float | None] = mapped_column(Float)
    precipitation: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(50), default="open-meteo", nullable=False)
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class RawWeatherApiResponse(Base):
    __tablename__ = "weather_api_responses"
    __table_args__ = {"schema": "raw"}

    raw_response_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    source_api: Mapped[str] = mapped_column(String(80), nullable=False)
    province_id: Mapped[int] = mapped_column(Integer, nullable=False)
    request_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StagingWeatherDaily(Base):
    __tablename__ = "weather_daily"
    __table_args__ = (
        UniqueConstraint("province_id", "observed_date", name="uq_staging_weather_daily"),
        {"schema": "staging"},
    )

    staging_weather_daily_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    province_id: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_valid: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StagingWeatherHourly(Base):
    __tablename__ = "weather_hourly"
    __table_args__ = (
        UniqueConstraint("province_id", "observed_at", name="uq_staging_weather_hourly"),
        {"schema": "staging"},
    )

    staging_weather_hourly_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    province_id: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_valid: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EtlRun(Base):
    __tablename__ = "etl_runs"
    __table_args__ = {"schema": "monitoring"}

    etl_run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)


class ValidationError(Base):
    __tablename__ = "validation_errors"
    __table_args__ = {"schema": "monitoring"}

    validation_error_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    source_table: Mapped[str] = mapped_column(String(120), nullable=False)
    province_id: Mapped[int | None] = mapped_column(Integer)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    invalid_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EtlLog(Base):
    __tablename__ = "etl_logs"
    __table_args__ = {"schema": "monitoring"}

    etl_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    event_name: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiRequest(Base):
    __tablename__ = "api_requests"
    __table_args__ = {"schema": "monitoring"}

    api_request_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    request_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    context: Mapped[dict | None] = mapped_column(JSONB)
