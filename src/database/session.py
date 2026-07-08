from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session as _Session
from sqlalchemy.orm import sessionmaker


@lru_cache(maxsize=1)
def _engine() -> Engine:
    from src.config.settings import get_settings

    settings = get_settings()
    return create_engine(
        settings.database_url,
        connect_args={"prepare_threshold": None},
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )


@lru_cache(maxsize=1)
def _factory():
    return sessionmaker(bind=_engine(), autoflush=False, autocommit=False)


def SessionLocal() -> _Session:
    """Return a new SQLAlchemy Session. Supports ``with SessionLocal() as session``."""
    return _factory()()
