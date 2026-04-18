from svcs import Registry

from src.market.ai_service import AIService, ai_service_factory
from src.market.api import (
    MarketPricesApi,
    SecurityApi,
    market_prices_factory,
    security_api_factory,
)
from src.market.cache import IndicatorCache, indicator_cache_factory
from src.market.eodhd import eodhd_gateway_factory
from src.market.gateway import MarketGateway
from src.market.repository import (
    IndicatorPreferencesRepository,
    PriceAlertRepository,
    PriceRepository,
    SecurityBrokerRepository,
    SecurityDocumentRepository,
    SecurityNoteRepository,
    SecurityRepository,
    WatchlistRepository,
)
from src.market.repository_eodhd import eodhd_price_repository_factory
from src.market.repository_sqlalchemy import (
    sqlalchemy_indicator_preferences_repository_factory,
    sqlalchemy_price_alert_repository_factory,
    sqlalchemy_security_broker_repository_factory,
    sqlalchemy_security_document_repository_factory,
    sqlalchemy_security_note_repository_factory,
    sqlalchemy_security_repository_factory,
    sqlalchemy_watchlist_repository_factory,
)
from src.market.service import MarketService, market_service_factory


def register_market_services(registry: Registry) -> None:
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
    registry.register_factory(
        PriceAlertRepository, sqlalchemy_price_alert_repository_factory
    )
    registry.register_factory(
        SecurityNoteRepository, sqlalchemy_security_note_repository_factory
    )
    registry.register_factory(
        SecurityDocumentRepository, sqlalchemy_security_document_repository_factory
    )
    registry.register_factory(
        IndicatorPreferencesRepository,
        sqlalchemy_indicator_preferences_repository_factory,
    )
    registry.register_factory(IndicatorCache, indicator_cache_factory)
    registry.register_factory(MarketPricesApi, market_prices_factory)
    registry.register_factory(SecurityApi, security_api_factory)
    registry.register_factory(MarketService, market_service_factory)
    registry.register_factory(AIService, ai_service_factory)
