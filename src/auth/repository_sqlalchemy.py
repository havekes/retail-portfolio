from datetime import datetime
from typing import override
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Container

from src.auth.api_types import UserId
from src.auth.model import UserModel, VerificationTokenModel
from src.auth.repository import UserRepository, VerificationTokenRepository
from src.auth.schema import UserSchema, VerificationTokenSchema


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

    @override
    async def mark_as_verified(self, user_id: UserId) -> None:
        await self._session.execute(
            update(UserModel).where(UserModel.id == user_id).values(is_verified=True)
        )
        await self._session.commit()


class SqlAlchemyVerificationTokenRepository(VerificationTokenRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def create_token(
        self, user_id: UserId, token: str, expires_at: datetime
    ) -> VerificationTokenSchema:
        token_db = VerificationTokenModel(
            id=str(uuid4()),
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )
        self._session.add(token_db)
        await self._session.commit()
        await self._session.refresh(token_db)
        return VerificationTokenSchema.model_validate(token_db)

    @override
    async def get_by_token(self, token: str) -> VerificationTokenSchema | None:
        result = await self._session.execute(
            select(VerificationTokenModel).where(VerificationTokenModel.token == token)
        )
        token_model = result.scalar_one_or_none()
        if token_model:
            return VerificationTokenSchema.model_validate(token_model)
        return None

    @override
    async def get_by_user(self, user_id: UserId) -> VerificationTokenSchema | None:
        result = await self._session.execute(
            select(VerificationTokenModel)
            .where(VerificationTokenModel.user_id == user_id)
            .where(VerificationTokenModel.is_used.is_(False))
            .order_by(VerificationTokenModel.created_at.desc())
        )
        token_model = result.scalars().first()
        if token_model:
            return VerificationTokenSchema.model_validate(token_model)
        return None

    @override
    async def mark_as_used(self, token_id: str) -> None:
        await self._session.execute(
            update(VerificationTokenModel)
            .where(VerificationTokenModel.id == token_id)
            .values(is_used=True)
        )
        await self._session.commit()

    @override
    async def invalidate_tokens_for_user(self, user_id: UserId) -> None:
        await self._session.execute(
            update(VerificationTokenModel)
            .where(VerificationTokenModel.user_id == user_id)
            .values(is_used=True)
        )
        await self._session.commit()


async def sqlalchemy_user_repository_factory(
    container: Container,
) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session=await container.aget(AsyncSession))


async def sqlalchemy_verification_token_repository_factory(
    container: Container,
) -> SqlAlchemyVerificationTokenRepository:
    return SqlAlchemyVerificationTokenRepository(
        session=await container.aget(AsyncSession)
    )
