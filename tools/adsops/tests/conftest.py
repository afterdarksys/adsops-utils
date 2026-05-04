"""Shared pytest fixtures for adsops tests."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_db_session():
    """Mocked SQLAlchemy session for unit tests without live PostgreSQL.

    Patches both the db module and service module references since service.py
    imports get_session by name at module load time.
    """
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)

    with patch("adsops.hostctl.db.get_session", return_value=session), \
         patch("adsops.hostctl.service.get_session", return_value=session):
        yield session
