"""
Database test fixtures.

Each test gets its own temp-file SQLite database (not `:memory:`, which
needs extra StaticPool wiring to be usable across the multiple connections
SQLAlchemy's default pool opens) with all tables created fresh, and torn
down afterward. No real PostgreSQL instance is required to run this suite -
see database/connection.py's docstring for why the same models work
against both.
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database.models import Base


@pytest.fixture
def db_session():
    db_path = Path(tempfile.mktemp(suffix=".db"))
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    from backend.auth import models as _auth_models  # noqa: F401  (registers auth tables on Base.metadata before create_all)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        db_path.unlink(missing_ok=True)
