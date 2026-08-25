"""Integration tests for auth router."""

import logging
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from src.config.settings import settings


@pytest.mark.anyio
async def test_signup_success(auth_client):
    """Test signup successfully creates a new user."""
    signup_request = {"email": "newuser@example.com", "password": "newpass"}

    response = await auth_client.post("/api/v1/auth/signup", json=signup_request)

    assert response.status_code == 200
    result = response.json()

    assert "access_token" not in result
    assert "message" in result
    assert result["message"] == "User created. Please verify your email before logging in."


@pytest.mark.anyio
async def test_signup_duplicate_email(auth_client, test_user):
    """Test signup with existing email raises 409."""
    signup_request = {"email": test_user.email, "password": "newpass"}

    response = await auth_client.post("/api/v1/auth/signup", json=signup_request)

    assert response.status_code == 409
    result = response.json()

    assert result["detail"] == "User with email already exists"


@pytest.mark.anyio
async def test_login_success(auth_client, test_user):
    """Test login successfully authenticates a verified user."""
    login_request = {"email": test_user.email, "password": "testpass"}

    response = await auth_client.post("/api/v1/auth/login", json=login_request)

    assert response.status_code == 200
    result = response.json()

    assert "access_token" in result
    assert result["user"]["email"] == test_user.email


@pytest.mark.anyio
async def test_login_unverified_user(auth_client, caplog):
    """Test login with unverified user raises 403."""
    caplog.set_level(logging.WARNING, logger="src.auth.router")
    signup_request = {"email": "unverified@example.com", "password": "newpass"}
    await auth_client.post("/api/v1/auth/signup", json=signup_request)

    login_request = {"email": "unverified@example.com", "password": "newpass"}
    response = await auth_client.post("/api/v1/auth/login", json=login_request)

    assert response.status_code == 403
    result = response.json()
    assert result["detail"] == "Email not verified"
    assert (
        f"Login failed for {login_request['email']}: Email not verified" in caplog.text
    )


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
    await auth_client.post("/api/v1/auth/signup", json={"email": email, "password": "pass"})

    user = await user_repo.get_by_email(email)
    assert user is not None
    await svc.generate_and_send_verification(email, user.id)

    # Get the token generated
    token_record = await token_repo.get_by_user(user.id)
    assert token_record is not None

    response = await auth_client.post("/api/v1/auth/verify-email", json={"token": token_record.token})

    assert response.status_code == 200
    assert response.json()["message"] == "Email verified successfully"

    # Login should now work
    login_response = await auth_client.post("/api/v1/auth/login", json={"email": email, "password": "pass"})
    assert login_response.status_code == 200


@pytest.mark.anyio
async def test_verify_email_invalid_token(auth_client):
    """Test verifying an email with an invalid token."""
    response = await auth_client.post("/api/v1/auth/verify-email", json={"token": "invalid-token-string"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired verification token"


@pytest.mark.anyio
async def test_resend_verification_success(auth_client):
    """Test resending verification email."""
    email = "resend@example.com"
    await auth_client.post("/api/v1/auth/signup", json={"email": email, "password": "pass"})

    response = await auth_client.post("/api/v1/auth/resend-verification", json={"email": email})

    assert response.status_code == 200
    assert response.json()["message"] == "Verification email sent if user exists and is unverified"


@pytest.mark.anyio
async def test_resend_verification_already_verified(auth_client, test_user):
    """Test resending verification email for verified user raises 400."""
    response = await auth_client.post("/api/v1/auth/resend-verification", json={"email": test_user.email})

    assert response.status_code == 200
    assert response.json()["message"] == "Verification email sent if user exists and is unverified"


@pytest.mark.anyio
async def test_resend_verification_nonexistent_user(auth_client):
    """Test resending verification email for nonexistent user succeeds silently."""
    response = await auth_client.post("/api/v1/auth/resend-verification", json={"email": "nobody@example.com"})

    assert response.status_code == 200
    assert response.json()["message"] == "Verification email sent if user exists and is unverified"


@pytest.mark.anyio
async def test_login_invalid_credentials(auth_client, other_user, caplog):
    """Test login with wrong credentials raises 401."""
    caplog.set_level(logging.WARNING, logger="src.auth.router")
    login_request = {"email": other_user.email, "password": "wrongpass"}

    response = await auth_client.post("/api/v1/auth/login", json=login_request)

    assert response.status_code == 401
    result = response.json()

    assert result["detail"] == "Invalid credentials"
    assert f"Login failed for {login_request['email']}: Invalid credentials" in caplog.text


@pytest.mark.anyio
async def test_login_nonexistent_user(auth_client, caplog):
    """Test login with non-existent email raises 401."""
    caplog.set_level(logging.WARNING, logger="src.auth.router")
    login_request = {"email": "nonexistent@example.com", "password": "somepass"}

    response = await auth_client.post("/api/v1/auth/login", json=login_request)

    assert response.status_code == 401
    result = response.json()

    assert result["detail"] == "Invalid credentials"
    assert f"Login failed for {login_request['email']}: Invalid credentials" in caplog.text


@pytest.mark.anyio
async def test_expired_token_returns_401(auth_client):
    """Test expired token on a protected endpoint returns 401, not 403."""
    expired_token = jwt.encode(
        {
            "sub": "test@example.com",
            "user_id": "00000000-0000-0000-0000-000000000000",
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
        },
        settings.secret_key,
        algorithm="HS256",
    )

    response = await auth_client.get(
        "/api/v1/accounts/sync-status",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token expired"


@pytest.mark.anyio
async def test_invalid_token_unknown_user_returns_401(auth_client):
    """Test valid-signed token for a user not in the DB returns 401, not 403."""
    ghost_token = jwt.encode(
        {
            "sub": "ghost@example.com",
            "user_id": "00000000-0000-0000-0000-000000000000",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        settings.secret_key,
        algorithm="HS256",
    )

    response = await auth_client.get(
        "/api/v1/accounts/sync-status",
        headers={"Authorization": f"Bearer {ghost_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token invalid"


@pytest.mark.anyio
async def test_2fa_status_initial(auth_client):
    """Test GET /2fa/status returns disabled by default."""
    response = await auth_client.get("/api/v1/auth/2fa/status")

    assert response.status_code == 200
    result = response.json()
    assert result["totp_enabled"] is False
    assert result["recovery_codes_remaining"] == 0


@pytest.mark.anyio
async def test_2fa_status_unauthenticated(client):
    """Test 2FA status requires authentication."""
    response = await client.get("/api/v1/auth/2fa/status")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_totp_setup(auth_client):
    """Test POST /2fa/totp/setup returns secret and otpauth URI."""
    response = await auth_client.post("/api/v1/auth/2fa/totp/setup")

    assert response.status_code == 200
    result = response.json()
    assert "secret" in result
    assert len(result["secret"]) == 32
    assert "provisioning_uri" in result
    assert result["provisioning_uri"].startswith("otpauth://totp/")
    assert "Retail" in result["provisioning_uri"]


@pytest.mark.anyio
async def test_totp_activate_flow_and_regenerate(auth_client):
    """Test complete TOTP activation and recovery code regeneration flow."""
    import pyotp

    # 1. Setup
    setup_resp = await auth_client.post("/api/v1/auth/2fa/totp/setup")
    assert setup_resp.status_code == 200
    secret = setup_resp.json()["secret"]

    # 2. Activate with valid code
    totp = pyotp.TOTP(secret)
    activate_resp = await auth_client.post(
        "/api/v1/auth/2fa/totp/activate",
        json={"code": totp.now()},
    )
    assert activate_resp.status_code == 200
    result = activate_resp.json()
    assert "recovery_codes" in result
    assert len(result["recovery_codes"]) == 8
    first_codes = result["recovery_codes"]

    # 3. Status should now be enabled with 8 codes
    status_resp = await auth_client.get("/api/v1/auth/2fa/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["totp_enabled"] is True
    assert status_resp.json()["recovery_codes_remaining"] == 8

    # 4. Regenerate recovery codes
    regen_resp = await auth_client.post(
        "/api/v1/auth/2fa/totp/recovery-codes/regenerate"
    )
    assert regen_resp.status_code == 200
    new_codes = regen_resp.json()["recovery_codes"]
    assert len(new_codes) == 8
    assert new_codes != first_codes

    # 5. Status check after regeneration
    status_resp2 = await auth_client.get("/api/v1/auth/2fa/status")
    assert status_resp2.status_code == 200
    assert status_resp2.json()["recovery_codes_remaining"] == 8


@pytest.mark.anyio
async def test_totp_activate_invalid_code(auth_client):
    """Test activating TOTP with invalid code returns 400."""
    await auth_client.post("/api/v1/auth/2fa/totp/setup")
    response = await auth_client.post(
        "/api/v1/auth/2fa/totp/activate",
        json={"code": "000000"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid TOTP code"


@pytest.mark.anyio
async def test_totp_disable_with_code(auth_client):
    """Test disabling TOTP with valid 6-digit code."""
    import pyotp

    setup_resp = await auth_client.post("/api/v1/auth/2fa/totp/setup")
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)

    await auth_client.post(
        "/api/v1/auth/2fa/totp/activate",
        json={"code": totp.now()},
    )

    # Disable with code
    disable_resp = await auth_client.post(
        "/api/v1/auth/2fa/totp/disable",
        json={"code": totp.now()},
    )
    assert disable_resp.status_code == 200
    assert (
        disable_resp.json()["message"]
        == "TOTP two-factor authentication disabled successfully"
    )

    # Status should be disabled
    status_resp = await auth_client.get("/api/v1/auth/2fa/status")
    assert status_resp.json()["totp_enabled"] is False
    assert status_resp.json()["recovery_codes_remaining"] == 0


@pytest.mark.anyio
async def test_totp_disable_with_password(auth_client):
    """Test disabling TOTP with user password."""
    import pyotp

    setup_resp = await auth_client.post("/api/v1/auth/2fa/totp/setup")
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)

    await auth_client.post(
        "/api/v1/auth/2fa/totp/activate",
        json={"code": totp.now()},
    )

    # Disable with password
    disable_resp = await auth_client.post(
        "/api/v1/auth/2fa/totp/disable",
        json={"password": "testpass"},
    )
    assert disable_resp.status_code == 200

    # Status should be disabled
    status_resp = await auth_client.get("/api/v1/auth/2fa/status")
    assert status_resp.json()["totp_enabled"] is False
    assert status_resp.json()["recovery_codes_remaining"] == 0


@pytest.mark.anyio
async def test_totp_disable_wrong_credentials(auth_client):
    """Test disabling TOTP with invalid password or code raises 400."""
    import pyotp

    setup_resp = await auth_client.post("/api/v1/auth/2fa/totp/setup")
    secret = setup_resp.json()["secret"]
    totp = pyotp.TOTP(secret)

    await auth_client.post(
        "/api/v1/auth/2fa/totp/activate",
        json={"code": totp.now()},
    )

    # Wrong password
    resp1 = await auth_client.post(
        "/api/v1/auth/2fa/totp/disable",
        json={"password": "wrongpassword"},
    )
    assert resp1.status_code == 400
    assert resp1.json()["detail"] == "Invalid password"

    # Wrong code
    resp2 = await auth_client.post(
        "/api/v1/auth/2fa/totp/disable",
        json={"code": "000000"},
    )
    assert resp2.status_code == 400
    assert resp2.json()["detail"] == "Invalid TOTP code"

    # Missing credentials
    resp3 = await auth_client.post(
        "/api/v1/auth/2fa/totp/disable",
        json={},
    )
    assert resp3.status_code == 400
    assert (
        resp3.json()["detail"]
        == "Either TOTP code or password is required to disable TOTP"
    )


@pytest.mark.anyio
async def test_totp_endpoints_require_auth(client):
    """Test all 2FA endpoints require authentication."""
    assert (await client.get("/api/v1/auth/2fa/status")).status_code == 401
    assert (await client.post("/api/v1/auth/2fa/totp/setup")).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/2fa/totp/activate", json={"code": "123456"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/2fa/totp/disable", json={"code": "123456"}
        )
    ).status_code == 401
    assert (
        await client.post("/api/v1/auth/2fa/totp/recovery-codes/regenerate")
    ).status_code == 401

