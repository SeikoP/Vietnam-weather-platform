from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.schemas.weather import (
    DailyWeatherResponse,
    HourlyWeatherResponse,
    WeatherStatisticsResponse,
)

router = APIRouter(tags=["weather"])
DB_SESSION = Depends(get_db_session)


@router.get("/daily", response_model=list[DailyWeatherResponse])
def daily_weather(
    province_id: int | None = Query(default=None, ge=1),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> list[DailyWeatherResponse]:
    from src.repositories.weather_repository import WeatherRepository

    rows = WeatherRepository(session).list_daily(province_id, start_date, end_date)
    return [DailyWeatherResponse.model_validate(row) for row in rows]


@router.get("/weather", response_model=list[DailyWeatherResponse])
def weather(
    province_id: int | None = Query(default=None, ge=1),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> list[DailyWeatherResponse]:
    return daily_weather(province_id, start_date, end_date, session)


@router.get("/hourly", response_model=list[HourlyWeatherResponse])
def hourly_weather(
    province_id: int | None = Query(default=None, ge=1),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> list[HourlyWeatherResponse]:
    from src.repositories.weather_repository import WeatherRepository

    rows = WeatherRepository(session).list_hourly(province_id, start_date, end_date)
    return [HourlyWeatherResponse.model_validate(row) for row in rows]


@router.get("/statistics", response_model=WeatherStatisticsResponse)
def weather_statistics(
    province_id: int | None = Query(default=None, ge=1),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> WeatherStatisticsResponse:
    from src.repositories.weather_repository import WeatherRepository

    stats = WeatherRepository(session).daily_statistics(province_id, start_date, end_date)
    return WeatherStatisticsResponse(**stats)
