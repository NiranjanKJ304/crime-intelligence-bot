"""
Database engine and session management.

Provides SQLAlchemy engine with connection pooling,
a session factory, and a FastAPI dependency for request-scoped sessions.
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    """Create a SQLAlchemy engine with connection pooling."""
    settings = settings or get_settings()
    return create_engine(
        settings.database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.debug,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine."""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ── Module-level singletons (lazy) ────────────────────────────────────

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the global engine singleton, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the global session factory singleton."""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory(get_engine())
    return _session_factory


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a request-scoped session.

    Usage:
        @app.get("/example")
        def endpoint(db: Session = Depends(get_db_session)):
            ...
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def ensure_schema_exists(engine: Engine, schema_name: str) -> None:
    """Create a PostgreSQL schema if it does not already exist."""
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        conn.commit()
