from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from svcs.fastapi import DepContainer

from src.auth.api_types import AccessTokenData, AuthResponse, User
from src.auth.exceptions import AuthInvalidCredentialsError, AuthUserAlreadyExistsError
from src.auth.repository import UserRepository
from src.auth.repository_sqlalchemy import sqlalchemy_user_repository_factory
from src.auth.schema import UserSchema
from src.config.settings import settings

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class AuthService:
    _user_repository: UserRepository

    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository


class UserApi:
    _user_repository: UserRepository

    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def get_current_user_from_token(self, token: str) -> User:
        try:
            token_data = self._decode_token(token)
        except jwt.ExpiredSignatureError as e:
            raise HTTPException(403, "Token expired") from e

        user = await self._user_repository.get_by_email(token_data.sub)

        if not user:
            raise HTTPException(403, "User not found for provided token")

        return User(id=user.id, email=user.email)

    def create_access_token(
        self, user_email: str, expires_delta: timedelta | None = None
    ):
        access_token_data = AccessTokenData(
            sub=user_email,
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

    async def signup(self, email: str, plain_text_password: str) -> AuthResponse:
        existing_user = await self._user_repository.get_by_email(email)

        if existing_user is not None:
            raise AuthUserAlreadyExistsError

        user = await self._user_repository.create_user(email, plain_text_password)
        access_token = self.create_access_token(user.email)

        return AuthResponse(
            access_token=access_token,
            user=User(**user.model_dump()),
        )

    async def login(self, email: str, plain_text_password: str) -> AuthResponse:
        user = await self._user_repository.get_by_email(email)

        if not user:
            raise AuthInvalidCredentialsError

        result = user.verify_password(plain_text_password)

        if not result:
            raise AuthInvalidCredentialsError

        access_token = self.create_access_token(user.email)

        return AuthResponse(
            access_token=access_token,
            user=User(**user.model_dump()),
        )

    def _decode_token(self, token: str) -> AccessTokenData:
        try:
            return AccessTokenData.model_validate(
                jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM]),
            )
        except jwt.DecodeError as e:
            message = "User unauthenticated or malformed token"
            raise HTTPException(401, message) from e


async def user_api_factory(
    container: DepContainer,
) -> UserApi:
    return UserApi(
        user_repository=await sqlalchemy_user_repository_factory(container),
    )


class AuthorizationApi:
    _user_service: UserApi

    def __init__(self, user_service: UserApi) -> None:
        self._user_service = user_service

    def check_entity_owned_by_user(
        self, user: User | UserSchema, entity: BaseModel | None, field: str = "user_id"
    ):
        if entity is None or user.id != getattr(entity, field):
            # Hide entity existance for security reasons
            raise HTTPException(404, "Entity does not exist")

    async def check_entity_owned_by_user_from_token(
        self, token: str, entity: BaseModel | None, field: str = "user_id"
    ):
        user = await self._user_service.get_current_user_from_token(token)
        self.check_entity_owned_by_user(user, entity, field)


async def authorization_api_factory(
    container: DepContainer,
) -> AuthorizationApi:
    return AuthorizationApi(
        user_service=await user_api_factory(container),
    )


async def current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_service: Annotated[UserApi, Depends(user_api_factory)],
) -> AsyncGenerator[User]:
    yield await user_service.get_current_user_from_token(token)
