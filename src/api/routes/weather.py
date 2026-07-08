from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.schemas.weather import (
    AqiHourlyResponse,
    DailyWeatherResponse,
    HourlyWeatherResponse,
    WeatherStatisticsResponse,
)

router = APIRouter(tags=["weather"])
DB_SESSION = Depends(get_db_session)


@router.get("/daily", response_model=list[DailyWeatherResponse])
def daily_weather(
    district_id: int | None = Query(default=None),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> list[DailyWeatherResponse]:
    from src.repositories.weather_repository import WeatherRepository

    rows = WeatherRepository(session).list_daily(district_id, start_date, end_date)
    return [DailyWeatherResponse.model_validate(r) for r in rows]


@router.get("/hourly", response_model=list[HourlyWeatherResponse])
def hourly_weather(
    district_id: int | None = Query(default=None),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> list[HourlyWeatherResponse]:
    from src.repositories.weather_repository import WeatherRepository

    rows = WeatherRepository(session).list_hourly(district_id, start_date, end_date)
    return [HourlyWeatherResponse.model_validate(r) for r in rows]


@router.get("/aqi", response_model=list[AqiHourlyResponse])
def aqi_hourly_weather(
    district_id: int | None = Query(default=None),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> list[AqiHourlyResponse]:
    from src.repositories.weather_repository import WeatherRepository

    rows = WeatherRepository(session).list_aqi_hourly(district_id, start_date, end_date)
    return [AqiHourlyResponse.model_validate(r) for r in rows]


@router.get("/statistics", response_model=WeatherStatisticsResponse)
def weather_statistics(
    district_id: int | None = Query(default=None),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> WeatherStatisticsResponse:
    from src.repositories.weather_repository import WeatherRepository

    stats = WeatherRepository(session).daily_statistics(district_id, start_date, end_date)
    return WeatherStatisticsResponse(**stats)
