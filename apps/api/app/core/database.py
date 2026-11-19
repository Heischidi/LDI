"""Database engine, session factory, and declarative base for SQLAlchemy 2.0."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def _build_engine():
    db_url = settings.effective_database_url
    connect_args = {}
    engine_kwargs: dict = {"pool_pre_ping": True}

    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    else:
        engine_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_recycle": 300})

    eng = create_engine(db_url, connect_args=connect_args, **engine_kwargs)

    if db_url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return eng


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


class Base(DeclarativeBase):
    """Base declarative class for all LDI database models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure closure after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
