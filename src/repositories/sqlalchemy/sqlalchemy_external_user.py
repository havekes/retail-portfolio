from typing import override
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Container

from src.models.external_user import ExternalUser as ExternalUserModel
from src.repositories.external_user import ExternalUserRepository
from src.schemas.external_user import FullExternalUser


class SqlAlchemyExternalUserRepository(ExternalUserRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @override
    async def create(self, external_user: FullExternalUser) -> FullExternalUser:
        external_user_model = ExternalUserModel(**external_user.model_dump())
        self._session.add(external_user_model)
        await self._session.commit()
        return external_user

    @override
    async def get(self, external_user_id: UUID) -> FullExternalUser | None:
        q = select(ExternalUserModel).where(ExternalUserModel.id == external_user_id)
        result = await self._session.scalar(q)
        if result is None:
            return None
        return FullExternalUser.model_validate(result)

    @override
    async def get_by_user_and_institution(
        self, user_id: UUID, institution_id: int
    ) -> list[FullExternalUser]:
        q = select(ExternalUserModel).where(
            ExternalUserModel.user_id == user_id,
            ExternalUserModel.institution_id == institution_id,
        )
        results = await self._session.scalars(q)
        return [
            FullExternalUser.model_validate(external_user)
            for external_user in results.all()
        ]

    @override
    async def get_unique(
        self, user_id: UUID, institution_id: int, username: str
    ) -> FullExternalUser | None:
        q = select(ExternalUserModel).where(
            ExternalUserModel.user_id == user_id,
            ExternalUserModel.institution_id == institution_id,
            ExternalUserModel.external_user_id == username,
        )
        result = await self._session.scalar(q)
        if result is None:
            return None
        return FullExternalUser.model_validate(result)

    @override
    async def exists(self, user_id: UUID, institution_id: int, username: str) -> bool:
        q = select(ExternalUserModel).where(
            ExternalUserModel.user_id == user_id,
            ExternalUserModel.institution_id == institution_id,
            ExternalUserModel.external_user_id == username,
        )
        return bool(await self._session.scalar(select(q.exists())))

    @override
    async def update_last_used_at(self, external_user: FullExternalUser) -> None:
        q = (
            update(ExternalUserModel)
            .where(ExternalUserModel.id == external_user.id)
            .values(last_used_at=func.now())
        )

        _ = await self._session.execute(q)
        await self._session.commit()


async def sqlalchemy_external_user_repository_factory(
    container: Container,
) -> ExternalUserRepository:
    return SqlAlchemyExternalUserRepository(session=await container.aget(AsyncSession))
