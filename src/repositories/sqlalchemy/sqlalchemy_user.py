from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User as UserModel
from src.repositories.user import UserRepository
from src.schemas.user import User


class SqlAlchemyUserRepository(UserRepository):
    session: AsyncSession

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        user_model = result.scalar_one_or_none()

        if user_model:
            return User.model_validate(user_model)

        return None
