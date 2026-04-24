from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from itsdangerous import BadData, URLSafeTimedSerializer

from src.auth.api_types import UserId
from src.auth.repository import UserRepository, VerificationTokenRepository
from src.config.settings import settings
from src.core.email import EmailService


class EmailVerificationService:
    _user_repository: UserRepository
    _token_repository: VerificationTokenRepository
    _email_service: EmailService
    _serializer: URLSafeTimedSerializer

    def __init__(
        self,
        user_repository: UserRepository,
        token_repository: VerificationTokenRepository,
        email_service: EmailService,
    ):
        self._user_repository = user_repository
        self._token_repository = token_repository
        self._email_service = email_service
        self._serializer = URLSafeTimedSerializer(settings.secret_key)

    def _generate_token(self, email: str) -> str:
        # Add a random uuid string so the token is always unique
        # even if the same email is signed up/resent immediately
        payload = {"email": email, "nonce": str(uuid4())}
        return self._serializer.dumps(payload, salt="email-verification")

    async def generate_and_send_verification(self, email: str, user_id: UserId) -> None:
        await self._token_repository.invalidate_tokens_for_user(user_id)

        token = self._generate_token(email)

        expires_at = datetime.now(UTC) + timedelta(
            hours=settings.email_verification_token_expiry_hours
        )

        await self._token_repository.create_token(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )

        self._email_service.send_verification_email(email, token)

    async def verify_token(self, token: str) -> None:
        token_record = await self._token_repository.get_by_token(token)
        if not token_record:
            raise HTTPException(400, "Invalid or expired verification token")

        if token_record.is_used:
            raise HTTPException(400, "Token has already been used")

        # Ensure we're comparing offset-aware datetimes
        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < datetime.now(UTC):
            raise HTTPException(400, "Token has expired")

        try:
            payload = self._serializer.loads(
                token,
                salt="email-verification",
                max_age=settings.email_verification_token_expiry_hours * 3600,
            )
        except BadData as e:
            raise HTTPException(400, "Invalid token") from e

        email = payload.get("email")
        if not email:
            raise HTTPException(400, "Invalid token")

        user = await self._user_repository.get_by_email(email)
        if not user or user.id != token_record.user_id:
            raise HTTPException(400, "Invalid user for this token")

        await self._user_repository.mark_as_verified(user.id)
        await self._token_repository.mark_as_used(token_record.id)

    async def resend_verification(self, email: str) -> None:
        user = await self._user_repository.get_by_email(email)
        if not user or user.is_verified:
            # Silently succeed to prevent email enumeration
            return

        # Optional: You could check if a valid token already exists and just resend that
        # Or generate a new one, invalidating old ones (by ignoring them)
        await self.generate_and_send_verification(user.email, user.id)
