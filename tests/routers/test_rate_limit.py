"""Integration tests for API rate limiting."""

import pytest
from src.config.limiter import limiter


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
        response = await auth_client.post("/api/auth/login", json=login_request)
        assert response.status_code == 200
        assert "x-ratelimit-limit" in response.headers or "X-RateLimit-Limit" in response.headers

    # 11th request should be rate-limited (status 429)
    response = await auth_client.post("/api/auth/login", json=login_request)
    assert response.status_code == 429


@pytest.mark.anyio
async def test_signup_rate_limit(auth_client):
    """Test POST /api/auth/signup rate limiting (5/minute)."""
    signup_request = {"email": "newuser_rl@example.com", "password": "newpassword123"}

    # First 5 requests should proceed (status 200 or 409)
    for _ in range(5):
        response = await auth_client.post("/api/auth/signup", json=signup_request)
        assert response.status_code in (200, 409)

    # 6th request should return 429
    response = await auth_client.post("/api/auth/signup", json=signup_request)
    assert response.status_code == 429


@pytest.mark.anyio
async def test_resend_verification_rate_limit(auth_client):
    """Test POST /api/auth/resend-verification rate limiting (3/minute)."""
    payload = {"email": "test@example.com"}

    for _ in range(3):
        response = await auth_client.post("/api/auth/resend-verification", json=payload)
        assert response.status_code == 200

    # 4th request should return 429
    response = await auth_client.post("/api/auth/resend-verification", json=payload)
    assert response.status_code == 429


@pytest.mark.anyio
async def test_account_sync_rate_limit(auth_client):
    """Test POST /api/accounts/{account_id}/sync rate limiting (3/minute)."""
    fake_account_id = "00000000-0000-0000-0000-000000000001"

    for _ in range(3):
        response = await auth_client.post(f"/api/accounts/{fake_account_id}/sync")
        # May be 404 or 200 depending on DB state, but shouldn't be 429 for the first 3
        assert response.status_code != 429

    # 4th request should be rate-limited (status 429)
    response = await auth_client.post(f"/api/accounts/{fake_account_id}/sync")
    assert response.status_code == 429
