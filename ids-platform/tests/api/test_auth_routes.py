"""
Tests for the auth REST API: login/refresh/logout/register/me/profile, and
protected-endpoint enforcement (401 unauthenticated, 403 wrong role) across
several existing endpoints from earlier milestones.
"""

from backend.core.config import get_settings


class TestLogin:
    def test_login_with_default_admin_succeeds(self, unauthenticated_client):
        settings = get_settings()
        response = unauthenticated_client.post("/auth/login", json={
            "username": settings.DEFAULT_ADMIN_USERNAME, "password": settings.DEFAULT_ADMIN_PASSWORD,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] and body["refresh_token"]
        assert body["token_type"] == "bearer"

    def test_login_with_wrong_password_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert response.status_code == 401


class TestProtectedEndpoints:
    def test_alerts_without_token_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.get("/alerts")
        assert response.status_code == 401

    def test_predict_without_token_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.post("/predict", json={"features": {}})
        assert response.status_code == 401

    def test_responses_without_token_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.get("/responses")
        assert response.status_code == 401

    def test_response_rules_without_token_returns_401(self, unauthenticated_client):
        response = unauthenticated_client.get("/response-rules")
        assert response.status_code == 401

    def test_health_remains_public_no_token_needed(self, unauthenticated_client):
        # Deliberately unauthenticated - health checks need to work for
        # infra monitoring tools that don't hold API credentials.
        response = unauthenticated_client.get("/health")
        assert response.status_code == 200

    def test_admin_client_fixture_can_reach_every_protected_endpoint(self, client):
        # `client` auto-authenticates as the seeded Admin (see conftest.py) -
        # Admin has every permission, so nothing should 401/403 here.
        for path in ["/alerts", "/flows", "/statistics", "/attacks/top", "/system/health", "/responses", "/response-rules"]:
            response = client.get(path)
            assert response.status_code == 200, f"{path} -> {response.status_code}: {response.text}"


class TestRolePermissions:
    def _register_and_login(self, client, username, role):
        settings = get_settings()
        # Registration itself requires no auth (see routes.py) - self-service signup.
        register_response = client.post("/auth/register", json={
            "username": username, "email": f"{username}@example.com", "password": "Passw0rd123", "role": role,
        })
        assert register_response.status_code == 201, register_response.text

        login_response = client.post("/auth/login", json={"username": username, "password": "Passw0rd123"})
        assert login_response.status_code == 200
        return login_response.json()["access_token"]

    def test_viewer_can_read_alerts(self, unauthenticated_client):
        token = self._register_and_login(unauthenticated_client, "viewer1", "Viewer")
        response = unauthenticated_client.get("/alerts", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    def test_viewer_cannot_execute_responses(self, unauthenticated_client):
        token = self._register_and_login(unauthenticated_client, "viewer2", "Viewer")
        response = unauthenticated_client.post(
            "/responses/execute", json={"alert_id": "does-not-matter"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_viewer_cannot_manage_users(self, unauthenticated_client):
        token = self._register_and_login(unauthenticated_client, "viewer3", "Viewer")
        response = unauthenticated_client.get("/users", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    def test_security_analyst_can_execute_responses(self, unauthenticated_client):
        token = self._register_and_login(unauthenticated_client, "analyst1", "Security Analyst")
        # A real alert doesn't exist, so this correctly 404s rather than
        # 403 - proving the permission check passed and execution was attempted.
        response = unauthenticated_client.post(
            "/responses/execute", json={"alert_id": "does-not-exist"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_security_analyst_cannot_write_settings(self, unauthenticated_client):
        token = self._register_and_login(unauthenticated_client, "analyst2", "Security Analyst")
        response = unauthenticated_client.put(
            "/response-rules", json={"simulation_mode": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_admin_can_list_users_and_roles_and_audit_log(self, client):
        assert client.get("/users").status_code == 200
        assert client.get("/roles").status_code == 200
        assert client.get("/audit").status_code == 200


class TestRefreshAndLogout:
    def test_full_login_refresh_logout_cycle(self, unauthenticated_client):
        settings = get_settings()
        login_response = unauthenticated_client.post("/auth/login", json={
            "username": settings.DEFAULT_ADMIN_USERNAME, "password": settings.DEFAULT_ADMIN_PASSWORD,
        })
        tokens = login_response.json()

        refresh_response = unauthenticated_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert new_tokens["refresh_token"] != tokens["refresh_token"]

        logout_response = unauthenticated_client.post(
            "/auth/logout", json={"refresh_token": new_tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
        )
        assert logout_response.status_code == 204

        second_refresh = unauthenticated_client.post("/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
        assert second_refresh.status_code == 401

    def test_me_returns_current_user_profile(self, client):
        response = client.get("/auth/me")
        assert response.status_code == 200
        body = response.json()
        assert body["username"] == "admin"
        assert body["role"] == "Admin"

    def test_update_profile_requires_correct_current_password(self, client):
        response = client.put("/auth/profile", json={"current_password": "wrong", "new_password": "NewPassw0rd1"})
        assert response.status_code == 400

    def test_update_profile_changes_password_successfully(self, client):
        settings = get_settings()
        response = client.put("/auth/profile", json={"current_password": settings.DEFAULT_ADMIN_PASSWORD, "new_password": "NewPassw0rd1"})
        assert response.status_code == 200


class TestPasswordResetPlaceholder:
    def test_forgot_password_always_returns_generic_message(self, unauthenticated_client):
        # Same response whether or not the email is registered - no user enumeration.
        r1 = unauthenticated_client.post("/auth/forgot-password", json={"email": "admin@example.com"})
        r2 = unauthenticated_client.post("/auth/forgot-password", json={"email": "no-such-user@example.com"})
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json() == r2.json()
