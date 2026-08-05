"""Low-level Telegram sending, extracted from response_engine/notifications.py (see email_service.py's docstring for why)."""

from __future__ import annotations

import requests

from backend.core.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramService:
    def send(self, text: str) -> tuple[bool, str]:
        settings = get_settings()
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            return False, "Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID unset)"

        try:
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            response = requests.post(url, json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text}, timeout=10)
            response.raise_for_status()
            return True, "Telegram message sent"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram send failed: %s", exc)
            return False, f"Telegram send failed: {exc}"


telegram_service = TelegramService()
