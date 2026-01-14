from collections.abc import AsyncGenerator, Generator

import jwt
from fastapi import HTTPException
from svcs import Container

from src.config.settings import settings
from src.enums import InstitutionEnum
from src.repositories.external_user import ExternalUserRepository
from src.repositories.user import UserRepository
from src.schemas import User
from src.schemas.auth import AccessTokenData
from src.services import auth


class UserService:
    user_repository: UserRepository
    external_user_repository: ExternalUserRepository

    def __init__(
        self,
        user_repository: UserRepository,
        external_user_repository: ExternalUserRepository,
    ):
        self.user_repository = user_repository
        self.external_user_repository = external_user_repository

    async def get_current_user_from_token(self, token: str) -> User:
        token_data = self.decode_token(token)
        user = await self.user_repository.get_by_email(token_data.sub)

        if not user:
            error = "User not found for provided token"
            raise SystemError(error)

        return user

    async def get_external_account_ids(
        self, user: User, institution: InstitutionEnum
    ) -> Generator[str]:
        external_accounts = (
            await self.external_user_repository.get_by_user_and_institution(
                user.id, institution.value
            )
        )

        return (account.external_user_id for account in external_accounts)

    def decode_token(self, token: str) -> AccessTokenData:
        try:
            return AccessTokenData.model_validate(
                jwt.decode(token, settings.secret_key, algorithms=[auth.ALGORITHM]),
            )
        except jwt.DecodeError as e:
            message = "User unauthenticated or malformed token"
            raise HTTPException(401, message) from e


async def user_service_factory(
    container: Container,
) -> AsyncGenerator[UserService]:
    yield UserService(
        user_repository=await container.aget(UserRepository),
        external_user_repository=await container.aget(ExternalUserRepository),
    )
