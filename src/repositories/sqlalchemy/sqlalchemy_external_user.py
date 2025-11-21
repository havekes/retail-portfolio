from typing import override
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.external_user import ExternalUser as ExternalUserModel
from src.repositories.external_user import ExternalUserRepository
from src.schemas.external_user import FullExternalUser


class SqlAlchemyExternalUserRepository(ExternalUserRepository):
    session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, external_user: FullExternalUser) -> FullExternalUser:
        external_user_model = ExternalUserModel(**external_user.model_dump())
        self.session.add(external_user_model)
        await self.session.commit()
        return external_user

    async def get_by_user_and_institution(
        self, user_id: UUID, institution_id: int
    ) -> list[FullExternalUser]:
        q = select(ExternalUserModel).where(
            ExternalUserModel.user_id == user_id,
            ExternalUserModel.institution_id == institution_id,
        )
        results = await self.session.scalars(q)
        return [
            FullExternalUser.model_validate(external_user)
            for external_user in results.all()
        ]

    async def exists_external_user_by_user_and_institution(
        self, user_id: UUID, institution_id: int
    ) -> bool:
        q = select(ExternalUserModel).where(
            ExternalUserModel.user_id == user_id,
            ExternalUserModel.institution_id == institution_id,
        )
        return bool(await self.session.scalar(select(q.exists())))
