from typing import override

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from svcs.fastapi import DepContainer

from src.account.enum import InstitutionEnum
from src.auth.api_types import UserId
from src.integration.api_types import IntegrationUserId
from src.integration.model import IntegrationUserModel
from src.integration.repository import IntegrationUserRepository
from src.integration.schema import IntegrationUserSchema


class SqlAlchemyIntegrationUserRepository(IntegrationUserRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def create(
        self, integration_user: IntegrationUserSchema
    ) -> IntegrationUserSchema:
        integration_user_model = IntegrationUserModel(**integration_user.model_dump())
        self._session.add(integration_user_model)
        await self._session.commit()
        return IntegrationUserSchema.model_validate(integration_user_model)

    @override
    async def get(
        self, integration_user_id: IntegrationUserId
    ) -> IntegrationUserSchema | None:
        query = select(IntegrationUserModel).where(
            IntegrationUserModel.id == integration_user_id
        )
        integration_user_model = await self._session.scalar(query)
        if integration_user_model is None:
            return None
        return IntegrationUserSchema.model_validate(integration_user_model)

    @override
    async def get_by_user_and_institution(
        self, user_id: UserId, institution: InstitutionEnum
    ) -> list[IntegrationUserSchema]:
        query = select(IntegrationUserModel).where(
            IntegrationUserModel.user_id == user_id,
            IntegrationUserModel.institution_id == institution.value,
        )
        integration_user_models = await self._session.scalars(query)
        return [
            IntegrationUserSchema.model_validate(integration_user_model)
            for integration_user_model in integration_user_models.all()
        ]

    @override
    async def get_unique(
        self, user_id: UserId, institution: InstitutionEnum, username: str
    ) -> IntegrationUserSchema | None:
        query = select(IntegrationUserModel).where(
            IntegrationUserModel.user_id == user_id,
            IntegrationUserModel.institution_id == institution.value,
            IntegrationUserModel.external_user_id == username,
        )
        integration_user_model = await self._session.scalar(query)
        if integration_user_model is None:
            return None
        return IntegrationUserSchema.model_validate(integration_user_model)

    @override
    async def exists(
        self, user_id: UserId, institution: InstitutionEnum, username: str
    ) -> bool:
        query = select(IntegrationUserModel).where(
            IntegrationUserModel.user_id == user_id,
            IntegrationUserModel.institution_id == institution.value,
            IntegrationUserModel.external_user_id == username,
        )
        return bool(await self._session.scalar(select(query.exists())))

    @override
    async def update_last_used_at(
        self, integration_user: IntegrationUserSchema
    ) -> None:
        query = (
            update(IntegrationUserModel)
            .where(IntegrationUserModel.id == integration_user.id)
            .values(last_used_at=func.now())
        )

        _ = await self._session.execute(query)
        await self._session.commit()


async def sqlalchemy_integration_user_repository_factory(
    container: DepContainer,
) -> IntegrationUserRepository:
    return SqlAlchemyIntegrationUserRepository(
        session=await container.aget(AsyncSession)
    )
