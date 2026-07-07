from collections.abc import Generator

from sqlalchemy.orm import Session


def get_db_session() -> Generator[Session]:
    from src.database.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
