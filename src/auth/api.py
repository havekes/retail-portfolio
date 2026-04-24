from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ValidationError
from svcs import Container
from svcs.fastapi import DepContainer

from src.auth.api_types import AccessTokenData, AuthResponse, SignupResponse, User
from src.auth.exceptions import (
    AuthInvalidCredentialsError,
    AuthUserAlreadyExistsError,
    AuthUserUnverifiedError,
)
from src.auth.repository import UserRepository
from src.auth.repository_sqlalchemy import sqlalchemy_user_repository_factory
from src.auth.schema import UserSchema
from src.auth.service import EmailVerificationService
from src.config.settings import settings

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


class UserApi:
    _user_repository: UserRepository
    _email_verification_service: EmailVerificationService

    def __init__(
        self,
        user_repository: UserRepository,
        email_verification_service: EmailVerificationService,
    ):
        self._user_repository = user_repository
        self._email_verification_service = email_verification_service

    async def get_current_user_from_token(self, token: str) -> User:
        """Retrieve the current user from the provided JWT token."""
        try:
            token_data = self._decode_token(token)
        except jwt.ExpiredSignatureError as e:
            raise HTTPException(403, "Token expired") from e

        user = await self._user_repository.get_by_email(token_data.sub)

        if not user:
            raise HTTPException(403, "Token invalid")

        return User(id=user.id, email=user.email)

    def create_access_token(
        self,
        user_email: str,
        user_id: UUID,
        expires_delta: timedelta | None = None,
    ):
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
        )

        return jwt.encode(
            access_token_data.model_dump(),
            settings.secret_key,
            algorithm=_ALGORITHM,
        )

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

    async def login(self, email: str, plain_text_password: str) -> AuthResponse:
        """Authenticate a user and return an access token."""
        user = await self._user_repository.get_by_email(email)

        if not user:
            raise AuthInvalidCredentialsError

        result = user.verify_password(plain_text_password)

        if not result:
            raise AuthInvalidCredentialsError

        if not user.is_verified:
            raise AuthUserUnverifiedError

        access_token = self.create_access_token(user.email, user.id)

        return AuthResponse(
            access_token=access_token,
            user=User(**user.model_dump()),
        )

    async def verify_email(self, token: str) -> None:
        """Verify a user's email address using the provided token."""
        await self._email_verification_service.verify_token(token)

    async def resend_verification(self, email: str) -> None:
        """Resend the email verification token to the specified email address."""
        await self._email_verification_service.resend_verification(email)

    def _decode_token(self, token: str) -> AccessTokenData:
        """Decode and validate a JWT token."""
        try:
            return AccessTokenData.model_validate(
                jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM]),
            )
        except (jwt.DecodeError, ValidationError) as e:
            message = "User unauthenticated or malformed token"
            raise HTTPException(401, message) from e


async def user_api_factory(
    container: Container,
) -> UserApi:
    return UserApi(
        user_repository=await sqlalchemy_user_repository_factory(container),
        email_verification_service=await container.aget(EmailVerificationService),
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
