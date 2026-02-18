from svcs import Registry

from src.market.api import (
    MarketPricesApi,
    SecurityApi,
    market_prices_factory,
    security_api_factory,
)
from src.market.repository import (
    PriceRepository,
    SecurityBrokerRepository,
    SecurityRepository,
)
from src.market.repository_eodhd import eodhd_price_repository_factory
from src.market.repository_sqlalchemy import (
    sqlalchemy_security_broker_repository_factory,
    sqlalchemy_security_repository_factory,
)


def register_market_services(registry: Registry) -> None:
    registry.register_factory(PriceRepository, eodhd_price_repository_factory)
    registry.register_factory(
        SecurityBrokerRepository, sqlalchemy_security_broker_repository_factory
    )
    registry.register_factory(
        SecurityRepository, sqlalchemy_security_repository_factory
    )
    registry.register_factory(MarketPricesApi, market_prices_factory)
    registry.register_factory(SecurityApi, security_api_factory)
