"""Province repository for database access."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import DimProvince


class ProvinceRepository:
    """Repository for province data access."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with database session."""
        self._session = session

    def list_all(self) -> list[DimProvince]:
        """List all provinces ordered by province_id."""
        return list(
            self._session.scalars(
                select(DimProvince).order_by(DimProvince.province_id),
            )
        )

    def get_by_id(self, province_id: int) -> DimProvince | None:
        """Get a province by its ID."""
        return self._session.scalar(
            select(DimProvince).where(DimProvince.province_id == province_id)
        )

    def get_by_name(self, province_name: str) -> DimProvince | None:
        """Get a province by its name."""
        return self._session.scalar(
            select(DimProvince).where(DimProvince.province_name == province_name)
        )
