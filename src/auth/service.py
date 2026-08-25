import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pyotp
from argon2 import PasswordHasher
from fastapi import HTTPException
from itsdangerous import BadData, URLSafeTimedSerializer
from svcs import Container

from src.auth.api_types import UserId
from src.auth.repository import (
    RecoveryCodeRepository,
    TotpRepository,
    UserRepository,
    VerificationTokenRepository,
)
from src.auth.schema import (
    TotpActivateResponse,
    TotpRegenerateCodesResponse,
    TotpSetupResponse,
    TwoFactorStatusResponse,
)
from src.config.settings import settings
from src.core.email import EmailService

_password_hasher = PasswordHasher()


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

        await self._email_service.send_verification_email(email, token)

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


async def email_verification_service_factory(
    container: Container,
) -> EmailVerificationService:
    return EmailVerificationService(
        user_repository=await container.aget(UserRepository),
        token_repository=await container.aget(VerificationTokenRepository),
        email_service=await container.aget(EmailService),
    )


_TOTP_CODE_LENGTH = 6


class TotpService:
    _totp_repository: TotpRepository
    _recovery_code_repository: RecoveryCodeRepository
    _user_repository: UserRepository

    def __init__(
        self,
        totp_repository: TotpRepository,
        recovery_code_repository: RecoveryCodeRepository,
        user_repository: UserRepository,
    ):
        self._totp_repository = totp_repository
        self._recovery_code_repository = recovery_code_repository
        self._user_repository = user_repository

    async def get_2fa_status(self, user_id: UserId) -> TwoFactorStatusResponse:
        totp = await self._totp_repository.get_by_user_id(user_id)
        totp_enabled = bool(totp and totp.is_verified)
        remaining = 0
        if totp_enabled:
            remaining = await self._recovery_code_repository.count_active_by_user_id(
                user_id
            )
        return TwoFactorStatusResponse(
            totp_enabled=totp_enabled,
            recovery_codes_remaining=remaining,
        )

    async def setup_totp(self, user_id: UserId, email: str) -> TotpSetupResponse:
        secret = pyotp.random_base32()
        await self._totp_repository.create_or_update(user_id, secret)
        totp = pyotp.totp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=email,
            issuer_name="Retail Portfolio",
        )
        return TotpSetupResponse(secret=secret, provisioning_uri=provisioning_uri)

    async def activate_totp(self, user_id: UserId, code: str) -> TotpActivateResponse:
        totp_record = await self._totp_repository.get_by_user_id(user_id)
        if not totp_record:
            raise HTTPException(400, "TOTP setup not initiated")

        totp = pyotp.totp.TOTP(totp_record.secret)
        if not totp.verify(code, valid_window=1):
            raise HTTPException(400, "Invalid TOTP code")

        await self._totp_repository.mark_as_verified(user_id)

        recovery_codes = [
            f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(8)
        ]
        code_hashes = [_password_hasher.hash(c) for c in recovery_codes]

        await self._recovery_code_repository.delete_by_user_id(user_id)
        await self._recovery_code_repository.create_recovery_codes(user_id, code_hashes)

        return TotpActivateResponse(recovery_codes=recovery_codes)

    async def disable_totp(
        self,
        user_id: UserId,
        code: str | None = None,
        password: str | None = None,
    ) -> None:
        totp_record = await self._totp_repository.get_by_user_id(user_id)
        if not totp_record or not totp_record.is_verified:
            raise HTTPException(400, "TOTP is not enabled")

        if not code and not password:
            raise HTTPException(
                400, "Either TOTP code or password is required to disable TOTP"
            )

        if code:
            totp = pyotp.totp.TOTP(totp_record.secret)
            if not totp.verify(code, valid_window=1):
                raise HTTPException(400, "Invalid TOTP code")
        elif password:
            user = await self._user_repository.get_by_id(user_id)
            if not user or not user.verify_password(password):
                raise HTTPException(400, "Invalid password")

        await self._totp_repository.delete_by_user_id(user_id)
        await self._recovery_code_repository.delete_by_user_id(user_id)

    async def regenerate_recovery_codes(
        self, user_id: UserId
    ) -> TotpRegenerateCodesResponse:
        totp_record = await self._totp_repository.get_by_user_id(user_id)
        if not totp_record or not totp_record.is_verified:
            raise HTTPException(400, "TOTP is not enabled")

        recovery_codes = [
            f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(8)
        ]
        code_hashes = [_password_hasher.hash(c) for c in recovery_codes]

        await self._recovery_code_repository.delete_by_user_id(user_id)
        await self._recovery_code_repository.create_recovery_codes(user_id, code_hashes)

        return TotpRegenerateCodesResponse(recovery_codes=recovery_codes)

    async def verify_2fa_login(self, user_id: UserId, code: str) -> bool:
        totp_record = await self._totp_repository.get_by_user_id(user_id)
        if not totp_record or not totp_record.is_verified:
            return False

        cleaned_code = code.strip()
        if cleaned_code.isdigit() and len(cleaned_code) == _TOTP_CODE_LENGTH:
            totp = pyotp.totp.TOTP(totp_record.secret)
            return bool(totp.verify(cleaned_code, valid_window=1))

        active_codes = await self._recovery_code_repository.get_active_by_user_id(
            user_id
        )
        for rc in active_codes:
            try:
                if _password_hasher.verify(rc.code_hash, cleaned_code):
                    await self._recovery_code_repository.mark_as_used(rc.id)
                    return True
            except Exception:  # noqa: BLE001, S110
                pass

        return False


async def totp_service_factory(
    container: Container,
) -> TotpService:
    return TotpService(
        totp_repository=await container.aget(TotpRepository),
        recovery_code_repository=await container.aget(RecoveryCodeRepository),
        user_repository=await container.aget(UserRepository),
    )
