"""DB fixture for tests/auth/ - isolated SQLite per test, seeded with default roles/permissions/admin."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth.authentication import seed_default_data
from backend.database.models import Base


@pytest.fixture
def db_session():
    db_path = Path(tempfile.mktemp(suffix=".db"))
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        db_path.unlink(missing_ok=True)


@pytest.fixture
def seeded_db(db_session):
    """A db_session with default roles/permissions/admin already seeded."""
    seed_default_data(db_session)
    db_session.commit()
    return db_session
