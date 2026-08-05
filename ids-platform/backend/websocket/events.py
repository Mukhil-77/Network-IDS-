"""
WebSocket event envelope: every message sent over /ws/alerts has this shape.

Milestone 8 addition: WSEventType gained the four response-lifecycle event
names, and `serialize_event()` generalizes what `serialize_alert_event()`
already did for one type - the latter is kept as a thin backward-compatible
wrapper so nothing that already imports it needs to change.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel


class WSEventType:
    ALERT = "alert"

    # Live packet feed (capture_service.py broadcasts one per parsed packet).
    PACKET = "packet"

    # Milestone 8: response engine lifecycle events (response_service.py)
    RESPONSE_STARTED = "response_started"
    RESPONSE_COMPLETED = "response_completed"
    RESPONSE_FAILED = "response_failed"
    ROLLBACK_COMPLETED = "rollback_completed"


class WSEvent(BaseModel):
    type: str
    payload: dict
    timestamp: str = ""

    def model_post_init(self, __context) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def serialize_event(event_type: str, payload: dict) -> str:
    """Build and JSON-serialize a WSEvent of any type. Used by broadcaster.py."""
    event = WSEvent(type=event_type, payload=payload)
    return event.model_dump_json()


def serialize_alert_event(alert_payload: dict) -> str:
    """Backward-compatible alias for serialize_event(WSEventType.ALERT, ...)."""
    return serialize_event(WSEventType.ALERT, alert_payload)
