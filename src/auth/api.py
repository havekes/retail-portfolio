import contextlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ValidationError
from svcs import Container
from svcs.fastapi import DepContainer

from src.auth.api_types import (
    AccessTokenData,
    AuthResponse,
    SignupResponse,
    User,
    UserId,
)
from src.auth.exception import (
    AuthInvalidCredentialsError,
    AuthUserAlreadyExistsError,
    AuthUserUnverifiedError,
)
from src.auth.repository import TotpRepository, UserRepository
from src.auth.repository_sqlalchemy import (
    sqlalchemy_totp_repository_factory,
    sqlalchemy_user_repository_factory,
)
from src.auth.schema import LoginChallengeResponse, UserSchema
from src.auth.service import EmailVerificationService
from src.config.settings import settings
from src.core.redis import RedisManager
from src.core.redis import redis_manager as default_redis_manager

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60
_dummy_hasher = PasswordHasher()
_DUMMY_PASSWORD_HASH = _dummy_hasher.hash("dummy-password-for-timing")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


class UserApi:
    _user_repository: UserRepository
    _email_verification_service: EmailVerificationService
    _totp_repository: TotpRepository | None
    _redis_manager: RedisManager

    def __init__(
        self,
        user_repository: UserRepository,
        email_verification_service: EmailVerificationService,
        totp_repository: TotpRepository | None = None,
        redis_manager: RedisManager | None = None,
    ):
        self._user_repository = user_repository
        self._email_verification_service = email_verification_service
        self._totp_repository = totp_repository
        self._redis_manager = (
            redis_manager if redis_manager is not None else default_redis_manager
        )

    async def get_current_user_from_token(self, token: str) -> User:
        """Retrieve the current user from the provided JWT token."""
        try:
            token_data = self._decode_token(token)
        except jwt.ExpiredSignatureError as e:
            raise HTTPException(401, "Token expired") from e

        if token_data.scope != "access":
            raise HTTPException(401, "Token invalid")

        if token_data.jti:
            async with self._redis_manager.client() as redis:
                if await redis.get(f"token:deny:{token_data.jti}"):
                    raise HTTPException(401, "Token revoked")

        user = await self._user_repository.get_by_email(token_data.sub)

        if not user:
            raise HTTPException(401, "Token invalid")

        return User(id=user.id, email=user.email)

    def create_access_token(
        self,
        user_email: str,
        user_id: UUID,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a JWT access token for the user."""
        access_token_data = AccessTokenData(
            sub=user_email,
            user_id=str(user_id),
            exp=int(
                (
                    datetime.now(UTC)
                    + (expires_delta or timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES))
                ).timestamp()
            ),
            scope="access",
            jti=str(uuid4()),
        )

        return jwt.encode(
            access_token_data.model_dump(),
            settings.secret_key,
            algorithm=_ALGORITHM,
        )

    def create_mfa_token(
        self,
        user_email: str,
        user_id: UUID,
        expires_delta: timedelta | None = None,
    ) -> str:
        """Create a short-lived MFA token for 2FA challenge."""
        mfa_token_data = AccessTokenData(
            sub=user_email,
            user_id=str(user_id),
            exp=int(
                (
                    datetime.now(UTC) + (expires_delta or timedelta(minutes=5))
                ).timestamp()
            ),
            scope="mfa_pending",
        )

        return jwt.encode(
            mfa_token_data.model_dump(),
            settings.secret_key,
            algorithm=_ALGORITHM,
        )

    def verify_mfa_token(self, token: str) -> AccessTokenData:
        """Decode MFA token, validate expiration and assert scope == 'mfa_pending'."""
        token_data = self._decode_token(token)
        if token_data.scope != "mfa_pending":
            raise HTTPException(401, "Token invalid")
        return token_data

    async def signup(self, email: str, plain_text_password: str) -> SignupResponse:
        """Register a new user and send a verification email."""
        existing_user = await self._user_repository.get_by_email(email)

        if existing_user is not None:
            raise AuthUserAlreadyExistsError

        user = await self._user_repository.create_user(email, plain_text_password)

        await self._email_verification_service.generate_and_send_verification(
            user.email, user.id
        )

        return SignupResponse(
            message="User created. Please verify your email before logging in."
        )

    async def login(
        self, email: str, plain_text_password: str
    ) -> AuthResponse | LoginChallengeResponse:
        """Authenticate a user and return an access token or 2FA challenge."""
        user = await self._user_repository.get_by_email(email)

        if not user:
            # Perform dummy verify to equalize timing with the known-user path
            with contextlib.suppress(Exception):
                _dummy_hasher.verify(_DUMMY_PASSWORD_HASH, plain_text_password)
            raise AuthInvalidCredentialsError

        result = user.verify_password(plain_text_password)

        if not result:
            raise AuthInvalidCredentialsError

        if not user.is_verified:
            # Deliberate: 403 tells the user to check their inbox for verification.
            # Folding this into generic 401 would leave users unable to self-recover.
            raise AuthUserUnverifiedError

        if self._totp_repository:
            totp = await self._totp_repository.get_by_user_id(user.id)
            if totp and totp.is_verified:
                mfa_token = self.create_mfa_token(user.email, user.id)
                return LoginChallengeResponse(requires_2fa=True, mfa_token=mfa_token)

        access_token = self.create_access_token(user.email, user.id)

        return AuthResponse(
            access_token=access_token,
            user=User(id=user.id, email=user.email),
        )

    async def verify_email(self, token: str) -> None:
        """Verify a user's email address using the provided token."""
        await self._email_verification_service.verify_token(token)

    async def resend_verification(self, email: str) -> None:
        """Resend the email verification token to the specified email address."""
        await self._email_verification_service.resend_verification(email)

    async def get_user_by_id(self, user_id: UserId) -> UserSchema | None:
        """Look up a user schema by user ID."""
        return await self._user_repository.get_by_id(user_id)

    async def get_email_for_user(self, user_id: UserId) -> str | None:
        """Look up a user's email by user ID, returning None if not found."""
        user = await self._user_repository.get_by_id(user_id)
        return user.email if user else None

    async def get_preferences(self, user_id: UserId) -> dict | None:
        """Retrieve the user's stored preferences, returning None if not saved."""
        return await self._user_repository.get_preferences(user_id)

    async def save_preferences(self, user_id: UserId, preferences: dict) -> None:
        """Store the user's preferences."""
        await self._user_repository.save_preferences(user_id, preferences)

    async def patch_preferences(self, user_id: UserId, preferences: dict) -> dict:
        """Partially update and retrieve the user's stored preferences."""
        return await self._user_repository.patch_preferences(user_id, preferences)

    async def revoke_token(self, token: str) -> None:
        """Revoke a JWT token by adding its jti to the Redis denylist."""
        try:
            token_data = self._decode_token(token)
        except HTTPException:
            return

        if not token_data.jti:
            return

        now = int(datetime.now(UTC).timestamp())
        remaining_ttl = token_data.exp - now
        if remaining_ttl > 0:
            async with self._redis_manager.client() as redis:
                await redis.setex(f"token:deny:{token_data.jti}", remaining_ttl, "1")

    async def update_last_login(self, user_id: UserId) -> None:
        """Update the user's last login timestamp."""
        await self._user_repository.update_last_login(user_id)

    def _decode_token(self, token: str) -> AccessTokenData:
        """Decode and validate a JWT token."""
        try:
            return AccessTokenData.model_validate(
                jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM]),
            )
        except jwt.ExpiredSignatureError as e:
            raise HTTPException(401, "Token expired") from e
        except (jwt.DecodeError, ValidationError) as e:
            message = "User unauthenticated or malformed token"
            raise HTTPException(401, message) from e


async def user_api_factory(
    container: Container,
) -> UserApi:
    return UserApi(
        user_repository=await sqlalchemy_user_repository_factory(container),
        email_verification_service=await container.aget(EmailVerificationService),
        totp_repository=await sqlalchemy_totp_repository_factory(container),
    )


class AuthorizationApi:
    _user_service: UserApi

    def __init__(self, user_service: UserApi) -> None:
        self._user_service = user_service

    def check_entity_owned_by_user(
        self, user: User | UserSchema, entity: BaseModel | None, field: str = "user_id"
    ):
        """Verify that the given entity is owned by the user."""
        if entity is None or user.id != getattr(entity, field):
            # Hide entity existance for security reasons
            raise HTTPException(404, "Entity does not exist")

    async def check_entity_owned_by_user_from_token(
        self, token: str, entity: BaseModel | None, field: str = "user_id"
    ):
        """Verify that the given entity is owned by the user identified by the token."""
        user = await self._user_service.get_current_user_from_token(token)
        self.check_entity_owned_by_user(user, entity, field)


async def authorization_api_factory(
    container: Container,
) -> AuthorizationApi:
    return AuthorizationApi(
        user_service=await user_api_factory(container),
    )


async def get_token(
    request: Request,
    token_from_header: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> str:
    token = request.cookies.get("auth_token") or token_from_header
    if not token:
        raise HTTPException(401, "Not authenticated")
    return token


async def current_user(
    token: Annotated[str, Depends(get_token)],
    services: DepContainer,
) -> AsyncGenerator[User]:
    user_service = await services.aget(UserApi)
    yield await user_service.get_current_user_from_token(token)
