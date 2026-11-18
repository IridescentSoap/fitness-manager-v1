"""T1 acceptance: T01/T02/T27, CSRF, login rate limit, permissions."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


ADMIN_PASSWORD = "AdminPass123!"
USER_PASSWORD = "UserPass1234!"


def _init_admin(client: TestClient) -> dict:
    response = client.post(
        "/api/setup/initialize",
        json={
            "username": "admin",
            "display_name": "管理员",
            "password": ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _csrf_headers(csrf_token: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf_token}


def test_t01_initialize_only_from_loopback_once(client: TestClient, remote_client: TestClient) -> None:
    status = client.get("/api/setup/status")
    assert status.status_code == 200
    assert status.json()["data"]["initialized"] is False

    remote = remote_client.post(
        "/api/setup/initialize",
        json={
            "username": "admin",
            "display_name": "管理员",
            "password": ADMIN_PASSWORD,
        },
    )
    assert remote.status_code == 403
    assert remote.json()["error"]["code"] == "FORBIDDEN"

    first = _init_admin(client)
    assert first["user"]["role"] == "ADMIN"
    assert first["csrf_token"]

    again = client.post(
        "/api/setup/initialize",
        json={
            "username": "admin2",
            "display_name": "管理员2",
            "password": ADMIN_PASSWORD,
        },
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ALREADY_INITIALIZED"

    status_after = client.get("/api/setup/status")
    assert status_after.json()["data"]["initialized"] is True


def test_login_logout_me_and_csrf_required(client: TestClient) -> None:
    _init_admin(client)
    data = _login(client, "admin", ADMIN_PASSWORD)
    assert data["user"]["username"] == "admin"
    assert data["csrf_token"]

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["data"]["user"]["display_name"] == "管理员"
    csrf = me.json()["data"]["csrf_token"]
    assert csrf

    # Mutation without CSRF must fail.
    no_csrf = client.post("/api/auth/logout")
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "CSRF_FAILED"

    logout = client.post("/api/auth/logout", headers=_csrf_headers(csrf))
    assert logout.status_code == 204

    me_after = client.get("/api/auth/me")
    assert me_after.status_code == 401


def test_login_rate_limited(client: TestClient) -> None:
    _init_admin(client)
    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


def test_t27_disable_and_reset_password_invalidate_sessions(client: TestClient) -> None:
    _init_admin(client)
    admin = _login(client, "admin", ADMIN_PASSWORD)
    admin_csrf = admin["csrf_token"]

    created = client.post(
        "/api/admin/users",
        headers=_csrf_headers(admin_csrf),
        json={
            "username": "alice",
            "display_name": "Alice",
            "password": USER_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["data"]["id"]

    user_client = client  # same jar; login as alice after
    # Use a second client for alice session isolation.
    from app.main import create_app
    from app.core.config import get_settings

    get_settings.cache_clear()
    alice_app = create_app()
    with TestClient(alice_app, base_url="http://127.0.0.1") as alice:
        alice_login = _login(alice, "alice", USER_PASSWORD)
        alice_csrf = alice_login["csrf_token"]
        assert alice.get("/api/auth/me").status_code == 200

        # Admin resets password -> old alice session dies.
        reset = client.post(
            f"/api/admin/users/{user_id}/reset-password",
            headers=_csrf_headers(admin_csrf),
            json={"new_password": "NewUserPass12!"},
        )
        assert reset.status_code == 200, reset.text
        assert alice.get("/api/auth/me").status_code == 401

        # Re-login with new password, then disable.
        alice_login2 = _login(alice, "alice", "NewUserPass12!")
        assert alice.get("/api/auth/me").status_code == 200

        disabled = client.patch(
            f"/api/admin/users/{user_id}",
            headers=_csrf_headers(admin_csrf),
            json={"status": "DISABLED"},
        )
        assert disabled.status_code == 200, disabled.text
        assert alice.get("/api/auth/me").status_code == 401


def test_t02_user_isolation_on_exercises(client: TestClient) -> None:
    _init_admin(client)
    admin = _login(client, "admin", ADMIN_PASSWORD)
    admin_csrf = admin["csrf_token"]

    for username, display in (("alice", "Alice"), ("bob", "Bob")):
        response = client.post(
            "/api/admin/users",
            headers=_csrf_headers(admin_csrf),
            json={
                "username": username,
                "display_name": display,
                "password": USER_PASSWORD,
            },
        )
        assert response.status_code == 201, response.text

    from app.main import create_app
    from app.core.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    with TestClient(app, base_url="http://127.0.0.1") as alice, TestClient(
        app, base_url="http://127.0.0.1"
    ) as bob:
        a = _login(alice, "alice", USER_PASSWORD)
        b = _login(bob, "bob", USER_PASSWORD)

        created = alice.post(
            "/api/exercises",
            headers=_csrf_headers(a["csrf_token"]),
            json={
                "name": "Alice私有动作",
                "category": "STRENGTH",
                "description": "仅Alice可见细节管理",
            },
        )
        assert created.status_code == 201, created.text
        exercise_id = created.json()["data"]["id"]

        # Bob cannot read or mutate Alice's custom exercise by ID.
        assert bob.get(f"/api/exercises/{exercise_id}").status_code == 404
        patch = bob.patch(
            f"/api/exercises/{exercise_id}",
            headers=_csrf_headers(b["csrf_token"]),
            json={"name": "被篡改"},
        )
        assert patch.status_code == 404

        # Alice list contains own + system presets; Bob list must not include Alice's name.
        alice_list = alice.get("/api/exercises").json()["data"]["items"]
        bob_list = bob.get("/api/exercises").json()["data"]["items"]
        assert any(item["id"] == exercise_id for item in alice_list)
        assert all(item["id"] != exercise_id for item in bob_list)
        assert any(item["owner_user_id"] is None for item in bob_list)


def test_change_password_invalidates_other_sessions(client: TestClient) -> None:
    _init_admin(client)
    from app.main import create_app
    from app.core.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    with TestClient(app, base_url="http://127.0.0.1") as c1, TestClient(
        app, base_url="http://127.0.0.1"
    ) as c2:
        d1 = _login(c1, "admin", ADMIN_PASSWORD)
        d2 = _login(c2, "admin", ADMIN_PASSWORD)
        assert c2.get("/api/auth/me").status_code == 200

        changed = c1.patch(
            "/api/auth/password",
            headers=_csrf_headers(d1["csrf_token"]),
            json={"old_password": ADMIN_PASSWORD, "new_password": "AdminPass999!"},
        )
        assert changed.status_code == 200, changed.text
        assert c2.get("/api/auth/me").status_code == 401
        assert c1.get("/api/auth/me").status_code == 200


def test_short_password_accepted_on_create_and_login(client: TestClient) -> None:
    _init_admin(client)
    admin = _login(client, "admin", ADMIN_PASSWORD)
    created = client.post(
        "/api/admin/users",
        headers=_csrf_headers(admin["csrf_token"]),
        json={"username": "shorty", "display_name": "Shorty", "password": "1"},
    )
    assert created.status_code == 201, created.text
    logged = client.post("/api/auth/login", json={"username": "shorty", "password": "1"})
    assert logged.status_code == 200, logged.text


def test_settings_sharing_defaults_private(client: TestClient) -> None:
    _init_admin(client)
    admin = _login(client, "admin", ADMIN_PASSWORD)
    sharing = client.get("/api/settings/sharing")
    assert sharing.status_code == 200
    data = sharing.json()["data"]
    assert data == {
        "share_training_stats": False,
        "share_weight_change": False,
        "share_weight_values": False,
    }

    updated = client.patch(
        "/api/settings/sharing",
        headers=_csrf_headers(admin["csrf_token"]),
        json={
            "share_training_stats": True,
            "share_weight_change": False,
            "share_weight_values": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["share_training_stats"] is True
