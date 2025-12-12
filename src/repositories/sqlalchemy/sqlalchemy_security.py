from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Container

from src.models.security import Security as SecurityModel
from src.repositories.security import SecurityRepository
from src.schemas.security import Security


class SqlAlchemySecurityRepository(SecurityRepository):
    _session: AsyncSession

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_or_create(self, security: Security) -> Security:
        values = security.model_dump()
        await self._session.execute(
            insert(SecurityModel).values(values).on_conflict_do_nothing()
        )

        security_model = await self._session.get(SecurityModel, security.symbol)
        assert security_model is not None
        result = Security.model_validate(security_model)
        await self._session.commit()
        return result


async def sqlaclhemy_security_repository_factory(
    container: Container,
) -> SqlAlchemySecurityRepository:
    return SqlAlchemySecurityRepository(session=await container.aget(AsyncSession))
