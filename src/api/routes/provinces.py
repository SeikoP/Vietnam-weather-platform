"""Provinces API routes."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.schemas.province import ProvinceResponse
from src.models.schemas.weather import DailyWeatherResponse, HourlyWeatherResponse

router = APIRouter(prefix="/provinces", tags=["provinces"])
DB_SESSION = Depends(get_db_session)


@router.get("", response_model=list[ProvinceResponse])
def list_provinces(session: Session = DB_SESSION) -> list[ProvinceResponse]:
    """List all provinces."""
    from src.repositories.province_repository import ProvinceRepository

    provinces = ProvinceRepository(session).list_all()
    return [ProvinceResponse.model_validate(province) for province in provinces]


@router.get("/{province_id}", response_model=ProvinceResponse)
def get_province(province_id: int, session: Session = DB_SESSION) -> ProvinceResponse:
    """Get a specific province by ID."""
    from src.repositories.province_repository import ProvinceRepository

    province = ProvinceRepository(session).get_by_id(province_id)
    if not province:
        raise HTTPException(status_code=404, detail=f"Province {province_id} not found")
    return ProvinceResponse.model_validate(province)


@router.get("/{province_id}/daily", response_model=list[DailyWeatherResponse])
def province_daily_weather(
    province_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> list[DailyWeatherResponse]:
    """List daily weather records for a specific province."""
    from src.repositories.province_repository import ProvinceRepository
    from src.repositories.weather_repository import WeatherRepository

    if not ProvinceRepository(session).get_by_id(province_id):
        raise HTTPException(status_code=404, detail=f"Province {province_id} not found")
    rows = WeatherRepository(session).list_daily(province_id, start_date, end_date)
    return [DailyWeatherResponse.model_validate(row) for row in rows]


@router.get("/{province_id}/hourly", response_model=list[HourlyWeatherResponse])
def province_hourly_weather(
    province_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
) -> list[HourlyWeatherResponse]:
    """List hourly weather records for a specific province."""
    from src.repositories.province_repository import ProvinceRepository
    from src.repositories.weather_repository import WeatherRepository

    if not ProvinceRepository(session).get_by_id(province_id):
        raise HTTPException(status_code=404, detail=f"Province {province_id} not found")
    rows = WeatherRepository(session).list_hourly(province_id, start_date, end_date)
    return [HourlyWeatherResponse.model_validate(row) for row in rows]