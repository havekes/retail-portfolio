from typing import override

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Container

from src.auth.model import UserModel
from src.auth.repository import UserRepository
from src.auth.schema import UserSchema


class SqlAlchemyUserRepository(UserRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_email(self, email: str) -> UserSchema | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        user_model = result.scalar_one_or_none()

        if user_model:
            return UserSchema.model_validate(user_model)

        return None

    @override
    async def create_user(self, email: str, plain_text_password: str) -> UserSchema:
        user_db = UserModel(email=email, password=plain_text_password)
        self._session.add(user_db)
        await self._session.commit()
        await self._session.refresh(user_db)
        return UserSchema.model_validate(user_db)


async def sqlalchemy_user_repository_factory(
    container: Container,
) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session=await container.aget(AsyncSession))
