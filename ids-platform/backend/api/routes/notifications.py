"""POST /notifications/test."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.schemas import NotificationTestRequest
from backend.auth.dependencies import require_permission
from backend.auth.models import User
from backend.notifications.notification_manager import notification_manager

router = APIRouter()


@router.post("/notifications/test", summary="Send a test notification through the channels configured for a severity")
async def test_notification(
    payload: NotificationTestRequest,
    user: User = Depends(require_permission("notifications:test")),
) -> dict:
    results = notification_manager.notify(payload.severity, "Test Notification", payload.message)
    return {
        "severity": payload.severity,
        "channels_attempted": list(results.keys()),
        "results": {channel: {"success": success, "message": message} for channel, (success, message) in results.items()},
    }
