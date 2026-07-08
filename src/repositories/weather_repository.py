"""Weather repository for database access."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from src.database.models import DimHour, FactAqiHourly, FactWeatherDaily, FactWeatherHourly


class WeatherRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_daily(
        self, district_id: int | None, start_date: date | None, end_date: date | None
    ) -> list[FactWeatherDaily]:
        stmt = select(FactWeatherDaily)
        if district_id is not None:
            stmt = stmt.where(FactWeatherDaily.district_id == district_id)
        if start_date is not None:
            stmt = stmt.where(FactWeatherDaily.observed_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(FactWeatherDaily.observed_date <= end_date)
        return list(
            self._session.scalars(
                stmt.order_by(FactWeatherDaily.observed_date, FactWeatherDaily.district_id)
            )
        )

    def list_hourly(
        self, district_id: int | None, start_date: date | None, end_date: date | None
    ) -> list[FactWeatherHourly]:
        stmt = select(FactWeatherHourly).join(FactWeatherHourly.hour).options(
            joinedload(FactWeatherHourly.hour)
        )
        if district_id is not None:
            stmt = stmt.where(FactWeatherHourly.district_id == district_id)
        if start_date is not None:
            stmt = stmt.where(DimHour.observed_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(DimHour.observed_date <= end_date)
        return list(
            self._session.scalars(
                stmt.order_by(DimHour.observed_at, FactWeatherHourly.district_id)
            )
        )

    def list_aqi_hourly(
        self, district_id: int | None, start_date: date | None, end_date: date | None
    ) -> list[FactAqiHourly]:
        stmt = select(FactAqiHourly).join(FactAqiHourly.hour).options(
            joinedload(FactAqiHourly.hour)
        )
        if district_id is not None:
            stmt = stmt.where(FactAqiHourly.district_id == district_id)
        if start_date is not None:
            stmt = stmt.where(DimHour.observed_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(DimHour.observed_date <= end_date)
        return list(
            self._session.scalars(
                stmt.order_by(DimHour.observed_at, FactAqiHourly.district_id)
            )
        )

    def daily_statistics(
        self, district_id: int | None, start_date: date | None, end_date: date | None
    ) -> dict:
        stmt = select(
            func.avg(FactWeatherDaily.temperature_2m_mean),
            func.max(FactWeatherDaily.temperature_2m_max),
            func.min(FactWeatherDaily.temperature_2m_min),
            func.sum(FactWeatherDaily.precipitation_sum),
        )
        if district_id is not None:
            stmt = stmt.where(FactWeatherDaily.district_id == district_id)
        if start_date is not None:
            stmt = stmt.where(FactWeatherDaily.observed_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(FactWeatherDaily.observed_date <= end_date)
        row = self._session.execute(stmt).one()
        return {
            "district_id": district_id,
            "start_date": start_date,
            "end_date": end_date,
            "avg_temperature_2m_mean": row[0],
            "max_temperature_2m_max": row[1],
            "min_temperature_2m_min": row[2],
            "total_precipitation_sum": row[3],
        }
