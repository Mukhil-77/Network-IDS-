"""
Database engine and session management.

Sync SQLAlchemy, not an async ORM - deliberately, for consistency: the rest
of this codebase (backend.ml, packet_capture, detection) is entirely
synchronous, and DetectionService already runs off the packet-capture
thread on its own thread pool (Milestone 5), so a synchronous DB write
there doesn't block capture either way (see alert_service.py). Introducing
async DB access would only add a second concurrency model for no benefit.

Two ways to get a session:
    - `get_db()`      - a FastAPI dependency (yields, auto-closes) for routes.
    - `session_scope()` - a plain context manager for non-request code
      (alert_service.py, statistics_service.py, startup scripts).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings
from backend.database.models import Base
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_settings = get_settings()

# `connect_args` only applies to SQLite (used by the test suite, see
# tests/database/conftest.py) - harmless no-op for PostgreSQL.
_connect_args = {"check_same_thread": False} if _settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(_settings.DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    """
    Create every table defined in database.models (and any other module
    that defines tables on the same Base - e.g. backend.auth.models) if it
    doesn't already exist. See database/migrations/ for why this - not
    Alembic - is what "migrations" means in this milestone.

    Every model module must be imported before `Base.metadata.create_all()`
    runs, or SQLAlchemy simply doesn't know that module's tables exist yet
    (declarative registration happens at import time) - the import below
    is what makes backend.auth.models' tables (users, roles, etc.) get
    created alongside everything else.
    """
    from backend.auth import models as _auth_models  # noqa: F401  (import registers auth's tables on Base.metadata)

    Base.metadata.create_all(bind=engine)
    logger.info("Database schema ensured (tables created if not already present)")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: `def route(..., db: Session = Depends(get_db))`. Commits on successful completion, rolls back on exception - same contract as session_scope()."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for DB access outside a FastAPI request (services, scripts)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
