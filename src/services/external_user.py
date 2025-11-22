from uuid import uuid4

from src.enums import InstitutionEnum
from src.repositories.external_user import ExternalUserRepository
from src.schemas import FullExternalUser, User


class ExternalUserService:
    _external_user_repositorys: ExternalUserRepository

    def __init__(self, external_user_repository: ExternalUserRepository):
        self._external_user_repository = external_user_repository

    async def get_or_create(
        self, user: User, institution: InstitutionEnum, external_user_id: str
    ) -> FullExternalUser:
        external_user = await self._external_user_repository.get(
            user.id,
            institution.value,
            external_user_id,
        )

        if not external_user:
            external_user = await self._external_user_repository.create(
                FullExternalUser(
                    uuid=uuid4(),
                    user_id=user.id,
                    institution_id=institution.value,
                    external_user_id=external_user_id,
                )
            )

        return external_user
