from svcs import Registry
from svcs.fastapi import DepContainer

from src.integration.brokers.wealthsimple import (
    WealthsimpleApiGateway,
    wealthsimple_api_wrapper_factory,
)
from src.integration.service import (
    IntegrationUserService,
    integration_user_service_factory,
)


def register_integration_services(registry: Registry) -> None:
    # Create wrappers that svcs will properly detect as taking a container
    async def wealthsimple_gateway_wrapper(_svcs_container: DepContainer):
        return await wealthsimple_api_wrapper_factory()

    async def integration_user_service_wrapper(svcs_container: DepContainer):
        return await integration_user_service_factory(svcs_container)

    registry.register_factory(WealthsimpleApiGateway, wealthsimple_gateway_wrapper)
    registry.register_factory(IntegrationUserService, integration_user_service_wrapper)
