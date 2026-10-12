"""Uniform listing currency resolution and caching for market data."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from src.market.api_types import SupportedExchange
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)

if TYPE_CHECKING:
    from src.market.endpoint_cache import EndpointResponseCache
    from src.market.gateway import MarketGateway

logger = logging.getLogger(__name__)

EXCHANGE_DEFAULT_CURRENCY: dict[SupportedExchange | None, str] = {
    "NYSE": "USD",
    "NASDAQ": "USD",
    "NYSEARCA": "USD",
    "AMEX": "USD",
    "TSX": "CAD",
    "LSE": "GBX",
    None: "USD",
}


def normalize_currency(code: str | None) -> str | None:
    """Normalize currency codes to ISO 4217 upper-case or pence GBX.

    Provider pence values (GBp, GBX) normalize to GBX; any other code is
    upper-cased. Returns None for empty or None inputs.
    """
    if code is None:
        return None
    trimmed = code.strip()
    if not trimmed:
        return None
    if trimmed == "GBp" or trimmed.upper() == "GBX":
        return "GBX"
    return trimmed.upper()


async def resolve_listing_currency(
    gateway: MarketGateway,
    cache: EndpointResponseCache,
    symbol: str,
    exchange: SupportedExchange | str | None = None,
) -> str:
    """Resolve the listing currency for a symbol and exchange.

    Resolution order:
    1. Company profile currency via get_company_profile.
    2. Deterministic exchange fallback (TSX -> CAD, LSE -> GBX, US/None -> USD).

    Caches the resolved currency through EndpointResponseCache with data class
    'metrics' and endpoint 'listing_currency'. If the company profile raises
    MarketDataNotFoundError, the fallback currency is cached and returned.
    If the profile read fails with a provider error, the fallback currency is
    returned and logged at warning level without caching.
    """
    normalized_symbol = symbol.upper()
    fallback = (
        EXCHANGE_DEFAULT_CURRENCY.get(exchange)  # pyright: ignore[reportArgumentType]
        or "USD"
    )
    params = {"symbol": normalized_symbol, "exchange": exchange}

    async def fetch() -> str:
        try:
            profile = await asyncio.to_thread(
                gateway.get_company_profile,
                normalized_symbol,
                exchange=exchange,
            )
        except MarketDataNotFoundError:
            return fallback
        else:
            resolved = normalize_currency(profile.currency)
            return resolved or fallback

    try:
        return await cache.cached_response(
            data_class="metrics",
            endpoint="listing_currency",
            params=params,
            fetch=fetch,
        )
    except (MarketDataProviderError, MarketDataConfigurationError) as exc:
        logger.warning(
            "Profile read failed for listing currency of %s (%s); "
            "falling back to %s: %s",
            normalized_symbol,
            exchange,
            fallback,
            exc,
        )
        return fallback
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Unexpected error resolving listing currency for %s (%s); "
            "falling back to %s: %s",
            normalized_symbol,
            exchange,
            fallback,
            exc,
        )
        return fallback
