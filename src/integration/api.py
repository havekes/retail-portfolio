from svcs import Container

from src.account.api_types import Account, AccountId
from src.account.enum import InstitutionEnum
from src.auth.api_types import UserId
from src.integration.api_types import IntegrationUser, IntegrationUserId
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.api_types import BrokerAccountId
from src.integration.brokers.wealthsimple import WealthsimpleApiGateway
from src.integration.exception import IntegrationUserNotFoundError
from src.integration.repository import IntegrationUserRepository


class IntegrationUserApi:
    _repository: IntegrationUserRepository

    def __init__(self, repository: IntegrationUserRepository):
        self._repository = repository

    async def get_by_id(
        self, integration_user_id: IntegrationUserId
    ) -> IntegrationUser:
        integration_user = await self._repository.get(integration_user_id)
        if integration_user is None:
            raise IntegrationUserNotFoundError(integration_user_id)

        return IntegrationUser.model_validate(integration_user)

    async def get_by_user_and_institution(
        self, user_id: UserId, institution: InstitutionEnum
    ) -> list[IntegrationUser]:
        integration_users = await self._repository.get_by_user_and_institution(
            user_id, institution
        )
        return [IntegrationUser.model_validate(u) for u in integration_users]


class IntegrationAccountApi:
    async def sync_account_positions(
        self,
        user_id: UserId,
        account: Account,
        broker_account_id: BrokerAccountId,
    ) -> None:
        from src.integration.task import sync_account_positions_task  # noqa: PLC0415

        sync_account_positions_task(
            user_id,
            account,
            broker_account_id,
            get_broker_gateway_class(InstitutionEnum(account.institution_id)),
        )


def get_broker_gateway_class(
    institution_id: InstitutionEnum,
) -> type[BrokerApiGateway]:
    return {
        InstitutionEnum.WEALTHSIMPLE.value: WealthsimpleApiGateway,
    }[institution_id.value]


async def integration_api_factory(container: Container) -> IntegrationUserApi:
    return IntegrationUserApi(
        repository=await container.aget(IntegrationUserRepository),
    )


async def integration_account_api_factory(_: Container) -> IntegrationAccountApi:
    return IntegrationAccountApi()
