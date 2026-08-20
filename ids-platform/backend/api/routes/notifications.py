"""
Notification endpoints.

    POST /notifications/test       Send a test notification per severity
    GET  /notifications/rules      Severity -> channel rule map
    PUT  /notifications/rules      Persist the rule map
    GET  /notifications/settings   Channel credentials (runtime store over env)
    PUT  /notifications/settings   Persist channel credentials
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.schemas import NotificationTestRequest
from backend.auth.dependencies import require_permission
from backend.auth.models import User
from backend.notifications.channel_settings import save_channel_settings
from backend.notifications.notification_manager import (
    VALID_CHANNELS,
    notification_manager,
)
from backend.notifications import channel_settings as channel_settings_store

router = APIRouter()

SEVERITIES = ["Critical", "High", "Medium", "Low"]


class NotificationRulesUpdate(BaseModel):
    rules: Dict[str, list[str]] = Field(..., description="severity -> channel list")


class NotificationSettingsUpdate(BaseModel):
    email: Dict[str, Any] = Field(None, description="smtp_host/smtp_port/smtp_username/smtp_password/from_address/to_address")
    telegram: Dict[str, Any] = Field(None, description="bot_token/chat_id")
    webhook: Dict[str, Any] = Field(None, description="url")


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


@router.get("/notifications/rules", summary="Current severity -> channel notification rules")
async def get_rules(_: User = Depends(require_permission("notifications:test"))) -> dict:
    return notification_manager.get_rules()


@router.put("/notifications/rules", summary="Persist severity -> channel notification rules")
async def put_rules(
    payload: NotificationRulesUpdate,
    _: User = Depends(require_permission("notifications:test")),
) -> dict:
    unknown = [sev for sev in payload.rules if sev not in SEVERITIES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown severity(ies): {unknown}. Valid: {SEVERITIES}",
        )
    for sev, channels in payload.rules.items():
        bad = [c for c in channels if c not in VALID_CHANNELS]
        if bad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown channel(s) for '{sev}': {bad}. Valid: {sorted(VALID_CHANNELS)}",
            )
    notification_manager.update_rules(payload.rules)
    return notification_manager.get_rules()


@router.get("/notifications/settings", summary="Channel credentials (env defaults overridden by runtime store)")
async def get_settings(_: User = Depends(require_permission("notifications:test"))) -> dict:
    return channel_settings_store.get_channel_settings()


@router.put("/notifications/settings", summary="Persist channel credentials in the runtime store")
async def put_settings(
    payload: NotificationSettingsUpdate,
    _: User = Depends(require_permission("notifications:test")),
) -> dict:
    for channel, values in [("email", payload.email), ("telegram", payload.telegram), ("webhook", payload.webhook)]:
        if values is not None:
            try:
                save_channel_settings(channel, values)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return channel_settings_store.get_channel_settings()
