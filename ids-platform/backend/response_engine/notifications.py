"""
Notification actions: send_email, send_telegram, webhook_notification, and
log_response (an always-safe, log-only action used by the "Low" severity
policy - see response_rules.yaml).

Milestone 10: the actual sending logic (SMTP/Telegram API/webhook POST)
moved to backend/notifications/{email,telegram,webhook}_service.py, so
it's shared with the new NotificationManager rather than existing twice.
This module now only handles the response-engine-specific concerns: the
simulation/live gate, building the incident subject/body, and wrapping the
result as an ActionResult.

Simulation mode never places the real network call and logs what it would
have sent; live mode delegates to the shared service, which itself no-ops
gracefully (returns success=False with an explanatory message) if the
relevant setting isn't configured - either way this action never raises.
"""

from __future__ import annotations

import time

from backend.core.config import get_settings
from backend.database.connection import session_scope
from backend.database.models import AuditLog
from backend.notifications.email_service import email_service
from backend.notifications.telegram_service import telegram_service
from backend.notifications.webhook_service import webhook_service
from backend.response_engine.response_registry import ActionResult, ResponseContext, register_action
from backend.response_engine.simulation import resolve_mode
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _incident_subject(context: ResponseContext) -> str:
    return f"[IDS Alert] {context.severity}: {context.attack_type} from {context.source_ip}"


def _incident_body(context: ResponseContext) -> str:
    return (
        f"Attack type: {context.attack_type}\n"
        f"Severity: {context.severity}\n"
        f"Source IP: {context.source_ip}\n"
        f"Destination IP: {context.destination_ip}\n"
        f"Alert ID: {context.alert_id}\n"
        f"Flow ID: {context.flow_id}\n"
    )


def send_email(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    mode = resolve_mode(context.mode)
    subject = _incident_subject(context)

    if mode == "live":
        success, message = email_service.send(get_settings().ALERT_EMAIL_TO, subject, _incident_body(context))
    else:
        success, message = True, f"[SIMULATION] Would email '{subject}' to configured recipient"

    logger.info("send_email mode=%s success=%s", mode, success)
    return ActionResult(
        action="send_email", status="success" if success else "failed", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000, metadata={"mode": mode},
    )


def send_telegram(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    mode = resolve_mode(context.mode)
    text = f"{_incident_subject(context)}\n\n{_incident_body(context)}"

    if mode == "live":
        success, message = telegram_service.send(text)
    else:
        success, message = True, f"[SIMULATION] Would send Telegram message: {_incident_subject(context)}"

    logger.info("send_telegram mode=%s success=%s", mode, success)
    return ActionResult(
        action="send_telegram", status="success" if success else "failed", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000, metadata={"mode": mode},
    )


def webhook_notification(context: ResponseContext) -> ActionResult:
    start = time.perf_counter()
    mode = resolve_mode(context.mode)
    payload = {
        "alert_id": context.alert_id, "attack_type": context.attack_type, "severity": context.severity,
        "source_ip": context.source_ip, "destination_ip": context.destination_ip,
    }

    if mode == "live":
        success, message = webhook_service.send(payload)
    else:
        success, message = True, "[SIMULATION] Would POST incident payload to configured webhook"

    logger.info("webhook_notification mode=%s success=%s", mode, success)
    return ActionResult(
        action="webhook_notification", status="success" if success else "failed", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000, metadata={"mode": mode},
    )


def log_response(context: ResponseContext) -> ActionResult:
    """Always-safe, log-only action - no external call, no live/simulation distinction. Used by the 'Low' severity policy."""
    start = time.perf_counter()
    with session_scope() as db:
        db.add(AuditLog(
            actor=context.operator, action="response_logged", target=context.alert_id,
            details={"severity": context.severity, "attack_type": context.attack_type},
        ))

    message = f"Logged: {context.attack_type} ({context.severity}) from {context.source_ip}"
    logger.info(message)
    return ActionResult(
        action="log_response", status="success", message=message,
        rollback_available=False, execution_time_ms=(time.perf_counter() - start) * 1000, metadata={},
    )


register_action("send_email", send_email)
register_action("send_telegram", send_telegram)
register_action("webhook_notification", webhook_notification)
register_action("log_response", log_response)
