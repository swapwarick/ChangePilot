"""Auth endpoint tests — using FastAPI's synchronous TestClient.

Run with:
    cd backend
    pytest tests/test_auth.py -v
"""
import uuid
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _uid() -> str:
    """Short unique suffix to prevent username conflicts across test runs."""
    return uuid.uuid4().hex[:6]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_success():
    u = _uid()
    res = client.post("/auth/register", json={
        "username": f"reguser_{u}",
        "password": "securepass123",
        "email": f"reguser_{u}@example.com",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == f"reguser_{u}"
    assert data["tier"] == "registered"
    assert "access_token" in data
    assert "refresh_token" in data


def test_register_duplicate_username():
    u = _uid()
    payload = {"username": f"dup_{u}", "password": "password123"}
    client.post("/auth/register", json=payload)
    res = client.post("/auth/register", json=payload)
    assert res.status_code == 409


def test_register_short_password():
    res = client.post("/auth/register", json={"username": f"sp_{_uid()}", "password": "123"})
    assert res.status_code == 422


def test_register_short_username():
    res = client.post("/auth/register", json={"username": "a", "password": "validpassword"})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_success():
    u = _uid()
    client.post("/auth/register", json={"username": f"login_{u}", "password": "mypassword1"})
    res = client.post("/auth/login", json={"username": f"login_{u}", "password": "mypassword1"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password():
    u = _uid()
    client.post("/auth/register", json={"username": f"wpw_{u}", "password": "correctpassword"})
    res = client.post("/auth/login", json={"username": f"wpw_{u}", "password": "wrongpassword"})
    assert res.status_code == 401


def test_login_unknown_user():
    res = client.post("/auth/login", json={"username": f"nobody_{_uid()}", "password": "any"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Guest session
# ---------------------------------------------------------------------------


def test_guest_session():
    res = client.post("/auth/guest")
    assert res.status_code == 201
    data = res.json()
    assert data["tier"] == "guest"
    assert data["username"].startswith("guest_")


# ---------------------------------------------------------------------------
# /me endpoint
# ---------------------------------------------------------------------------


def test_me_authenticated():
    u = _uid()
    reg = client.post("/auth/register", json={"username": f"me_{u}", "password": "mepassword1"})
    token = reg.json()["access_token"]
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == f"me_{u}"
    assert body["tier"] == "registered"
    assert "storage_used_bytes" in body
    assert "storage_quota_bytes" in body


def test_me_unauthenticated():
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_me_invalid_token():
    res = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


def test_token_refresh():
    u = _uid()
    reg = client.post("/auth/register", json={"username": f"refresh_{u}", "password": "refreshpass1"})
    data = reg.json()
    res = client.post("/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert res.status_code == 200
    new_data = res.json()
    assert "access_token" in new_data
    # Refresh token should be rotated
    assert new_data["refresh_token"] != data["refresh_token"]


def test_token_refresh_invalid():
    res = client.post("/auth/refresh", json={"refresh_token": "invalid.token.here"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


def test_logout_registered():
    u = _uid()
    reg = client.post("/auth/register", json={"username": f"logout_{u}", "password": "logoutpass1"})
    token = reg.json()["access_token"]
    res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 204


def test_guest_logout_purges_data():
    """Guest logout should return 204 and purge guest account."""
    guest = client.post("/auth/guest")
    token = guest.json()["access_token"]
    res = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 204


# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------


def test_auth_config():
    res = client.get("/auth/config")
    assert res.status_code == 200
    assert "is_cloud" in res.json()
