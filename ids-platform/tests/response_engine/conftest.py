"""DB fixture for tests/response_engine/ - same isolated-SQLite-per-test pattern used elsewhere."""

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
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        db_path.unlink(missing_ok=True)


@pytest.fixture
def policy_engine(tmp_path):
    """A PolicyEngine backed by a throwaway copy of the default rules file, so tests never mutate the real one."""
    import shutil

    from backend.response_engine.response_rules import DEFAULT_RULES_PATH, PolicyEngine

    test_rules_path = tmp_path / "response_rules.yaml"
    shutil.copy(DEFAULT_RULES_PATH, test_rules_path)
    return PolicyEngine(rules_path=test_rules_path)
