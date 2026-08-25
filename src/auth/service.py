import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pyotp
import webauthn
from argon2 import PasswordHasher
from fastapi import HTTPException
from itsdangerous import BadData, URLSafeTimedSerializer
from svcs import Container
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url,
    parse_authentication_credential_json,
    parse_client_data_json,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

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
    TotpActivateResponse,
    TotpRegenerateCodesResponse,
    TotpSetupResponse,
    TwoFactorStatusResponse,
    UserSchema,
)
from src.config.settings import settings
from src.core.email import EmailService
from src.core.redis import (
    RedisManager,
)
from src.core.redis import (
    redis_manager as default_redis_manager,
)

logger = logging.getLogger(__name__)
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


class PasskeyService:
    _passkey_repository: PasskeyRepository
    _user_repository: UserRepository
    _redis_manager: RedisManager

    def __init__(
        self,
        passkey_repository: PasskeyRepository,
        user_repository: UserRepository,
        redis_manager: RedisManager | None = None,
    ):
        self._passkey_repository = passkey_repository
        self._user_repository = user_repository
        self._redis_manager = (
            redis_manager if redis_manager is not None else default_redis_manager
        )

    async def generate_registration_options(self, user_id: UserId, email: str) -> dict:
        existing_passkeys = await self._passkey_repository.get_by_user_id(user_id)
        exclude_credentials = [
            PublicKeyCredentialDescriptor(id=p.credential_id) for p in existing_passkeys
        ]

        options = webauthn.generate_registration_options(
            rp_id=settings.webauthn_rp_id,
            rp_name=settings.webauthn_rp_name,
            user_id=user_id.bytes,
            user_name=email,
            user_display_name=email,
            attestation=AttestationConveyancePreference.NONE,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
            exclude_credentials=exclude_credentials or None,
        )

        challenge_b64 = bytes_to_base64url(options.challenge)
        async with self._redis_manager.client() as redis:
            await redis.setex(
                f"webauthn:challenge:reg:{user_id}",
                settings.webauthn_challenge_ttl_seconds,
                challenge_b64,
            )

        return json.loads(webauthn.options_to_json(options))

    async def verify_registration(
        self, user_id: UserId, request: PasskeyRegisterVerifyRequest
    ) -> PasskeyResponse:
        key = f"webauthn:challenge:reg:{user_id}"
        async with self._redis_manager.client() as redis:
            challenge_b64 = await redis.get(key)
            if not challenge_b64:
                raise HTTPException(400, "Registration challenge expired or not found")
            await redis.delete(key)

        challenge_str = (
            challenge_b64.decode("utf-8")
            if isinstance(challenge_b64, bytes)
            else challenge_b64
        )
        expected_challenge = base64url_to_bytes(challenge_str)

        try:
            verified = webauthn.verify_registration_response(
                credential=request.credential,
                expected_challenge=expected_challenge,
                expected_rp_id=settings.webauthn_rp_id,
                expected_origin=settings.webauthn_origin,
                require_user_verification=False,
            )
        except Exception as e:
            logger.warning("Passkey registration verification failed: %s", e)
            raise HTTPException(400, "Invalid registration response") from e

        transports = None
        if isinstance(request.credential, dict):
            transports = request.credential.get("response", {}).get("transports")
        elif isinstance(request.credential, str):
            try:
                parsed_cred = json.loads(request.credential)
                transports = parsed_cred.get("response", {}).get("transports")
            except Exception:  # noqa: BLE001, S110
                pass

        passkey = await self._passkey_repository.create_passkey(
            user_id=user_id,
            credential_id=verified.credential_id,
            public_key=verified.credential_public_key,
            sign_count=verified.sign_count,
            name=request.name,
            transports=transports,
        )
        return PasskeyResponse.model_validate(passkey)

    async def list_passkeys(self, user_id: UserId) -> list[PasskeyResponse]:
        passkeys = await self._passkey_repository.get_by_user_id(user_id)
        return [PasskeyResponse.model_validate(p) for p in passkeys]

    async def delete_passkey(self, passkey_id: UUID, user_id: UserId) -> None:
        deleted = await self._passkey_repository.delete_by_id(passkey_id, user_id)
        if not deleted:
            raise HTTPException(404, "Passkey not found")

    async def rename_passkey(
        self, passkey_id: UUID, user_id: UserId, name: str
    ) -> PasskeyResponse:
        passkey = await self._passkey_repository.get_by_id(passkey_id)
        if not passkey or passkey.user_id != user_id:
            raise HTTPException(404, "Passkey not found")
        updated = await self._passkey_repository.update_name(passkey_id, name)
        if not updated:
            raise HTTPException(404, "Passkey not found")
        return PasskeyResponse.model_validate(updated)

    async def generate_authentication_options(self, email: str | None = None) -> dict:
        allow_credentials = None
        if email:
            user = await self._user_repository.get_by_email(email)
            if user:
                passkeys = await self._passkey_repository.get_by_user_id(user.id)
                if passkeys:
                    allow_credentials = [
                        PublicKeyCredentialDescriptor(id=p.credential_id)
                        for p in passkeys
                    ]

        options = webauthn.generate_authentication_options(
            rp_id=settings.webauthn_rp_id,
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.PREFERRED,
        )

        challenge_b64 = bytes_to_base64url(options.challenge)
        async with self._redis_manager.client() as redis:
            await redis.setex(
                f"webauthn:challenge:auth:{challenge_b64}",
                settings.webauthn_challenge_ttl_seconds,
                "1",
            )

        return json.loads(webauthn.options_to_json(options))

    async def verify_authentication(
        self, credential: dict | str
    ) -> tuple[UserSchema, PasskeySchema]:
        try:
            parsed = parse_authentication_credential_json(credential)
        except Exception as e:
            raise HTTPException(400, "Invalid authentication credential format") from e

        passkey = await self._passkey_repository.get_by_credential_id(parsed.raw_id)
        if not passkey:
            raise HTTPException(401, "Passkey not recognized")

        user = await self._user_repository.get_by_id(passkey.user_id)
        if not user or not user.is_active:
            raise HTTPException(401, "User not found or inactive")
        if not user.is_verified:
            raise HTTPException(403, "Email not verified")

        try:
            client_data = parse_client_data_json(parsed.response.client_data_json)
            challenge_b64 = bytes_to_base64url(client_data.challenge)
        except Exception as e:
            raise HTTPException(400, "Invalid clientDataJSON") from e

        key = f"webauthn:challenge:auth:{challenge_b64}"
        async with self._redis_manager.client() as redis:
            exists = await redis.get(key)
            if not exists:
                raise HTTPException(
                    400, "Authentication challenge expired or not found"
                )
            await redis.delete(key)

        try:
            verified = webauthn.verify_authentication_response(
                credential=credential,
                expected_challenge=client_data.challenge,
                expected_rp_id=settings.webauthn_rp_id,
                expected_origin=settings.webauthn_origin,
                credential_public_key=passkey.public_key,
                credential_current_sign_count=passkey.sign_count,
                require_user_verification=False,
            )
        except Exception as e:
            logger.warning("Passkey authentication verification failed: %s", e)
            raise HTTPException(401, "Invalid passkey authentication") from e

        await self._passkey_repository.update_sign_count_and_last_used(
            passkey_id=passkey.id,
            sign_count=verified.new_sign_count,
        )
        return user, passkey


async def passkey_service_factory(
    container: Container,
) -> PasskeyService:
    return PasskeyService(
        passkey_repository=await container.aget(PasskeyRepository),
        user_repository=await container.aget(UserRepository),
    )
