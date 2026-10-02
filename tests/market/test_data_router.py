"""Offline tests for the service-to-service market data endpoints.

The data-plane gateway is a ``MagicMock`` (no provider is ever dialed) and the
endpoint cache is the real T13 ``EndpointResponseCache`` layered over the
autouse in-memory Redis fake. The *real* ``require_service_token`` dependency
runs: tests patch the configured token and send the header, exercising the
byte-comparison path end to end.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
import threading
from unittest.mock import MagicMock

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from src.config.settings import settings
from src.main import app
from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPrice,
    IncomeStatement,
    KeyMetrics,
    OptionsChain,
    OptionsChainEntry,
    OptionsContract,
    OptionsGreeks,
    OptionsQuote,
    SymbolLookupResult,
)
from src.market.endpoint_cache import EndpointResponseCache
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)
from src.market.gateway import DataPlaneMarketGateway, MarketGateway
from tests.fixtures.redis import FakeRedis

_SERVICE_TOKEN = "test-service-token-value"  # noqa: S105

_PRICES_URL = "/api/v1/market/data/prices/AAPL"
_PRICES_QUERY = "?from=2026-01-01&to=2026-01-31"
_SEARCH_URL = "/api/v1/market/data/symbols/search"
_OPTIONS_URL = "/api/v1/market/data/options/AAPL"
_FUNDAMENTALS_URL = "/api/v1/market/data/fundamentals/AAPL"
_STATEMENTS_URL = "/api/v1/market/data/fundamentals/AAPL/statements"

_PROVIDER_NAMES = ("polygon", "fmp", "eodhd", "finnhub")


def _headers(token: str = _SERVICE_TOKEN) -> dict[str, str]:
    return {"X-Service-Token": token}


@pytest.fixture
def mock_gateway() -> MagicMock:
    gateway = MagicMock(spec=MarketGateway)
    gateway.get_prices.return_value = []
    gateway.lookup_symbol.return_value = []
    gateway.get_options_chain.return_value = OptionsChain(underlying_symbol="AAPL")
    gateway.get_company_profile.return_value = _company_profile()
    gateway.get_key_metrics.return_value = _key_metrics()
    gateway.get_financial_ratios.return_value = _financial_ratios()
    gateway.get_income_statement.return_value = [_income_statement()]
    gateway.get_balance_sheet.return_value = [_balance_sheet()]
    gateway.get_cash_flow_statement.return_value = [_cash_flow_statement()]
    return gateway


@pytest.fixture
def endpoint_cache() -> EndpointResponseCache:
    return EndpointResponseCache()


@pytest.fixture
async def client(
    mock_gateway: MagicMock,
    endpoint_cache: EndpointResponseCache,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    """Real app + lifespan, with the data-plane gateway and cache overridden.

    No dependency override is used for ``require_service_token``: the real
    dependency runs against the patched settings token.
    """
    monkeypatch.setattr(settings, "market_data_service_token", _SERVICE_TOKEN)

    async with LifespanManager(app) as manager:
        app.state.svcs_registry.register_value(DataPlaneMarketGateway, mock_gateway)
        app.state.svcs_registry.register_value(EndpointResponseCache, endpoint_cache)
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
        ) as test_client:
            yield test_client


def _historical_price(day: date = date(2026, 1, 2)) -> HistoricalPrice:
    return HistoricalPrice(
        id=1,
        security_id=None,
        date=day,
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("154.00"),
        adjusted_close=Decimal("153.50"),
        volume=1_000_000,
    )


def _options_chain() -> OptionsChain:
    return OptionsChain(
        underlying_symbol="AAPL",
        as_of=date(2026, 1, 2),
        contracts=[
            OptionsChainEntry(
                contract=OptionsContract(
                    contract_ticker="O:AAPL260116C00150000",
                    symbol="AAPL",
                    strike_price=Decimal("150"),
                    expiration_date=date(2026, 1, 16),
                    contract_type="call",
                ),
                quote=OptionsQuote(
                    implied_volatility=Decimal("0.2417"),
                    open_interest=8421,
                    day_volume=1875,
                    greeks=OptionsGreeks(
                        delta=Decimal("0.5314"),
                        gamma=Decimal("0.0128"),
                        theta=Decimal("-0.0731"),
                        vega=Decimal("0.3412"),
                    ),
                ),
            )
        ],
    )


def _company_profile(symbol: str = "AAPL") -> CompanyProfile:
    return CompanyProfile(
        symbol=symbol,
        company_name="Apple Inc.",
        market_cap=Decimal("3400000000000"),
        sector="Technology",
        industry="Consumer Electronics",
        ceo="Tim Cook",
        full_time_employees=164000,
        currency="USD",
    )


def _key_metrics(symbol: str = "AAPL") -> KeyMetrics:
    return KeyMetrics(
        symbol=symbol,
        date=date(2024, 9, 28),
        fiscal_year="2024",
        period="FY",
        market_cap=Decimal("3400000000000"),
        pe_ratio=Decimal("36.28"),
        enterprise_value_over_ebitda=Decimal("25.14"),
    )


def _financial_ratios(symbol: str = "AAPL") -> FinancialRatios:
    return FinancialRatios(
        symbol=symbol,
        date=date(2024, 9, 28),
        fiscal_year="2024",
        period="FY",
        gross_profit_margin=Decimal("0.4621"),
        return_on_equity=Decimal("1.6466"),
        debt_to_equity=Decimal("1.87"),
    )


def _income_statement(symbol: str = "AAPL") -> IncomeStatement:
    return IncomeStatement(
        date=date(2024, 9, 28),
        symbol=symbol,
        reported_currency="USD",
        fiscal_year="2024",
        period="FY",
        revenue=Decimal("391035000000"),
        gross_profit=Decimal("180683000000"),
        net_income=Decimal("93736000000"),
        eps_diluted=Decimal("6.08"),
    )


def _balance_sheet(symbol: str = "AAPL") -> BalanceSheet:
    return BalanceSheet(
        date=date(2024, 9, 28),
        symbol=symbol,
        reported_currency="USD",
        fiscal_year="2024",
        period="FY",
        total_assets=Decimal("364980000000"),
        total_liabilities=Decimal("308030000000"),
        total_equity=Decimal("56950000000"),
    )


def _cash_flow_statement(symbol: str = "AAPL") -> CashFlowStatement:
    return CashFlowStatement(
        date=date(2024, 9, 28),
        symbol=symbol,
        reported_currency="USD",
        fiscal_year="2024",
        period="FY",
        net_income=Decimal("93736000000"),
        operating_cash_flow=Decimal("118254000000"),
        free_cash_flow=Decimal("108807000000"),
    )


def _endpoint_keys(storage: FakeRedis, prefix: str) -> list[str]:
    return [key for key in storage.data if key.startswith(prefix)]


# --------------------------------------------------------------------------- #
# AC1/AC2: unified JSON shapes.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_prices_returns_unified_json(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_prices.return_value = [_historical_price()]

    response = await client.get(f"{_PRICES_URL}{_PRICES_QUERY}", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["exchange"] is None
    assert body["from_date"] == "2026-01-01"
    assert body["to_date"] == "2026-01-31"
    assert len(body["items"]) == 1

    bar = body["items"][0]
    assert bar["date"] == "2026-01-02"
    assert Decimal(str(bar["open"])) == Decimal("150.00")
    assert Decimal(str(bar["adjusted_close"])) == Decimal("153.50")
    assert bar["volume"] == 1_000_000
    # DB-flavoured fields must not leak onto the data plane.
    assert "id" not in bar
    assert "security_id" not in bar


@pytest.mark.anyio
async def test_symbol_search_returns_list(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.lookup_symbol.return_value = [
        SymbolLookupResult(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            exchange_short_name="NASDAQ",
            currency="USD",
            security_type="stock",
            country="US",
        )
    ]

    response = await client.get(f"{_SEARCH_URL}?q=apple", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["symbol"] == "AAPL"
    assert body[0]["exchange_short_name"] == "NASDAQ"
    mock_gateway.lookup_symbol.assert_called_once_with("apple")


@pytest.mark.anyio
async def test_options_returns_polygon_mirrored_fields(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_options_chain.return_value = _options_chain()

    response = await client.get(
        f"{_OPTIONS_URL}?option_type=call&strike_min=100&strike_max=200",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["underlying_symbol"] == "AAPL"

    entry = body["contracts"][0]
    contract = entry["contract"]
    assert contract["contract_ticker"] == "O:AAPL260116C00150000"
    assert Decimal(str(contract["strike_price"])) == Decimal("150")
    assert contract["expiration_date"] == "2026-01-16"
    assert contract["contract_type"] == "call"

    quote = entry["quote"]
    assert Decimal(str(quote["implied_volatility"])) == Decimal("0.2417")
    assert quote["open_interest"] == 8421
    assert quote["day_volume"] == 1875
    assert Decimal(str(quote["greeks"]["delta"])) == Decimal("0.5314")
    assert Decimal(str(quote["greeks"]["gamma"])) == Decimal("0.0128")
    assert Decimal(str(quote["greeks"]["theta"])) == Decimal("-0.0731")
    assert Decimal(str(quote["greeks"]["vega"])) == Decimal("0.3412")

    # The provider-agnostic filters reach the gateway unchanged.
    _args, kwargs = mock_gateway.get_options_chain.call_args
    assert kwargs["contract_type"] == "call"
    assert kwargs["strike_min"] == Decimal("100")
    assert kwargs["strike_max"] == Decimal("200")


# --------------------------------------------------------------------------- #
# AC3: every route is served through the endpoint response cache.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_repeated_prices_request_is_a_cache_hit(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.get_prices.return_value = [_historical_price()]
    url = f"{_PRICES_URL}{_PRICES_QUERY}"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    mock_gateway.get_prices.assert_called_once()
    # The data plane has no security identity: the call carries symbol/exchange
    # and no fabricated placeholder id.
    args, kwargs = mock_gateway.get_prices.call_args
    assert args == ("AAPL", "", date(2026, 1, 1), date(2026, 1, 31))
    assert "security_id" not in kwargs
    assert (
        len(
            _endpoint_keys(
                mock_redis_storage, "market:ep:prices:history:"
            )
        )
        == 1
    )


@pytest.mark.anyio
async def test_repeated_search_is_cached_under_search_class(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.lookup_symbol.return_value = [
        SymbolLookupResult(symbol="AAPL", name="Apple Inc.")
    ]

    await client.get(f"{_SEARCH_URL}?q=apple", headers=_headers())
    await client.get(f"{_SEARCH_URL}?q=apple", headers=_headers())

    mock_gateway.lookup_symbol.assert_called_once()
    keys = _endpoint_keys(mock_redis_storage, "market:ep:search:symbol_lookup:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_repeated_options_is_cached_under_options_class(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.get_options_chain.return_value = _options_chain()

    await client.get(_OPTIONS_URL, headers=_headers())
    await client.get(_OPTIONS_URL, headers=_headers())

    mock_gateway.get_options_chain.assert_called_once()
    keys = _endpoint_keys(mock_redis_storage, "market:ep:options:chain:")
    assert len(keys) == 1


# --------------------------------------------------------------------------- #
# AC4: structured 404 / generic 502-503 with no provider names.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_unknown_symbol_returns_structured_404(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_prices.side_effect = MarketDataNotFoundError("ZZZZ")

    response = await client.get(
        "/api/v1/market/data/prices/ZZZZ?from=2026-01-01&to=2026-01-31",
        headers=_headers(),
    )

    assert response.status_code == 404
    assert "ZZZZ" in response.json()["detail"]


@pytest.mark.anyio
async def test_unknown_symbol_prices_is_negative_cached(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.get_prices.side_effect = MarketDataNotFoundError("ZZZZ")
    url = "/api/v1/market/data/prices/ZZZZ?from=2026-01-01&to=2026-01-31"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 404
    assert first.json()["detail"] == second.json()["detail"]
    # The 404 was negative-cached: the upstream gateway ran exactly once.
    mock_gateway.get_prices.assert_called_once()

    detail = first.json()["detail"].lower()
    for provider in _PROVIDER_NAMES:
        assert provider not in detail

    keys = _endpoint_keys(mock_redis_storage, "market:ep:prices:history:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_unknown_underlying_options_is_negative_cached(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.get_options_chain.side_effect = MarketDataNotFoundError("ZZZZ")
    url = "/api/v1/market/data/options/ZZZZ"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 404
    assert first.json()["detail"] == second.json()["detail"]
    # No second Polygon read for the same missing underlying.
    mock_gateway.get_options_chain.assert_called_once()

    keys = _endpoint_keys(mock_redis_storage, "market:ep:options:chain:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_unknown_symbol_search_is_negative_cached(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.lookup_symbol.side_effect = MarketDataNotFoundError("ZZZZ")
    url = f"{_SEARCH_URL}?q=ZZZZ"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 404
    assert first.json()["detail"] == second.json()["detail"]
    # The 404 was negative-cached: the upstream gateway ran exactly once.
    mock_gateway.lookup_symbol.assert_called_once_with("ZZZZ")

    keys = _endpoint_keys(mock_redis_storage, "market:ep:search:symbol_lookup:")
    assert len(keys) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method_name",
    ["get_company_profile", "get_key_metrics", "get_financial_ratios"],
)
async def test_unknown_fundamentals_symbol_is_negative_cached(
    client: AsyncClient,
    mock_gateway: MagicMock,
    mock_redis_storage: FakeRedis,
    method_name: str,
) -> None:
    getattr(mock_gateway, method_name).side_effect = MarketDataNotFoundError("ZZZZ")
    url = "/api/v1/market/data/fundamentals/ZZZZ"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 404
    assert first.json()["detail"] == second.json()["detail"]
    # The 404 was negative-cached: the upstream gateway ran exactly once.
    getattr(mock_gateway, method_name).assert_called_once()

    keys = _endpoint_keys(mock_redis_storage, "market:ep:metrics:fundamentals:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_unknown_statements_symbol_is_negative_cached(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.get_income_statement.side_effect = MarketDataNotFoundError("ZZZZ")
    url = f"{_STATEMENTS_URL}?statement=income"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 404
    assert first.json()["detail"] == second.json()["detail"]
    # The 404 was negative-cached: the upstream gateway ran exactly once.
    mock_gateway.get_income_statement.assert_called_once()

    keys = _endpoint_keys(mock_redis_storage, "market:ep:statements:statements:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_transient_provider_failure_is_not_negative_cached(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_prices.side_effect = MarketDataProviderError("raw upstream failure")
    url = f"{_PRICES_URL}{_PRICES_QUERY}"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    # A 5xx must propagate uncached: the gateway is retried on the next request.
    assert first.status_code == second.status_code == 502
    assert mock_gateway.get_prices.call_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("side_effect", "expected_status"),
    [
        (MarketDataProviderError("raw upstream failure"), 502),
        (MarketDataConfigurationError("raw config failure"), 503),
    ],
)
async def test_search_provider_failure_is_generic(
    client: AsyncClient,
    mock_gateway: MagicMock,
    side_effect: Exception,
    expected_status: int,
) -> None:
    mock_gateway.lookup_symbol.side_effect = side_effect

    first = await client.get(f"{_SEARCH_URL}?q=apple", headers=_headers())
    second = await client.get(f"{_SEARCH_URL}?q=apple", headers=_headers())

    # A 5xx must propagate uncached: the gateway is retried on the next request.
    assert first.status_code == second.status_code == expected_status
    assert mock_gateway.lookup_symbol.call_count == 2
    detail = first.json()["detail"].lower()
    assert "raw" not in detail
    for provider in _PROVIDER_NAMES:
        assert provider not in detail


@pytest.mark.anyio
async def test_empty_search_returns_404_and_caches_the_empty_result(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.lookup_symbol.return_value = []

    first = await client.get(f"{_SEARCH_URL}?q=nothing", headers=_headers())
    second = await client.get(f"{_SEARCH_URL}?q=nothing", headers=_headers())

    assert first.status_code == 404
    assert second.status_code == 404
    # The empty result was cached, so the gateway ran exactly once.
    mock_gateway.lookup_symbol.assert_called_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("side_effect", "expected_status"),
    [
        (MarketDataProviderError("raw upstream failure"), 502),
        (MarketDataConfigurationError("raw config failure"), 503),
    ],
)
async def test_provider_failure_is_generic(
    client: AsyncClient,
    mock_gateway: MagicMock,
    side_effect: Exception,
    expected_status: int,
) -> None:
    mock_gateway.get_prices.side_effect = side_effect

    response = await client.get(f"{_PRICES_URL}{_PRICES_QUERY}", headers=_headers())

    assert response.status_code == expected_status
    detail = response.json()["detail"].lower()
    assert "raw" not in detail
    for provider in _PROVIDER_NAMES:
        assert provider not in detail


# --------------------------------------------------------------------------- #
# AC1: every route requires the service token.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        f"{_PRICES_URL}{_PRICES_QUERY}",
        f"{_SEARCH_URL}?q=apple",
        _OPTIONS_URL,
        _FUNDAMENTALS_URL,
        f"{_STATEMENTS_URL}?statement=income",
    ],
)
async def test_missing_token_returns_401(
    client: AsyncClient, mock_gateway: MagicMock, url: str
) -> None:
    response = await client.get(url)

    assert response.status_code == 401
    mock_gateway.get_prices.assert_not_called()
    mock_gateway.lookup_symbol.assert_not_called()
    mock_gateway.get_options_chain.assert_not_called()
    mock_gateway.get_company_profile.assert_not_called()
    mock_gateway.get_key_metrics.assert_not_called()
    mock_gateway.get_financial_ratios.assert_not_called()
    mock_gateway.get_income_statement.assert_not_called()


@pytest.mark.anyio
async def test_wrong_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        f"{_PRICES_URL}{_PRICES_QUERY}", headers=_headers("wrong-token")
    )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_non_ascii_token_returns_401_not_500(client: AsyncClient) -> None:
    # httpx refuses a non-ASCII ``str`` header before it reaches the app, so
    # send the latin-1 bytes the server decodes.
    response = await client.get(
        f"{_PRICES_URL}{_PRICES_QUERY}",
        headers={b"X-Service-Token": b"tok\xe9n"},
    )

    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# AC5: invalid input yields 422.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_invalid_date_returns_422(client: AsyncClient) -> None:
    response = await client.get(
        f"{_PRICES_URL}?from=2026-13-99&to=2026-01-31", headers=_headers()
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_from_after_to_returns_422(client: AsyncClient) -> None:
    response = await client.get(
        f"{_PRICES_URL}?from=2026-02-01&to=2026-01-31", headers=_headers()
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_unknown_option_type_returns_422(client: AsyncClient) -> None:
    response = await client.get(f"{_OPTIONS_URL}?option_type=warrant", headers=_headers())

    assert response.status_code == 422


@pytest.mark.anyio
async def test_strike_min_above_max_returns_422(client: AsyncClient) -> None:
    response = await client.get(
        f"{_OPTIONS_URL}?strike_min=200&strike_max=100", headers=_headers()
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# AC1/AC2: fundamentals overview and statements unified JSON shapes.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_fundamentals_returns_profile_metrics_and_ratios(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    response = await client.get(_FUNDAMENTALS_URL, headers=_headers())

    assert response.status_code == 200
    body = response.json()
    profile = body["profile"]
    assert profile["company_name"] == "Apple Inc."
    assert Decimal(str(profile["market_cap"])) == Decimal("3400000000000")
    assert profile["ceo"] == "Tim Cook"
    assert profile["currency"] == "USD"

    key_metrics = body["key_metrics"]
    assert Decimal(str(key_metrics["pe_ratio"])) == Decimal("36.28")
    assert Decimal(str(key_metrics["enterprise_value_over_ebitda"])) == Decimal(
        "25.14"
    )

    ratios = body["ratios"]
    assert Decimal(str(ratios["gross_profit_margin"])) == Decimal("0.4621")
    assert Decimal(str(ratios["return_on_equity"])) == Decimal("1.6466")


@pytest.mark.anyio
async def test_fundamentals_forwards_exchange_to_gateway(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    response = await client.get(
        f"{_FUNDAMENTALS_URL}?exchange=LSE", headers=_headers()
    )

    assert response.status_code == 200
    mock_gateway.get_company_profile.assert_called_once_with("AAPL", exchange="LSE")
    mock_gateway.get_key_metrics.assert_called_once_with("AAPL", exchange="LSE")
    mock_gateway.get_financial_ratios.assert_called_once_with("AAPL", exchange="LSE")


@pytest.mark.anyio
async def test_fundamentals_reads_issued_concurrently(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    barrier = threading.Barrier(3, timeout=5.0)

    def side_effect_profile(*args: object, **kwargs: object) -> CompanyProfile:
        barrier.wait()
        return _company_profile()

    def side_effect_metrics(*args: object, **kwargs: object) -> KeyMetrics:
        barrier.wait()
        return _key_metrics()

    def side_effect_ratios(*args: object, **kwargs: object) -> FinancialRatios:
        barrier.wait()
        return _financial_ratios()

    mock_gateway.get_company_profile.side_effect = side_effect_profile
    mock_gateway.get_key_metrics.side_effect = side_effect_metrics
    mock_gateway.get_financial_ratios.side_effect = side_effect_ratios

    response = await client.get(_FUNDAMENTALS_URL, headers=_headers())

    assert response.status_code == 200
    mock_gateway.get_company_profile.assert_called_once()
    mock_gateway.get_key_metrics.assert_called_once()
    mock_gateway.get_financial_ratios.assert_called_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("statement", "method_name", "model", "field", "value"),
    [
        ("income", "get_income_statement", IncomeStatement, "revenue", "391035000000"),
        ("balance", "get_balance_sheet", BalanceSheet, "total_assets", "364980000000"),
        (
            "cashflow",
            "get_cash_flow_statement",
            CashFlowStatement,
            "operating_cash_flow",
            "118254000000",
        ),
    ],
)
async def test_statements_returns_full_fmp_shape(
    client: AsyncClient,
    mock_gateway: MagicMock,
    statement: str,
    method_name: str,
    model: type[BaseModel],
    field: str,
    value: str,
) -> None:
    response = await client.get(
        f"{_STATEMENTS_URL}?statement={statement}", headers=_headers()
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1

    row = body[0]
    # The full FMP-shaped line-item set is preserved: no invented, merged or
    # silently dropped fields.
    assert set(row) == set(model.model_fields)
    assert row["date"] == "2024-09-28"
    assert row["symbol"] == "AAPL"
    assert row["period"] == "FY"
    assert row["fiscal_year"] == "2024"
    assert Decimal(str(row[field])) == Decimal(value)

    # The provider read receives the requested statement/period/limit.
    getattr(mock_gateway, method_name).assert_called_once_with(
        "AAPL", "annual", 5, exchange=None
    )


@pytest.mark.anyio
async def test_statements_accepts_quarter_and_limit(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    response = await client.get(
        f"{_STATEMENTS_URL}?statement=income&period=quarter&limit=2",
        headers=_headers(),
    )

    assert response.status_code == 200
    mock_gateway.get_income_statement.assert_called_once_with(
        "AAPL", "quarter", 2, exchange=None
    )


@pytest.mark.anyio
async def test_statements_forwards_exchange_to_gateway(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    response = await client.get(
        f"{_STATEMENTS_URL}?statement=income&exchange=LSE", headers=_headers()
    )

    assert response.status_code == 200
    mock_gateway.get_income_statement.assert_called_once_with(
        "AAPL", "annual", 5, exchange="LSE"
    )


# --------------------------------------------------------------------------- #
# AC2: invalid statement/period/limit yields 422.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
@pytest.mark.parametrize(
    "query",
    [
        "statement=q4",
        "statement=income&period=fiscal",
        "statement=income&limit=0",
        "statement=income&limit=21",
    ],
)
async def test_statements_invalid_params_return_422(
    client: AsyncClient, mock_gateway: MagicMock, query: str
) -> None:
    response = await client.get(f"{_STATEMENTS_URL}?{query}", headers=_headers())

    assert response.status_code == 422
    mock_gateway.get_income_statement.assert_not_called()


# --------------------------------------------------------------------------- #
# AC4/AC5: structured 404 and generic 502-503 with no provider names.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method_name",
    ["get_company_profile", "get_key_metrics", "get_financial_ratios"],
)
async def test_fundamentals_unknown_symbol_returns_404(
    client: AsyncClient, mock_gateway: MagicMock, method_name: str
) -> None:
    getattr(mock_gateway, method_name).side_effect = MarketDataNotFoundError("ZZZZ")

    response = await client.get(
        "/api/v1/market/data/fundamentals/ZZZZ", headers=_headers()
    )

    assert response.status_code == 404
    assert "ZZZZ" in response.json()["detail"]


@pytest.mark.anyio
async def test_statements_unknown_symbol_returns_404(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_income_statement.side_effect = MarketDataNotFoundError("ZZZZ")

    response = await client.get(
        "/api/v1/market/data/fundamentals/ZZZZ/statements?statement=income",
        headers=_headers(),
    )

    assert response.status_code == 404
    assert "ZZZZ" in response.json()["detail"]


@pytest.mark.anyio
async def test_empty_statements_returns_404_and_caches_empty(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_income_statement.return_value = []
    url = f"{_STATEMENTS_URL}?statement=income"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == 404
    assert second.status_code == 404
    # The empty successful result was cached, so the gateway ran exactly once.
    mock_gateway.get_income_statement.assert_called_once()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("side_effect", "expected_status"),
    [
        (MarketDataProviderError("raw upstream failure"), 502),
        (MarketDataConfigurationError("raw config failure"), 503),
    ],
)
@pytest.mark.parametrize(
    "url",
    [_FUNDAMENTALS_URL, f"{_STATEMENTS_URL}?statement=income"],
)
async def test_fundamentals_provider_failure_is_generic(
    client: AsyncClient,
    mock_gateway: MagicMock,
    side_effect: Exception,
    expected_status: int,
    url: str,
) -> None:
    mock_gateway.get_company_profile.side_effect = side_effect
    mock_gateway.get_income_statement.side_effect = side_effect

    response = await client.get(url, headers=_headers())

    assert response.status_code == expected_status
    detail = response.json()["detail"].lower()
    assert "raw" not in detail
    for provider in _PROVIDER_NAMES:
        assert provider not in detail


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failing_method",
    ["get_company_profile", "get_key_metrics", "get_financial_ratios"],
)
@pytest.mark.parametrize(
    ("side_effect", "expected_status"),
    [
        (MarketDataProviderError("fmp provider raw failure"), 502),
        (MarketDataConfigurationError("polygon missing api key"), 503),
    ],
)
async def test_fundamentals_concurrent_partial_failure(
    client: AsyncClient,
    mock_gateway: MagicMock,
    failing_method: str,
    side_effect: Exception,
    expected_status: int,
) -> None:
    getattr(mock_gateway, failing_method).side_effect = side_effect

    response = await client.get(_FUNDAMENTALS_URL, headers=_headers())

    assert response.status_code == expected_status
    detail = response.json()["detail"].lower()
    assert "raw" not in detail
    for provider in _PROVIDER_NAMES:
        assert provider not in detail


# --------------------------------------------------------------------------- #
# AC3: every fundamentals route is served through the endpoint response cache.
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_repeated_fundamentals_is_cached_under_metrics_class(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    first = await client.get(_FUNDAMENTALS_URL, headers=_headers())
    second = await client.get(_FUNDAMENTALS_URL, headers=_headers())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    mock_gateway.get_company_profile.assert_called_once()
    mock_gateway.get_key_metrics.assert_called_once()
    mock_gateway.get_financial_ratios.assert_called_once()
    keys = _endpoint_keys(mock_redis_storage, "market:ep:metrics:fundamentals:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_repeated_statements_is_cached_under_statements_class(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    url = f"{_STATEMENTS_URL}?statement=balance"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    mock_gateway.get_balance_sheet.assert_called_once()
    keys = _endpoint_keys(mock_redis_storage, "market:ep:statements:statements:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_statements_failure_is_not_cached(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    url = f"{_STATEMENTS_URL}?statement=income"
    mock_gateway.get_income_statement.side_effect = MarketDataProviderError("boom")

    first = await client.get(url, headers=_headers())
    assert first.status_code == 502

    # Heal the gateway: the failed fetch must not have been cached, so the next
    # request refetches and succeeds.
    mock_gateway.get_income_statement.side_effect = None
    mock_gateway.get_income_statement.return_value = [_income_statement()]

    second = await client.get(url, headers=_headers())
    assert second.status_code == 200
    assert mock_gateway.get_income_statement.call_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [_FUNDAMENTALS_URL, f"{_STATEMENTS_URL}?statement=income"],
)
async def test_new_routes_non_ascii_token_returns_401_not_500(
    client: AsyncClient, url: str
) -> None:
    response = await client.get(url, headers={b"X-Service-Token": b"tok\xe9n"})

    assert response.status_code == 401
