"""
Low-level email sending. Extracted here (Milestone 10) from what used to
be inline smtplib code inside response_engine/notifications.py's send_email
action - that action now delegates to this class instead of duplicating
the SMTP logic, per this milestone's "reuse, don't duplicate" instruction.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from backend.notifications.channel_settings import get_channel
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    def _config(self) -> dict:
        # Runtime store overrides env defaults; see channel_settings.py.
        return get_channel("email")

    def send(self, to: str, subject: str, body: str) -> tuple[bool, str]:
        """
        Returns (success, message). Never raises - a notification failure
        must never crash whatever triggered it (a response action, a test
        button, etc.) - the caller decides what to do with a failure.
        """
        cfg = self._config()
        smtp_host = cfg.get("smtp_host") or ""
        if not smtp_host or not to:
            return False, "SMTP not configured (SMTP_HOST unset) or no recipient given"

        try:
            from_address = cfg.get("from_address") or cfg.get("smtp_username") or ""
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = from_address
            msg["To"] = to
            msg.set_content(body)

            port = int(cfg.get("smtp_port") or 587)
            with smtplib.SMTP(smtp_host, port, timeout=10) as server:
                server.starttls()
                if cfg.get("smtp_username"):
                    server.login(cfg.get("smtp_username"), cfg.get("smtp_password") or "")
                server.send_message(msg)
            return True, f"Email sent to {to}"
        except Exception as exc:  # noqa: BLE001 - notification delivery must degrade gracefully, never raise
            logger.warning("Email send failed: %s", exc)
            return False, f"Email send failed: {exc}"


email_service = EmailService()
