from sqlalchemy.ext.asyncio import AsyncSession
from svcs import Registry

from src.account.registry import register_account_services
from src.auth import register_auth_services
from src.config.database import DatabaseSessionManager
from src.config.settings import settings
from src.integration.registry import register_integration_services
from src.market import register_market_services
from src.stubs.wealthsimple import StubWealthsimpleApiGateway


def register_services(
    registry: Registry,
    sessionmanager: DatabaseSessionManager,
) -> None:
    registry.register_factory(AsyncSession, sessionmanager.session)

    # Account APIs and Repositories
    register_account_services(registry)
    register_auth_services(registry)

    # Conditionally register stub or production services
    if settings.stub_external_api:
        register_integration_stub_services(registry)
        register_market_stub_services(registry)
    else:
        register_integration_services(registry)
        register_market_services(registry)


def register_integration_stub_services(registry: Registry) -> None:
    """Register stub services for integration domain."""
    from src.integration.api import (  # noqa: PLC0415
        IntegrationAccountApi,
        IntegrationUserApi,
        integration_account_api_factory,
        integration_api_factory,
    )
    from src.integration.brokers.wealthsimple import (  # noqa: PLC0415
        WealthsimpleApiGateway,
    )
    from src.integration.repository import IntegrationUserRepository  # noqa: PLC0415
    from src.integration.repository_sqlalchemy import (  # noqa: PLC0415
        sqlalchemy_integration_user_repository_factory,
    )
    from src.integration.service import (  # noqa: PLC0415
        IntegrationUserService,
        integration_user_service_factory,
    )

    registry.register_factory(WealthsimpleApiGateway, StubWealthsimpleApiGateway)
    registry.register_factory(
        IntegrationUserRepository, sqlalchemy_integration_user_repository_factory
    )
    registry.register_factory(IntegrationUserService, integration_user_service_factory)
    registry.register_factory(IntegrationUserApi, integration_api_factory)
    registry.register_factory(IntegrationAccountApi, integration_account_api_factory)


def register_market_stub_services(registry: Registry) -> None:
    """Register stub services for market domain."""
    from src.market.api import (  # noqa: PLC0415
        MarketPricesApi,
        SecurityApi,
        market_prices_factory,
        security_api_factory,
    )
    from src.market.eodhd import eodhd_gateway_factory  # noqa: PLC0415
    from src.market.gateway import MarketGateway  # noqa: PLC0415
    from src.market.repository import (  # noqa: PLC0415
        PriceRepository,
        SecurityBrokerRepository,
        SecurityRepository,
        WatchlistRepository,
    )
    from src.market.repository_eodhd import (  # noqa: PLC0415
        eodhd_price_repository_factory,
    )
    from src.market.repository_sqlalchemy import (  # noqa: PLC0415
        sqlalchemy_security_broker_repository_factory,
        sqlalchemy_security_repository_factory,
        sqlalchemy_watchlist_repository_factory,
    )
    from src.market.service import (  # noqa: PLC0415
        MarketService,
        market_service_factory,
    )

    registry.register_factory(MarketGateway, eodhd_gateway_factory)
    registry.register_factory(PriceRepository, eodhd_price_repository_factory)
    registry.register_factory(
        SecurityBrokerRepository, sqlalchemy_security_broker_repository_factory
    )
    registry.register_factory(
        SecurityRepository, sqlalchemy_security_repository_factory
    )
    registry.register_factory(
        WatchlistRepository, sqlalchemy_watchlist_repository_factory
    )
    registry.register_factory(MarketPricesApi, market_prices_factory)
    registry.register_factory(SecurityApi, security_api_factory)
    registry.register_factory(MarketService, market_service_factory)
