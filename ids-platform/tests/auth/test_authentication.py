"""Tests for authentication.py: seeding, login, refresh rotation, logout."""

import pytest
from sqlalchemy import select

from backend.auth import authentication
from backend.auth.authentication import AuthenticationError
from backend.auth.models import Permission, Role, User, UserSession
from backend.core.config import get_settings
from backend.database.models import AuditLog


class TestSeedDefaultData:
    def test_seeds_permissions_roles_and_default_admin(self, db_session):
        authentication.seed_default_data(db_session)
        db_session.commit()

        assert db_session.execute(select(Permission)).first() is not None
        roles = {r.name for r in db_session.execute(select(Role)).scalars().all()}
        assert roles == {"Admin", "Security Analyst", "Viewer"}

        admin_user = db_session.execute(select(User).where(User.username == "admin")).scalars().first()
        assert admin_user is not None
        assert admin_user.role.name == "Admin"

    def test_admin_role_has_every_permission(self, seeded_db):
        admin_role = seeded_db.execute(select(Role).where(Role.name == "Admin")).scalars().first()
        all_permission_names = {p.name for p in seeded_db.execute(select(Permission)).scalars().all()}
        assert {p.name for p in admin_role.permissions} == all_permission_names

    def test_viewer_role_is_read_only(self, seeded_db):
        viewer_role = seeded_db.execute(select(Role).where(Role.name == "Viewer")).scalars().first()
        permission_names = {p.name for p in viewer_role.permissions}
        assert "responses:execute" not in permission_names
        assert "users:write" not in permission_names
        assert "alerts:read" in permission_names

    def test_seeding_twice_does_not_duplicate_or_reset_data(self, seeded_db):
        # An operator may have since deactivated the default admin, or
        # changed a role's permissions - re-seeding on the next restart
        # must never clobber that.
        admin_user = seeded_db.execute(select(User).where(User.username == "admin")).scalars().first()
        admin_user.is_active = False
        seeded_db.commit()

        authentication.seed_default_data(seeded_db)
        seeded_db.commit()

        users = seeded_db.execute(select(User)).scalars().all()
        assert len(users) == 1
        assert users[0].is_active is False  # not reset back to True


class TestLogin:
    def test_login_with_correct_credentials_succeeds(self, seeded_db):
        settings = get_settings()
        access, refresh, expires_in = authentication.login(seeded_db, settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_ADMIN_PASSWORD, "127.0.0.1", "pytest")
        assert access and refresh
        assert expires_in == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    def test_login_with_wrong_password_raises_and_audits_failure(self, seeded_db):
        with pytest.raises(AuthenticationError):
            authentication.login(seeded_db, "admin", "wrong-password", "127.0.0.1", "pytest")

        failure = seeded_db.execute(select(AuditLog).where(AuditLog.action == authentication.audit.LOGIN_FAILED)).scalars().first()
        assert failure is not None
        assert failure.status == "failed"

    def test_login_with_unknown_username_raises_same_error_as_wrong_password(self, seeded_db):
        # Deliberately generic message either way - avoids username enumeration.
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            authentication.login(seeded_db, "no-such-user", "whatever", "127.0.0.1", "pytest")

    def test_successful_login_creates_a_session_and_updates_last_login(self, seeded_db):
        settings = get_settings()
        authentication.login(seeded_db, settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_ADMIN_PASSWORD, "127.0.0.1", "pytest")

        user = seeded_db.execute(select(User).where(User.username == "admin")).scalars().first()
        assert user.last_login_at is not None
        sessions = seeded_db.execute(select(UserSession).where(UserSession.user_id == user.id)).scalars().all()
        assert len(sessions) == 1

    def test_login_of_deactivated_account_fails(self, seeded_db):
        settings = get_settings()
        user = seeded_db.execute(select(User).where(User.username == "admin")).scalars().first()
        user.is_active = False
        seeded_db.commit()

        with pytest.raises(AuthenticationError, match="deactivated"):
            authentication.login(seeded_db, settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_ADMIN_PASSWORD, "127.0.0.1", "pytest")


class TestRefreshRotation:
    def test_refresh_issues_new_tokens(self, seeded_db):
        settings = get_settings()
        _, refresh_token, _ = authentication.login(seeded_db, settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_ADMIN_PASSWORD, "127.0.0.1", "pytest")

        new_access, new_refresh, _ = authentication.refresh_access_token(seeded_db, refresh_token, "127.0.0.1", "pytest")
        assert new_access
        assert new_refresh != refresh_token

    def test_reusing_a_rotated_refresh_token_fails(self, seeded_db):
        settings = get_settings()
        _, refresh_token, _ = authentication.login(seeded_db, settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_ADMIN_PASSWORD, "127.0.0.1", "pytest")
        authentication.refresh_access_token(seeded_db, refresh_token, "127.0.0.1", "pytest")

        with pytest.raises(AuthenticationError, match="already been used"):
            authentication.refresh_access_token(seeded_db, refresh_token, "127.0.0.1", "pytest")

    def test_refresh_with_an_access_token_fails(self, seeded_db):
        settings = get_settings()
        access_token, _, _ = authentication.login(seeded_db, settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_ADMIN_PASSWORD, "127.0.0.1", "pytest")

        with pytest.raises(AuthenticationError):
            authentication.refresh_access_token(seeded_db, access_token, "127.0.0.1", "pytest")


class TestLogout:
    def test_logout_revokes_the_session(self, seeded_db):
        settings = get_settings()
        _, refresh_token, _ = authentication.login(seeded_db, settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_ADMIN_PASSWORD, "127.0.0.1", "pytest")

        authentication.logout(seeded_db, refresh_token, "admin", "127.0.0.1")

        with pytest.raises(AuthenticationError):
            authentication.refresh_access_token(seeded_db, refresh_token, "127.0.0.1", "pytest")

    def test_logout_with_an_already_invalid_token_does_not_raise(self, seeded_db):
        authentication.logout(seeded_db, "not-a-real-token", "admin", "127.0.0.1")  # must not raise
