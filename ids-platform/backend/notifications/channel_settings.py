"""
Runtime notification channel settings.

The three channel services (email/telegram/webhook) originally read only
from environment-based Settings. This module adds a per-deployment JSON
store (config/channel_settings.json) whose values *override* the env
defaults at runtime, so an operator can configure SMTP/Telegram/webhook
credentials from the Notification Settings UI without touching .env or
restarting the process.

Precedence: env Settings (defaults) < channel_settings.json (persisted
runtime overrides). Any field left out of the JSON file keeps its env
value, so a partial file is fine and deleting an entry falls back to env.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SETTINGS_PATH = Path(__file__).parent / "config" / "channel_settings.json"

# All keys the Notification Settings UI can edit, per channel. The email
# recipient field is called `to_address` internally but rendered as
# "recipient" in the UI.
VALID_KEYS = {
    "email": {"smtp_host", "smtp_port", "smtp_username", "smtp_password", "from_address", "to_address"},
    "telegram": {"bot_token", "chat_id"},
    "webhook": {"url"},
}

_lock = threading.RLock()
_cache: dict | None = None


def _env_defaults() -> dict:
    from backend.core.config import get_settings

    settings = get_settings()
    return {
        "email": {
            "smtp_host": settings.SMTP_HOST,
            "smtp_port": settings.SMTP_PORT,
            "smtp_username": settings.SMTP_USERNAME,
            "smtp_password": settings.SMTP_PASSWORD,
            "from_address": settings.ALERT_EMAIL_FROM,
            "to_address": settings.ALERT_EMAIL_TO,
        },
        "telegram": {
            "bot_token": settings.TELEGRAM_BOT_TOKEN,
            "chat_id": settings.TELEGRAM_CHAT_ID,
        },
        "webhook": {
            "url": settings.RESPONSE_WEBHOOK_URL,
        },
    }


def _load_file() -> dict:
    path = DEFAULT_SETTINGS_PATH
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        logger.warning("Failed to read %s; using empty overrides", path)
        return {}
    return data if isinstance(data, dict) else {}


def get_channel_settings() -> dict:
    """Merged view: env defaults overridden by the persisted JSON store."""
    global _cache
    with _lock:
        if _cache is None:
            _cache = _load_file()
        merged = _env_defaults()
        for channel, overrides in _cache.items():
            if channel in merged and isinstance(overrides, dict):
                for key, value in overrides.items():
                    if key in VALID_KEYS.get(channel, set()):
                        merged[channel][key] = value
        return merged


def get_channel(channel: str) -> dict:
    return get_channel_settings().get(channel, {})


def save_channel_settings(channel: str, values: dict) -> dict:
    """Persist (some of) one channel's settings. Returns the merged channel view."""
    global _cache
    if channel not in VALID_KEYS:
        raise ValueError(f"Unknown notification channel '{channel}'; valid: {sorted(VALID_KEYS)}")

    unknown = [k for k in values if k not in VALID_KEYS[channel]]
    if unknown:
        raise ValueError(f"Unknown setting(s) for channel '{channel}': {unknown}")

    with _lock:
        _cache = _load_file()
        channel_store = _cache.setdefault(channel, {})
        channel_store.update({k: v for k, v in values.items() if v is not None})

        path = DEFAULT_SETTINGS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_cache, f, indent=2, sort_keys=True)

    logger.info("Notification channel settings updated: %s", channel)
    return get_channel(channel)
