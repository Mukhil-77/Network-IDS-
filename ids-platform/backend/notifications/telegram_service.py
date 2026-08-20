"""Low-level Telegram sending, extracted from response_engine/notifications.py (see email_service.py's docstring for why)."""

from __future__ import annotations

import requests

from backend.notifications.channel_settings import get_channel
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramService:
    def send(self, text: str) -> tuple[bool, str]:
        # Runtime store overrides env defaults; see channel_settings.py.
        cfg = get_channel("telegram")
        bot_token = cfg.get("bot_token") or ""
        chat_id = cfg.get("chat_id") or ""
        if not bot_token or not chat_id:
            return False, "Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID unset)"

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            response = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
            response.raise_for_status()
            return True, "Telegram message sent"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram send failed: %s", exc)
            return False, f"Telegram send failed: {exc}"


telegram_service = TelegramService()
