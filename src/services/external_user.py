from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

from svcs import Container

from src.enums import InstitutionEnum
from src.repositories.external_user import ExternalUserRepository
from src.schemas import FullExternalUser, User


class ExternalUserService:
    _external_user_repository: ExternalUserRepository

    def __init__(self, external_user_repository: ExternalUserRepository):
        self._external_user_repository = external_user_repository

    async def get_or_create(
        self, user: User, institution: InstitutionEnum, username: str
    ) -> FullExternalUser:
        external_user = await self._external_user_repository.get_unique(
            user.id, institution.value, username
        )

        # TODO update last_used_at

        if not external_user:
            external_user = await self._external_user_repository.create(
                FullExternalUser(
                    id=uuid4(),
                    user_id=user.id,
                    institution_id=institution.value,
                    external_user_id=username,
                    last_used_at=datetime.now(UTC),
                    display_name=f"{institution.name} account",
                )
            )

        return external_user


async def external_user_service_factory(
    container: Container,
) -> AsyncGenerator[ExternalUserService]:
    yield ExternalUserService(
        external_user_repository=await container.aget(
            ExternalUserRepository,
        ),
    )
