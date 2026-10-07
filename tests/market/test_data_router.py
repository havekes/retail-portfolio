"""Offline tests for the service-to-service market data endpoints.

The data-plane gateway is a ``MagicMock`` (no provider is ever dialed) and the
endpoint cache is the real T13 ``EndpointResponseCache`` layered over the
autouse in-memory Redis fake. The *real* ``require_service_token`` dependency
runs: tests patch the configured token and send the header, exercising the
byte-comparison path end to end.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest
from asgi_lifespan import LifespanManager
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from src.config.settings import settings
from src.main import app
from src.market.service import IndicatorServiceClient
from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPrice,
    IncomeStatement,
    KeyMetrics,
    OptionExpirations,
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
_OPTIONS_EXPIRATIONS_URL = "/api/v1/market/data/options/AAPL/expirations"
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
    gateway.get_options_chain.return_value = OptionsChain(
        underlying_symbol="AAPL", currency=""
    )
    gateway.get_option_expirations.return_value = OptionExpirations(
        underlying_symbol="AAPL",
        expirations=[date(2025, 1, 17)],
    )
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
def mock_indicator_client() -> MagicMock:
    mock_client = MagicMock(spec=IndicatorServiceClient)
    mock_client.compute = AsyncMock(return_value={})
    return mock_client


@pytest.fixture
async def client(
    mock_gateway: MagicMock,
    endpoint_cache: EndpointResponseCache,
    mock_indicator_client: MagicMock,
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
        app.state.svcs_registry.register_value(
            IndicatorServiceClient, mock_indicator_client
        )
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
        currency="",
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


def _option_expirations() -> OptionExpirations:
    return OptionExpirations(
        underlying_symbol="SPY",
        expirations=[date(2025, 1, 17), date(2025, 2, 21)],
        truncated=False,
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
    assert body["currency"] == "USD"
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
async def test_prices_with_exchange_tsx_resolves_cad(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_prices.return_value = [_historical_price()]
    mock_gateway.get_company_profile.return_value = _company_profile("SHOP").model_copy(
        update={"currency": "CAD"}
    )

    response = await client.get(
        "/api/v1/market/data/prices/SHOP?from=2026-01-01&to=2026-01-31&exchange=TSX",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "SHOP"
    assert body["exchange"] == "TSX"
    assert body["currency"] == "CAD"


@pytest.mark.anyio
async def test_prices_missing_profile_uses_fallback_and_does_not_404(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_prices.return_value = [_historical_price()]
    mock_gateway.get_company_profile.side_effect = MarketDataNotFoundError("SHOP")

    response = await client.get(
        "/api/v1/market/data/prices/SHOP?from=2026-01-01&to=2026-01-31&exchange=TSX",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "CAD"


@pytest.mark.anyio
async def test_prices_profile_provider_error_falls_back_and_does_not_fail(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_prices.return_value = [_historical_price()]
    mock_gateway.get_company_profile.side_effect = MarketDataProviderError(
        "FMP down"
    )

    response = await client.get(f"{_PRICES_URL}{_PRICES_QUERY}", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "USD"


@pytest.mark.anyio
async def test_prices_without_dates_defaults_to_last_year_ending_today(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    today = datetime.now(UTC).date()
    expected_from = today - timedelta(days=365)
    mock_gateway.get_prices.return_value = [_historical_price(today)]

    response = await client.get(_PRICES_URL, headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["from_date"] == expected_from.isoformat()
    assert body["to_date"] == today.isoformat()
    assert body["interval"] == "day"

    args, _ = mock_gateway.get_prices.call_args
    assert args[2] == expected_from
    assert args[3] == today


@pytest.mark.anyio
async def test_prices_monthly_interval_aggregates_120_bars(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    # 2015-01-01 to 2024-12-31 spans 120 months.
    # Provide 2 daily prices per month.
    prices: list[HistoricalPrice] = []
    for year in range(2015, 2025):
        for month in range(1, 13):
            prices.append(_historical_price(date(year, month, 1)))
            prices.append(_historical_price(date(year, month, 15)))

    mock_gateway.get_prices.return_value = prices

    response = await client.get(
        f"{_PRICES_URL}?from=2015-01-01&to=2024-12-31&interval=month",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["interval"] == "month"
    assert len(body["items"]) == 120
    assert body["currency"] == "USD"


@pytest.mark.anyio
async def test_prices_five_year_daily_range_succeeds(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_prices.return_value = [_historical_price(date(2020, 1, 2))]

    response = await client.get(
        f"{_PRICES_URL}?from=2019-10-01&to=2024-09-30&interval=day",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["interval"] == "day"


@pytest.mark.anyio
async def test_prices_over_2000_weekdays_daily_returns_422_before_gateway_call(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    response = await client.get(
        f"{_PRICES_URL}?from=2015-01-01&to=2024-12-31&interval=day",
        headers=_headers(),
    )

    assert response.status_code == 422
    mock_gateway.get_prices.assert_not_called()
    detail = response.json()["detail"].lower()
    assert "week" in detail or "month" in detail
    assert "2000" in detail


@pytest.mark.anyio
async def test_prices_currency_preserved_across_all_intervals(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_prices.return_value = [_historical_price(date(2026, 1, 2))]

    for interval in ("day", "week", "month"):
        response = await client.get(
            f"{_PRICES_URL}?from=2026-01-01&to=2026-01-31&interval={interval}",
            headers=_headers(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["currency"] == "USD"
        assert body["interval"] == interval


@pytest.mark.anyio
async def test_prices_cache_key_includes_interval(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.get_prices.return_value = [
        _historical_price(date(2026, 1, 2)),
        _historical_price(date(2026, 1, 5)),
    ]
    url_day = f"{_PRICES_URL}?from=2026-01-01&to=2026-01-31&interval=day"
    url_week = f"{_PRICES_URL}?from=2026-01-01&to=2026-01-31&interval=week"

    r_day = await client.get(url_day, headers=_headers())
    r_week = await client.get(url_week, headers=_headers())

    assert r_day.status_code == 200
    assert r_week.status_code == 200
    # Both intervals result in a gateway fetch since cache keys differ
    assert mock_gateway.get_prices.call_count == 2
    keys = _endpoint_keys(mock_redis_storage, "market:ep:prices:history:")
    assert len(keys) == 2


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
        f"{_OPTIONS_URL}?expiry=2026-01-16&option_type=call&strike_min=100&strike_max=200",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["underlying_symbol"] == "AAPL"
    assert body["currency"] == "USD"
    assert body["truncated"] is False

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
    assert kwargs["expiration"] == date(2026, 1, 16)
    assert kwargs["contract_type"] == "call"
    assert kwargs["strike_min"] == Decimal("100")
    assert kwargs["strike_max"] == Decimal("200")


@pytest.mark.anyio
async def test_options_missing_profile_uses_fallback_and_does_not_404(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_options_chain.return_value = _options_chain()
    mock_gateway.get_company_profile.side_effect = MarketDataNotFoundError("AAPL")

    response = await client.get(f"{_OPTIONS_URL}?expiry=2026-01-16", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["underlying_symbol"] == "AAPL"
    assert body["currency"] == "USD"


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
    mock_gateway.get_company_profile.assert_called_once()


@pytest.mark.anyio
async def test_repeated_prices_different_date_range_shares_currency_cache(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_prices.return_value = [_historical_price()]

    r1 = await client.get(
        f"{_PRICES_URL}?from=2026-01-01&to=2026-01-10", headers=_headers()
    )
    r2 = await client.get(
        f"{_PRICES_URL}?from=2026-01-11&to=2026-01-20", headers=_headers()
    )

    assert r1.status_code == r2.status_code == 200
    assert mock_gateway.get_prices.call_count == 2
    mock_gateway.get_company_profile.assert_called_once()


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
    url = f"{_OPTIONS_URL}?expiry=2026-01-16"

    await client.get(url, headers=_headers())
    await client.get(url, headers=_headers())

    mock_gateway.get_options_chain.assert_called_once()
    keys = _endpoint_keys(mock_redis_storage, "market:ep:options:chain:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_options_truncated_flag_survives_endpoint_cache_round_trip(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    chain = _options_chain()
    chain.truncated = True
    mock_gateway.get_options_chain.return_value = chain
    url = f"{_OPTIONS_URL}?expiry=2026-01-16"

    first = await client.get(url, headers=_headers())
    assert first.status_code == 200
    assert first.json()["truncated"] is True

    # Second call served from endpoint cache
    second = await client.get(url, headers=_headers())
    assert second.status_code == 200
    assert second.json()["truncated"] is True

    mock_gateway.get_options_chain.assert_called_once()
    keys = _endpoint_keys(mock_redis_storage, "market:ep:options:chain:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_option_expirations_returns_expected_payload(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_option_expirations.return_value = _option_expirations()

    response = await client.get(
        "/api/v1/market/data/options/SPY/expirations",
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["underlying_symbol"] == "SPY"
    assert payload["expirations"] == ["2025-01-17", "2025-02-21"]
    assert payload["truncated"] is False
    mock_gateway.get_option_expirations.assert_called_once_with("SPY")


@pytest.mark.anyio
async def test_repeated_option_expirations_is_cached_under_options_class(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.get_option_expirations.return_value = _option_expirations()
    url = "/api/v1/market/data/options/SPY/expirations"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    mock_gateway.get_option_expirations.assert_called_once_with("SPY")
    keys = _endpoint_keys(mock_redis_storage, "market:ep:options:expirations:")
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
    url = "/api/v1/market/data/options/ZZZZ?expiry=2026-01-16"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 404
    assert first.json()["detail"] == second.json()["detail"]
    # No second Polygon read for the same missing underlying.
    mock_gateway.get_options_chain.assert_called_once()

    keys = _endpoint_keys(mock_redis_storage, "market:ep:options:chain:")
    assert len(keys) == 1


@pytest.mark.anyio
async def test_unknown_underlying_option_expirations_is_negative_cached(
    client: AsyncClient, mock_gateway: MagicMock, mock_redis_storage: FakeRedis
) -> None:
    mock_gateway.get_option_expirations.side_effect = MarketDataNotFoundError("ZZZZ")
    url = "/api/v1/market/data/options/ZZZZ/expirations"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 404
    assert first.json()["detail"] == second.json()["detail"]
    mock_gateway.get_option_expirations.assert_called_once_with("ZZZZ")

    keys = _endpoint_keys(mock_redis_storage, "market:ep:options:expirations:")
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
async def test_unknown_fundamentals_symbol_is_negative_cached(
    client: AsyncClient,
    mock_gateway: MagicMock,
    mock_redis_storage: FakeRedis,
) -> None:
    mock_gateway.get_company_profile.side_effect = MarketDataNotFoundError("ZZZZ")
    url = "/api/v1/market/data/fundamentals/ZZZZ"

    first = await client.get(url, headers=_headers())
    second = await client.get(url, headers=_headers())

    assert first.status_code == second.status_code == 404
    assert first.json()["detail"] == second.json()["detail"]
    # The 404 was negative-cached: the upstream gateway ran exactly once.
    mock_gateway.get_company_profile.assert_called_once()

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
        _OPTIONS_EXPIRATIONS_URL,
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
    mock_gateway.get_option_expirations.assert_not_called()
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
async def test_options_without_expiry_returns_422(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    response = await client.get("/api/v1/market/data/options/SPY", headers=_headers())

    assert response.status_code == 422
    mock_gateway.get_options_chain.assert_not_called()


@pytest.mark.anyio
async def test_unknown_option_type_returns_422(client: AsyncClient) -> None:
    response = await client.get(
        f"{_OPTIONS_URL}?expiry=2026-01-16&option_type=warrant", headers=_headers()
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_strike_min_above_max_returns_422(client: AsyncClient) -> None:
    response = await client.get(
        f"{_OPTIONS_URL}?expiry=2026-01-16&strike_min=200&strike_max=100", headers=_headers()
    )

    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/market/data/prices/AAPL?from=2024-01-01&to=2024-02-01&exchange=XETRA",
        "/api/v1/market/data/fundamentals/AAPL?exchange=XETRA",
        "/api/v1/market/data/fundamentals/AAPL/statements?statement=income&exchange=XETRA",
    ],
)
async def test_unsupported_exchange_returns_422_with_accepted_codes(
    client: AsyncClient, mock_gateway: MagicMock, url: str
) -> None:
    response = await client.get(url, headers=_headers())

    assert response.status_code == 422
    detail_str = str(response.json()["detail"])
    for code in ("NYSE", "NASDAQ", "NYSEARCA", "AMEX", "TSX", "LSE"):
        assert code in detail_str
    mock_gateway.get_prices.assert_not_called()
    mock_gateway.get_company_profile.assert_not_called()
    mock_gateway.get_income_statement.assert_not_called()


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
async def test_fundamentals_missing_ratios_returns_null_section(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_financial_ratios.side_effect = MarketDataNotFoundError("AAPL")

    response = await client.get(_FUNDAMENTALS_URL, headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["symbol"] == "AAPL"
    assert body["profile"]["company_name"] == "Apple Inc."
    assert body["key_metrics"] is not None
    assert Decimal(str(body["key_metrics"]["pe_ratio"])) == Decimal("36.28")
    assert body["ratios"] is None


@pytest.mark.anyio
async def test_fundamentals_missing_key_metrics_returns_null_section(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_key_metrics.side_effect = MarketDataNotFoundError("AAPL")

    response = await client.get(_FUNDAMENTALS_URL, headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["symbol"] == "AAPL"
    assert body["profile"]["company_name"] == "Apple Inc."
    assert body["key_metrics"] is None
    assert body["ratios"] is not None
    assert Decimal(str(body["ratios"]["debt_to_equity"])) == Decimal("1.87")


@pytest.mark.anyio
async def test_fundamentals_missing_both_metrics_and_ratios_returns_null_sections(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_key_metrics.side_effect = MarketDataNotFoundError("AAPL")
    mock_gateway.get_financial_ratios.side_effect = MarketDataNotFoundError("AAPL")

    response = await client.get(_FUNDAMENTALS_URL, headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["symbol"] == "AAPL"
    assert body["key_metrics"] is None
    assert body["ratios"] is None


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
async def test_fundamentals_missing_profile_returns_404(
    client: AsyncClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.get_company_profile.side_effect = MarketDataNotFoundError("ZZZZ")

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


# --------------------------------------------------------------------------- #
# Technical Indicators (T08)
# --------------------------------------------------------------------------- #


def _generate_daily_prices(
    start: date,
    end: date,
    base_price: float = 100.0,
) -> list[HistoricalPrice]:
    prices = []
    cur = start
    price_val = base_price
    while cur <= end:
        if cur.weekday() < 5:
            prices.append(
                HistoricalPrice(
                    date=cur,
                    open=Decimal(str(round(price_val, 2))),
                    high=Decimal(str(round(price_val + 2.0, 2))),
                    low=Decimal(str(round(price_val - 2.0, 2))),
                    close=Decimal(str(round(price_val + 1.0, 2))),
                    adjusted_close=Decimal(str(round(price_val + 1.0, 2))),
                    volume=1_000_000,
                )
            )
            price_val += 0.5
        cur += timedelta(days=1)
    return prices


@pytest.mark.anyio
async def test_indicator_rsi_series_warmup_and_trimming(
    client: AsyncClient,
    mock_gateway: MagicMock,
    mock_indicator_client: MagicMock,
) -> None:
    from_date = date(2026, 1, 1)
    to_date = date(2026, 3, 31)

    # 3 months range plus warm-up (warmup for RSI 14: ~68 calendar days, so prices start in Oct 2025)
    all_prices = _generate_daily_prices(date(2025, 10, 1), to_date)
    mock_gateway.get_prices.return_value = all_prices

    async def fake_rsi_compute(interval, candles, indicators):
        spec = indicators[0]
        idle = spec.period or 14
        points = []
        for idx, c in enumerate(candles):
            if idx >= idle:
                points.append(
                    {
                        "time": c.time,
                        "value": 50.0 + (idx % 20),
                        "rsi": 50.0 + (idx % 20),
                    }
                )
        return {"rsi": points}

    mock_indicator_client.compute.side_effect = fake_rsi_compute

    url = f"/api/v1/market/data/indicators/AAPL?indicator=rsi&from={from_date}&to={to_date}"
    response = await client.get(url, headers=_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["indicator"] == "rsi"
    assert data["from_date"] == "2026-01-01"
    assert data["to_date"] == "2026-03-31"
    assert data["params"] == {"period": 14}
    assert "currency" in data

    # Verify warm-up was fetched and passed to indicator-service
    called_candles = mock_indicator_client.compute.call_args[1]["candles"]
    assert len(called_candles) > len(data["points"])
    # First candle passed to indicator-service is well before from_date
    assert called_candles[0].time < from_date.isoformat()

    # Verify trimmed points: first point dated on or after from_date
    points = data["points"]
    assert len(points) > 0
    first_point_date = date.fromisoformat(points[0]["time"])
    assert first_point_date >= from_date

    # Count trading days in [from_date, to_date]
    expected_trading_days = [
        p.date.isoformat() for p in all_prices if from_date <= p.date <= to_date
    ]
    assert [p["time"] for p in points] == expected_trading_days

    # None with a null value caused by missing warm-up
    for pt in points:
        assert pt["value"] is not None
        assert pt["rsi"] is not None


@pytest.mark.anyio
async def test_indicator_spec_mapping_and_defaults(
    client: AsyncClient,
    mock_gateway: MagicMock,
    mock_indicator_client: MagicMock,
) -> None:
    prices = _generate_daily_prices(date(2025, 9, 1), date(2026, 1, 31))
    mock_gateway.get_prices.return_value = prices

    # 1. Bollinger defaults: mapped to "bb", period=20, stdDev=2.0
    mock_indicator_client.compute.return_value = {
        "bb": [{"time": "2026-01-02", "middle": 100.0, "upper": 105.0, "lower": 95.0}]
    }
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=bollinger&from=2026-01-01&to=2026-01-31",
        headers=_headers(),
    )
    assert resp.status_code == 200
    spec = mock_indicator_client.compute.call_args[1]["indicators"][0]
    assert spec.type == "bb"
    assert spec.period == 20
    assert spec.std_dev == 2.0
    body = resp.json()
    assert body["indicator"] == "bollinger"
    assert body["params"] == {"period": 20, "std_dev": 2.0}

    # 2. Bollinger explicit period and std_dev
    mock_indicator_client.compute.reset_mock()
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=bollinger&period=30&std_dev=2.5&from=2026-01-01&to=2026-01-31",
        headers=_headers(),
    )
    assert resp.status_code == 200
    spec = mock_indicator_client.compute.call_args[1]["indicators"][0]
    assert spec.type == "bb"
    assert spec.period == 30
    assert spec.std_dev == 2.5
    assert resp.json()["params"] == {"period": 30, "std_dev": 2.5}

    # 3. MACD defaults: fast=12, slow=26, signal=9
    mock_indicator_client.compute.reset_mock()
    mock_indicator_client.compute.return_value = {
        "macd": [
            {
                "time": "2026-01-02",
                "macd": 1.5,
                "signal": 1.2,
                "histogram": 0.3,
            }
        ]
    }
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=macd&from=2026-01-01&to=2026-01-31",
        headers=_headers(),
    )
    assert resp.status_code == 200
    spec = mock_indicator_client.compute.call_args[1]["indicators"][0]
    assert spec.type == "macd"
    assert spec.fast == 12
    assert spec.slow == 26
    assert spec.signal == 9
    assert resp.json()["params"] == {"fast": 12, "slow": 26, "signal": 9}

    # 4. SMA defaults: period=14
    mock_indicator_client.compute.reset_mock()
    mock_indicator_client.compute.return_value = {
        "sma": [{"time": "2026-01-02", "value": 100.0}]
    }
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=sma&from=2026-01-01&to=2026-01-31",
        headers=_headers(),
    )
    assert resp.status_code == 200
    spec = mock_indicator_client.compute.call_args[1]["indicators"][0]
    assert spec.type == "sma"
    assert spec.period == 14
    assert resp.json()["params"] == {"period": 14}

    # 5. EMA defaults: period=14
    mock_indicator_client.compute.reset_mock()
    mock_indicator_client.compute.return_value = {
        "ema": [{"time": "2026-01-02", "value": 100.0}]
    }
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=ema&from=2026-01-01&to=2026-01-31",
        headers=_headers(),
    )
    assert resp.status_code == 200
    spec = mock_indicator_client.compute.call_args[1]["indicators"][0]
    assert spec.type == "ema"
    assert spec.period == 14
    assert resp.json()["params"] == {"period": 14}


@pytest.mark.anyio
async def test_indicator_unsupported_or_out_of_range_422(
    client: AsyncClient,
) -> None:
    # Unsupported indicator
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=unsupported",
        headers=_headers(),
    )
    assert resp.status_code == 422

    # Period out of range (< 2 or > 400)
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=rsi&period=1",
        headers=_headers(),
    )
    assert resp.status_code == 422

    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=rsi&period=401",
        headers=_headers(),
    )
    assert resp.status_code == 422

    # MACD params out of range
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=macd&fast=1",
        headers=_headers(),
    )
    assert resp.status_code == 422

    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=macd&slow=401",
        headers=_headers(),
    )
    assert resp.status_code == 422

    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=macd&signal=1",
        headers=_headers(),
    )
    assert resp.status_code == 422

    # std_dev <= 0
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=bollinger&std_dev=0",
        headers=_headers(),
    )
    assert resp.status_code == 422

    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=bollinger&std_dev=-1",
        headers=_headers(),
    )
    assert resp.status_code == 422

    # from > to
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=rsi&from=2026-02-01&to=2026-01-01",
        headers=_headers(),
    )
    assert resp.status_code == 422
    assert "from must be less than or equal to to" in resp.json()["detail"]

    # Over-cap range (> 2000 bars) returns same 422 as price history
    resp = await client.get(
        "/api/v1/market/data/indicators/AAPL?indicator=rsi&from=2010-01-01&to=2026-01-01",
        headers=_headers(),
    )
    assert resp.status_code == 422
    assert "exceeding the limit of 2000" in resp.json()["detail"]


@pytest.mark.anyio
async def test_indicator_currency_resolution(
    client: AsyncClient,
    mock_gateway: MagicMock,
    mock_indicator_client: MagicMock,
) -> None:
    mock_gateway.get_prices.return_value = _generate_daily_prices(
        date(2025, 10, 1), date(2026, 1, 31)
    )
    mock_gateway.get_company_profile.return_value = _company_profile("SHOP").model_copy(
        update={"currency": "CAD"}
    )
    mock_indicator_client.compute.return_value = {
        "rsi": [{"time": "2026-01-02", "value": 50.0, "rsi": 50.0}]
    }

    resp = await client.get(
        "/api/v1/market/data/indicators/SHOP?indicator=rsi&exchange=TSX&from=2026-01-01&to=2026-01-31",
        headers=_headers(),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "SHOP"
    assert body["exchange"] == "TSX"
    assert body["currency"] == "CAD"


@pytest.mark.anyio
async def test_indicator_service_unavailability_503_not_cached(
    client: AsyncClient,
    mock_gateway: MagicMock,
    mock_indicator_client: MagicMock,
) -> None:
    mock_gateway.get_prices.return_value = _generate_daily_prices(
        date(2025, 10, 1), date(2026, 1, 31)
    )
    mock_indicator_client.compute.side_effect = HTTPException(
        status_code=503,
        detail="Indicator service unavailable",
    )

    url = "/api/v1/market/data/indicators/AAPL?indicator=rsi&from=2026-01-01&to=2026-01-31"
    first = await client.get(url, headers=_headers())
    assert first.status_code == 503
    assert first.json()["detail"] == "Indicator service unavailable"

    second = await client.get(url, headers=_headers())
    assert second.status_code == 503

    # Both calls hit compute; the 503 was not cached
    assert mock_indicator_client.compute.call_count == 2


@pytest.mark.anyio
async def test_indicator_repeated_request_served_from_cache(
    client: AsyncClient,
    mock_gateway: MagicMock,
    mock_indicator_client: MagicMock,
) -> None:
    mock_gateway.get_prices.return_value = _generate_daily_prices(
        date(2025, 10, 1), date(2026, 1, 31)
    )
    mock_indicator_client.compute.return_value = {
        "rsi": [{"time": "2026-01-02", "value": 55.0, "rsi": 55.0}]
    }

    url = "/api/v1/market/data/indicators/AAPL?indicator=rsi&from=2026-01-01&to=2026-01-31"
    first = await client.get(url, headers=_headers())
    assert first.status_code == 200
    assert mock_gateway.get_prices.call_count == 1
    assert mock_indicator_client.compute.call_count == 1

    second = await client.get(url, headers=_headers())
    assert second.status_code == 200
    assert first.json() == second.json()

    # Cached: neither gateway nor indicator client called again
    assert mock_gateway.get_prices.call_count == 1
    assert mock_indicator_client.compute.call_count == 1


@pytest.mark.anyio
async def test_indicator_unknown_symbol_404_and_empty_points_404(
    client: AsyncClient,
    mock_gateway: MagicMock,
) -> None:
    # Unknown symbol from gateway
    mock_gateway.get_prices.side_effect = MarketDataNotFoundError("ZZZZ")
    resp = await client.get(
        "/api/v1/market/data/indicators/ZZZZ?indicator=rsi",
        headers=_headers(),
    )
    assert resp.status_code == 404
    assert "ZZZZ" in resp.json()["detail"]

    # Empty prices returns 404
    mock_gateway.get_prices.side_effect = None
    mock_gateway.get_prices.return_value = []
    resp2 = await client.get(
        "/api/v1/market/data/indicators/EMPTY?indicator=rsi",
        headers=_headers(),
    )
    assert resp2.status_code == 404
    assert "EMPTY" in resp2.json()["detail"]

