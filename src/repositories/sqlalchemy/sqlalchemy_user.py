from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Container

from src.models.user import User as UserModel
from src.repositories.user import UserRepository
from src.schemas.user import User


class SqlAlchemyUserRepository(UserRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        user_model = result.scalar_one_or_none()

        if user_model:
            return User.model_validate(user_model)

        return None

    async def create_user(self, email: str, hashed_password: str) -> UserSchema:
        user_db = UserModel(email=email, password=hashed_password)
        self._session.add(user_db)
        await self._session.commit()
        await self._session.refresh(user_db)
        return User.model_validate(user_db)


async def sqlalchemy_user_repository_factory(
    container: Container,
) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session=await container.aget(AsyncSession))
