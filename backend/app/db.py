from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def build_engine(database_url: str) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return create_engine(database_url, **options)



_session_factory: sessionmaker | None = None


def get_session_factory() -> sessionmaker:
    """Build the production pool lazily so tests can replace the DB dependency.

    This does not provide a local persistence fallback; runtime still requires the
    configured PostgreSQL/Neon driver and connection.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=build_engine(get_settings().database_url), autoflush=False, autocommit=False
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> None:
    """Raise when the configured PostgreSQL database cannot answer a basic query."""
    with get_session_factory()() as db:
        db.execute(text("SELECT 1"))
