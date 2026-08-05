"""
Incident lifecycle: open -> assigned -> in_progress -> resolved -> closed
(not strictly linear - see VALID_TRANSITIONS; an incident can jump straight
from open to resolved, but never backward from closed). Owns the
timeline-append logic so every state change is uniformly recorded, rather
than each caller building its own timeline entry shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.database.models import Incident
from backend.database.repositories.incidents import IncidentFilters, IncidentRepository
from backend.utils.logger import get_logger

logger = get_logger(__name__)

VALID_STATUSES = ["open", "assigned", "in_progress", "resolved", "closed"]

# Which status transitions are allowed from each current status - a closed
# incident is genuinely final (reopen it as a new incident if needed,
# rather than muddying the audit trail of what "closed" means).
VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"open", "assigned", "in_progress", "resolved", "closed"},
    "assigned": {"assigned", "in_progress", "resolved", "closed"},
    "in_progress": {"in_progress", "resolved", "closed"},
    "resolved": {"resolved", "closed", "in_progress"},  # resolved -> in_progress covers "turned out not fixed"
    "closed": {"closed"},
}


class InvalidTransitionError(Exception):
    pass


def _timeline_entry(actor: str, action: str, note: str = "") -> dict:
    return {"timestamp": datetime.now(timezone.utc).isoformat(), "actor": actor, "action": action, "note": note}


def create_incident(
    db: Session, *, title: str, description: str, severity: str, priority: str,
    created_by: str, alert_id: str | None = None,
) -> Incident:
    incident = Incident(
        title=title, description=description, severity=severity, priority=priority,
        created_by=created_by, alert_id=alert_id, status="open",
        timeline=[_timeline_entry(created_by, "created", f"Incident opened: {title}")],
    )
    return IncidentRepository(db).create(incident)


def update_incident(
    db: Session, incident_id: str, actor: str, *,
    status: str | None = None, owner: str | None = None, priority: str | None = None, note: str | None = None,
) -> Incident:
    """
    Raises:
        ValueError: incident not found.
        InvalidTransitionError: `status` isn't reachable from the incident's current status.
    """
    incident = IncidentRepository(db).get(incident_id)
    if incident is None:
        raise ValueError(f"Incident '{incident_id}' not found")

    timeline = list(incident.timeline or [])

    if status is not None and status != incident.status:
        if status not in VALID_TRANSITIONS.get(incident.status, set()):
            raise InvalidTransitionError(f"Cannot transition incident from '{incident.status}' to '{status}'")
        timeline.append(_timeline_entry(actor, "status_changed", f"{incident.status} -> {status}"))
        incident.status = status
        if status == "closed":
            incident.closed_at = datetime.now(timezone.utc)

    if owner is not None and owner != incident.owner:
        timeline.append(_timeline_entry(actor, "assigned", f"Assigned to {owner}"))
        incident.owner = owner

    if priority is not None and priority != incident.priority:
        timeline.append(_timeline_entry(actor, "priority_changed", f"{incident.priority} -> {priority}"))
        incident.priority = priority

    if note:
        timeline.append(_timeline_entry(actor, "note", note))

    incident.timeline = timeline
    incident.updated_at = datetime.now(timezone.utc)
    return incident
