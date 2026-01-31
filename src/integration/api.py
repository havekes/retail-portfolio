from src.account.enum import InstitutionEnum
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.wealthsimple import WealthsimpleApiGateway


def get_broker_gateway_class(
    institution_id: InstitutionEnum,
) -> type[BrokerApiGateway]:
    return {
        InstitutionEnum.WEALTHSIMPLE.value: WealthsimpleApiGateway,
    }[institution_id.value]
