from datetime import date, timedelta

from sqlalchemy.dialects.postgresql import insert

from src.database.models import DimDate
from src.database.session import SessionLocal

START_DATE = date(2023, 6, 1)


def date_key(value: date) -> int:
    return int(value.strftime("%Y%m%d"))


def build_rows(
    start_date: date = START_DATE, end_date: date | None = None
) -> list[dict[str, object]]:
    if end_date is None:
        end_date = date.today()
    rows: list[dict[str, object]] = []
    current = start_date
    while current <= end_date:
        rows.append(
            {
                "date_key": date_key(current),
                "date": current,
                "year": current.year,
                "quarter": ((current.month - 1) // 3) + 1,
                "month": current.month,
                "day": current.day,
                "day_of_week": current.isoweekday(),
                "is_weekend": current.isoweekday() in {6, 7},
            }
        )
        current += timedelta(days=1)
    return rows


def main() -> None:
    statement = insert(DimDate).values(build_rows())
    statement = statement.on_conflict_do_nothing(index_elements=[DimDate.date_key])
    with SessionLocal() as session:
        session.execute(statement)
        session.commit()


if __name__ == "__main__":
    main()
