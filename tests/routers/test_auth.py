"""Integration tests for auth router."""

import pytest


@pytest.mark.anyio
async def test_signup_success(auth_client):
    """Test signup successfully creates a new user."""
    signup_request = {"email": "newuser@example.com", "password": "newpass"}

    response = await auth_client.post("/api/auth/signup", json=signup_request)

    assert response.status_code == 200
    result = response.json()

    assert "access_token" in result
    assert result["user"]["email"] == signup_request["email"]


@pytest.mark.anyio
async def test_signup_duplicate_email(auth_client, test_user):
    """Test signup with existing email raises 409."""
    signup_request = {"email": test_user.email, "password": "newpass"}

    response = await auth_client.post("/api/auth/signup", json=signup_request)

    assert response.status_code == 409
    result = response.json()

    assert result["detail"] == "User with email already exists"


@pytest.mark.anyio
async def test_login_success(auth_client, test_user):
    """Test login successfully authenticates a user."""
    login_request = {"email": test_user.email, "password": "testpass"}

    response = await auth_client.post("/api/auth/login", json=login_request)

    assert response.status_code == 200
    result = response.json()

    assert "access_token" in result
    assert result["user"]["email"] == test_user.email


@pytest.mark.anyio
async def test_login_invalid_credentials(auth_client, other_user):
    """Test login with wrong credentials raises 401."""
    login_request = {"email": other_user.email, "password": "wrongpass"}

    response = await auth_client.post("/api/auth/login", json=login_request)

    assert response.status_code == 401
    result = response.json()

    assert result["detail"] == "Invalid credentials"


@pytest.mark.anyio
async def test_login_nonexistent_user(auth_client):
    """Test login with non-existent email raises 401."""
    login_request = {"email": "nonexistent@example.com", "password": "somepass"}

    response = await auth_client.post("/api/auth/login", json=login_request)

    assert response.status_code == 401
    result = response.json()

    assert result["detail"] == "Invalid credentials"
