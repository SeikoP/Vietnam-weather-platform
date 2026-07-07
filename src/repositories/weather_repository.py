"""Weather repository for database access."""

from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from src.database.models import FactWeatherDaily, FactWeatherHourly


class WeatherRepository:
    """Repository for weather data access."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session."""
        self._session = session

    def list_daily(
        self,
        province_id: int | None,
        start_date: date | None,
        end_date: date | None,
    ) -> list[FactWeatherDaily]:
        """List daily weather records with optional filters."""
        statement: Select[tuple[FactWeatherDaily]] = select(FactWeatherDaily)
        if province_id is not None:
            statement = statement.where(FactWeatherDaily.province_id == province_id)
        if start_date is not None:
            statement = statement.where(FactWeatherDaily.observed_date >= start_date)
        if end_date is not None:
            statement = statement.where(FactWeatherDaily.observed_date <= end_date)
        statement = statement.order_by(FactWeatherDaily.observed_date, FactWeatherDaily.province_id)
        return list(self._session.scalars(statement))

    def list_hourly(
        self,
        province_id: int | None,
        start_date: date | None,
        end_date: date | None,
    ) -> list[FactWeatherHourly]:
        """List hourly weather records with optional filters."""
        statement: Select[tuple[FactWeatherHourly]] = select(FactWeatherHourly)
        if province_id is not None:
            statement = statement.where(FactWeatherHourly.province_id == province_id)
        if start_date is not None:
            statement = statement.where(FactWeatherHourly.observed_date >= start_date)
        if end_date is not None:
            statement = statement.where(FactWeatherHourly.observed_date <= end_date)
        statement = statement.order_by(FactWeatherHourly.observed_at, FactWeatherHourly.province_id)
        return list(self._session.scalars(statement))

    def daily_statistics(
        self,
        province_id: int | None,
        start_date: date | None,
        end_date: date | None,
    ) -> dict[str, object]:
        """Calculate daily weather statistics with optional filters."""
        statement = select(
            func.avg(FactWeatherDaily.temperature_2m_mean),
            func.max(FactWeatherDaily.temperature_2m_max),
            func.min(FactWeatherDaily.temperature_2m_min),
            func.sum(FactWeatherDaily.precipitation_sum),
        )
        if province_id is not None:
            statement = statement.where(FactWeatherDaily.province_id == province_id)
        if start_date is not None:
            statement = statement.where(FactWeatherDaily.observed_date >= start_date)
        if end_date is not None:
            statement = statement.where(FactWeatherDaily.observed_date <= end_date)
        row = self._session.execute(statement).one()
        return {
            "province_id": province_id,
            "start_date": start_date,
            "end_date": end_date,
            "avg_temperature_2m_mean": row[0],
            "max_temperature_2m_max": row[1],
            "min_temperature_2m_min": row[2],
            "total_precipitation_sum": row[3],
        }
