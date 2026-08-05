"""
Incident management service (documented path: incidents/incident_service.py).

Full incident lifecycle: open -> assigned -> in_progress -> resolved ->
closed, with timeline recording, ownership and priority management. The
implementation lives in backend/services/incident_service.py (which the
incidents API routes import); this module is the documented entry point and
re-exports the complete public API so both import paths work identically.
"""

from backend.services.incident_service import (
    VALID_STATUSES,
    VALID_TRANSITIONS,
    InvalidTransitionError,
    create_incident,
    update_incident,
)

__all__ = [
    "VALID_STATUSES",
    "VALID_TRANSITIONS",
    "InvalidTransitionError",
    "create_incident",
    "update_incident",
]
