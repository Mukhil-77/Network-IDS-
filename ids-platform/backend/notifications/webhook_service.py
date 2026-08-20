"""Low-level webhook delivery, extracted from response_engine/notifications.py (see email_service.py's docstring for why)."""

from __future__ import annotations

import requests

from backend.notifications.channel_settings import get_channel
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WebhookService:
    def send(self, payload: dict) -> tuple[bool, str]:
        # Runtime store overrides env defaults; see channel_settings.py.
        url = get_channel("webhook").get("url") or ""
        if not url:
            return False, "No webhook URL configured (RESPONSE_WEBHOOK_URL unset)"

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True, f"Webhook delivered to {url}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Webhook delivery failed: %s", exc)
            return False, f"Webhook delivery failed: {exc}"


webhook_service = WebhookService()
