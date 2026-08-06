"""SQLAlchemy engine, session, and declarative base configuration."""

import logging  # hataları ve önemli mesajları kaydetmek için logging modülünü içe aktarır
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# bu dosyada oluşan hataları kaydetmek için bir logger oluşturulur.
logger = logging.getLogger(__name__)


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for future SQLAlchemy declarative models."""


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and close it after the request completes."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> bool:
    """Check PostgreSQL connectivity and log any SQLAlchemy error."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database connection check failed.")
        return False

    return True
