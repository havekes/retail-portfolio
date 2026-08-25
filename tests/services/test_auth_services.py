from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pyotp
import pytest
from argon2 import PasswordHasher
from fastapi import HTTPException
from itsdangerous import URLSafeTimedSerializer

from src.auth.api_types import UserId
from src.auth.repository import (
    RecoveryCodeRepository,
    TotpRepository,
    UserRepository,
    VerificationTokenRepository,
)
from src.auth.schema import (
    RecoveryCodeSchema,
    TotpSchema,
    UserSchema,
    VerificationTokenSchema,
)
from src.auth.service import EmailVerificationService, TotpService
from src.config.settings import settings
from src.core.email import EmailSendError, EmailService

_password_hasher = PasswordHasher()


class MockUserRepository(UserRepository):
    def __init__(self):
        self.users = {}
        self.verified_users = set()
        self.preferences: dict[UserId, dict] = {}

    async def get_by_id(self, user_id: UserId) -> UserSchema | None:
        return next((u for u in self.users.values() if u.id == user_id), None)

    async def get_by_email(self, email: str) -> UserSchema | None:
        return self.users.get(email)

    async def create_user(self, email: str, plain_text_password: str) -> UserSchema:
        user_id = uuid4()
        user = UserSchema(
            id=user_id,
            email=email,
            password=f"hashed_{plain_text_password}",
            is_active=True,
            is_verified=False,
            last_login_at=None,
            created_at=datetime.now(UTC),
        )
        self.users[email] = user
        return user

    async def mark_as_verified(self, user_id: UserId) -> None:
        self.verified_users.add(user_id)

    async def get_preferences(self, user_id: UserId) -> dict | None:
        return self.preferences.get(user_id)

    async def save_preferences(self, user_id: UserId, preferences: dict) -> None:
        self.preferences[user_id] = preferences

    async def patch_preferences(self, user_id: UserId, preferences: dict) -> dict:
        current = self.preferences.get(user_id) or {}
        updated = {**current, **preferences}
        self.preferences[user_id] = updated
        return updated


class MockVerificationTokenRepository(VerificationTokenRepository):
    def __init__(self):
        self.tokens = {}
        self.used_tokens = set()

    async def create_token(
        self, user_id: UserId, token: str, expires_at: datetime
    ) -> VerificationTokenSchema:
        token_id = str(uuid4())
        record = VerificationTokenSchema(
            id=token_id,
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            is_used=False,
            created_at=datetime.now(UTC),
        )
        self.tokens[token] = record
        return record

    async def get_by_token(self, token: str) -> VerificationTokenSchema | None:
        record = self.tokens.get(token)
        if record and record.id in self.used_tokens:
            record.is_used = True
        return record

    async def get_by_user(self, user_id: UserId) -> VerificationTokenSchema | None:
        pass

    async def mark_as_used(self, token_id: str) -> None:
        self.used_tokens.add(token_id)

    async def invalidate_tokens_for_user(self, user_id: UserId) -> None:
        for token_record in self.tokens.values():
            if token_record.user_id == user_id:
                self.used_tokens.add(token_record.id)


class MockEmailService(EmailService):
    def __init__(self):
        self.sent_emails = []

    async def send_verification_email(self, email: str, token: str) -> None:
        self.sent_emails.append((email, token))


class FailingEmailService(EmailService):
    """Simulates an SMTP failure."""

    async def send_verification_email(self, email: str, token: str) -> None:  # noqa: ARG002
        msg = "Simulated SMTP failure"
        raise EmailSendError(msg)


@pytest.fixture
def mock_user_repo():
    return MockUserRepository()


@pytest.fixture
def mock_token_repo():
    return MockVerificationTokenRepository()


@pytest.fixture
def mock_email_service():
    return MockEmailService()


@pytest.fixture
def verification_service(mock_user_repo, mock_token_repo, mock_email_service):
    return EmailVerificationService(
        user_repository=mock_user_repo,
        token_repository=mock_token_repo,
        email_service=mock_email_service,
    )


@pytest.mark.asyncio
async def test_generate_and_send_verification(
    verification_service, mock_token_repo, mock_email_service
):
    user_id = uuid4()
    email = "test@example.com"
    await verification_service.generate_and_send_verification(email, user_id)

    assert len(mock_email_service.sent_emails) == 1
    sent_email, sent_token = mock_email_service.sent_emails[0]
    assert sent_email == email

    saved_token = mock_token_repo.tokens.get(sent_token)
    assert saved_token is not None
    assert saved_token.user_id == user_id


@pytest.mark.asyncio
async def test_verify_token_success(
    verification_service, mock_user_repo, mock_token_repo, mock_email_service
):
    user_id = uuid4()
    email = "test@example.com"
    mock_user_repo.users[email] = UserSchema(
        id=user_id,
        email=email,
        password="hashed",  # noqa: S106
        is_active=True,
        is_verified=False,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )

    await verification_service.generate_and_send_verification(email, user_id)
    _sent_email, sent_token = mock_email_service.sent_emails[0]

    await verification_service.verify_token(sent_token)

    assert user_id in mock_user_repo.verified_users

    saved_token = mock_token_repo.tokens.get(sent_token)
    assert saved_token.id in mock_token_repo.used_tokens


@pytest.mark.asyncio
async def test_verify_token_expired(verification_service, mock_token_repo):
    user_id = uuid4()
    token = "some-token"  # noqa: S105

    # Create expired token
    mock_token_repo.tokens[token] = VerificationTokenSchema(
        id=str(uuid4()),
        user_id=user_id,
        token=token,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
        is_used=False,
        created_at=datetime.now(UTC) - timedelta(hours=2),
    )

    with pytest.raises(HTTPException) as exc:
        await verification_service.verify_token(token)
    assert exc.value.status_code == 400  # noqa: PLR2004
    assert "Token has expired" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_email_send_failure_propagates(mock_user_repo, mock_token_repo):
    """EmailSendError must propagate out of generate_and_send_verification."""
    failing_service = FailingEmailService()
    verification_service = EmailVerificationService(
        user_repository=mock_user_repo,
        token_repository=mock_token_repo,
        email_service=failing_service,
    )
    user_id = uuid4()
    with pytest.raises(EmailSendError):
        await verification_service.generate_and_send_verification(
            "user@example.com", user_id
        )


class MockTotpRepository(TotpRepository):
    def __init__(self):
        self.totps: dict[UserId, TotpSchema] = {}

    async def get_by_user_id(self, user_id: UserId) -> TotpSchema | None:
        return self.totps.get(user_id)

    async def create_or_update(self, user_id: UserId, secret: str) -> TotpSchema:
        totp = TotpSchema(
            id=uuid4(),
            user_id=user_id,
            secret=secret,
            is_verified=False,
            created_at=datetime.now(UTC),
        )
        self.totps[user_id] = totp
        return totp

    async def mark_as_verified(self, user_id: UserId) -> None:
        if user_id in self.totps:
            self.totps[user_id] = TotpSchema(
                id=self.totps[user_id].id,
                user_id=user_id,
                secret=self.totps[user_id].secret,
                is_verified=True,
                created_at=self.totps[user_id].created_at,
            )

    async def delete_by_user_id(self, user_id: UserId) -> None:
        self.totps.pop(user_id, None)


class MockRecoveryCodeRepository(RecoveryCodeRepository):
    def __init__(self):
        self.codes: dict[UserId, list[RecoveryCodeSchema]] = {}

    async def create_recovery_codes(
        self, user_id: UserId, code_hashes: list[str]
    ) -> list[RecoveryCodeSchema]:
        created = [
            RecoveryCodeSchema(
                id=uuid4(),
                user_id=user_id,
                code_hash=h,
                is_used=False,
                created_at=datetime.now(UTC),
            )
            for h in code_hashes
        ]
        self.codes[user_id] = created
        return created

    async def get_by_user_id(self, user_id: UserId) -> list[RecoveryCodeSchema]:
        return self.codes.get(user_id, [])

    async def get_active_by_user_id(self, user_id: UserId) -> list[RecoveryCodeSchema]:
        return [c for c in self.codes.get(user_id, []) if not c.is_used]

    async def mark_as_used(self, code_id: UUID) -> None:
        for user_codes in self.codes.values():
            for i, c in enumerate(user_codes):
                if c.id == code_id:
                    user_codes[i] = RecoveryCodeSchema(
                        id=c.id,
                        user_id=c.user_id,
                        code_hash=c.code_hash,
                        is_used=True,
                        used_at=datetime.now(UTC),
                        created_at=c.created_at,
                    )

    async def count_active_by_user_id(self, user_id: UserId) -> int:
        return sum(1 for c in self.codes.get(user_id, []) if not c.is_used)

    async def delete_by_user_id(self, user_id: UserId) -> None:
        self.codes.pop(user_id, None)


@pytest.fixture
def mock_totp_repo():
    return MockTotpRepository()


@pytest.fixture
def mock_recovery_code_repo():
    return MockRecoveryCodeRepository()


@pytest.fixture
def totp_service(mock_totp_repo, mock_recovery_code_repo, mock_user_repo):
    return TotpService(
        totp_repository=mock_totp_repo,
        recovery_code_repository=mock_recovery_code_repo,
        user_repository=mock_user_repo,
    )


@pytest.mark.asyncio
async def test_totp_status_disabled_initially(totp_service):
    user_id = uuid4()
    status = await totp_service.get_2fa_status(user_id)
    assert status.totp_enabled is False
    assert status.recovery_codes_remaining == 0


@pytest.mark.asyncio
async def test_totp_setup_returns_secret_and_uri(totp_service, mock_totp_repo):
    user_id = uuid4()
    email = "user@example.com"
    resp = await totp_service.setup_totp(user_id, email)

    assert resp.secret is not None
    assert len(resp.secret) == 32
    assert "otpauth://totp/" in resp.provisioning_uri
    assert "user" in resp.provisioning_uri
    assert "Retail" in resp.provisioning_uri

    totp_record = await mock_totp_repo.get_by_user_id(user_id)
    assert totp_record is not None
    assert totp_record.secret == resp.secret
    assert totp_record.is_verified is False


@pytest.mark.asyncio
async def test_totp_activate_success(
    totp_service, mock_totp_repo, mock_recovery_code_repo  # noqa: ARG001
):
    user_id = uuid4()
    email = "user@example.com"
    setup_resp = await totp_service.setup_totp(user_id, email)

    totp = pyotp.TOTP(setup_resp.secret)
    valid_code = totp.now()

    activate_resp = await totp_service.activate_totp(user_id, valid_code)

    assert len(activate_resp.recovery_codes) == 8
    totp_record = await mock_totp_repo.get_by_user_id(user_id)
    assert totp_record is not None
    assert totp_record.is_verified is True

    status = await totp_service.get_2fa_status(user_id)
    assert status.totp_enabled is True
    assert status.recovery_codes_remaining == 8


@pytest.mark.asyncio
async def test_totp_activate_invalid_code(totp_service):
    user_id = uuid4()
    await totp_service.setup_totp(user_id, "user@example.com")

    with pytest.raises(HTTPException) as exc:
        await totp_service.activate_totp(user_id, "000000")
    assert exc.value.status_code == 400
    assert "Invalid TOTP code" in exc.value.detail


@pytest.mark.asyncio
async def test_totp_activate_without_setup(totp_service):
    user_id = uuid4()
    with pytest.raises(HTTPException) as exc:
        await totp_service.activate_totp(user_id, "123456")
    assert exc.value.status_code == 400
    assert "TOTP setup not initiated" in exc.value.detail


@pytest.mark.asyncio
async def test_totp_regenerate_codes_success(totp_service):
    user_id = uuid4()
    setup_resp = await totp_service.setup_totp(user_id, "user@example.com")
    totp = pyotp.TOTP(setup_resp.secret)
    await totp_service.activate_totp(user_id, totp.now())

    regen_resp = await totp_service.regenerate_recovery_codes(user_id)
    assert len(regen_resp.recovery_codes) == 8

    status = await totp_service.get_2fa_status(user_id)
    assert status.recovery_codes_remaining == 8


@pytest.mark.asyncio
async def test_totp_regenerate_codes_when_not_enabled(totp_service):
    user_id = uuid4()
    with pytest.raises(HTTPException) as exc:
        await totp_service.regenerate_recovery_codes(user_id)
    assert exc.value.status_code == 400
    assert "TOTP is not enabled" in exc.value.detail


@pytest.mark.asyncio
async def test_totp_disable_with_code(
    totp_service, mock_totp_repo, mock_recovery_code_repo  # noqa: ARG001
):
    user_id = uuid4()
    setup_resp = await totp_service.setup_totp(user_id, "user@example.com")
    totp = pyotp.TOTP(setup_resp.secret)
    await totp_service.activate_totp(user_id, totp.now())

    await totp_service.disable_totp(user_id, code=totp.now())

    status = await totp_service.get_2fa_status(user_id)
    assert status.totp_enabled is False
    assert status.recovery_codes_remaining == 0
    assert await mock_totp_repo.get_by_user_id(user_id) is None


@pytest.mark.asyncio
async def test_totp_disable_with_password(
    totp_service, mock_user_repo, mock_totp_repo, mock_recovery_code_repo  # noqa: ARG001
):
    user_id = uuid4()
    email = "test_disable@example.com"
    password = "secretpassword"
    mock_user_repo.users[email] = UserSchema(
        id=user_id,
        email=email,
        password=_password_hasher.hash(password),
        is_active=True,
        is_verified=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )

    setup_resp = await totp_service.setup_totp(user_id, email)
    totp = pyotp.TOTP(setup_resp.secret)
    await totp_service.activate_totp(user_id, totp.now())

    await totp_service.disable_totp(user_id, password=password)

    status = await totp_service.get_2fa_status(user_id)
    assert status.totp_enabled is False
    assert status.recovery_codes_remaining == 0


@pytest.mark.asyncio
async def test_totp_disable_invalid_code(totp_service):
    user_id = uuid4()
    setup_resp = await totp_service.setup_totp(user_id, "user@example.com")
    totp = pyotp.TOTP(setup_resp.secret)
    await totp_service.activate_totp(user_id, totp.now())

    with pytest.raises(HTTPException) as exc:
        await totp_service.disable_totp(user_id, code="000000")
    assert exc.value.status_code == 400
    assert "Invalid TOTP code" in exc.value.detail


@pytest.mark.asyncio
async def test_totp_disable_invalid_password(totp_service, mock_user_repo):
    user_id = uuid4()
    email = "test_disable2@example.com"
    mock_user_repo.users[email] = UserSchema(
        id=user_id,
        email=email,
        password=_password_hasher.hash("correct_password"),
        is_active=True,
        is_verified=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )

    setup_resp = await totp_service.setup_totp(user_id, email)
    totp = pyotp.TOTP(setup_resp.secret)
    await totp_service.activate_totp(user_id, totp.now())

    with pytest.raises(HTTPException) as exc:
        await totp_service.disable_totp(user_id, password="wrong_password")
    assert exc.value.status_code == 400
    assert "Invalid password" in exc.value.detail


@pytest.mark.asyncio
async def test_totp_disable_missing_credentials(totp_service):
    user_id = uuid4()
    setup_resp = await totp_service.setup_totp(user_id, "user@example.com")
    totp = pyotp.TOTP(setup_resp.secret)
    await totp_service.activate_totp(user_id, totp.now())

    with pytest.raises(HTTPException) as exc:
        await totp_service.disable_totp(user_id)
    assert exc.value.status_code == 400
    assert "Either TOTP code or password is required" in exc.value.detail


@pytest.mark.asyncio
async def test_totp_disable_when_not_enabled(totp_service):
    user_id = uuid4()
    with pytest.raises(HTTPException) as exc:
        await totp_service.disable_totp(user_id, code="123456")
    assert exc.value.status_code == 400
    assert "TOTP is not enabled" in exc.value.detail


@pytest.mark.asyncio
async def test_verify_2fa_login_when_disabled(totp_service):
    user_id = uuid4()
    assert await totp_service.verify_2fa_login(user_id, "123456") is False


@pytest.mark.asyncio
async def test_verify_2fa_login_valid_totp(totp_service):
    user_id = uuid4()
    setup_resp = await totp_service.setup_totp(user_id, "user@example.com")
    totp = pyotp.TOTP(setup_resp.secret)
    await totp_service.activate_totp(user_id, totp.now())

    # Valid TOTP code returns True
    assert await totp_service.verify_2fa_login(user_id, totp.now()) is True


@pytest.mark.asyncio
async def test_verify_2fa_login_invalid_totp(totp_service):
    user_id = uuid4()
    setup_resp = await totp_service.setup_totp(user_id, "user@example.com")
    totp = pyotp.TOTP(setup_resp.secret)
    await totp_service.activate_totp(user_id, totp.now())

    # Invalid 6-digit code returns False
    assert await totp_service.verify_2fa_login(user_id, "000000") is False


@pytest.mark.asyncio
async def test_verify_2fa_login_valid_recovery_code(totp_service):
    user_id = uuid4()
    setup_resp = await totp_service.setup_totp(user_id, "user@example.com")
    totp = pyotp.TOTP(setup_resp.secret)
    act_resp = await totp_service.activate_totp(user_id, totp.now())

    recovery_code = act_resp.recovery_codes[0]

    # Valid recovery code returns True and consumes code
    assert await totp_service.verify_2fa_login(user_id, f"  {recovery_code}  ") is True

    status = await totp_service.get_2fa_status(user_id)
    assert status.recovery_codes_remaining == 7


@pytest.mark.asyncio
async def test_verify_2fa_login_reused_recovery_code(totp_service):
    user_id = uuid4()
    setup_resp = await totp_service.setup_totp(user_id, "user@example.com")
    totp = pyotp.TOTP(setup_resp.secret)
    act_resp = await totp_service.activate_totp(user_id, totp.now())

    recovery_code = act_resp.recovery_codes[0]

    # First use succeeds
    assert await totp_service.verify_2fa_login(user_id, recovery_code) is True

    # Reusing same recovery code fails
    assert await totp_service.verify_2fa_login(user_id, recovery_code) is False


@pytest.mark.asyncio
async def test_verify_2fa_login_invalid_recovery_code(totp_service):
    user_id = uuid4()
    setup_resp = await totp_service.setup_totp(user_id, "user@example.com")
    totp = pyotp.TOTP(setup_resp.secret)
    await totp_service.activate_totp(user_id, totp.now())

    # Completely wrong recovery code string
    assert await totp_service.verify_2fa_login(user_id, "invalid-recovery-code") is False
