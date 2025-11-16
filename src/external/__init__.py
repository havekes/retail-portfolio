from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import InstitutionEnum
from src.external.wealthsimple import Wealthsimple
from src.external.wrapper import ExternalAPIWrapper
from src.schemas import User


def get_external_api_wrapper(
    institution: InstitutionEnum, session: AsyncSession, user: User, username: str
) -> ExternalAPIWrapper:
    client_map = {InstitutionEnum.WEALTHSIMPLE.value: Wealthsimple}

    return client_map[institution.value](session, user, username)
