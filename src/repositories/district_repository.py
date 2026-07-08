"""District repository for database access."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import DimDistrict


class DistrictRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[DimDistrict]:
        return list(self._session.scalars(select(DimDistrict).order_by(DimDistrict.district_id)))

    def get_by_id(self, district_id: int) -> DimDistrict | None:
        return self._session.scalar(
            select(DimDistrict).where(DimDistrict.district_id == district_id)
        )

    def get_by_name(self, district_name: str) -> DimDistrict | None:
        return self._session.scalar(
            select(DimDistrict).where(DimDistrict.district_name == district_name)
        )
