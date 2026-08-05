"""Tests for audit.py."""

from sqlalchemy import select

from backend.auth import audit
from backend.database.models import AuditLog


def test_log_event_writes_every_field(db_session):
    entry = audit.log_event(
        db_session, actor="alice", action=audit.LOGIN_SUCCESS, target="alice",
        role="Admin", ip_address="10.0.0.1", status="success", details={"note": "test"},
    )

    assert entry.id is not None
    fetched = db_session.get(AuditLog, entry.id)
    assert fetched.actor == "alice"
    assert fetched.action == audit.LOGIN_SUCCESS
    assert fetched.role == "Admin"
    assert fetched.ip_address == "10.0.0.1"
    assert fetched.status == "success"
    assert fetched.details == {"note": "test"}


def test_log_event_defaults_status_to_success(db_session):
    entry = audit.log_event(db_session, actor="bob", action="some_action")
    assert entry.status == "success"


def test_log_event_supports_failed_status(db_session):
    entry = audit.log_event(db_session, actor="bob", action=audit.LOGIN_FAILED, status="failed")
    assert entry.status == "failed"


def test_multiple_events_are_all_persisted_independently(db_session):
    audit.log_event(db_session, actor="alice", action=audit.LOGIN_SUCCESS)
    audit.log_event(db_session, actor="alice", action=audit.LOGOUT)
    db_session.commit()

    entries = db_session.execute(select(AuditLog).where(AuditLog.actor == "alice")).scalars().all()
    assert {e.action for e in entries} == {audit.LOGIN_SUCCESS, audit.LOGOUT}
