from svcs import Registry

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
