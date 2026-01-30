from src.account.api_types import InstitutionEnum
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.wealthsimple import WealthsimpleApiGateway


def get_broker_gateway_class(
    institution: InstitutionEnum,
) -> type[BrokerApiGateway]:
    return {
        InstitutionEnum.WEALTHSIMPLE.value: WealthsimpleApiGateway,
    }[institution.value]
