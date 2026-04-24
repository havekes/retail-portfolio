from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from itsdangerous import URLSafeTimedSerializer

from src.auth.api_types import UserId
from src.auth.repository import UserRepository, VerificationTokenRepository
from src.auth.schema import UserSchema, VerificationTokenSchema
from src.auth.service import EmailVerificationService
from src.config.settings import settings
from src.core.email import EmailSendError, EmailService


class MockUserRepository(UserRepository):
    def __init__(self):
        self.users = {}
        self.verified_users = set()

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

    def send_verification_email(self, email: str, token: str) -> None:
        self.sent_emails.append((email, token))


class FailingEmailService(EmailService):
    """Simulates an SMTP failure."""

    def send_verification_email(self, email: str, token: str) -> None:  # noqa: ARG002
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
