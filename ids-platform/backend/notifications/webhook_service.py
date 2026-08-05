"""Low-level webhook delivery, extracted from response_engine/notifications.py (see email_service.py's docstring for why)."""

from __future__ import annotations

import requests

from backend.core.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WebhookService:
    def send(self, payload: dict) -> tuple[bool, str]:
        settings = get_settings()
        if not settings.RESPONSE_WEBHOOK_URL:
            return False, "No webhook URL configured (RESPONSE_WEBHOOK_URL unset)"

        try:
            response = requests.post(settings.RESPONSE_WEBHOOK_URL, json=payload, timeout=10)
            response.raise_for_status()
            return True, f"Webhook delivered to {settings.RESPONSE_WEBHOOK_URL}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Webhook delivery failed: %s", exc)
            return False, f"Webhook delivery failed: {exc}"


webhook_service = WebhookService()
