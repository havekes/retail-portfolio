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

from src.market.api_types import HistoricalPrice, SymbolLookupResult
from src.market.exception import MarketDataNotFoundError, MarketDataProviderError
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
    http_client = httpx.Client(transport=transport)
    return FmpGateway(api_key="test-key", base_url=base_url, client=http_client)


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
            200, json={"Error Message": "Invalid API KEY. Please retry."}
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
    assert "Invalid API KEY" not in message
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
        client=httpx.Client(transport=httpx.MockTransport(handler)),
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
        client=httpx.Client(transport=transport),
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
