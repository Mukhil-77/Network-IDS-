"""Tests for authorization.py."""

from sqlalchemy import select

from backend.auth.authorization import has_any_permission, has_permission, has_role, user_permissions
from backend.auth.models import Role, User


def get_user_with_role(db, role_name: str, username: str = "test-user") -> User:
    role = db.execute(select(Role).where(Role.name == role_name)).scalars().first()
    user = User(username=username, email=f"{username}@example.com", hashed_password="x", role_id=role.id)
    db.add(user)
    db.flush()
    return user


class TestHasPermission:
    def test_admin_has_a_users_write_permission(self, seeded_db):
        admin = get_user_with_role(seeded_db, "Admin")
        assert has_permission(admin, "users:write") is True

    def test_viewer_lacks_a_users_write_permission(self, seeded_db):
        viewer = get_user_with_role(seeded_db, "Viewer", "viewer-user")
        assert has_permission(viewer, "users:write") is False

    def test_viewer_has_alerts_read(self, seeded_db):
        viewer = get_user_with_role(seeded_db, "Viewer", "viewer-user")
        assert has_permission(viewer, "alerts:read") is True

    def test_security_analyst_can_execute_responses_but_not_manage_users(self, seeded_db):
        analyst = get_user_with_role(seeded_db, "Security Analyst", "analyst-user")
        assert has_permission(analyst, "responses:execute") is True
        assert has_permission(analyst, "users:write") is False


def test_has_any_permission_matches_if_any_one_is_granted(seeded_db):
    viewer = get_user_with_role(seeded_db, "Viewer", "viewer-user2")
    assert has_any_permission(viewer, "users:write", "alerts:read") is True
    assert has_any_permission(viewer, "users:write", "roles:read") is False


def test_has_role(seeded_db):
    admin = get_user_with_role(seeded_db, "Admin", "admin-user2")
    assert has_role(admin, "Admin") is True
    assert has_role(admin, "Viewer", "Security Analyst") is False
    assert has_role(admin, "Admin", "Security Analyst") is True


def test_user_permissions_returns_the_full_set(seeded_db):
    viewer = get_user_with_role(seeded_db, "Viewer", "viewer-user3")
    permissions = user_permissions(viewer)
    assert permissions == {
        "alerts:read", "flows:read", "statistics:read",
        "reports:read", "analytics:read", "threat_intel:read", "incidents:read",
    }
