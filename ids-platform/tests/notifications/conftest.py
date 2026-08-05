import pytest

from backend.notifications.notification_manager import NotificationManager


@pytest.fixture
def notification_manager(tmp_path):
    """A NotificationManager backed by a throwaway rules file, with fake underlying services."""
    import shutil
    from backend.notifications.notification_manager import DEFAULT_RULES_PATH

    test_rules_path = tmp_path / "notification_rules.yaml"
    shutil.copy(DEFAULT_RULES_PATH, test_rules_path)
    return NotificationManager(rules_path=test_rules_path)
