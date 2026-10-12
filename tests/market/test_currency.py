"""Tests for listing currency resolution and caching."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from src.market.api_types import CompanyProfile
from src.market.currency import (
    EXCHANGE_DEFAULT_CURRENCY,
    normalize_currency,
    resolve_listing_currency,
)
from src.market.endpoint_cache import EndpointResponseCache
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)
from src.market.gateway import MarketGateway


def test_normalize_currency() -> None:
    assert normalize_currency(None) is None
    assert normalize_currency("") is None
    assert normalize_currency("   ") is None
    assert normalize_currency("usd") == "USD"
    assert normalize_currency("USD") == "USD"
    assert normalize_currency("cad") == "CAD"
    assert normalize_currency("CAD") == "CAD"
    assert normalize_currency("eur") == "EUR"
    assert normalize_currency("gbp") == "GBP"
    assert normalize_currency("GBP") == "GBP"
    assert normalize_currency("GBp") == "GBX"
    assert normalize_currency("GBX") == "GBX"
    assert normalize_currency("gbx") == "GBX"


def test_exchange_default_currency() -> None:
    assert EXCHANGE_DEFAULT_CURRENCY["TSX"] == "CAD"
    assert EXCHANGE_DEFAULT_CURRENCY["LSE"] == "GBX"
    assert EXCHANGE_DEFAULT_CURRENCY["NYSE"] == "USD"
    assert EXCHANGE_DEFAULT_CURRENCY["NASDAQ"] == "USD"
    assert EXCHANGE_DEFAULT_CURRENCY["NYSEARCA"] == "USD"
    assert EXCHANGE_DEFAULT_CURRENCY["AMEX"] == "USD"
    assert EXCHANGE_DEFAULT_CURRENCY[None] == "USD"


@pytest.fixture
def cache() -> EndpointResponseCache:
    return EndpointResponseCache()


@pytest.fixture
def mock_gateway() -> MagicMock:
    gateway = MagicMock(spec=MarketGateway)
    return gateway


@pytest.mark.anyio
async def test_resolve_listing_currency_uses_profile_currency(
    mock_gateway: MagicMock, cache: EndpointResponseCache
) -> None:
    mock_gateway.get_company_profile.return_value = CompanyProfile(
        symbol="AAPL", company_name="Apple", currency="USD"
    )

    currency = await resolve_listing_currency(mock_gateway, cache, "AAPL")
    assert currency == "USD"
    mock_gateway.get_company_profile.assert_called_once_with("AAPL", exchange=None)


@pytest.mark.anyio
async def test_resolve_listing_currency_normalizes_pence(
    mock_gateway: MagicMock, cache: EndpointResponseCache
) -> None:
    mock_gateway.get_company_profile.return_value = CompanyProfile(
        symbol="VOD", company_name="Vodafone", currency="GBp"
    )

    currency = await resolve_listing_currency(
        mock_gateway, cache, "VOD", exchange="LSE"
    )
    assert currency == "GBX"


@pytest.mark.anyio
async def test_resolve_listing_currency_empty_profile_currency_uses_fallback(
    mock_gateway: MagicMock, cache: EndpointResponseCache
) -> None:
    mock_gateway.get_company_profile.return_value = CompanyProfile(
        symbol="SHOP", company_name="Shopify", currency=None
    )

    currency = await resolve_listing_currency(
        mock_gateway, cache, "SHOP", exchange="TSX"
    )
    assert currency == "CAD"


@pytest.mark.anyio
async def test_resolve_listing_currency_missing_profile_uses_fallback_and_caches(
    mock_gateway: MagicMock, cache: EndpointResponseCache
) -> None:
    mock_gateway.get_company_profile.side_effect = MarketDataNotFoundError("SHOP")

    first = await resolve_listing_currency(mock_gateway, cache, "SHOP", exchange="TSX")
    assert first == "CAD"

    second = await resolve_listing_currency(
        mock_gateway, cache, "SHOP", exchange="TSX"
    )
    assert second == "CAD"

    assert mock_gateway.get_company_profile.call_count == 1


@pytest.mark.anyio
async def test_resolve_listing_currency_cached_on_repeated_calls(
    mock_gateway: MagicMock, cache: EndpointResponseCache
) -> None:
    mock_gateway.get_company_profile.return_value = CompanyProfile(
        symbol="AAPL", company_name="Apple", currency="USD"
    )

    first = await resolve_listing_currency(mock_gateway, cache, "AAPL")
    second = await resolve_listing_currency(mock_gateway, cache, "AAPL")
    assert first == "USD"
    assert second == "USD"
    assert mock_gateway.get_company_profile.call_count == 1


@pytest.mark.anyio
async def test_resolve_listing_currency_provider_error_falls_back_and_logs_warning(
    mock_gateway: MagicMock,
    cache: EndpointResponseCache,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_gateway.get_company_profile.side_effect = MarketDataProviderError(
        "FMP 500 error"
    )

    with caplog.at_level(logging.WARNING):
        currency = await resolve_listing_currency(
            mock_gateway, cache, "SHOP", exchange="TSX"
        )

    assert currency == "CAD"
    assert any("Profile read failed" in record.message for record in caplog.records)


@pytest.mark.anyio
async def test_resolve_listing_currency_configuration_error_falls_back(
    mock_gateway: MagicMock,
    cache: EndpointResponseCache,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_gateway.get_company_profile.side_effect = MarketDataConfigurationError(
        "Missing API key"
    )

    with caplog.at_level(logging.WARNING):
        currency = await resolve_listing_currency(
            mock_gateway, cache, "VOD", exchange="LSE"
        )

    assert currency == "GBX"
    assert any("Profile read failed" in record.message for record in caplog.records)
