from sqlalchemy.dialects.postgresql import insert

from src.database.models import DimProvince
from src.database.seeds.provinces import PROVINCES
from src.database.session import SessionLocal


def main() -> None:
    payload = [
        {
            "province_id": province_id,
            "province_name": province_name,
            "latitude": latitude,
            "longitude": longitude,
        }
        for province_id, province_name, latitude, longitude in PROVINCES
    ]
    statement = insert(DimProvince).values(payload)
    statement = statement.on_conflict_do_update(
        index_elements=[DimProvince.province_id],
        set_={
            "province_name": statement.excluded.province_name,
            "latitude": statement.excluded.latitude,
            "longitude": statement.excluded.longitude,
        },
    )
    with SessionLocal() as session:
        session.execute(statement)
        session.commit()


if __name__ == "__main__":
    main()
