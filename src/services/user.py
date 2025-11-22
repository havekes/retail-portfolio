from collections.abc import Generator

from src.enums import InstitutionEnum
from src.repositories.external_user import ExternalUserRepository, FullExternalUser
from src.repositories.user import UserRepository
from src.schemas import User


class UserService:
    user_repository: UserRepository
    external_account_repository: ExternalUserRepository

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

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
            await self.external_account_repository.get_by_user_and_institution(
                user.id, institution.value
            )
        )

        return (account.external_user_id for account in external_accounts)
