from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from svcs import Container

from src.auth.api_types import AccessTokenData, AuthResponse, User
from src.auth.exceptions import AuthInvalidCredentialsError, AuthUserAlreadyExistsError
from src.auth.repository import UserRepository
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
        token_data = self._decode_token(token)
        user = await self._user_repository.get_by_email(token_data.sub)

        if not user:
            error = "User not found for provided token"
            raise SystemError(error)

        return User.model_validate(user)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def hash_password(self, password: str) -> str:
        password_bytes = password.encode("utf-8")[:72]
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

        return hashed.decode("utf-8")

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

    async def signup(self, email: str, password: str) -> AuthResponse:
        existing_user = await self._user_repository.get_by_email(email)

        if existing_user is not None:
            raise AuthUserAlreadyExistsError

        hashed_password = self.hash_password(password)
        user = await self._user_repository.create_user(email, hashed_password)
        access_token = self.create_access_token(user.email)

        return AuthResponse(
            access_token=access_token,
            user=User.model_validate(user),
        )

    async def login(self, email: str, password: str) -> AuthResponse:
        user = await self._user_repository.get_by_email(email)

        if not user or not self.verify_password(password, user.password):
            raise AuthInvalidCredentialsError

        access_token = self.create_access_token(user.email)

        return AuthResponse(
            access_token=access_token,
            user=User.model_validate(user),
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
    container: Container,
) -> UserApi:
    return UserApi(
        user_repository=await container.aget(UserRepository),
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
    container: Container,
) -> AuthorizationApi:
    return AuthorizationApi(
        user_service=await user_api_factory(container),
    )


async def current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_service: Annotated[UserApi, Depends(user_api_factory)],
) -> AsyncGenerator[User]:
    yield await user_service.get_current_user_from_token(token)
