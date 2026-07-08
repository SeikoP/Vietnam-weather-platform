from sqlalchemy.dialects.postgresql import insert

from src.database.models import DimDistrict
from src.database.seeds.districts import DISTRICTS
from src.database.session import SessionLocal


def main() -> None:
    payload = [
        {
            "district_id": district_id,
            "district_name": district_name,
            "latitude": latitude,
            "longitude": longitude,
        }
        for district_id, district_name, latitude, longitude in DISTRICTS
    ]
    statement = insert(DimDistrict).values(payload)
    statement = statement.on_conflict_do_update(
        index_elements=[DimDistrict.district_id],
        set_={
            "district_name": statement.excluded.district_name,
            "latitude": statement.excluded.latitude,
            "longitude": statement.excluded.longitude,
        },
    )
    with SessionLocal() as session:
        session.execute(statement)
        session.commit()


if __name__ == "__main__":
    main()
