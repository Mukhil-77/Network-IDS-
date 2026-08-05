"""
Default admin user seeding (documented path: auth/seed.py).

The seeding logic itself lives in backend/auth/authentication.py
(``seed_default_data``), which main.py calls once per startup - it
idempotently creates the default roles, permissions and the admin account
(admin / admin123) only if no users exist yet, then records the event in the
audit log.

This module is the documented entry point for that behavior: call
``seed_default_data(db)`` from anywhere - a migration, a CLI, a test - and
get the same idempotent result.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.auth.authentication import seed_default_data

__all__ = ["seed_default_data"]


def run(db: Session) -> None:
    """Convenience alias: seed the database in place."""
    seed_default_data(db)
