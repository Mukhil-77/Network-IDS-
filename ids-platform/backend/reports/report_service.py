"""
Assembles a report dict for any of the spec's report types, reusing
analytics_service/statistics_service/repositories rather than recomputing
anything - this module's only job is picking which sections a given
report type includes (via templates/report_templates.py) and shaping them
into one dict, then handing that to pdf_generator/csv_export/json.dumps
for the actual export format.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.analytics.analytics_service import get_overview, get_trends
from backend.database.models import ThreatIndicator
from backend.database.repositories.incidents import IncidentRepository
from backend.database.repositories.responses import ResponseRepository
from backend.database.repositories.statistics import AttackStatisticsRepository
from backend.reports.templates.report_templates import REPORT_SECTIONS, REPORT_TITLES
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class UnknownReportTypeError(Exception):
    pass


def _period_for(report_type: str, start_date: Optional[datetime], end_date: Optional[datetime]) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if start_date and end_date:
        return start_date, end_date
    if report_type == "daily":
        return now - timedelta(days=1), now
    if report_type == "weekly":
        return now - timedelta(days=7), now
    if report_type == "monthly":
        return now - timedelta(days=30), now
    return now - timedelta(days=7), now  # sensible default for report types with no natural period (incident, threat_summary, executive_summary)


def generate(
    db: Session,
    report_type: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    incident_id: Optional[str] = None,
) -> dict:
    """
    Raises:
        UnknownReportTypeError: `report_type` isn't one of REPORT_TYPES.
        ValueError: report_type == "incident" but no matching incident exists.
    """
    if report_type not in REPORT_SECTIONS:
        raise UnknownReportTypeError(f"Unknown report type '{report_type}'. Valid types: {list(REPORT_SECTIONS.keys())}")

    period_start, period_end = _period_for(report_type, start_date, end_date)
    days = max(1, (period_end - period_start).days)

    sections: dict = {}
    for section_name in REPORT_SECTIONS[report_type]:
        sections[section_name] = _build_section(db, section_name, days, incident_id)

    return {
        "title": REPORT_TITLES[report_type],
        "report_type": report_type,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
    }


def _build_section(db: Session, section_name: str, days: int, incident_id: Optional[str]):
    if section_name == "overview":
        return get_overview(db, timeline_days=days)
    if section_name == "trends":
        return get_trends(db, timeline_days=days)
    if section_name == "top_attacks":
        return [
            {"attack_type": row.attack_type, "total_count": row.total_count, "avg_confidence": round(row.avg_confidence, 1)}
            for row in AttackStatisticsRepository(db).top(limit=10)
        ]
    if section_name == "incidents":
        result = IncidentRepository(db).list(page_size=50)
        return [
            {"id": i.id, "title": i.title, "severity": i.severity, "status": i.status, "owner": i.owner or "unassigned"}
            for i in result.items
        ]
    if section_name == "responses":
        rows = ResponseRepository(db).latest(limit=50)
        return [
            {"action": r.action, "status": r.status, "mode": r.mode, "execution_time_ms": round(r.execution_time_ms, 1)}
            for r in rows
        ]
    if section_name == "threat_indicators":
        indicators = db.execute(select(ThreatIndicator).limit(50)).scalars().all()
        return [{"value": i.value, "tag": i.tag, "source": i.source, "confidence": i.confidence} for i in indicators]
    if section_name == "incident_detail":
        if incident_id is None:
            raise ValueError("report_type='incident' requires an incident_id")
        incident = IncidentRepository(db).get(incident_id)
        if incident is None:
            raise ValueError(f"Incident '{incident_id}' not found")
        return {
            "id": incident.id, "title": incident.title, "description": incident.description,
            "severity": incident.severity, "priority": incident.priority, "status": incident.status,
            "owner": incident.owner, "timeline": incident.timeline,
        }
    return None
