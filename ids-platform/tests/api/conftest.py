"""
Fixtures scoped to tests/api/ only.

Nested conftest.py files inherit fixtures from parent directories, so
`trained_model_dir` and `valid_feature_payload` (defined in tests/conftest.py
for the Milestone 3 suite) are available here unchanged - nothing in
tests/conftest.py needed to be touched to add the API test suite.

Milestone 6 addition: every route that touches the database goes through
FastAPI's `get_db` dependency, so both fixtures below override it with an
isolated, freshly-created SQLite database per test - no real PostgreSQL
instance is needed to run this suite (see database/connection.py's
docstring for why the same models work against both engines).
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import get_settings
from backend.database.connection import get_db
from backend.database.models import Base
from backend.main import app
from backend.services.prediction_service import prediction_service


def _authenticate_as_default_admin(test_client: TestClient) -> str:
    """
    Logs in as the default admin (seeded at startup by seed_default_data())
    and attaches the access token as a default header, so every request
    this client makes for the rest of the test is already authenticated.
    Returns the access token, for tests that need it directly (e.g. the
    WebSocket tests, which pass it as a query param instead of a header).
    """
    settings = get_settings()
    response = test_client.post("/auth/login", json={
        "username": settings.DEFAULT_ADMIN_USERNAME,
        "password": settings.DEFAULT_ADMIN_PASSWORD,
    })
    assert response.status_code == 200, f"Test setup: default admin login failed: {response.text}"
    token = response.json()["access_token"]
    test_client.headers.update({"Authorization": f"Bearer {token}"})
    return token


def _override_db(app):
    """Point app's get_db dependency, AND connection.py's module-level engine/SessionLocal
    (used directly by main.py's lifespan for init_db()/session_scope()), at a fresh,
    isolated SQLite file for the duration of one test."""
    import backend.database.connection as connection_module

    db_path = Path(tempfile.mktemp(suffix=".db"))
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    original_engine = connection_module.engine
    original_session_local = connection_module.SessionLocal
    connection_module.engine = engine
    connection_module.SessionLocal = TestSessionLocal

    def _get_test_db():
        db = TestSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    return engine, db_path, original_engine, original_session_local


def _cleanup_db(app, engine, db_path, original_engine, original_session_local):
    import backend.database.connection as connection_module

    app.dependency_overrides.pop(get_db, None)
    connection_module.engine = original_engine
    connection_module.SessionLocal = original_session_local
    engine.dispose()
    db_path.unlink(missing_ok=True)


@pytest.fixture
def client() -> TestClient:
    """A TestClient with no model configured (models_dir points somewhere empty), backed by an isolated test DB, authenticated as the default admin."""
    prediction_service.models_dir = "this/path/does/not/exist"
    engine, db_path, orig_engine, orig_session_local = _override_db(app)
    try:
        with TestClient(app) as test_client:
            test_client.access_token = _authenticate_as_default_admin(test_client)
            yield test_client
    finally:
        _cleanup_db(app, engine, db_path, orig_engine, orig_session_local)


@pytest.fixture
def client_with_model(trained_model_dir) -> TestClient:
    """A TestClient pointed at the synthetic trained model from tests/conftest.py, backed by an isolated test DB, authenticated as the default admin."""
    prediction_service.models_dir = str(trained_model_dir.parent)
    engine, db_path, orig_engine, orig_session_local = _override_db(app)
    try:
        with TestClient(app) as test_client:
            test_client.access_token = _authenticate_as_default_admin(test_client)
            yield test_client
    finally:
        _cleanup_db(app, engine, db_path, orig_engine, orig_session_local)


@pytest.fixture
def unauthenticated_client() -> TestClient:
    """A TestClient with no Authorization header at all - for tests that specifically verify auth is enforced."""
    engine, db_path, orig_engine, orig_session_local = _override_db(app)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        _cleanup_db(app, engine, db_path, orig_engine, orig_session_local)
