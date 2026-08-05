"""Tests for NotificationManager."""

from unittest.mock import MagicMock

import pytest

from backend.notifications.notification_manager import NotificationManager


class TestRules:
    def test_default_rules_match_the_spec_example(self, notification_manager):
        assert notification_manager.channels_for("Critical") == ["email", "telegram", "webhook"]
        assert notification_manager.channels_for("High") == ["email"]
        assert notification_manager.channels_for("Medium") == ["telegram"]
        assert notification_manager.channels_for("Low") == ["dashboard"]

    def test_unmapped_severity_returns_empty_list(self, notification_manager):
        assert notification_manager.channels_for("Unmapped") == []

    def test_update_rules_persists_and_reloads(self, notification_manager):
        notification_manager.update_rules({"Critical": ["email"]})
        assert notification_manager.channels_for("Critical") == ["email"]

        reloaded = NotificationManager(rules_path=notification_manager.rules_path)
        assert reloaded.channels_for("Critical") == ["email"]

    def test_update_rules_rejects_unknown_channel(self, notification_manager):
        with pytest.raises(ValueError, match="fax"):
            notification_manager.update_rules({"Critical": ["fax"]})


class TestNotify:
    def test_notify_calls_every_configured_channel(self, notification_manager):
        notification_manager.email_service = MagicMock()
        notification_manager.telegram_service = MagicMock()
        notification_manager.webhook_service = MagicMock()
        notification_manager.email_service.send.return_value = (True, "sent")
        notification_manager.telegram_service.send.return_value = (True, "sent")
        notification_manager.webhook_service.send.return_value = (True, "sent")

        results = notification_manager.notify("Critical", "Subject", "Body")

        assert set(results.keys()) == {"email", "telegram", "webhook"}
        notification_manager.email_service.send.assert_called_once()
        notification_manager.telegram_service.send.assert_called_once()
        notification_manager.webhook_service.send.assert_called_once()

    def test_dashboard_channel_never_calls_an_external_service(self, notification_manager):
        results = notification_manager.notify("Low", "Subject", "Body")
        assert results["dashboard"][0] is True

    def test_notify_reports_per_channel_failure_independently(self, notification_manager):
        notification_manager.email_service = MagicMock()
        notification_manager.email_service.send.return_value = (False, "SMTP down")

        results = notification_manager.notify("High", "Subject", "Body")
        assert results["email"] == (False, "SMTP down")
