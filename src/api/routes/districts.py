"""Districts API routes."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.dependencies import get_db_session
from src.models.schemas.district import DistrictResponse
from src.models.schemas.weather import (
    AqiHourlyResponse,
    DailyWeatherResponse,
    HourlyWeatherResponse,
)

router = APIRouter(prefix="/districts", tags=["districts"])
DB_SESSION = Depends(get_db_session)
DEFAULT_LIMIT = Query(default=100, ge=1, le=1000)
DEFAULT_OFFSET = Query(default=0, ge=0)


@router.get("", response_model=list[DistrictResponse])
def list_districts(session: Session = DB_SESSION):
    from src.repositories.district_repository import DistrictRepository

    return [DistrictResponse.model_validate(d) for d in DistrictRepository(session).list_all()]


@router.get("/{district_id}", response_model=DistrictResponse)
def get_district(district_id: int, session: Session = DB_SESSION):
    from src.repositories.district_repository import DistrictRepository

    district = DistrictRepository(session).get_by_id(district_id)
    if not district:
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")
    return DistrictResponse.model_validate(district)


@router.get("/{district_id}/daily", response_model=list[DailyWeatherResponse])
def district_daily_weather(
    district_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = DB_SESSION,
):
    from src.repositories.district_repository import DistrictRepository
    from src.repositories.weather_repository import WeatherRepository

    if not DistrictRepository(session).get_by_id(district_id):
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")
    rows = WeatherRepository(session).list_daily(district_id, start_date, end_date)
    return [DailyWeatherResponse.model_validate(r) for r in rows]


@router.get("/{district_id}/hourly", response_model=list[HourlyWeatherResponse])
def district_hourly_weather(
    district_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = DEFAULT_OFFSET,
    session: Session = DB_SESSION,
):
    from src.repositories.district_repository import DistrictRepository
    from src.repositories.weather_repository import WeatherRepository

    if not DistrictRepository(session).get_by_id(district_id):
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")
    rows = WeatherRepository(session).list_hourly(district_id, start_date, end_date, limit, offset)
    return [HourlyWeatherResponse.model_validate(r) for r in rows]


@router.get("/{district_id}/aqi", response_model=list[AqiHourlyResponse])
def district_aqi_hourly(
    district_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = DEFAULT_OFFSET,
    session: Session = DB_SESSION,
):
    from src.repositories.district_repository import DistrictRepository
    from src.repositories.weather_repository import WeatherRepository

    if not DistrictRepository(session).get_by_id(district_id):
        raise HTTPException(status_code=404, detail=f"District {district_id} not found")
    rows = WeatherRepository(session).list_aqi_hourly(
        district_id, start_date, end_date, limit, offset
    )
    return [AqiHourlyResponse.model_validate(r) for r in rows]
