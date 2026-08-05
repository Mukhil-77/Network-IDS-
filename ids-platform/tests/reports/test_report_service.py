"""Tests for report_service.py."""

import pytest

from backend.reports import report_service
from backend.services import incident_service


class TestGenerate:
    def test_unknown_report_type_raises(self, db_session):
        with pytest.raises(report_service.UnknownReportTypeError):
            report_service.generate(db_session, "not_a_real_type")

    @pytest.mark.parametrize("report_type", ["daily", "weekly", "monthly", "threat_summary", "executive_summary"])
    def test_every_report_type_generates_without_error(self, db_session, report_type):
        report = report_service.generate(db_session, report_type)
        assert report["title"]
        assert report["report_type"] == report_type
        assert isinstance(report["sections"], dict)
        assert len(report["sections"]) > 0

    def test_custom_report_uses_the_given_date_range(self, db_session):
        from datetime import datetime, timezone
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 8, tzinfo=timezone.utc)

        report = report_service.generate(db_session, "custom", start_date=start, end_date=end)
        assert report["period_start"] == start.isoformat()
        assert report["period_end"] == end.isoformat()

    def test_incident_report_includes_the_named_incident(self, db_session):
        incident = incident_service.create_incident(
            db_session, title="Test Incident", description="d", severity="High", priority="High", created_by="alice",
        )
        db_session.commit()

        report = report_service.generate(db_session, "incident", incident_id=incident.id)
        assert report["sections"]["incident_detail"]["title"] == "Test Incident"

    def test_incident_report_without_id_raises(self, db_session):
        with pytest.raises(ValueError, match="requires an incident_id"):
            report_service.generate(db_session, "incident")

    def test_incident_report_with_unknown_id_raises(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            report_service.generate(db_session, "incident", incident_id="does-not-exist")
