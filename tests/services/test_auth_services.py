import contextlib
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pyotp
import pytest
from argon2 import PasswordHasher
from fastapi import HTTPException
from itsdangerous import URLSafeTimedSerializer
from webauthn.authentication.verify_authentication_response import VerifiedAuthentication
from webauthn.registration.verify_registration_response import VerifiedRegistration

from src.auth.api_types import UserId
from src.auth.repository import (
    PasskeyRepository,
    RecoveryCodeRepository,
    TotpRepository,
    UserRepository,
    VerificationTokenRepository,
)
from src.auth.schema import (
    PasskeyRegisterVerifyRequest,
    PasskeyResponse,
    PasskeySchema,
    RecoveryCodeSchema,
    TotpSchema,
    UserSchema,
    VerificationTokenSchema,
)
from src.auth.service import EmailVerificationService, PasskeyService, TotpService
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


class MockPasskeyRepository(PasskeyRepository):
    def __init__(self):
        self.passkeys: dict[UUID, PasskeySchema] = {}

    async def create_passkey(  # noqa: PLR0913
        self,
        user_id: UserId,
        *,
        credential_id: bytes,
        public_key: bytes,
        sign_count: int = 0,
        name: str = "Passkey",
        transports: list[str] | None = None,
    ) -> PasskeySchema:
        p_id = uuid4()
        schema = PasskeySchema(
            id=p_id,
            user_id=user_id,
            credential_id=credential_id,
            public_key=public_key,
            sign_count=sign_count,
            name=name,
            transports=transports,
            created_at=datetime.now(UTC),
            last_used_at=None,
        )
        self.passkeys[p_id] = schema
        return schema

    async def get_by_id(self, passkey_id: UUID) -> PasskeySchema | None:
        return self.passkeys.get(passkey_id)

    async def get_by_credential_id(self, credential_id: bytes) -> PasskeySchema | None:
        return next(
            (p for p in self.passkeys.values() if p.credential_id == credential_id),
            None,
        )

    async def get_by_user_id(self, user_id: UserId) -> list[PasskeySchema]:
        return [p for p in self.passkeys.values() if p.user_id == user_id]

    async def update_name(self, passkey_id: UUID, name: str) -> PasskeySchema | None:
        p = self.passkeys.get(passkey_id)
        if not p:
            return None
        updated = p.model_copy(update={"name": name})
        self.passkeys[passkey_id] = updated
        return updated

    async def update_sign_count_and_last_used(
        self, passkey_id: UUID, sign_count: int, last_used_at: datetime | None = None
    ) -> None:
        p = self.passkeys.get(passkey_id)
        if p:
            ts = last_used_at or datetime.now(UTC)
            self.passkeys[passkey_id] = p.model_copy(
                update={"sign_count": sign_count, "last_used_at": ts}
            )

    async def delete_by_id(self, passkey_id: UUID, user_id: UserId) -> bool:
        p = self.passkeys.get(passkey_id)
        if p and p.user_id == user_id:
            del self.passkeys[passkey_id]
            return True
        return False


class MockRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def setex(self, key: str, time: int, value: str) -> None:  # noqa: ARG002
        self.data[key] = value

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self.data.pop(k, None)


class MockRedisManager:
    def __init__(self):
        self.redis = MockRedis()

    @contextlib.asynccontextmanager
    async def client(self):
        yield self.redis


@pytest.fixture
def mock_passkey_repo():
    return MockPasskeyRepository()


@pytest.fixture
def mock_redis_manager():
    return MockRedisManager()


@pytest.fixture
def passkey_service(mock_passkey_repo, mock_user_repo, mock_redis_manager):
    return PasskeyService(
        passkey_repository=mock_passkey_repo,
        user_repository=mock_user_repo,
        redis_manager=mock_redis_manager,
    )


@pytest.mark.asyncio
async def test_passkey_generate_registration_options(
    passkey_service, mock_redis_manager, mock_passkey_repo
):
    user_id = uuid4()
    email = "passkey_user@example.com"

    # With no existing passkeys
    options = await passkey_service.generate_registration_options(user_id, email)
    assert options["rp"]["id"] == settings.webauthn_rp_id
    assert options["user"]["name"] == email
    assert "challenge" in options

    challenge_key = f"webauthn:challenge:reg:{user_id}"
    assert await mock_redis_manager.redis.get(challenge_key) is not None

    # With existing passkey
    await mock_passkey_repo.create_passkey(
        user_id,
        credential_id=b"existing_cred_1",
        public_key=b"existing_pubkey_1",
        sign_count=0,
    )
    options2 = await passkey_service.generate_registration_options(user_id, email)
    assert len(options2.get("excludeCredentials", [])) == 1


@pytest.mark.asyncio
async def test_passkey_verify_registration_success(
    passkey_service, mock_redis_manager, mock_passkey_repo
):
    user_id = uuid4()
    email = "passkey_user@example.com"

    options = await passkey_service.generate_registration_options(user_id, email)
    challenge = options["challenge"]

    fake_verified = MagicMock(spec=VerifiedRegistration)
    fake_verified.credential_id = b"new_cred_id_123"
    fake_verified.credential_public_key = b"new_pub_key_456"
    fake_verified.sign_count = 0

    with patch(
        "src.auth.service.webauthn.verify_registration_response",
        return_value=fake_verified,
    ):
        req = PasskeyRegisterVerifyRequest(
            credential={
                "id": "cred_id",
                "rawId": "raw_id",
                "response": {"transports": ["internal"]},
                "type": "public-key",
            },
            name="My Mac Passkey",
        )
        resp = await passkey_service.verify_registration(user_id, req)
        assert resp.name == "My Mac Passkey"
        assert resp.transports == ["internal"]
        assert await mock_redis_manager.redis.get(f"webauthn:challenge:reg:{user_id}") is None
        assert await mock_passkey_repo.get_by_credential_id(b"new_cred_id_123") is not None


@pytest.mark.asyncio
async def test_passkey_verify_registration_missing_challenge(passkey_service):
    user_id = uuid4()
    req = PasskeyRegisterVerifyRequest(
        credential={"id": "cred_id"},
        name="My Passkey",
    )
    with pytest.raises(HTTPException) as exc:
        await passkey_service.verify_registration(user_id, req)
    assert exc.value.status_code == 400
    assert "Registration challenge expired or not found" in exc.value.detail


@pytest.mark.asyncio
async def test_passkey_verify_registration_invalid_response(
    passkey_service, mock_redis_manager
):
    user_id = uuid4()
    await mock_redis_manager.redis.setex(
        f"webauthn:challenge:reg:{user_id}", 300, "fake_challenge_b64"
    )

    with patch(
        "src.auth.service.webauthn.verify_registration_response",
        side_effect=Exception("Invalid signature"),
    ):
        req = PasskeyRegisterVerifyRequest(
            credential={"id": "cred_id"},
            name="My Passkey",
        )
        with pytest.raises(HTTPException) as exc:
            await passkey_service.verify_registration(user_id, req)
        assert exc.value.status_code == 400
        assert "Invalid registration response" in exc.value.detail


@pytest.mark.asyncio
async def test_passkey_list_passkeys(passkey_service, mock_passkey_repo):
    user_id = uuid4()
    await mock_passkey_repo.create_passkey(
        user_id,
        credential_id=b"c1",
        public_key=b"pk1",
        name="Key 1",
    )
    await mock_passkey_repo.create_passkey(
        user_id,
        credential_id=b"c2",
        public_key=b"pk2",
        name="Key 2",
    )

    passkeys = await passkey_service.list_passkeys(user_id)
    assert len(passkeys) == 2
    assert {p.name for p in passkeys} == {"Key 1", "Key 2"}


@pytest.mark.asyncio
async def test_passkey_delete_passkey(passkey_service, mock_passkey_repo):
    user_id = uuid4()
    p = await mock_passkey_repo.create_passkey(
        user_id,
        credential_id=b"c1",
        public_key=b"pk1",
        name="Key 1",
    )

    # Deleting own passkey succeeds
    await passkey_service.delete_passkey(p.id, user_id)
    assert await mock_passkey_repo.get_by_id(p.id) is None

    # Deleting non-existent passkey raises 404
    with pytest.raises(HTTPException) as exc:
        await passkey_service.delete_passkey(p.id, user_id)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_passkey_rename_passkey(passkey_service, mock_passkey_repo):
    user_id = uuid4()
    p = await mock_passkey_repo.create_passkey(
        user_id,
        credential_id=b"c1",
        public_key=b"pk1",
        name="Old Name",
    )

    renamed = await passkey_service.rename_passkey(p.id, user_id, "New Name")
    assert renamed.name == "New Name"

    with pytest.raises(HTTPException) as exc:
        await passkey_service.rename_passkey(uuid4(), user_id, "Other")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_passkey_generate_authentication_options(
    passkey_service, mock_user_repo, mock_passkey_repo, mock_redis_manager
):
    user_id = uuid4()
    email = "auth_test@example.com"
    mock_user_repo.users[email] = UserSchema(
        id=user_id,
        email=email,
        password="hashed_password",
        is_active=True,
        is_verified=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )
    await mock_passkey_repo.create_passkey(
        user_id,
        credential_id=b"cred_auth_1",
        public_key=b"pk_auth_1",
    )

    # Without email (usernameless)
    options = await passkey_service.generate_authentication_options()
    assert "challenge" in options
    challenge_key = f"webauthn:challenge:auth:{options['challenge']}"
    assert await mock_redis_manager.redis.get(challenge_key) is not None

    # With email (populates allowCredentials)
    options_with_email = await passkey_service.generate_authentication_options(email)
    assert len(options_with_email.get("allowCredentials", [])) == 1


@pytest.mark.asyncio
async def test_passkey_verify_authentication_success(
    passkey_service, mock_user_repo, mock_passkey_repo, mock_redis_manager
):
    user_id = uuid4()
    email = "passkey_login_user@example.com"
    mock_user_repo.users[email] = UserSchema(
        id=user_id,
        email=email,
        password="hashed_password",
        is_active=True,
        is_verified=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )
    cred_id = b"auth_cred_bytes"
    pub_key = b"auth_pubkey_bytes"
    passkey = await mock_passkey_repo.create_passkey(
        user_id,
        credential_id=cred_id,
        public_key=pub_key,
        sign_count=1,
    )

    raw_cred_dict = {
        "id": "base64_cred_id",
        "rawId": "base64_cred_id",
        "response": {
            "clientDataJSON": "eyJjaGFsbGVuZ2UiOiAiY2hhbGxlbmdlIn0",
            "authenticatorData": "auth_data",
            "signature": "sig",
        },
        "type": "public-key",
    }

    mock_parsed_cred = MagicMock()
    mock_parsed_cred.raw_id = cred_id
    mock_parsed_cred.response.client_data_json = b"client_data_bytes"

    mock_client_data = MagicMock()
    mock_client_data.challenge = b"challenge_bytes"

    # Seed challenge in redis
    challenge_b64 = "Y2hhbGxlbmdlX2J5dGVz"
    with patch(
        "src.auth.service.bytes_to_base64url", return_value=challenge_b64
    ):
        await mock_redis_manager.redis.setex(
            f"webauthn:challenge:auth:{challenge_b64}", 300, "1"
        )

    fake_verified_auth = MagicMock(spec=VerifiedAuthentication)
    fake_verified_auth.new_sign_count = 2

    with (
        patch(
            "src.auth.service.parse_authentication_credential_json",
            return_value=mock_parsed_cred,
        ),
        patch(
            "src.auth.service.parse_client_data_json",
            return_value=mock_client_data,
        ),
        patch(
            "src.auth.service.bytes_to_base64url",
            return_value=challenge_b64,
        ),
        patch(
            "src.auth.service.webauthn.verify_authentication_response",
            return_value=fake_verified_auth,
        ),
    ):
        user, verified_passkey = await passkey_service.verify_authentication(raw_cred_dict)
        assert user.id == user_id
        assert verified_passkey.id == passkey.id

        updated = await mock_passkey_repo.get_by_id(passkey.id)
        assert updated.sign_count == 2
        assert updated.last_used_at is not None
        assert await mock_redis_manager.redis.get(f"webauthn:challenge:auth:{challenge_b64}") is None


@pytest.mark.asyncio
async def test_passkey_verify_authentication_unrecognized_passkey(passkey_service):
    mock_parsed_cred = MagicMock()
    mock_parsed_cred.raw_id = b"unknown_cred_id"

    with patch(
        "src.auth.service.parse_authentication_credential_json",
        return_value=mock_parsed_cred,
    ):
        with pytest.raises(HTTPException) as exc:
            await passkey_service.verify_authentication({"id": "some_id"})
        assert exc.value.status_code == 401
        assert "Passkey not recognized" in exc.value.detail


@pytest.mark.asyncio
async def test_passkey_verify_authentication_user_inactive_or_unverified(
    passkey_service, mock_user_repo, mock_passkey_repo
):
    user_id = uuid4()
    email = "inactive_user@example.com"
    mock_user_repo.users[email] = UserSchema(
        id=user_id,
        email=email,
        password="hashed_password",
        is_active=False,
        is_verified=True,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )
    cred_id = b"inactive_cred_id"
    await mock_passkey_repo.create_passkey(
        user_id,
        credential_id=cred_id,
        public_key=b"pk",
    )

    mock_parsed_cred = MagicMock()
    mock_parsed_cred.raw_id = cred_id

    with patch(
        "src.auth.service.parse_authentication_credential_json",
        return_value=mock_parsed_cred,
    ):
        with pytest.raises(HTTPException) as exc:
            await passkey_service.verify_authentication({"id": "some_id"})
        assert exc.value.status_code == 401
        assert "User not found or inactive" in exc.value.detail

    # Now unverified user
    unverified_id = uuid4()
    unverified_email = "unverified@example.com"
    mock_user_repo.users[unverified_email] = UserSchema(
        id=unverified_id,
        email=unverified_email,
        password="hashed_password",
        is_active=True,
        is_verified=False,
        last_login_at=None,
        created_at=datetime.now(UTC),
    )
    unverified_cred_id = b"unverified_cred_id"
    await mock_passkey_repo.create_passkey(
        unverified_id,
        credential_id=unverified_cred_id,
        public_key=b"pk",
    )
    mock_parsed_cred.raw_id = unverified_cred_id

    with patch(
        "src.auth.service.parse_authentication_credential_json",
        return_value=mock_parsed_cred,
    ):
        with pytest.raises(HTTPException) as exc:
            await passkey_service.verify_authentication({"id": "some_id"})
        assert exc.value.status_code == 403
        assert "Email not verified" in exc.value.detail

