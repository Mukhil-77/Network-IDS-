"""Tests for incident_service.py: creation, transitions, and timeline tracking."""

import pytest

from backend.services import incident_service


def make_incident(db, **overrides):
    defaults = dict(title="Test Incident", description="d", severity="High", priority="High", created_by="alice")
    defaults.update(overrides)
    return incident_service.create_incident(db, **defaults)


class TestCreate:
    def test_creates_with_open_status_and_a_creation_timeline_entry(self, db_session):
        incident = make_incident(db_session)
        assert incident.status == "open"
        assert len(incident.timeline) == 1
        assert incident.timeline[0]["action"] == "created"

    def test_links_an_alert_id_when_given(self, db_session):
        incident = make_incident(db_session, alert_id="alert-123")
        assert incident.alert_id == "alert-123"


class TestUpdate:
    def test_valid_status_transition_succeeds(self, db_session):
        incident = make_incident(db_session)
        updated = incident_service.update_incident(db_session, incident.id, "bob", status="assigned")
        assert updated.status == "assigned"

    def test_invalid_status_transition_raises(self, db_session):
        incident = make_incident(db_session)
        incident_service.update_incident(db_session, incident.id, "bob", status="closed")
        with pytest.raises(incident_service.InvalidTransitionError):
            incident_service.update_incident(db_session, incident.id, "bob", status="open")

    def test_closing_sets_closed_at(self, db_session):
        incident = make_incident(db_session)
        updated = incident_service.update_incident(db_session, incident.id, "bob", status="closed")
        assert updated.closed_at is not None

    def test_assigning_an_owner_appends_a_timeline_entry(self, db_session):
        incident = make_incident(db_session)
        updated = incident_service.update_incident(db_session, incident.id, "bob", owner="carol")
        assert updated.owner == "carol"
        assert any(e["action"] == "assigned" for e in updated.timeline)

    def test_adding_a_note_appends_without_changing_status(self, db_session):
        incident = make_incident(db_session)
        updated = incident_service.update_incident(db_session, incident.id, "bob", note="Found the root cause")
        assert updated.status == "open"
        assert any(e["note"] == "Found the root cause" for e in updated.timeline)

    def test_updating_unknown_incident_raises(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            incident_service.update_incident(db_session, "does-not-exist", "bob", status="assigned")

    def test_priority_change_is_tracked_in_timeline(self, db_session):
        incident = make_incident(db_session, priority="Low")
        updated = incident_service.update_incident(db_session, incident.id, "bob", priority="Urgent")
        assert updated.priority == "Urgent"
        assert any(e["action"] == "priority_changed" for e in updated.timeline)

    def test_resolved_can_go_back_to_in_progress(self, db_session):
        incident = make_incident(db_session)
        incident_service.update_incident(db_session, incident.id, "bob", status="resolved")
        updated = incident_service.update_incident(db_session, incident.id, "bob", status="in_progress")
        assert updated.status == "in_progress"
