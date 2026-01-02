from collections.abc import AsyncGenerator, Generator

from svcs import Container

from src.enums import InstitutionEnum
from src.repositories.external_user import ExternalUserRepository
from src.repositories.user import UserRepository
from src.schemas import User


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

    async def get_current_user(self) -> User:
        """Placeholder, getting user from token should be implemented here"""
        user = await self.user_repository.get_by_email("greg@havek.es")

        if not user:
            error = "User not found"
            raise SystemError(error)

        return user

    async def get_current_user_external_account_ids(
        self, institution: InstitutionEnum
    ) -> Generator[str]:
        user = await self.get_current_user()
        external_accounts = (
            await self.external_user_repository.get_by_user_and_institution(
                user.id, institution.value
            )
        )

        return (account.external_user_id for account in external_accounts)


async def user_service_factory(
    container: Container,
) -> AsyncGenerator[UserService]:
    yield UserService(
        user_repository=await container.aget(UserRepository),
        external_user_repository=await container.aget(ExternalUserRepository),
    )
