import time

import jwt
import pytest
from fastapi import Request

from src.config.limiter import limiter, user_or_ip_key_func
from src.config.settings import settings


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset limiter storage before each test."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.mark.anyio
async def test_login_rate_limit(auth_client, test_user):
    """Test POST /api/auth/login rate limiting (10/minute)."""
    login_request = {"email": test_user.email, "password": "testpass"}

    # First 10 requests should proceed (status 200) and include rate limit headers
    for _ in range(10):
        response = await auth_client.post("/api/v1/auth/login", json=login_request)
        assert response.status_code == 200
        assert "x-ratelimit-limit" in response.headers or "X-RateLimit-Limit" in response.headers

    # 11th request should be rate-limited (status 429)
    response = await auth_client.post("/api/v1/auth/login", json=login_request)
    assert response.status_code == 429


@pytest.mark.anyio
async def test_signup_rate_limit(auth_client):
    """Test POST /api/auth/signup rate limiting (5/minute)."""
    signup_request = {"email": "newuser_rl@example.com", "password": "newpassword123"}

    # First 5 requests should proceed (status 200 or 409)
    for _ in range(5):
        response = await auth_client.post("/api/v1/auth/signup", json=signup_request)
        assert response.status_code in (200, 409)

    # 6th request should return 429
    response = await auth_client.post("/api/v1/auth/signup", json=signup_request)
    assert response.status_code == 429


@pytest.mark.anyio
async def test_resend_verification_rate_limit(auth_client):
    """Test POST /api/auth/resend-verification rate limiting (3/minute)."""
    payload = {"email": "test@example.com"}

    for _ in range(3):
        response = await auth_client.post("/api/v1/auth/resend-verification", json=payload)
        assert response.status_code == 200

    # 4th request should return 429
    response = await auth_client.post("/api/v1/auth/resend-verification", json=payload)
    assert response.status_code == 429


@pytest.mark.anyio
async def test_account_sync_rate_limit(auth_client):
    """Test POST /api/accounts/{account_id}/sync rate limiting (3/minute)."""
    fake_account_id = "00000000-0000-0000-0000-000000000001"

    for _ in range(3):
        response = await auth_client.post(f"/api/v1/accounts/{fake_account_id}/sync")
        # May be 404 or 200 depending on DB state, but shouldn't be 429 for the first 3
        assert response.status_code != 429

    # 4th request should be rate-limited (status 429)
    response = await auth_client.post(f"/api/v1/accounts/{fake_account_id}/sync")
    assert response.status_code == 429


@pytest.mark.anyio
async def test_login_rate_limit_garbage_jwt_cannot_bypass(client, test_user):
    """Test that rotating unverified/forged JWTs cannot bypass login rate limiting."""
    login_request = {"email": test_user.email, "password": "wrongpassword"}

    for i in range(10):
        forged_jwt = jwt.encode(
            {"sub": f"attacker_{i}", "user_id": f"fake_id_{i}"},
            "untrusted_secret_key_32bytes_long!",
            algorithm="HS256",
        )
        response = await client.post(
            "/api/v1/auth/login",
            json=login_request,
            headers={"Authorization": f"Bearer {forged_jwt}"},
        )
        assert response.status_code == 401

    forged_jwt_11 = jwt.encode(
        {"sub": "attacker_11", "user_id": "fake_id_11"},
        "untrusted_secret_key_32bytes_long!",
        algorithm="HS256",
    )
    response = await client.post(
        "/api/v1/auth/login",
        json=login_request,
        headers={"Authorization": f"Bearer {forged_jwt_11}"},
    )
    assert response.status_code == 429


@pytest.mark.anyio
async def test_login_rate_limit_garbage_jwt_with_valid_creds(client, test_user):
    """Test that valid login attempts with rotating forged JWT headers still rate limit by IP."""
    login_request = {"email": test_user.email, "password": "testpass"}

    for i in range(10):
        forged_jwt = jwt.encode(
            {"sub": f"attacker_{i}", "user_id": f"fake_id_{i}"},
            "untrusted_secret_key_32bytes_long!",
            algorithm="HS256",
        )
        response = await client.post(
            "/api/v1/auth/login",
            json=login_request,
            headers={"Authorization": f"Bearer {forged_jwt}"},
        )
        assert response.status_code == 200
        client.cookies.clear()

    forged_jwt_11 = jwt.encode(
        {"sub": "attacker_11", "user_id": "fake_id_11"},
        "untrusted_secret_key_32bytes_long!",
        algorithm="HS256",
    )
    response = await client.post(
        "/api/v1/auth/login",
        json=login_request,
        headers={"Authorization": f"Bearer {forged_jwt_11}"},
    )
    assert response.status_code == 429


def _build_request(
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    client_ip: str = "192.168.1.100",
) -> Request:
    header_list = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        header_list.append((b"cookie", cookie_header.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": header_list,
        "client": (client_ip, 12345),
    }
    return Request(scope)


def test_user_or_ip_key_func_no_auth():
    """Unauthenticated request returns client IP."""
    req = _build_request(client_ip="10.0.0.1")
    assert user_or_ip_key_func(req) == "10.0.0.1"


def test_user_or_ip_key_func_valid_jwt_user_id():
    """Valid signed token with user_id returns user:<user_id>."""
    token = jwt.encode({"user_id": "user-123"}, settings.secret_key, algorithm="HS256")
    req = _build_request(headers={"Authorization": f"Bearer {token}"})
    assert user_or_ip_key_func(req) == "user:user-123"


def test_user_or_ip_key_func_valid_jwt_sub():
    """Valid signed token with sub (and no user_id) returns user:<sub>."""
    token = jwt.encode({"sub": "user-sub-456"}, settings.secret_key, algorithm="HS256")
    req = _build_request(headers={"Authorization": f"Bearer {token}"})
    assert user_or_ip_key_func(req) == "user:user-sub-456"


def test_user_or_ip_key_func_bearer_lowercase():
    """Valid signed token with lowercase 'bearer ' prefix is handled correctly."""
    token = jwt.encode({"user_id": "user-789"}, settings.secret_key, algorithm="HS256")
    req = _build_request(headers={"Authorization": f"bearer {token}"})
    assert user_or_ip_key_func(req) == "user:user-789"


def test_user_or_ip_key_func_cookie_token():
    """Valid signed token in auth_token cookie returns user:<user_id>."""
    token = jwt.encode({"user_id": "user-cookie"}, settings.secret_key, algorithm="HS256")
    req = _build_request(cookies={"auth_token": token})
    assert user_or_ip_key_func(req) == "user:user-cookie"


def test_user_or_ip_key_func_invalid_signature():
    """Token with invalid signature falls back to client IP."""
    forged_token = jwt.encode(
        {"user_id": "attacker"}, "wrong_secret_key_32bytes_long!", algorithm="HS256"
    )
    req = _build_request(
        headers={"Authorization": f"Bearer {forged_token}"},
        client_ip="10.0.0.2",
    )
    assert user_or_ip_key_func(req) == "10.0.0.2"


def test_user_or_ip_key_func_expired_token():
    """Expired token falls back to client IP."""
    expired_token = jwt.encode(
        {"user_id": "user-expired", "exp": int(time.time()) - 3600},
        settings.secret_key,
        algorithm="HS256",
    )
    req = _build_request(
        headers={"Authorization": f"Bearer {expired_token}"},
        client_ip="10.0.0.3",
    )
    assert user_or_ip_key_func(req) == "10.0.0.3"


def test_user_or_ip_key_func_malformed_token():
    """Malformed token string falls back to client IP."""
    req = _build_request(
        headers={"Authorization": "Bearer not-a-jwt"},
        client_ip="10.0.0.4",
    )
    assert user_or_ip_key_func(req) == "10.0.0.4"


def test_user_or_ip_key_func_missing_user_claims():
    """Valid signed token missing user_id and sub falls back to client IP."""
    token = jwt.encode({"other": "claim"}, settings.secret_key, algorithm="HS256")
    req = _build_request(
        headers={"Authorization": f"Bearer {token}"},
        client_ip="10.0.0.5",
    )
    assert user_or_ip_key_func(req) == "10.0.0.5"


def test_user_or_ip_key_func_empty_secret_key(monkeypatch):
    """When secret_key is empty, token verification is bypassed and falls back to client IP."""
    token = jwt.encode({"user_id": "user-123"}, "any_secret_key_32bytes_long!!!!", algorithm="HS256")
    monkeypatch.setattr(settings, "secret_key", "")
    req = _build_request(
        headers={"Authorization": f"Bearer {token}"},
        client_ip="10.0.0.6",
    )
    assert user_or_ip_key_func(req) == "10.0.0.6"


