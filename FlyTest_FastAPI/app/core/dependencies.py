from collections.abc import Generator

from app.config import Settings, get_settings
from app.db.session import SessionLocal


def get_settings_dependency() -> Settings:
    return get_settings()


def get_db() -> Generator:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
