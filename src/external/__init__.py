from typing import NewType

from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import InstitutionEnum
from src.external.api_wrapper import ExternalAPIWrapper
from src.external.wealthsimple import WealthsimpleApiWrapper
from src.schemas import User


def get_external_api_wrapper_class(
    institution: InstitutionEnum,
) -> type[ExternalAPIWrapper]:
    client_map = {InstitutionEnum.WEALTHSIMPLE.value: WealthsimpleApiWrapper}

    return client_map[institution.value]
