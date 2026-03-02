"""Integration tests for auth router."""

import pytest


@pytest.mark.anyio
async def test_signup_success(auth_client):
    """Test signup successfully creates a new user."""
    signup_request = {"email": "newuser@example.com", "password": "newpass"}

    response = await auth_client.post("/api/auth/signup", json=signup_request)

    assert response.status_code == 200
    result = response.json()

    assert "access_token" not in result
    assert "message" in result
    assert result["message"] == "User created. Please verify your email before logging in."


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
    """Test login successfully authenticates a verified user."""
    login_request = {"email": test_user.email, "password": "testpass"}

    response = await auth_client.post("/api/auth/login", json=login_request)

    assert response.status_code == 200
    result = response.json()

    assert "access_token" in result
    assert result["user"]["email"] == test_user.email


@pytest.mark.anyio
async def test_login_unverified_user(auth_client):
    """Test login with unverified user raises 403."""
    signup_request = {"email": "unverified@example.com", "password": "newpass"}
    await auth_client.post("/api/auth/signup", json=signup_request)

    login_request = {"email": "unverified@example.com", "password": "newpass"}
    response = await auth_client.post("/api/auth/login", json=login_request)

    assert response.status_code == 403
    result = response.json()
    assert result["detail"] == "Email not verified"


@pytest.mark.anyio
async def test_verify_email_success(auth_client, db_session):
    """Test verifying an email with a valid token."""
    from src.auth.service import EmailService, EmailVerificationService
    from src.auth.repository_sqlalchemy import SqlAlchemyUserRepository, SqlAlchemyVerificationTokenRepository

    user_repo = SqlAlchemyUserRepository(db_session)
    token_repo = SqlAlchemyVerificationTokenRepository(db_session)
    email_service = EmailService()
    svc = EmailVerificationService(user_repo, token_repo, email_service)

    email = "toverify@example.com"
    await auth_client.post("/api/auth/signup", json={"email": email, "password": "pass"})

    user = await user_repo.get_by_email(email)
    await svc.generate_and_send_verification(email, user.id)

    # Get the token generated
    token_record = await token_repo.get_by_user(user.id)
    assert token_record is not None

    response = await auth_client.post("/api/auth/verify-email", json={"token": token_record.token})

    assert response.status_code == 200
    assert response.json()["message"] == "Email verified successfully"

    # Login should now work
    login_response = await auth_client.post("/api/auth/login", json={"email": email, "password": "pass"})
    assert login_response.status_code == 200


@pytest.mark.anyio
async def test_verify_email_invalid_token(auth_client):
    """Test verifying an email with an invalid token."""
    response = await auth_client.post("/api/auth/verify-email", json={"token": "invalid-token-string"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired verification token"


@pytest.mark.anyio
async def test_resend_verification_success(auth_client):
    """Test resending verification email."""
    email = "resend@example.com"
    await auth_client.post("/api/auth/signup", json={"email": email, "password": "pass"})

    response = await auth_client.post("/api/auth/resend-verification", json={"email": email})

    assert response.status_code == 200
    assert response.json()["message"] == "Verification email sent if user exists and is unverified"


@pytest.mark.anyio
async def test_resend_verification_already_verified(auth_client, test_user):
    """Test resending verification email for verified user raises 400."""
    response = await auth_client.post("/api/auth/resend-verification", json={"email": test_user.email})

    assert response.status_code == 400
    assert response.json()["detail"] == "User is already verified"


@pytest.mark.anyio
async def test_resend_verification_nonexistent_user(auth_client):
    """Test resending verification email for nonexistent user succeeds silently."""
    response = await auth_client.post("/api/auth/resend-verification", json={"email": "nobody@example.com"})

    assert response.status_code == 200
    assert response.json()["message"] == "Verification email sent if user exists and is unverified"


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
