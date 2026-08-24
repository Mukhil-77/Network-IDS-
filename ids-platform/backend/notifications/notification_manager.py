"""
Configurable severity -> channel notification rules, loaded from
notification_rules.yaml (same pattern as response_engine/response_rules.py's
PolicyEngine - a second YAML-configured rules engine, not a copy-pasted one:
this one decides *where to notify*, that one decides *what response
actions to run*; a "Critical" policy's `send_email` action and this
module's own Critical -> [email, ...] rule are two independent, optional
paths to the same EmailService - see this module's docstring at the bottom
for how the two relate).

Primary use in this milestone: POST /notifications/test, so an operator
can verify a channel is configured correctly without waiting for a real
alert. Available for other code to call `notify()` directly too.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

import yaml

from backend.notifications.email_service import EmailService, email_service as default_email_service
from backend.notifications.telegram_service import TelegramService, telegram_service as default_telegram_service
from backend.notifications.webhook_service import WebhookService, webhook_service as default_webhook_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RULES_PATH = Path(__file__).parent / "config" / "notification_rules.yaml"
VALID_CHANNELS = {"email", "telegram", "webhook", "dashboard"}


def _resolve_rules_path() -> Path:
    """
    Desktop-app packaging: the default path lives next to the code (read-only
    in a frozen PyInstaller build), but update_rules() writes it back, so the
    Electron shell points NOTIFICATION_RULES_PATH at a writable user-data copy.
    Falls back to the packaged default when unset (normal/bundled dev).
    """
    override = os.environ.get("NOTIFICATION_RULES_PATH")
    if override:
        return Path(override)
    return DEFAULT_RULES_PATH


class NotificationManager:
    def __init__(
        self,
        rules_path: Optional[Path] = None,
        email_service: EmailService = default_email_service,
        telegram_service: TelegramService = default_telegram_service,
        webhook_service: WebhookService = default_webhook_service,
    ):
        self.rules_path = rules_path or _resolve_rules_path()
        self.email_service = email_service
        self.telegram_service = telegram_service
        self.webhook_service = webhook_service
        self._lock = threading.RLock()
        self._rules: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.rules_path.is_file():
                logger.warning("Notification rules file not found at %s; using empty rule set", self.rules_path)
                self._rules = {}
                return
            with open(self.rules_path) as f:
                data = yaml.safe_load(f) or {}
            self._rules = {str(k): list(v) for k, v in data.items()}

    def get_rules(self) -> dict[str, list[str]]:
        with self._lock:
            return {severity: list(channels) for severity, channels in self._rules.items()}

    def update_rules(self, rules: dict[str, list[str]]) -> None:
        for severity, channels in rules.items():
            unknown = [c for c in channels if c not in VALID_CHANNELS]
            if unknown:
                raise ValueError(f"Unknown channel(s) for severity '{severity}': {unknown}. Valid channels: {sorted(VALID_CHANNELS)}")

        with self._lock:
            self._rules = {k: list(v) for k, v in rules.items()}
            self.rules_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.rules_path, "w") as f:
                yaml.safe_dump(self._rules, f, sort_keys=False)
        logger.info("Notification rules updated")

    def channels_for(self, severity: str) -> list[str]:
        with self._lock:
            return list(self._rules.get(severity, []))

    def notify(self, severity: str, subject: str, body: str, webhook_payload: Optional[dict] = None) -> dict[str, tuple[bool, str]]:
        """
        Sends `subject`/`body` over every channel configured for `severity`.
        Returns {channel: (success, message)} for every channel attempted -
        "dashboard" always reports (True, "...") without an external call
        (see this module's docstring).
        """
        results: dict[str, tuple[bool, str]] = {}
        for channel in self.channels_for(severity):
            if channel == "email":
                results["email"] = self.email_service.send(_default_recipient(), subject, body)
            elif channel == "telegram":
                results["telegram"] = self.telegram_service.send(f"{subject}\n\n{body}")
            elif channel == "webhook":
                results["webhook"] = self.webhook_service.send(webhook_payload or {"subject": subject, "body": body})
            elif channel == "dashboard":
                results["dashboard"] = (True, "Delivered via the existing WebSocket alert broadcast (no separate action needed)")
            else:
                results[channel] = (False, f"Unknown channel '{channel}'")

        logger.info("Notification dispatched for severity=%s -> %s", severity, {c: r[0] for c, r in results.items()})
        return results


def _default_recipient() -> str:
    from backend.core.config import get_settings
    return get_settings().ALERT_EMAIL_TO


# Process-wide instance.
notification_manager = NotificationManager()
