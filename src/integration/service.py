from datetime import UTC, datetime
from uuid import uuid4

from svcs.fastapi import DepContainer

from src.account.enum import InstitutionEnum
from src.auth.api_types import User
from src.integration.api_types import IntegrationUser
from src.integration.repository import IntegrationUserRepository
from src.integration.repository_sqlalchemy import (
    sqlalchemy_integration_user_repository_factory,
)
from src.integration.schema import IntegrationUserSchema


class IntegrationUserService:
    _integration_user_repository: IntegrationUserRepository

    def __init__(self, integration_user_repository: IntegrationUserRepository):
        self._integration_user_repository = integration_user_repository

    async def get_or_create(
        self, user: User, institution: InstitutionEnum, username: str
    ) -> IntegrationUser:
        integration_user = await self._integration_user_repository.get_unique(
            user.id, institution, username
        )

        if integration_user:
            integration_user.last_used_at = datetime.now(UTC)
            await self._integration_user_repository.update_last_used_at(
                integration_user
            )

        if not integration_user:
            integration_user = await self._integration_user_repository.create(
                IntegrationUserSchema(
                    id=uuid4(),
                    user_id=user.id,
                    institution_id=institution,
                    external_user_id=username,
                    last_used_at=datetime.now(UTC),
                    display_name=f"{institution.name} account",
                )
            )

        return IntegrationUser.model_validate(integration_user)


async def integration_user_service_factory(
    container: DepContainer,
) -> IntegrationUserService:
    return IntegrationUserService(
        integration_user_repository=await sqlalchemy_integration_user_repository_factory(  # noqa: E501
            container
        )
    )
