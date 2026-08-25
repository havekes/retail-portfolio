from datetime import UTC, datetime
from typing import override
from uuid import UUID, uuid4

from sqlalchemy import cast, delete, func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Container

from src.auth.api_types import UserId
from src.auth.model import (
    PasskeyModel,
    RecoveryCodeModel,
    TotpModel,
    UserModel,
    VerificationTokenModel,
)
from src.auth.repository import (
    PasskeyRepository,
    RecoveryCodeRepository,
    TotpRepository,
    UserRepository,
    VerificationTokenRepository,
)
from src.auth.schema import (
    PasskeySchema,
    RecoveryCodeSchema,
    TotpSchema,
    UserSchema,
    VerificationTokenSchema,
)


class SqlAlchemyUserRepository(UserRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_id(self, user_id: UserId) -> UserSchema | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        user_model = result.scalar_one_or_none()

        if user_model:
            return UserSchema.model_validate(user_model)

        return None

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

    @override
    async def get_preferences(self, user_id: UserId) -> dict | None:
        result = await self._session.execute(
            select(UserModel.preferences).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()

    @override
    async def save_preferences(self, user_id: UserId, preferences: dict) -> None:
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(preferences=preferences)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    @override
    async def patch_preferences(self, user_id: UserId, preferences: dict) -> dict:
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(
                preferences=func.coalesce(
                    cast(UserModel.preferences, JSONB),
                    cast({}, JSONB),
                ).op("||")(cast(preferences, JSONB))
            )
            .returning(UserModel.preferences)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        updated = result.scalar_one_or_none()
        return updated if updated is not None else {}


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


class SqlAlchemyTotpRepository(TotpRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def get_by_user_id(self, user_id: UserId) -> TotpSchema | None:
        result = await self._session.execute(
            select(TotpModel).where(TotpModel.user_id == user_id)
        )
        totp_model = result.scalar_one_or_none()
        if totp_model:
            return TotpSchema.model_validate(totp_model)
        return None

    @override
    async def create_or_update(self, user_id: UserId, secret: str) -> TotpSchema:
        result = await self._session.execute(
            select(TotpModel).where(TotpModel.user_id == user_id)
        )
        totp_model = result.scalar_one_or_none()
        if totp_model:
            totp_model.secret = secret
            totp_model.is_verified = False
        else:
            totp_model = TotpModel(
                id=uuid4(),
                user_id=user_id,
                secret=secret,
                is_verified=False,
            )
            self._session.add(totp_model)
        await self._session.commit()
        await self._session.refresh(totp_model)
        return TotpSchema.model_validate(totp_model)

    @override
    async def mark_as_verified(self, user_id: UserId) -> None:
        await self._session.execute(
            update(TotpModel)
            .where(TotpModel.user_id == user_id)
            .values(is_verified=True)
        )
        await self._session.commit()

    @override
    async def delete_by_user_id(self, user_id: UserId) -> None:
        await self._session.execute(
            delete(TotpModel).where(TotpModel.user_id == user_id)
        )
        await self._session.commit()


class SqlAlchemyRecoveryCodeRepository(RecoveryCodeRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def create_recovery_codes(
        self, user_id: UserId, code_hashes: list[str]
    ) -> list[RecoveryCodeSchema]:
        models = [
            RecoveryCodeModel(
                id=uuid4(),
                user_id=user_id,
                code_hash=code_hash,
                is_used=False,
            )
            for code_hash in code_hashes
        ]
        self._session.add_all(models)
        await self._session.commit()
        for m in models:
            await self._session.refresh(m)
        return [RecoveryCodeSchema.model_validate(m) for m in models]

    @override
    async def get_by_user_id(self, user_id: UserId) -> list[RecoveryCodeSchema]:
        result = await self._session.execute(
            select(RecoveryCodeModel).where(RecoveryCodeModel.user_id == user_id)
        )
        return [
            RecoveryCodeSchema.model_validate(model) for model in result.scalars().all()
        ]

    @override
    async def get_active_by_user_id(self, user_id: UserId) -> list[RecoveryCodeSchema]:
        result = await self._session.execute(
            select(RecoveryCodeModel).where(
                RecoveryCodeModel.user_id == user_id,
                RecoveryCodeModel.is_used.is_(False),
            )
        )
        return [
            RecoveryCodeSchema.model_validate(model) for model in result.scalars().all()
        ]

    @override
    async def mark_as_used(self, code_id: UUID) -> None:
        await self._session.execute(
            update(RecoveryCodeModel)
            .where(RecoveryCodeModel.id == code_id)
            .values(is_used=True, used_at=datetime.now(UTC))
        )
        await self._session.commit()

    @override
    async def count_active_by_user_id(self, user_id: UserId) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(RecoveryCodeModel)
            .where(
                RecoveryCodeModel.user_id == user_id,
                RecoveryCodeModel.is_used.is_(False),
            )
        )
        return result.scalar() or 0

    @override
    async def delete_by_user_id(self, user_id: UserId) -> None:
        await self._session.execute(
            delete(RecoveryCodeModel).where(RecoveryCodeModel.user_id == user_id)
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


async def sqlalchemy_totp_repository_factory(
    container: Container,
) -> SqlAlchemyTotpRepository:
    return SqlAlchemyTotpRepository(session=await container.aget(AsyncSession))


async def sqlalchemy_recovery_code_repository_factory(
    container: Container,
) -> SqlAlchemyRecoveryCodeRepository:
    return SqlAlchemyRecoveryCodeRepository(session=await container.aget(AsyncSession))


class SqlAlchemyPasskeyRepository(PasskeyRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    @override
    async def create_passkey(
        self,
        user_id: UserId,
        *,
        credential_id: bytes,
        public_key: bytes,
        sign_count: int = 0,
        name: str = "Passkey",
        transports: list[str] | None = None,
    ) -> PasskeySchema:
        passkey = PasskeyModel(
            id=uuid4(),
            user_id=user_id,
            credential_id=credential_id,
            public_key=public_key,
            sign_count=sign_count,
            name=name,
            transports=transports,
        )
        self._session.add(passkey)
        await self._session.commit()
        await self._session.refresh(passkey)
        return PasskeySchema.model_validate(passkey)

    @override
    async def get_by_id(self, passkey_id: UUID) -> PasskeySchema | None:
        result = await self._session.execute(
            select(PasskeyModel).where(PasskeyModel.id == passkey_id)
        )
        passkey = result.scalar_one_or_none()
        if passkey:
            return PasskeySchema.model_validate(passkey)
        return None

    @override
    async def get_by_credential_id(self, credential_id: bytes) -> PasskeySchema | None:
        result = await self._session.execute(
            select(PasskeyModel).where(PasskeyModel.credential_id == credential_id)
        )
        passkey = result.scalar_one_or_none()
        if passkey:
            return PasskeySchema.model_validate(passkey)
        return None

    @override
    async def get_by_user_id(self, user_id: UserId) -> list[PasskeySchema]:
        result = await self._session.execute(
            select(PasskeyModel)
            .where(PasskeyModel.user_id == user_id)
            .order_by(PasskeyModel.created_at.desc())
        )
        return [PasskeySchema.model_validate(m) for m in result.scalars().all()]

    @override
    async def update_name(self, passkey_id: UUID, name: str) -> PasskeySchema | None:
        result = await self._session.execute(
            update(PasskeyModel)
            .where(PasskeyModel.id == passkey_id)
            .values(name=name)
            .returning(PasskeyModel)
        )
        await self._session.commit()
        passkey = result.scalar_one_or_none()
        if passkey:
            return PasskeySchema.model_validate(passkey)
        return None

    @override
    async def update_sign_count_and_last_used(
        self, passkey_id: UUID, sign_count: int, last_used_at: datetime | None = None
    ) -> None:
        ts = last_used_at or datetime.now(UTC)
        await self._session.execute(
            update(PasskeyModel)
            .where(PasskeyModel.id == passkey_id)
            .values(sign_count=sign_count, last_used_at=ts)
        )
        await self._session.commit()

    @override
    async def delete_by_id(self, passkey_id: UUID, user_id: UserId) -> bool:
        result = await self._session.execute(
            delete(PasskeyModel)
            .where(
                PasskeyModel.id == passkey_id,
                PasskeyModel.user_id == user_id,
            )
            .returning(PasskeyModel.id)
        )
        await self._session.commit()
        return result.scalar_one_or_none() is not None


async def sqlalchemy_passkey_repository_factory(
    container: Container,
) -> SqlAlchemyPasskeyRepository:
    return SqlAlchemyPasskeyRepository(session=await container.aget(AsyncSession))
