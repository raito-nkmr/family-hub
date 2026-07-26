import pytest

from app.core.config import Settings
from app.database.session import create_database_engine


def test_create_database_engine_uses_psycopg() -> None:
    settings = Settings(database_url="postgresql+psycopg://user:password@localhost/database")

    engine = create_database_engine(settings)

    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    engine.dispose()


def test_create_database_engine_requires_database_url() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL is not configured"):
        create_database_engine(Settings(database_url=None))
