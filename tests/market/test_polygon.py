# ruff: noqa: PLR2004, SLF001
"""Tests for the Polygon options-chain gateway.

Every test patches ``src.market.polygon.requests.get``: no test dials the
network (no DNS, no HTTP, no Redis).
"""

from datetime import date
from decimal import Decimal
from typing import cast
from unittest.mock import patch

import pytest
import requests

from src.market.api_types import OptionsChain, OptionsContract
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)
from src.market.polygon import (
    _MAX_PAGES,
    PolygonGateway,
    _split_occ_ticker,
    polygon_gateway_factory,
)
from src.stubs.polygon import StubPolygonGateway


class FakeResponse:
    """Minimal ``requests.Response`` stand-in with a no-op ``raise_for_status``."""

    def __init__(
        self,
        status_code: int = 200,
        payload: object = None,
        *,
        json_error: bool = False,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self) -> object:
        if self._json_error:
            msg = "not valid JSON"
            raise ValueError(msg)
        return self._payload

    def raise_for_status(self) -> None:
        return None


def _result(
    ticker: str,
    strike: object,
    expiration: str,
    contract_type: str,
    *,
    delta: object = "0.5",
    gamma: object = "0.01",
    theta: object = "-0.02",
    vega: object = "0.1",
    rho: object = "0.01",
    implied_volatility: object = "0.25",
    open_interest: object = 100,
    day_volume: object = 10,
) -> dict[str, object]:
    return {
        "details": {
            "ticker": ticker,
            "contract_type": contract_type,
            "expiration_date": expiration,
            "strike_price": strike,
            "shares_per_contract": 100,
            "primary_exchange": "BATO",
        },
        "greeks": {
            "delta": delta,
            "gamma": gamma,
            "theta": theta,
            "vega": vega,
            "rho": rho,
        },
        "implied_volatility": implied_volatility,
        "open_interest": open_interest,
        "day": {
            "volume": day_volume,
            "open": "9.75",
            "high": "11.20",
            "low": "9.55",
            "close": "10.60",
        },
    }


CALL = _result(
    "O:AAPL250117C00150000",
    150.0,
    "2025-01-17",
    "call",
    delta="0.5314",
    gamma="0.0128",
    theta="-0.0731",
    vega="0.3412",
    rho="0.0318",
    implied_volatility="0.2417",
    open_interest=8421,
    day_volume=1875,
)
PUT = _result(
    "O:AAPL250117P00150000",
    150.0,
    "2025-01-17",
    "put",
    delta="-0.4686",
    gamma="0.0128",
    theta="-0.0201",
    vega="0.3412",
    rho="-0.0318",
    implied_volatility="0.2612",
    open_interest=5210,
    day_volume=640,
)


def _snapshot(results: list[dict[str, object]], next_url: str | None = None):
    payload: dict[str, object] = {"status": "OK", "results": results}
    if next_url is not None:
        payload["next_url"] = next_url
    return payload


# --------------------------------------------------------------------------- #
# OCC ticker helper.
# --------------------------------------------------------------------------- #


def test_split_occ_ticker_derives_underlying():
    assert _split_occ_ticker("O:AAPL250117C00150000") == "AAPL"
    assert _split_occ_ticker("O:SPY241220P00500000") == "SPY"
    assert _split_occ_ticker("O:BRK.B250117C00150000") == "BRK.B"
    assert _split_occ_ticker("not-an-occ-ticker") == ""


# --------------------------------------------------------------------------- #
# Parsing: mocked payload -> T01 options types.
# --------------------------------------------------------------------------- #


@patch("src.market.polygon.requests.get")
def test_get_options_chain_parses_mocked_payload(mock_get):
    mock_get.return_value = FakeResponse(payload=_snapshot([CALL, PUT]))
    gateway = PolygonGateway(api_key="test-key")

    chain = gateway.get_options_chain("aapl")

    assert isinstance(chain, OptionsChain)
    assert chain.underlying_symbol == "AAPL"
    assert chain.as_of is None
    assert len(chain.contracts) == 2

    call = chain.contracts[0]
    assert isinstance(call.contract, OptionsContract)
    assert call.contract.contract_ticker == "O:AAPL250117C00150000"
    assert call.contract.symbol == "AAPL"
    assert call.contract.strike_price == Decimal("150")
    assert call.contract.expiration_date == date(2025, 1, 17)
    assert call.contract.contract_type == "call"
    assert call.contract.shares_per_contract == 100
    assert call.contract.primary_exchange == "BATO"
    assert call.quote.implied_volatility == Decimal("0.2417")
    assert call.quote.open_interest == 8421
    assert call.quote.day_volume == 1875

    greeks = call.quote.greeks
    assert greeks is not None
    assert greeks.delta == Decimal("0.5314")
    assert greeks.gamma == Decimal("0.0128")
    assert greeks.theta == Decimal("-0.0731")
    assert greeks.vega == Decimal("0.3412")

    put = chain.contracts[1]
    assert put.contract.contract_type == "put"
    assert put.contract.contract_ticker == "O:AAPL250117P00150000"
    assert put.quote.implied_volatility == Decimal("0.2612")

    url = mock_get.call_args.args[0]
    assert "apiKey=test-key" in url
    assert "limit=250" in url
    assert mock_get.call_args.kwargs["timeout"] == 10


@patch("src.market.polygon.requests.get")
def test_missing_optional_snapshot_fields_are_tolerated(mock_get):
    sparse: dict[str, object] = {
        "details": {
            "ticker": "O:AAPL250117C00150000",
            "contract_type": "call",
            "expiration_date": "2025-01-17",
            "strike_price": 150.0,
        }
    }
    mock_get.return_value = FakeResponse(payload=_snapshot([sparse]))

    chain = PolygonGateway(api_key="k").get_options_chain("AAPL")

    entry = chain.contracts[0]
    assert entry.quote.implied_volatility is None
    assert entry.quote.open_interest is None
    assert entry.quote.day_volume is None
    assert entry.quote.greeks is None
    # Missing contract metadata falls back to the T01 defaults.
    assert entry.contract.shares_per_contract == 100
    assert entry.contract.primary_exchange is None


@patch("src.market.polygon.requests.get")
def test_contract_details_pass_through_shares_and_exchange(mock_get):
    result = _result("O:AAPL250117C00150000", 150.0, "2025-01-17", "call")
    details = cast("dict[str, object]", result["details"])
    details["shares_per_contract"] = 10
    details["primary_exchange"] = "CBOE"
    mock_get.return_value = FakeResponse(payload=_snapshot([result]))

    chain = PolygonGateway(api_key="k").get_options_chain("AAPL")

    contract = chain.contracts[0].contract
    assert contract.shares_per_contract == 10
    assert contract.primary_exchange == "CBOE"


# --------------------------------------------------------------------------- #
# Filters.
# --------------------------------------------------------------------------- #


@patch("src.market.polygon.requests.get")
def test_expiration_and_contract_type_are_query_params(mock_get):
    mock_get.return_value = FakeResponse(payload=_snapshot([PUT]))

    chain = PolygonGateway(api_key="k").get_options_chain(
        "AAPL",
        expiration=date(2025, 1, 17),
        contract_type="put",
    )

    url = mock_get.call_args.args[0]
    assert "expiration_date=2025-01-17" in url
    assert "contract_type=put" in url
    assert len(chain.contracts) == 1
    assert chain.contracts[0].contract.contract_type == "put"


@patch("src.market.polygon.requests.get")
def test_strike_range_is_filtered_locally(mock_get):
    low = _result("O:AAPL250117C00100000", 100.0, "2025-01-17", "call")
    mid = _result("O:AAPL250117C00150000", 150.0, "2025-01-17", "call")
    high = _result("O:AAPL250117C00200000", 200.0, "2025-01-17", "call")
    mock_get.return_value = FakeResponse(payload=_snapshot([low, mid, high]))

    chain = PolygonGateway(api_key="k").get_options_chain(
        "AAPL",
        strike_min=Decimal("120"),
        strike_max=Decimal("180"),
    )

    assert [entry.contract.strike_price for entry in chain.contracts] == [
        Decimal("150")
    ]
    # Strike bounds are applied client-side, never sent upstream.
    url = mock_get.call_args.args[0]
    assert "strike" not in url.lower()


@patch("src.market.polygon.requests.get")
def test_strike_range_only_minimum(mock_get):
    low = _result("O:AAPL250117C00100000", 100.0, "2025-01-17", "call")
    high = _result("O:AAPL250117C00200000", 200.0, "2025-01-17", "call")
    mock_get.return_value = FakeResponse(payload=_snapshot([low, high]))

    chain = PolygonGateway(api_key="k").get_options_chain(
        "AAPL", strike_min=Decimal("150")
    )

    assert [entry.contract.strike_price for entry in chain.contracts] == [
        Decimal("200")
    ]


# --------------------------------------------------------------------------- #
# Not-found / provider-failure mapping (no provider leakage).
# --------------------------------------------------------------------------- #


@patch("src.market.polygon.requests.get")
def test_http_404_raises_not_found(mock_get):
    mock_get.return_value = FakeResponse(status_code=404)

    with pytest.raises(MarketDataNotFoundError) as exc_info:
        PolygonGateway(api_key="k").get_options_chain("ZZZZ")

    assert exc_info.value.symbol == "ZZZZ"
    assert "polygon" not in str(exc_info.value).lower()


@patch("src.market.polygon.requests.get")
def test_empty_chain_raises_not_found(mock_get):
    mock_get.return_value = FakeResponse(payload=_snapshot([]))

    with pytest.raises(MarketDataNotFoundError) as exc_info:
        PolygonGateway(api_key="k").get_options_chain("AAPL")

    assert exc_info.value.symbol == "AAPL"
    assert "polygon" not in str(exc_info.value).lower()


@patch("src.market.polygon.requests.get")
def test_filters_that_empty_the_chain_raise_not_found(mock_get):
    mock_get.return_value = FakeResponse(payload=_snapshot([CALL]))

    with pytest.raises(MarketDataNotFoundError):
        PolygonGateway(api_key="k").get_options_chain(
            "AAPL", strike_min=Decimal("999")
        )


@pytest.mark.parametrize("status", [401, 403])
@patch("src.market.polygon.requests.get")
def test_unauthorized_raises_configuration_error(mock_get, status):
    mock_get.return_value = FakeResponse(status_code=status)

    with pytest.raises(MarketDataConfigurationError) as exc_info:
        PolygonGateway(api_key="k").get_options_chain("AAPL")

    assert "polygon" not in str(exc_info.value).lower()


@pytest.mark.parametrize("status", [500, 502, 429])
@patch("src.market.polygon.requests.get")
def test_non_200_raises_provider_error(mock_get, status):
    mock_get.return_value = FakeResponse(status_code=status)

    with pytest.raises(MarketDataProviderError) as exc_info:
        PolygonGateway(api_key="k").get_options_chain("AAPL")

    assert "polygon" not in str(exc_info.value).lower()


@patch("src.market.polygon.requests.get")
def test_request_exception_raises_provider_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("connection refused")

    with pytest.raises(MarketDataProviderError) as exc_info:
        PolygonGateway(api_key="k").get_options_chain("AAPL")

    assert "polygon" not in str(exc_info.value).lower()
    assert "connection refused" not in str(exc_info.value).lower()


@patch("src.market.polygon.requests.get")
def test_undecodable_payload_raises_provider_error(mock_get):
    mock_get.return_value = FakeResponse(payload=None, json_error=True)

    with pytest.raises(MarketDataProviderError) as exc_info:
        PolygonGateway(api_key="k").get_options_chain("AAPL")

    assert "polygon" not in str(exc_info.value).lower()


@patch("src.market.polygon.requests.get")
def test_missing_results_key_raises_provider_error(mock_get):
    mock_get.return_value = FakeResponse(payload={"status": "OK"})

    with pytest.raises(MarketDataProviderError):
        PolygonGateway(api_key="k").get_options_chain("AAPL")


@patch("src.market.polygon.requests.get")
def test_malformed_contract_raises_provider_error(mock_get):
    malformed: dict[str, object] = {
        "details": {
            "ticker": "O:AAPL250117C00150000",
            "contract_type": "call",
            "expiration_date": "not-a-date",
            "strike_price": 150.0,
        }
    }
    mock_get.return_value = FakeResponse(payload=_snapshot([malformed]))

    with pytest.raises(MarketDataProviderError):
        PolygonGateway(api_key="k").get_options_chain("AAPL")


# --------------------------------------------------------------------------- #
# Pagination.
# --------------------------------------------------------------------------- #


@patch("src.market.polygon.requests.get")
def test_next_url_is_followed_and_entries_merged(mock_get):
    next_url = "https://api.polygon.io/v3/snapshot/options/AAPL?cursor=abc"
    mock_get.side_effect = [
        FakeResponse(payload=_snapshot([CALL], next_url=next_url)),
        FakeResponse(payload=_snapshot([PUT])),
    ]

    chain = PolygonGateway(api_key="k").get_options_chain("AAPL")

    assert len(chain.contracts) == 2
    assert mock_get.call_count == 2
    second_url = mock_get.call_args_list[1].args[0]
    assert second_url.startswith(next_url)
    assert "apiKey=k" in second_url


@patch("src.market.polygon.requests.get")
def test_next_url_with_existing_api_key_is_not_duplicated(mock_get):
    next_url = "https://api.polygon.io/v3/snapshot/options/AAPL?cursor=abc&apiKey=k"
    mock_get.side_effect = [
        FakeResponse(payload=_snapshot([CALL], next_url=next_url)),
        FakeResponse(payload=_snapshot([PUT])),
    ]

    PolygonGateway(api_key="k").get_options_chain("AAPL")

    second_url = mock_get.call_args_list[1].args[0]
    assert second_url.count("apiKey=") == 1


@patch("src.market.polygon.requests.get")
def test_sticky_next_url_is_truncated_at_cap(mock_get):
    """A looping cursor stops at the page cap and serves the pages already fetched."""
    sticky = "https://api.polygon.io/v3/snapshot/options/AAPL?cursor=sticky"
    mock_get.side_effect = lambda *args, **kwargs: FakeResponse(
        payload=_snapshot([CALL], next_url=sticky)
    )

    chain = PolygonGateway(api_key="k").get_options_chain("AAPL")

    # The loop bails once the page cap is reached instead of hanging forever,
    # and the accumulated contracts are returned rather than discarded.
    assert mock_get.call_count == _MAX_PAGES
    assert len(chain.contracts) == _MAX_PAGES
    assert chain.contracts[0].contract.contract_ticker == "O:AAPL250117C00150000"
    assert "polygon" not in chain.underlying_symbol.lower()


# --------------------------------------------------------------------------- #
# Factory.
# --------------------------------------------------------------------------- #


def test_polygon_gateway_factory_uses_settings_key(monkeypatch):
    from src.market import polygon as polygon_module

    monkeypatch.setattr(polygon_module.settings, "stub_external_api", False)
    monkeypatch.setattr(polygon_module.settings, "polygon_api_key", "factory-key")

    gateway = polygon_gateway_factory()

    assert isinstance(gateway, PolygonGateway)
    assert gateway._api_key == "factory-key"


def test_polygon_gateway_factory_returns_stub_in_stub_mode(monkeypatch):
    from src.market import polygon as polygon_module

    monkeypatch.setattr(polygon_module.settings, "stub_external_api", True)

    gateway = polygon_gateway_factory()

    assert isinstance(gateway, StubPolygonGateway)


def test_stub_polygon_gateway_serves_deterministic_options():
    gateway = StubPolygonGateway(api_key="stub")

    chain = gateway.get_options_chain("AAPL")
    assert chain.underlying_symbol == "AAPL"
    assert chain.as_of == date(2024, 12, 2)
    assert len(chain.contracts) == 4

    filtered = gateway.get_options_chain("AAPL", contract_type="put")
    assert {entry.contract.contract_type for entry in filtered.contracts} == {"put"}

    with pytest.raises(MarketDataNotFoundError):
        gateway.get_options_chain("ZZZZ")
