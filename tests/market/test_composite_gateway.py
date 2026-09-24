# ruff: noqa: PLR2004, SLF001
"""Routing tests for the provider-agnostic composite gateway.

Hand-written fake FMP/Polygon gateways record every call and return sentinel
values. No test dials the network or Redis.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPrice,
    IncomeStatement,
    KeyMetrics,
    OptionsChain,
    SecuritySearchResult,
    SymbolLookupResult,
)
from src.market.composite import CompositeMarketGateway
from src.market.exception import MarketDataProviderError
from src.market.gateway import MarketGateway

SID = uuid4()
FROM_DATE = date(2024, 1, 2)
TO_DATE = date(2024, 1, 5)
FROM_DT = datetime(2024, 1, 2, tzinfo=UTC)
TO_DT = datetime(2024, 1, 5, tzinfo=UTC)
EXPIRY = date(2025, 1, 17)


class FakeFmpGateway(MarketGateway):
    """Records calls and returns sentinel values for every FMP capability."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.intraday_error: MarketDataProviderError | None = None

    def _record(
        self, name: str, args: tuple[object, ...], kwargs: dict[str, object] | None = None
    ) -> None:
        self.calls.append((name, args, kwargs or {}))

    def search(self, query: str) -> list[SecuritySearchResult]:
        self._record("search", (query,))
        return [
            SecuritySearchResult(
                code="AAPL",
                exchange="NASDAQ",
                name="Apple Inc.",
                currency="USD",
                security_type="Common Stock",
                isin=None,
                country="US",
            )
        ]

    def get_price_on_date(
        self, security_id, symbol, exchange, date
    ) -> HistoricalPrice | None:
        self._record("get_price_on_date", (security_id, symbol, exchange, date))
        return HistoricalPrice(
            security_id=security_id,
            date=date,
            open=Decimal("1"),
            high=Decimal("2"),
            low=Decimal("0.5"),
            close=Decimal("1.5"),
            adjusted_close=Decimal("1.5"),
            volume=10,
        )

    def get_prices(self, security_id, symbol, exchange, from_date, to_date):
        self._record("get_prices", (security_id, symbol, exchange, from_date, to_date))
        return []

    def get_intraday_prices(
        self, security_id, symbol, exchange, from_datetime, to_datetime, interval="1h"
    ):
        self._record(
            "get_intraday_prices",
            (security_id, symbol, exchange, from_datetime, to_datetime, interval),
        )
        if self.intraday_error is not None:
            raise self.intraday_error
        return []

    def lookup_symbol(self, query: str) -> list[SymbolLookupResult]:
        self._record("lookup_symbol", (query,))
        return [SymbolLookupResult(symbol="AAPL", name="Apple Inc.")]

    def get_company_profile(
        self, symbol: str, *, exchange=None
    ) -> CompanyProfile:
        self._record("get_company_profile", (symbol,))
        return CompanyProfile(symbol=symbol, company_name="Apple Inc.")

    def get_income_statement(self, symbol, period="annual", limit=5, *, exchange=None):
        self._record("get_income_statement", (symbol, period, limit))
        return [IncomeStatement(date=FROM_DATE, symbol=symbol)]

    def get_balance_sheet(self, symbol, period="annual", limit=5, *, exchange=None):
        self._record("get_balance_sheet", (symbol, period, limit))
        return [BalanceSheet(date=FROM_DATE, symbol=symbol)]

    def get_cash_flow_statement(
        self, symbol, period="annual", limit=5, *, exchange=None
    ):
        self._record("get_cash_flow_statement", (symbol, period, limit))
        return [CashFlowStatement(date=FROM_DATE, symbol=symbol)]

    def get_key_metrics(self, symbol: str, *, exchange=None) -> KeyMetrics:
        self._record("get_key_metrics", (symbol,))
        return KeyMetrics(symbol=symbol, date=FROM_DATE)

    def get_financial_ratios(
        self, symbol, period="annual", *, exchange=None
    ) -> FinancialRatios:
        self._record("get_financial_ratios", (symbol, period))
        return FinancialRatios(symbol=symbol, date=FROM_DATE)


class FakePolygonGateway(MarketGateway):
    """Records options-chain calls and returns a sentinel chain."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def get_options_chain(
        self,
        symbol,
        *,
        expiration=None,
        contract_type=None,
        strike_min=None,
        strike_max=None,
    ) -> OptionsChain:
        self.calls.append(
            (
                "get_options_chain",
                (symbol,),
                {
                    "expiration": expiration,
                    "contract_type": contract_type,
                    "strike_min": strike_min,
                    "strike_max": strike_max,
                },
            )
        )
        return OptionsChain(underlying_symbol=symbol, as_of=None, contracts=[])

    # The composite must never route price/search capabilities to Polygon; if it
    # did, these would fail loudly.
    def search(self, query):
        raise AssertionError("Polygon must not receive search calls")

    def get_price_on_date(self, security_id, symbol, exchange, date):
        raise AssertionError("Polygon must not receive price calls")

    def get_prices(self, security_id, symbol, exchange, from_date, to_date):
        raise AssertionError("Polygon must not receive price calls")

    def get_intraday_prices(
        self, security_id, symbol, exchange, from_datetime, to_datetime, interval="1h"
    ):
        raise AssertionError("Polygon must not receive intraday calls")


@pytest.fixture
def fakes() -> tuple[FakeFmpGateway, FakePolygonGateway, CompositeMarketGateway]:
    fmp = FakeFmpGateway()
    polygon = FakePolygonGateway()
    return fmp, polygon, CompositeMarketGateway(fmp=fmp, polygon=polygon)


def test_price_capabilities_route_to_fmp(fakes):
    fmp, _polygon, composite = fakes

    composite.get_price_on_date(SID, "AAPL", "NASDAQ", FROM_DATE)
    composite.get_prices(SID, "AAPL", "NASDAQ", FROM_DATE, TO_DATE)
    composite.get_intraday_prices(SID, "AAPL", "NASDAQ", FROM_DT, TO_DT)

    assert [name for name, *_ in fmp.calls] == [
        "get_price_on_date",
        "get_prices",
        "get_intraday_prices",
    ]
    assert fmp.calls[0][1] == (SID, "AAPL", "NASDAQ", FROM_DATE)


def test_search_and_lookup_route_to_fmp(fakes):
    fmp, _polygon, composite = fakes

    assert composite.search("apple")[0].code == "AAPL"
    assert composite.lookup_symbol("app")[0].symbol == "AAPL"

    assert [name for name, *_ in fmp.calls] == ["search", "lookup_symbol"]


def test_fundamentals_route_to_fmp(fakes):
    fmp, _polygon, composite = fakes

    composite.get_company_profile("AAPL")
    composite.get_income_statement("AAPL", "quarter", 2)
    composite.get_balance_sheet("AAPL")
    composite.get_cash_flow_statement("AAPL")
    composite.get_key_metrics("AAPL")
    composite.get_financial_ratios("AAPL", "quarter")

    assert [name for name, *_ in fmp.calls] == [
        "get_company_profile",
        "get_income_statement",
        "get_balance_sheet",
        "get_cash_flow_statement",
        "get_key_metrics",
        "get_financial_ratios",
    ]
    # Period/limit arguments pass straight through.
    assert fmp.calls[1][1] == ("AAPL", "quarter", 2)
    assert fmp.calls[5][1] == ("AAPL", "quarter")


def test_options_route_to_polygon_with_filters(fakes):
    fmp, polygon, composite = fakes

    composite.get_options_chain(
        "AAPL",
        expiration=EXPIRY,
        contract_type="call",
        strike_min=Decimal("100"),
        strike_max=Decimal("200"),
    )

    assert [name for name, *_ in polygon.calls] == ["get_options_chain"]
    assert polygon.calls[0][1] == ("AAPL",)
    assert polygon.calls[0][2] == {
        "expiration": EXPIRY,
        "contract_type": "call",
        "strike_min": Decimal("100"),
        "strike_max": Decimal("200"),
    }
    # Options never leak to FMP.
    assert all(name != "get_options_chain" for name, *_ in fmp.calls)


def test_unsupported_capability_error_surfaces_unchanged(fakes):
    fmp, _polygon, composite = fakes
    fmp.intraday_error = MarketDataProviderError("capability not supported")

    with pytest.raises(MarketDataProviderError, match="capability not supported"):
        composite.get_intraday_prices(SID, "AAPL", "NASDAQ", FROM_DT, TO_DT)
