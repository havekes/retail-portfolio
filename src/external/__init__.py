from src.enums import InstitutionEnum
from src.external.api_wrapper import ExternalAPIWrapper
from src.external.wealthsimple import WealthsimpleApiWrapper


def get_external_api_wrapper_class(
    institution: InstitutionEnum,
) -> type[ExternalAPIWrapper]:
    client_map = {InstitutionEnum.WEALTHSIMPLE.value: WealthsimpleApiWrapper}

    return client_map[institution.value]
