from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()

# ---------------------------------------------------------------------------
# analyst schema — dimensions
# ---------------------------------------------------------------------------


class DimDate(Base):
    __tablename__ = "dim_date"
    __table_args__ = {"schema": "analyst"}

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False)


class DimDistrict(Base):
    __tablename__ = "dim_district"
    __table_args__ = (
        CheckConstraint("latitude between 20.5 and 21.5", name="ck_dim_district_latitude_hn"),
        CheckConstraint("longitude between 105.2 and 106.1", name="ck_dim_district_longitude_hn"),
        {"schema": "analyst"},
    )

    district_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    daily_weather: Mapped[list["FactWeatherDaily"]] = relationship(back_populates="district")


# ---------------------------------------------------------------------------
# analyst schema — fact tables
# ---------------------------------------------------------------------------


class FactWeatherDaily(Base):
    __tablename__ = "fact_weather_daily"
    __table_args__ = (
        UniqueConstraint("district_id", "date_key", name="uq_fact_weather_daily_district_date"),
        {"schema": "analyst"},
    )

    weather_daily_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    district_id: Mapped[int] = mapped_column(
        ForeignKey("analyst.dim_district.district_id"), nullable=False
    )
    date_key: Mapped[int] = mapped_column(ForeignKey("analyst.dim_date.date_key"), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    temperature_2m_mean: Mapped[float | None] = mapped_column(Float)
    temperature_2m_max: Mapped[float | None] = mapped_column(Float)
    temperature_2m_min: Mapped[float | None] = mapped_column(Float)
    apparent_temperature_mean: Mapped[float | None] = mapped_column(Float)
    relative_humidity_2m_mean: Mapped[float | None] = mapped_column(Float)
    dew_point_2m_mean: Mapped[float | None] = mapped_column(Float)
    surface_pressure_mean: Mapped[float | None] = mapped_column(Float)
    vapour_pressure_deficit_mean: Mapped[float | None] = mapped_column(Float)
    wind_speed_10m_max: Mapped[float | None] = mapped_column(Float)
    wind_gusts_10m_max: Mapped[float | None] = mapped_column(Float)
    cloud_cover_mean: Mapped[float | None] = mapped_column(Float)
    shortwave_radiation_sum: Mapped[float | None] = mapped_column(Float)
    precipitation_sum: Mapped[float | None] = mapped_column(Float)
    rain_sum: Mapped[float | None] = mapped_column(Float)
    weather_code: Mapped[int | None] = mapped_column(SmallInteger)
    soil_moisture_0_to_7cm_mean: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(50), default="open-meteo", nullable=False)
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    district: Mapped[DimDistrict] = relationship(back_populates="daily_weather")


class FactWeatherHourly(Base):
    __tablename__ = "fact_weather_hourly"
    __table_args__ = (
        UniqueConstraint("district_id", "observed_at", name="uq_fact_weather_hourly_district_time"),
        {"schema": "analyst"},
    )

    weather_hourly_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    district_id: Mapped[int] = mapped_column(
        ForeignKey("analyst.dim_district.district_id"), nullable=False
    )
    date_key: Mapped[int] = mapped_column(ForeignKey("analyst.dim_date.date_key"), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    temperature_2m: Mapped[float | None] = mapped_column(Float)
    apparent_temperature: Mapped[float | None] = mapped_column(Float)
    relative_humidity_2m: Mapped[float | None] = mapped_column(Float)
    dew_point_2m: Mapped[float | None] = mapped_column(Float)
    surface_pressure: Mapped[float | None] = mapped_column(Float)
    vapour_pressure_deficit: Mapped[float | None] = mapped_column(Float)
    wind_speed_10m: Mapped[float | None] = mapped_column(Float)
    wind_gusts_10m: Mapped[float | None] = mapped_column(Float)
    cloud_cover: Mapped[float | None] = mapped_column(Float)
    shortwave_radiation: Mapped[float | None] = mapped_column(Float)
    precipitation: Mapped[float | None] = mapped_column(Float)
    rain: Mapped[float | None] = mapped_column(Float)
    weather_code: Mapped[int | None] = mapped_column(SmallInteger)
    soil_moisture_0_to_7cm: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(50), default="open-meteo", nullable=False)
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FactAqiHourly(Base):
    __tablename__ = "fact_aqi_hourly"
    __table_args__ = (
        UniqueConstraint("district_id", "observed_at", name="uq_fact_aqi_hourly_district_time"),
        {"schema": "analyst"},
    )

    aqi_hourly_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    district_id: Mapped[int] = mapped_column(
        ForeignKey("analyst.dim_district.district_id"), nullable=False
    )
    date_key: Mapped[int] = mapped_column(ForeignKey("analyst.dim_date.date_key"), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    european_aqi: Mapped[float | None] = mapped_column(Float)
    us_aqi: Mapped[float | None] = mapped_column(Float)
    pm10: Mapped[float | None] = mapped_column(Float)
    pm2_5: Mapped[float | None] = mapped_column(Float)
    carbon_monoxide: Mapped[float | None] = mapped_column(Float)
    carbon_dioxide: Mapped[float | None] = mapped_column(Float)
    nitrogen_dioxide: Mapped[float | None] = mapped_column(Float)
    sulphur_dioxide: Mapped[float | None] = mapped_column(Float)
    ozone: Mapped[float | None] = mapped_column(Float)
    aerosol_optical_depth: Mapped[float | None] = mapped_column(Float)
    dust: Mapped[float | None] = mapped_column(Float)
    uv_index: Mapped[float | None] = mapped_column(Float)
    uv_index_clear_sky: Mapped[float | None] = mapped_column(Float)
    ammonia: Mapped[float | None] = mapped_column(Float)
    methane: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(
        String(50), default="open-meteo-air-quality", nullable=False
    )
    etl_run_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# monitoring schema
# ---------------------------------------------------------------------------


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

    logs: Mapped[list["EtlLog"]] = relationship(back_populates="etl_run")
    validation_errors: Mapped[list["ValidationError"]] = relationship(back_populates="etl_run")


class EtlLog(Base):
    __tablename__ = "etl_logs"
    __table_args__ = {"schema": "monitoring"}

    etl_log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    etl_run_id: Mapped[int | None] = mapped_column(ForeignKey("monitoring.etl_runs.etl_run_id"))
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    event_name: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    etl_run: Mapped["EtlRun | None"] = relationship(back_populates="logs")


class ValidationError(Base):
    __tablename__ = "validation_errors"
    __table_args__ = {"schema": "monitoring"}

    validation_error_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    etl_run_id: Mapped[int | None] = mapped_column(ForeignKey("monitoring.etl_runs.etl_run_id"))
    source_table: Mapped[str] = mapped_column(String(120), nullable=False)
    district_id: Mapped[int | None] = mapped_column(Integer)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    invalid_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    etl_run: Mapped["EtlRun | None"] = relationship(back_populates="validation_errors")


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
