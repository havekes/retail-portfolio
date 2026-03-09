from svcs import Registry

from src.integration.api import (
    IntegrationAccountApi,
    IntegrationUserApi,
    integration_account_api_factory,
    integration_api_factory,
)
from src.integration.brokers.wealthsimple import (
    WealthsimpleApiGateway,
    wealthsimple_api_wrapper_factory,
)
from src.integration.repository import IntegrationUserRepository
from src.integration.repository_sqlalchemy import (
    sqlalchemy_integration_user_repository_factory,
)
from src.integration.service import (
    IntegrationUserService,
    integration_user_service_factory,
)


def register_integration_services(registry: Registry) -> None:
    registry.register_factory(WealthsimpleApiGateway, wealthsimple_api_wrapper_factory)
    registry.register_factory(
        IntegrationUserRepository, sqlalchemy_integration_user_repository_factory
    )
    registry.register_factory(IntegrationUserService, integration_user_service_factory)
    registry.register_factory(IntegrationUserApi, integration_api_factory)
    registry.register_factory(IntegrationAccountApi, integration_account_api_factory)
