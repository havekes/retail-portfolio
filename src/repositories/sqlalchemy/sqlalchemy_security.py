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

    async def create_or_update(self, security: Security) -> Security:
        pass


async def sqlaclhemy_security_repository_factory(
    container: Container,
) -> SqlAlchemySecurityRepository:
    return SqlAlchemySecurityRepository(session=await container.aget(AsyncSession))
