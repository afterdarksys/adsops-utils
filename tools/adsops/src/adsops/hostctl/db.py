from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from adsops.config import get_db_url

_engine = None


def get_engine():
    """Return the SQLAlchemy engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_db_url(),
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,  # equivalent to Go's db.Ping()
        )
    return _engine


def get_session() -> Session:
    """Return a new SQLAlchemy session."""
    factory = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return factory()
