# ruff: noqa: PLR2004, SLF001
"""Tests for the FMP-backed gateway, symbol mapping and error translation.

Everything is offline: outbound HTTP is driven through an injected
``httpx.MockTransport`` so no test can dial the network.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest

from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPrice,
    IncomeStatement,
    KeyMetrics,
    SymbolLookupResult,
)
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)
from src.market.fmp import FmpGateway, FmpHttpClient, map_to_fmp_ticker
from src.stubs.fmp import StubFmpGateway

_FMP_PAYLOAD: dict[str, Any] = {
    "symbol": "AAPL",
    "historical": [
        {
            "date": "2024-01-05",
            "open": 180.5,
            "high": 182.0,
            "low": 179.1,
            "close": 181.2,
            "adjClose": 181.0,
            "volume": 1234567,
        },
        {
            "date": "2024-01-04",
            "open": 179.0,
            "high": 181.5,
            "low": 178.2,
            "close": 180.5,
            "adjClose": 180.3,
            "volume": 987654,
        },
    ],
}


def _gateway(
    handler: "Callable[[httpx.Request], httpx.Response] | httpx.MockTransport",
    base_url: str = "https://fmp.test",
):
    transport = (
        handler
        if isinstance(handler, httpx.MockTransport)
        else httpx.MockTransport(handler)
    )
    return FmpGateway(api_key="test-key", base_url=base_url, client=_client(transport))


# Every ``httpx.Client`` a test constructs is registered here and closed on
# teardown, so no test leaves a client (or its pooled connections) dangling.
_OPEN_CLIENTS: list[httpx.Client] = []


@pytest.fixture(autouse=True)
def _close_http_clients():
    """Close all ``httpx.Client`` instances a test built (AC3: no leaks)."""
    yield
    while _OPEN_CLIENTS:
        _OPEN_CLIENTS.pop().close()


def _client(transport: httpx.MockTransport) -> httpx.Client:
    """Build a mock-transport client and track it for teardown."""
    client = httpx.Client(transport=transport)
    _OPEN_CLIENTS.append(client)
    return client


# --------------------------------------------------------------------------- #
# Symbol mapping (AC2)
# --------------------------------------------------------------------------- #


def test_map_to_fmp_ticker_us_exchanges():
    assert map_to_fmp_ticker("AAPL", "NASDAQ") == "AAPL"
    assert map_to_fmp_ticker("IBM", "NYSE") == "IBM"
    assert map_to_fmp_ticker("SPY", "NYSEARCA") == "SPY"
    assert map_to_fmp_ticker("XYZ", "AMEX") == "XYZ"
    assert map_to_fmp_ticker("aapl", "nasdaq") == "AAPL"


def test_map_to_fmp_ticker_non_us_exchanges():
    assert map_to_fmp_ticker("RY", "TSX") == "RY.TO"
    assert map_to_fmp_ticker("VOD", "LSE") == "VOD.L"
    assert map_to_fmp_ticker("ry", "tsx") == "RY.TO"


def test_map_to_fmp_ticker_unknown_exchange_passes_through():
    assert map_to_fmp_ticker("AAPL", "US") == "AAPL"
    assert map_to_fmp_ticker("XYZ", "UNKNOWN") == "XYZ"


# --------------------------------------------------------------------------- #
# Happy path: prices (AC1)
# --------------------------------------------------------------------------- #

# PLR0911 justification: the handler has one return per canned request shape.
_PLR0911 = ""


def test_get_prices_parses_mocked_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/historical-price-full/AAPL"
        assert request.url.params["from"] == "2024-01-04"
        assert request.url.params["to"] == "2024-01-05"
        assert request.url.params["apikey"] == "test-key"
        return httpx.Response(200, json=_FMP_PAYLOAD)

    gateway = _gateway(handler)
    security_id = uuid4()
    prices = gateway.get_prices(
        security_id=security_id,
        symbol="AAPL",
        exchange="NASDAQ",
        from_date=date(2024, 1, 4),
        to_date=date(2024, 1, 5),
    )

    assert len(prices) == 2
    assert all(isinstance(price, HistoricalPrice) for price in prices)
    # Sorted ascending by date even though the payload was newest-first.
    assert [price.date for price in prices] == [date(2024, 1, 4), date(2024, 1, 5)]
    first = prices[0]
    assert first.security_id == security_id
    assert first.open == Decimal("179.0")
    assert first.high == Decimal("181.5")
    assert first.low == Decimal("178.2")
    assert first.close == Decimal("180.5")
    assert first.adjusted_close == Decimal("180.3")
    assert first.volume == 987654


def test_get_price_on_date_returns_single_price():
    def handler(request: httpx.Request) -> httpx.Response:
        requested = request.url.params["from"]
        rows = [row for row in _FMP_PAYLOAD["historical"] if row["date"] == requested]
        return httpx.Response(200, json={"symbol": "AAPL", "historical": rows})

    gateway = _gateway(handler)
    price = gateway.get_price_on_date(
        security_id=uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        date=date(2024, 1, 5),
    )

    assert price is not None
    assert price.date == date(2024, 1, 5)
    assert price.close == Decimal("181.2")
    assert price.volume == 1234567


def test_get_prices_maps_non_us_ticker():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"historical": []})

    gateway = _gateway(handler)
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_prices(
            security_id=uuid4(),
            symbol="RY",
            exchange="TSX",
            from_date=date(2024, 1, 4),
            to_date=date(2024, 1, 5),
        )

    assert captured["path"] == "/api/v3/historical-price-full/RY.TO"


def test_search_maps_to_symbol_lookup_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/symbol-search"
        assert request.url.params["query"] == "apple"
        return httpx.Response(
            200,
            json=[
                {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "exchange": "NASDAQ Global Select",
                    "exchangeShortName": "NASDAQ",
                    "currency": "USD",
                    "type": "Common Stock",
                    "country": "US",
                }
            ],
        )

    gateway = _gateway(handler)
    results = gateway.search("apple")

    assert len(results) == 1
    assert results[0].code == "AAPL"
    assert results[0].exchange == "NASDAQ"
    assert results[0].name == "Apple Inc."
    assert results[0].currency == "USD"
    assert results[0].country == "US"


# --------------------------------------------------------------------------- #
# Error mapping (AC3)
# --------------------------------------------------------------------------- #


def test_error_message_payload_maps_to_not_found():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"Error Message": "Symbol not found or unavailable."}
        )

    gateway = _gateway(handler)
    with pytest.raises(MarketDataNotFoundError) as exc_info:
        gateway.get_prices(
            security_id=uuid4(),
            symbol="AAPL",
            exchange="NASDAQ",
            from_date=date(2024, 1, 4),
            to_date=date(2024, 1, 5),
        )

    message = str(exc_info.value)
    assert "AAPL.NASDAQ" in message
    assert "Symbol not found" not in message
    assert "Error Message" not in message


def test_empty_historical_maps_to_not_found():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"symbol": "AAPL", "historical": []})

    gateway = _gateway(handler)
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_prices(
            security_id=uuid4(),
            symbol="AAPL",
            exchange="NASDAQ",
            from_date=date(2024, 1, 4),
            to_date=date(2024, 1, 5),
        )


def test_missing_historical_maps_to_not_found():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"symbol": "AAPL"})

    gateway = _gateway(handler)
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_prices(
            security_id=uuid4(),
            symbol="AAPL",
            exchange="NASDAQ",
            from_date=date(2024, 1, 4),
            to_date=date(2024, 1, 5),
        )


def test_http_500_maps_to_provider_error_without_leaking_body():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="FMP upstream exploded: secret detail")

    gateway = _gateway(handler)
    with pytest.raises(MarketDataProviderError) as exc_info:
        gateway.get_prices(
            security_id=uuid4(),
            symbol="AAPL",
            exchange="NASDAQ",
            from_date=date(2024, 1, 4),
            to_date=date(2024, 1, 5),
        )

    assert "secret detail" not in str(exc_info.value)
    assert "upstream exploded" not in str(exc_info.value)


def test_timeout_maps_to_provider_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    gateway = _gateway(handler)
    with pytest.raises(MarketDataProviderError):
        gateway.get_prices(
            security_id=uuid4(),
            symbol="AAPL",
            exchange="NASDAQ",
            from_date=date(2024, 1, 4),
            to_date=date(2024, 1, 5),
        )


def test_connection_error_maps_to_provider_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    gateway = _gateway(handler)
    with pytest.raises(MarketDataProviderError):
        gateway.get_prices(
            security_id=uuid4(),
            symbol="AAPL",
            exchange="NASDAQ",
            from_date=date(2024, 1, 4),
            to_date=date(2024, 1, 5),
        )


# --------------------------------------------------------------------------- #
# FmpHttpClient seams
# --------------------------------------------------------------------------- #


def test_fmp_http_client_appends_api_key_and_raises_on_non_2xx():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["apikey"] = request.url.params["apikey"]
        return httpx.Response(200, json={"ok": True})

    client = FmpHttpClient(
        api_key="abc",
        base_url="https://fmp.test",
        client=_client(httpx.MockTransport(handler)),
    )
    assert client.get_json("api/v3/profile/AAPL") == {"ok": True}
    assert seen["apikey"] == "abc"


def test_fmp_gateway_accepts_injected_http_client():
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json=_FMP_PAYLOAD)
    )
    client = FmpHttpClient(
        api_key="abc",
        base_url="https://fmp.test",
        client=_client(transport),
    )
    gateway = FmpGateway(api_key="abc", client=client)
    prices = gateway.get_prices(
        security_id=uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        from_date=date(2024, 1, 4),
        to_date=date(2024, 1, 5),
    )
    assert len(prices) == 2


# --------------------------------------------------------------------------- #
# Lifecycle: closing owned clients, leaving injected clients alone.
# --------------------------------------------------------------------------- #


def test_fmp_gateway_close_closes_its_owned_http_client():
    gateway = FmpGateway(api_key="abc", base_url="https://fmp.test")
    inner = gateway._client

    gateway.close()

    assert inner._client.is_closed


def test_fmp_gateway_close_leaves_injected_client_open():
    injected = _client(
        httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
    )

    gateway = FmpGateway(api_key="abc", client=injected)
    gateway.close()

    # The injected client is the caller's responsibility (httpx ownership).
    assert not injected.is_closed


def test_fmp_http_client_close_leaves_injected_client_open():
    injected = _client(
        httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
    )

    FmpHttpClient(api_key="abc", client=injected).close()

    assert not injected.is_closed


def test_fmp_http_client_close_closes_its_own_client():
    client = FmpHttpClient(api_key="abc", base_url="https://fmp.test")
    try:
        client.close()
        assert client._client.is_closed
    finally:
        # ``close`` is idempotent; guard test teardown just in case.
        client.close()


# --------------------------------------------------------------------------- #
# Stub gateway
# --------------------------------------------------------------------------- #


def test_stub_fmp_gateway_generates_deterministic_prices():
    gateway = StubFmpGateway(api_key="stub")
    security_id = uuid4()
    prices = gateway.get_prices(
        security_id=security_id,
        symbol="AAPL",
        exchange="NASDAQ",
        from_date=date(2024, 1, 1),
        to_date=date(2024, 1, 3),
    )

    assert len(prices) == 3
    assert (
        gateway.get_prices(
            security_id=security_id,
            symbol="AAPL",
            exchange="NASDAQ",
            from_date=date(2024, 1, 1),
            to_date=date(2024, 1, 3),
        )
        == prices
    )
    single = gateway.get_price_on_date(
        security_id=security_id,
        symbol="AAPL",
        exchange="NASDAQ",
        date=date(2024, 1, 1),
    )
    assert single is not None
    assert isinstance(single, HistoricalPrice)


def test_stub_fmp_gateway_search_and_lookup():
    gateway = StubFmpGateway(api_key="stub")

    results = gateway.search("apple")
    assert [result.code for result in results] == ["AAPL"]

    lookups = gateway.lookup_symbol("vod")
    assert all(isinstance(result, SymbolLookupResult) for result in lookups)
    assert [result.symbol for result in lookups] == ["VOD"]


def test_stub_fmp_gateway_unknown_and_failure_knobs():
    gateway = StubFmpGateway(api_key="stub")
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_prices(
            security_id=uuid4(),
            symbol="ZZZZ",
            exchange="NASDAQ",
            from_date=date(2024, 1, 1),
            to_date=date(2024, 1, 2),
        )

    overriding = StubFmpGateway(api_key="stub", unknown_symbols={"AAPL"})
    with pytest.raises(MarketDataNotFoundError):
        overriding.get_price_on_date(
            security_id=uuid4(),
            symbol="AAPL",
            exchange="NASDAQ",
            date=date(2024, 1, 1),
        )

    failing = StubFmpGateway(api_key="stub", fail_on_symbols={"AAPL"})
    with pytest.raises(MarketDataProviderError):
        failing.get_prices(
            security_id=uuid4(),
            symbol="AAPL",
            exchange="NASDAQ",
            from_date=date(2024, 1, 1),
            to_date=date(2024, 1, 2),
        )
    assert failing.get_prices(
        security_id=uuid4(),
        symbol="MSFT",
        exchange="NASDAQ",
        from_date=date(2024, 1, 1),
        to_date=date(2024, 1, 2),
    )


def test_stub_fmp_gateway_intraday_prices():
    gateway = StubFmpGateway(api_key="stub")
    prices = gateway.get_intraday_prices(
        security_id=uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        from_datetime=datetime(2026, 7, 28, 10, 0, tzinfo=UTC),
        to_datetime=datetime(2026, 7, 28, 13, 0, tzinfo=UTC),
    )
    assert len(prices) == 4
    assert all(price.timestamp.tzinfo is not None for price in prices)


# --------------------------------------------------------------------------- #
# Fundamentals: canned FMP-shaped payloads.
# --------------------------------------------------------------------------- #

_PROFILE_PAYLOAD: list[dict[str, Any]] = [
    {
        "symbol": "AAPL",
        "companyName": "Apple Inc.",
        "marketCap": "3400000000000",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "beta": "1.24",
        "price": "229.87",
        "website": "https://www.apple.com",
        "description": "Apple Inc. designs and sells consumer electronics.",
        "ceo": "Tim Cook",
        "fullTimeEmployees": "164000",
        "exchangeShortName": "NASDAQ",
        "exchange": "NASDAQ Global Select",
        "currency": "USD",
        "ipoDate": "1980-12-12",
        "cik": "0000320193",
        "isin": "US0378331005",
        "image": "https://images.example.com/AAPL.png",
        "isActivelyTrading": "true",
    }
]

_INCOME_PAYLOAD: list[dict[str, Any]] = [
    {
        "date": "2024-09-28",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "cik": "0000320193",
        "fillingDate": "2024-11-01",
        "acceptedDate": "2024-11-01 06:01:36",
        "fiscalYear": "2024",
        "period": "FY",
        "revenue": "391035000000",
        "costOfRevenue": "210352000000",
        "grossProfit": "180683000000",
        "researchAndDevelopmentExpenses": "31370000000",
        "sellingGeneralAndAdministrativeExpenses": "26097000000",
        "operatingExpenses": "57467000000",
        "operatingIncome": "123216000000",
        "interestExpense": "0",
        "otherIncomeExpense": "-12830000000",
        "incomeTaxExpense": "29749000000",
        "netIncome": "93736000000",
        "eps": "6.11",
        "epsDiluted": "6.08",
        "weightedAverageSharesOutstanding": "15343783000",
        "weightedAverageSharesOutstandingDiluted": "15408095000",
    },
    {
        "date": "2023-09-30",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "cik": "0000320193",
        "fillingDate": "2023-11-03",
        "acceptedDate": "2023-11-03 06:01:15",
        "fiscalYear": "2023",
        "period": "FY",
        "revenue": "383285000000",
        "costOfRevenue": "214137000000",
        "grossProfit": "169148000000",
        "researchAndDevelopmentExpenses": "29915000000",
        "sellingGeneralAndAdministrativeExpenses": "24932000000",
        "operatingExpenses": "54847000000",
        "operatingIncome": "114301000000",
        "interestExpense": "3933000000",
        "otherIncomeExpense": "-565000000",
        "incomeTaxExpense": "16741000000",
        "netIncome": "96995000000",
        "eps": "6.16",
        "epsDiluted": "6.13",
        "weightedAverageSharesOutstanding": "15744231000",
        "weightedAverageSharesOutstandingDiluted": "15812547000",
    },
]

_BALANCE_PAYLOAD: list[dict[str, Any]] = [
    {
        "date": "2024-09-28",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "cik": "0000320193",
        "fiscalYear": "2024",
        "period": "FY",
        "totalAssets": "364980000000",
        "currentAssets": "152987000000",
        "totalLiabilities": "308030000000",
        "currentLiabilities": "176392000000",
        "totalDebt": "106629000000",
        "cashAndCashEquivalents": "29943000000",
        "inventory": "7286000000",
        "receivables": "33410000000",
        "payables": "68960000000",
        "goodwill": "0",
        "retainedEarnings": "-19154000000",
        "totalEquity": "56950000000",
        "commonStock": "83276000000",
        "netDebt": "76686000000",
    },
    {
        "date": "2023-09-30",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "cik": "0000320193",
        "fiscalYear": "2023",
        "period": "FY",
        "totalAssets": "352583000000",
        "currentAssets": "143566000000",
        "totalLiabilities": "290437000000",
        "currentLiabilities": "145308000000",
        "totalDebt": "111088000000",
        "cashAndCashEquivalents": "29965000000",
        "inventory": "6331000000",
        "receivables": "29508000000",
        "payables": "62611000000",
        "goodwill": "0",
        "retainedEarnings": "-2144000000",
        "totalEquity": "62146000000",
        "commonStock": "73812000000",
        "netDebt": "81123000000",
    },
]

_CASH_FLOW_PAYLOAD: list[dict[str, Any]] = [
    {
        "date": "2024-09-28",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "cik": "0000320193",
        "fiscalYear": "2024",
        "period": "FY",
        "netIncome": "93736000000",
        "operatingCashFlow": "118254000000",
        "investingCashFlow": "2935000000",
        "financingCashFlow": "-121983000000",
        "capitalExpenditure": "-9447000000",
        "freeCashFlow": "108807000000",
        "dividendsPaid": "-15234000000",
        "stockBasedCompensation": "11688000000",
        "cashChange": "-7943000000",
    },
    {
        "date": "2023-09-30",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "cik": "0000320193",
        "fiscalYear": "2023",
        "period": "FY",
        "netIncome": "96995000000",
        "operatingCashFlow": "110543000000",
        "investingCashFlow": "3705000000",
        "financingCashFlow": "-108488000000",
        "capitalExpenditure": "-10959000000",
        "freeCashFlow": "99584000000",
        "dividendsPaid": "-15025000000",
        "stockBasedCompensation": "10833000000",
        "cashChange": "5760000000",
    },
]

_METRICS_PAYLOAD: list[dict[str, Any]] = [
    {
        "symbol": "AAPL",
        "date": "2024-09-28",
        "fiscalYear": "2024",
        "period": "FY",
        "marketCap": "3400000000000",
        "enterpriseValue": "3476686000000",
        "peRatio": "36.28",
        "pegRatio": "2.11",
        "priceToSalesRatio": "8.69",
        "priceToBookRatio": "59.71",
        "enterpriseValueOverEBITDA": "25.14",
        "evToSales": "8.89",
        "dividendYield": "0.0044",
        "payoutRatio": "0.16",
        "currentRatio": "0.87",
        "quickRatio": "0.83",
        "debtToEquity": "1.87",
        "workingCapital": "-23405000000",
    }
]

_RATIOS_PAYLOAD: list[dict[str, Any]] = [
    {
        "symbol": "AAPL",
        "date": "2024-09-28",
        "fiscalYear": "2024",
        "period": "FY",
        "grossProfitMargin": "0.4621",
        "operatingProfitMargin": "0.3151",
        "netProfitMargin": "0.2397",
        "returnOnAssets": "0.2568",
        "returnOnEquity": "1.6466",
        "returnOnCapitalEmployed": "0.5708",
        "interestCoverage": "0.0",
        "quickRatio": "0.8261",
        "currentRatio": "0.8673",
        "debtToEquity": "1.8727",
        "priceEarningsRatio": "36.28",
        "bookValuePerShare": "3.85",
        "dividendYield": "0.0044",
    }
]


# --------------------------------------------------------------------------- #
# Fundamentals: happy path, one test per capability (AC1, AC2).
# --------------------------------------------------------------------------- #


def test_get_company_profile_parses_mocked_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/profile/AAPL"
        assert request.url.params["apikey"] == "test-key"
        return httpx.Response(200, json=_PROFILE_PAYLOAD)

    profile = _gateway(handler).get_company_profile("AAPL")

    assert isinstance(profile, CompanyProfile)
    assert profile.symbol == "AAPL"
    assert profile.company_name == "Apple Inc."
    assert profile.market_cap == Decimal("3400000000000")
    assert profile.sector == "Technology"
    assert profile.industry == "Consumer Electronics"
    assert profile.beta == Decimal("1.24")
    assert profile.price == Decimal("229.87")
    assert profile.website == "https://www.apple.com"
    assert profile.description == "Apple Inc. designs and sells consumer electronics."
    assert profile.ceo == "Tim Cook"
    assert profile.full_time_employees == 164000
    assert profile.exchange_short_name == "NASDAQ"
    assert profile.exchange == "NASDAQ Global Select"
    assert profile.currency == "USD"
    assert profile.ipo_date == date(1980, 12, 12)
    assert profile.cik == "0000320193"
    assert profile.isin == "US0378331005"
    assert profile.image == "https://images.example.com/AAPL.png"
    assert profile.is_actively_trading is True


def test_get_income_statement_parses_mocked_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/income-statement/AAPL"
        assert request.url.params["period"] == "annual"
        assert request.url.params["limit"] == "5"
        return httpx.Response(200, json=_INCOME_PAYLOAD)

    statements = _gateway(handler).get_income_statement("AAPL")

    assert len(statements) == 2
    assert all(isinstance(item, IncomeStatement) for item in statements)
    first = statements[0]
    assert first.date == date(2024, 9, 28)
    assert first.symbol == "AAPL"
    assert first.reported_currency == "USD"
    assert first.cik == "0000320193"
    assert first.filling_date == date(2024, 11, 1)
    assert first.accepted_date == datetime(2024, 11, 1, 6, 1, 36)
    assert first.fiscal_year == "2024"
    assert first.period == "FY"
    assert first.revenue == Decimal("391035000000")
    assert first.cost_of_revenue == Decimal("210352000000")
    assert first.gross_profit == Decimal("180683000000")
    assert first.research_and_development_expenses == Decimal("31370000000")
    assert first.selling_general_and_administrative_expenses == Decimal("26097000000")
    assert first.operating_expenses == Decimal("57467000000")
    assert first.operating_income == Decimal("123216000000")
    assert first.interest_expense == Decimal("0")
    assert first.other_income_expense == Decimal("-12830000000")
    assert first.income_tax_expense == Decimal("29749000000")
    assert first.net_income == Decimal("93736000000")
    assert first.eps == Decimal("6.11")
    assert first.eps_diluted == Decimal("6.08")
    assert first.weighted_average_shares_outstanding == Decimal("15343783000")
    assert first.weighted_average_shares_outstanding_diluted == Decimal("15408095000")
    assert statements[1].fiscal_year == "2023"


def test_get_balance_sheet_parses_mocked_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/balance-sheet-statement/AAPL"
        assert request.url.params["period"] == "annual"
        assert request.url.params["limit"] == "5"
        return httpx.Response(200, json=_BALANCE_PAYLOAD)

    sheets = _gateway(handler).get_balance_sheet("AAPL")

    assert len(sheets) == 2
    assert all(isinstance(item, BalanceSheet) for item in sheets)
    first = sheets[0]
    assert first.date == date(2024, 9, 28)
    assert first.symbol == "AAPL"
    assert first.reported_currency == "USD"
    assert first.cik == "0000320193"
    assert first.fiscal_year == "2024"
    assert first.period == "FY"
    assert first.total_assets == Decimal("364980000000")
    assert first.current_assets == Decimal("152987000000")
    assert first.total_liabilities == Decimal("308030000000")
    assert first.current_liabilities == Decimal("176392000000")
    assert first.total_debt == Decimal("106629000000")
    assert first.cash_and_cash_equivalents == Decimal("29943000000")
    assert first.inventory == Decimal("7286000000")
    assert first.receivables == Decimal("33410000000")
    assert first.payables == Decimal("68960000000")
    assert first.goodwill == Decimal("0")
    assert first.retained_earnings == Decimal("-19154000000")
    assert first.total_equity == Decimal("56950000000")
    assert first.common_stock == Decimal("83276000000")
    assert first.net_debt == Decimal("76686000000")


def test_get_cash_flow_statement_parses_mocked_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/cash-flow-statement/AAPL"
        assert request.url.params["period"] == "annual"
        assert request.url.params["limit"] == "5"
        return httpx.Response(200, json=_CASH_FLOW_PAYLOAD)

    statements = _gateway(handler).get_cash_flow_statement("AAPL")

    assert len(statements) == 2
    assert all(isinstance(item, CashFlowStatement) for item in statements)
    first = statements[0]
    assert first.date == date(2024, 9, 28)
    assert first.symbol == "AAPL"
    assert first.reported_currency == "USD"
    assert first.cik == "0000320193"
    assert first.fiscal_year == "2024"
    assert first.period == "FY"
    assert first.net_income == Decimal("93736000000")
    assert first.operating_cash_flow == Decimal("118254000000")
    assert first.investing_cash_flow == Decimal("2935000000")
    assert first.financing_cash_flow == Decimal("-121983000000")
    assert first.capital_expenditure == Decimal("-9447000000")
    assert first.free_cash_flow == Decimal("108807000000")
    assert first.dividends_paid == Decimal("-15234000000")
    assert first.stock_based_compensation == Decimal("11688000000")
    assert first.cash_change == Decimal("-7943000000")


def test_get_key_metrics_parses_mocked_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/key-metrics/AAPL"
        return httpx.Response(200, json=_METRICS_PAYLOAD)

    metrics = _gateway(handler).get_key_metrics("AAPL")

    assert isinstance(metrics, KeyMetrics)
    assert metrics.symbol == "AAPL"
    assert metrics.date == date(2024, 9, 28)
    assert metrics.fiscal_year == "2024"
    assert metrics.period == "FY"
    assert metrics.market_cap == Decimal("3400000000000")
    assert metrics.enterprise_value == Decimal("3476686000000")
    assert metrics.pe_ratio == Decimal("36.28")
    assert metrics.peg_ratio == Decimal("2.11")
    assert metrics.price_to_sales_ratio == Decimal("8.69")
    assert metrics.price_to_book_ratio == Decimal("59.71")
    assert metrics.enterprise_value_over_ebitda == Decimal("25.14")
    assert metrics.ev_to_sales == Decimal("8.89")
    assert metrics.dividend_yield == Decimal("0.0044")
    assert metrics.payout_ratio == Decimal("0.16")
    assert metrics.current_ratio == Decimal("0.87")
    assert metrics.quick_ratio == Decimal("0.83")
    assert metrics.debt_to_equity == Decimal("1.87")
    assert metrics.working_capital == Decimal("-23405000000")


def test_get_financial_ratios_parses_mocked_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/ratios/AAPL"
        assert request.url.params["period"] == "annual"
        return httpx.Response(200, json=_RATIOS_PAYLOAD)

    ratios = _gateway(handler).get_financial_ratios("AAPL")

    assert isinstance(ratios, FinancialRatios)
    assert ratios.symbol == "AAPL"
    assert ratios.date == date(2024, 9, 28)
    assert ratios.fiscal_year == "2024"
    assert ratios.period == "FY"
    assert ratios.gross_profit_margin == Decimal("0.4621")
    assert ratios.operating_profit_margin == Decimal("0.3151")
    assert ratios.net_profit_margin == Decimal("0.2397")
    assert ratios.return_on_assets == Decimal("0.2568")
    assert ratios.return_on_equity == Decimal("1.6466")
    assert ratios.return_on_capital_employed == Decimal("0.5708")
    assert ratios.interest_coverage == Decimal("0.0")
    assert ratios.quick_ratio == Decimal("0.8261")
    assert ratios.current_ratio == Decimal("0.8673")
    assert ratios.debt_to_equity == Decimal("1.8727")
    assert ratios.price_earnings_ratio == Decimal("36.28")
    assert ratios.book_value_per_share == Decimal("3.85")
    assert ratios.dividend_yield == Decimal("0.0044")


# --------------------------------------------------------------------------- #
# Fundamentals: missing optional fields, not-found, provider failures (AC4).
# --------------------------------------------------------------------------- #


def test_fundamentals_missing_optional_fields_do_not_raise():
    profile_payload = [{"symbol": "AAPL", "companyName": "Apple Inc."}]
    income_payload = [{"date": "2024-09-28", "symbol": "AAPL"}]
    balance_payload = [{"date": "2024-09-28", "symbol": "AAPL"}]
    cash_flow_payload = [{"date": "2024-09-28", "symbol": "AAPL"}]
    metrics_payload = [{"date": "2024-09-28", "symbol": "AAPL"}]
    ratios_payload = [{"date": "2024-09-28", "symbol": "AAPL"}]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "profile" in path:
            return httpx.Response(200, json=profile_payload)
        if "income-statement" in path:
            return httpx.Response(200, json=income_payload)
        if "balance-sheet" in path:
            return httpx.Response(200, json=balance_payload)
        if "cash-flow" in path:
            return httpx.Response(200, json=cash_flow_payload)
        if "key-metrics" in path:
            return httpx.Response(200, json=metrics_payload)
        return httpx.Response(200, json=ratios_payload)

    gateway = _gateway(handler)

    profile = gateway.get_company_profile("AAPL")
    assert profile.market_cap is None
    assert profile.sector is None
    assert profile.full_time_employees is None
    assert profile.ipo_date is None
    assert profile.is_actively_trading is None

    income = gateway.get_income_statement("AAPL")[0]
    assert income.revenue is None
    assert income.fiscal_year is None
    assert income.accepted_date is None

    balance = gateway.get_balance_sheet("AAPL")[0]
    assert balance.total_assets is None
    assert balance.net_debt is None

    cash_flow = gateway.get_cash_flow_statement("AAPL")[0]
    assert cash_flow.operating_cash_flow is None
    assert cash_flow.cash_change is None

    metrics = gateway.get_key_metrics("AAPL")
    assert metrics.market_cap is None
    assert metrics.pe_ratio is None

    ratios = gateway.get_financial_ratios("AAPL")
    assert ratios.gross_profit_margin is None
    assert ratios.dividend_yield is None


def test_fundamentals_empty_payload_maps_to_not_found():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    gateway = _gateway(handler)

    with pytest.raises(MarketDataNotFoundError):
        gateway.get_company_profile("ZZZZ")
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_income_statement("ZZZZ")
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_balance_sheet("ZZZZ")
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_cash_flow_statement("ZZZZ")
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_key_metrics("ZZZZ")
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_financial_ratios("ZZZZ")


def test_fundamentals_http_500_maps_to_provider_error_without_body_leak():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="FMP upstream exploded: secret detail")

    gateway = _gateway(handler)
    with pytest.raises(MarketDataProviderError) as exc_info:
        gateway.get_income_statement("AAPL")

    assert "secret detail" not in str(exc_info.value)
    assert "upstream exploded" not in str(exc_info.value)


def test_fundamentals_timeout_maps_to_provider_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    gateway = _gateway(handler)
    with pytest.raises(MarketDataProviderError):
        gateway.get_income_statement("AAPL")


# --------------------------------------------------------------------------- #
# Fundamentals: period/limit validation and forwarding (AC3).
# --------------------------------------------------------------------------- #


def test_invalid_period_raises_before_http():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_INCOME_PAYLOAD)

    gateway = _gateway(handler)

    with pytest.raises(ValueError, match="period"):
        gateway.get_income_statement("AAPL", period="monthly")
    with pytest.raises(ValueError, match="period"):
        gateway.get_financial_ratios("AAPL", period="monthly")

    assert calls == []


def test_limit_and_period_are_forwarded():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["period"] = request.url.params["period"]
        seen["limit"] = request.url.params["limit"]
        return httpx.Response(200, json=_INCOME_PAYLOAD)

    _gateway(handler).get_income_statement("AAPL", period="quarter", limit=3)

    assert seen["period"] == "quarter"
    assert seen["limit"] == "3"


def test_statement_reads_fmp_legacy_and_stable_key_spellings():
    income_row = {
        "date": "2024-09-28",
        "symbol": "AAPL",
        "calendarYear": "2024",
        "weightedAverageShsOut": "15343783000",
        "weightedAverageShsOutDil": "15408095000",
        "totalOtherIncomeExpensesNet": "-12830000000",
    }
    balance_row = {
        "date": "2024-09-28",
        "symbol": "AAPL",
        "totalCurrentAssets": "152987000000",
        "totalCurrentLiabilities": "176392000000",
        "totalStockholdersEquity": "56950000000",
        "netReceivables": "33410000000",
        "accountPayables": "68960000000",
    }
    cash_flow_row = {
        "date": "2024-09-28",
        "symbol": "AAPL",
        "netCashProvidedByOperatingActivities": "118254000000",
        "netCashUsedForInvestingActivites": "2935000000",
        "netCashUsedProvidedByFinancingActivities": "-121983000000",
        "netChangeInCash": "-7943000000",
    }
    metrics_row = {"date": "2024-09-28", "symbol": "AAPL", "debtEquityRatio": "1.87"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "income-statement" in path:
            return httpx.Response(200, json=[income_row])
        if "balance-sheet" in path:
            return httpx.Response(200, json=[balance_row])
        if "cash-flow" in path:
            return httpx.Response(200, json=[cash_flow_row])
        return httpx.Response(200, json=[metrics_row])

    gateway = _gateway(handler)

    income = gateway.get_income_statement("AAPL")[0]
    assert income.fiscal_year == "2024"
    assert income.weighted_average_shares_outstanding == Decimal("15343783000")
    assert income.weighted_average_shares_outstanding_diluted == Decimal("15408095000")
    assert income.other_income_expense == Decimal("-12830000000")

    balance = gateway.get_balance_sheet("AAPL")[0]
    assert balance.current_assets == Decimal("152987000000")
    assert balance.current_liabilities == Decimal("176392000000")
    assert balance.total_equity == Decimal("56950000000")
    assert balance.receivables == Decimal("33410000000")
    assert balance.payables == Decimal("68960000000")

    cash_flow = gateway.get_cash_flow_statement("AAPL")[0]
    assert cash_flow.operating_cash_flow == Decimal("118254000000")
    assert cash_flow.investing_cash_flow == Decimal("2935000000")
    assert cash_flow.financing_cash_flow == Decimal("-121983000000")
    assert cash_flow.cash_change == Decimal("-7943000000")

    assert gateway.get_key_metrics("AAPL").debt_to_equity == Decimal("1.87")


# --------------------------------------------------------------------------- #
# Fundamentals: Error Message discrimination (review follow-up b).
# --------------------------------------------------------------------------- #


def test_fundamentals_error_message_maps_to_not_found():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"Error Message": "Symbol not found or unavailable."}
        )

    gateway = _gateway(handler)
    with pytest.raises(MarketDataNotFoundError) as exc_info:
        gateway.get_income_statement("AAPL")

    assert "AAPL" in str(exc_info.value)
    assert "Symbol not found" not in str(exc_info.value)


@pytest.mark.parametrize(
    "message",
    [
        "Invalid API KEY. Please retry.",
        "Limit Rate exceeded",
        "Requests count exceeds quota",
    ],
)
def test_credential_and_quota_messages_map_to_configuration_error(message):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Error Message": message})

    gateway = _gateway(handler)
    with pytest.raises(MarketDataConfigurationError) as exc_info:
        gateway.get_income_statement("AAPL")

    assert message not in str(exc_info.value)


def test_historical_credential_message_maps_to_configuration_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"Error Message": "Invalid API KEY. Please retry."}
        )

    gateway = _gateway(handler)
    with pytest.raises(MarketDataConfigurationError):
        gateway.get_prices(
            security_id=uuid4(),
            symbol="AAPL",
            exchange="NASDAQ",
            from_date=date(2024, 1, 4),
            to_date=date(2024, 1, 5),
        )


# --------------------------------------------------------------------------- #
# Search hardening (review follow-up a).
# --------------------------------------------------------------------------- #


def test_search_tolerates_rows_missing_name_and_symbol():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"symbol": "AAPL", "exchange": "NASDAQ"},
                {"name": "No Symbol Inc.", "exchange": "NASDAQ"},
                {},
            ],
        )

    results = _gateway(handler).search("apple")

    assert len(results) == 3
    assert results[0].code == "AAPL"
    assert results[0].name == ""
    assert results[1].code == ""
    assert results[1].name == "No Symbol Inc."
    assert results[2].code == ""
    assert results[2].name == ""


def test_lookup_symbol_skips_rows_without_a_usable_symbol():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"},
                {"name": "No Symbol Inc.", "exchange": "NASDAQ"},
                {},
                "not-a-dict",
                {"symbol": "   ", "name": "Blank Symbol"},
            ],
        )

    lookups = _gateway(handler).lookup_symbol("apple")

    # Structural surprises in a row are skipped, never raised.
    assert [item.symbol for item in lookups] == ["AAPL"]
    assert lookups[0].name == "Apple Inc."


# --------------------------------------------------------------------------- #
# Stub gateway fundamentals.
# --------------------------------------------------------------------------- #


def test_stub_fmp_gateway_fundamentals_are_deterministic():
    gateway = StubFmpGateway(api_key="stub")

    profile = gateway.get_company_profile("AAPL")
    assert isinstance(profile, CompanyProfile)
    assert profile.company_name == "Apple Inc."
    assert profile.market_cap == Decimal("3400000000000")
    assert gateway.get_company_profile("aapl") == profile

    income = gateway.get_income_statement("MSFT")
    assert len(income) == 2
    assert all(isinstance(item, IncomeStatement) for item in income)
    assert income[0].revenue == Decimal("245122000000")
    assert gateway.get_income_statement("MSFT", limit=1) == [income[0]]

    sheets = gateway.get_balance_sheet("AAPL")
    assert all(isinstance(item, BalanceSheet) for item in sheets)
    assert sheets[0].total_assets == Decimal("364980000000")

    cash_flows = gateway.get_cash_flow_statement("AAPL")
    assert all(isinstance(item, CashFlowStatement) for item in cash_flows)
    assert cash_flows[0].free_cash_flow == Decimal("108807000000")

    metrics = gateway.get_key_metrics("AAPL")
    assert isinstance(metrics, KeyMetrics)
    assert metrics.market_cap == Decimal("3400000000000")

    ratios = gateway.get_financial_ratios("MSFT")
    assert isinstance(ratios, FinancialRatios)
    assert ratios.net_profit_margin == Decimal("0.3596")


def test_stub_fmp_gateway_fundamentals_error_and_period_paths():
    gateway = StubFmpGateway(api_key="stub")

    with pytest.raises(MarketDataNotFoundError):
        gateway.get_company_profile("ZZZZ")
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_income_statement("ZZZZ")
    with pytest.raises(MarketDataProviderError):
        StubFmpGateway(api_key="stub", fail_on_symbols={"AAPL"}).get_key_metrics("AAPL")
    with pytest.raises(ValueError, match="period"):
        gateway.get_income_statement("AAPL", period="monthly")
    with pytest.raises(ValueError, match="period"):
        gateway.get_financial_ratios("AAPL", period="monthly")
