"""Tests for email_service.py, telegram_service.py, webhook_service.py."""

from unittest.mock import patch

from backend.notifications.email_service import EmailService
from backend.notifications.telegram_service import TelegramService
from backend.notifications.webhook_service import WebhookService


class TestEmailService:
    def test_unconfigured_smtp_returns_failure_without_raising(self, monkeypatch):
        from backend.core.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("SMTP_HOST", "")
        get_settings.cache_clear()

        success, message = EmailService().send("a@example.com", "Subject", "Body")
        assert success is False
        assert "not configured" in message
        get_settings.cache_clear()

    def test_configured_smtp_sends_successfully(self, monkeypatch):
        from backend.core.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        get_settings.cache_clear()

        with patch("backend.notifications.email_service.smtplib.SMTP") as mock_smtp:
            success, message = EmailService().send("a@example.com", "Subject", "Body")
        assert success is True
        assert "sent" in message
        mock_smtp.assert_called_once()
        get_settings.cache_clear()

    def test_smtp_exception_is_caught_and_reported_as_failure(self, monkeypatch):
        from backend.core.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        get_settings.cache_clear()

        with patch("backend.notifications.email_service.smtplib.SMTP", side_effect=RuntimeError("connection refused")):
            success, message = EmailService().send("a@example.com", "Subject", "Body")
        assert success is False
        assert "failed" in message.lower()
        get_settings.cache_clear()


class TestTelegramService:
    def test_unconfigured_returns_failure(self, monkeypatch):
        from backend.core.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        get_settings.cache_clear()

        success, message = TelegramService().send("hello")
        assert success is False
        get_settings.cache_clear()

    def test_configured_sends_via_requests(self, monkeypatch):
        from backend.core.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        get_settings.cache_clear()

        with patch("backend.notifications.telegram_service.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = lambda: None
            success, message = TelegramService().send("hello")
        assert success is True
        mock_post.assert_called_once()
        get_settings.cache_clear()


class TestWebhookService:
    def test_unconfigured_returns_failure(self, monkeypatch):
        from backend.core.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("RESPONSE_WEBHOOK_URL", "")
        get_settings.cache_clear()

        success, message = WebhookService().send({"key": "value"})
        assert success is False
        get_settings.cache_clear()

    def test_configured_posts_payload(self, monkeypatch):
        from backend.core.config import get_settings
        get_settings.cache_clear()
        monkeypatch.setenv("RESPONSE_WEBHOOK_URL", "https://example.com/hook")
        get_settings.cache_clear()

        with patch("backend.notifications.webhook_service.requests.post") as mock_post:
            mock_post.return_value.raise_for_status = lambda: None
            success, message = WebhookService().send({"key": "value"})
        assert success is True
        mock_post.assert_called_once_with("https://example.com/hook", json={"key": "value"}, timeout=10)
        get_settings.cache_clear()
