"""
db_session fixture for tests/services/.

tests/database/conftest.py's db_session isn't inherited here (sibling
directory, not a parent) - this is the same isolated-SQLite-per-test
fixture, duplicated because it's test infrastructure, not application code.
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.models import Base


@pytest.fixture
def db_session():
    db_path = Path(tempfile.mktemp(suffix=".db"))
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    from backend.auth import models as _auth_models  # noqa: F401  (registers auth tables on Base.metadata before create_all)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        db_path.unlink(missing_ok=True)
