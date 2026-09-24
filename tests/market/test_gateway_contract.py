# ruff: noqa: PLR2004, SLF001
"""Contract tests for the provider-agnostic fundamentals/options gateway seam.

Everything here is offline: the only data sources are hand-built reference
JSON samples and the deterministic ``StubEodhdGateway`` fixtures. No network,
no Redis.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest

from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    IncomeStatement,
    KeyMetrics,
    OptionsChain,
    OptionsChainEntry,
    OptionsContract,
    OptionsGreeks,
    OptionsQuote,
    SymbolLookupResult,
)
from src.market.eodhd import EodhdGateway
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)
from src.stubs.eodhd import StubEodhdGateway

PROVIDER_TOKENS = ("fmp", "polygon", "eodhd", "eod")

NEW_TYPE_NAMES = (
    "CompanyProfile",
    "IncomeStatement",
    "BalanceSheet",
    "CashFlowStatement",
    "KeyMetrics",
    "FinancialRatios",
    "SymbolLookupResult",
    "OptionsContract",
    "OptionsGreeks",
    "OptionsQuote",
    "OptionsChainEntry",
    "OptionsChain",
)

NEW_GATEWAY_METHODS = (
    "lookup_symbol",
    "get_company_profile",
    "get_income_statement",
    "get_balance_sheet",
    "get_cash_flow_statement",
    "get_key_metrics",
    "get_financial_ratios",
    "get_options_chain",
)

NEW_EXCEPTION_NAMES = (
    "MarketDataNotFoundError",
    "MarketDataProviderError",
    "MarketDataConfigurationError",
)


# --------------------------------------------------------------------------- #
# Types: reference-shaped JSON validates against the models.
# --------------------------------------------------------------------------- #


def test_fmp_shaped_profile_and_income_statement_validate():
    profile = CompanyProfile(
        symbol="AAPL",
        company_name="Apple Inc.",
        market_cap="3000000000000",
        sector="Technology",
        beta="1.24",
        price="229.87",
        full_time_employees=164000,
        ipo_date=date(1980, 12, 12),
        is_actively_trading=True,
    )
    assert profile.company_name == "Apple Inc."
    assert profile.market_cap == Decimal("3000000000000")
    assert profile.full_time_employees == 164000
    assert profile.ipo_date == date(1980, 12, 12)
    assert profile.is_actively_trading is True

    statement = IncomeStatement(
        date=date(2024, 9, 28),
        symbol="AAPL",
        reported_currency="USD",
        fiscal_year="2024",
        period="FY",
        revenue="391035000000",
        net_income="93736000000",
        eps_diluted="6.08",
        weighted_average_shares_outstanding="15343783000",
        weighted_average_shares_outstanding_diluted="15408095000",
    )
    assert statement.date == date(2024, 9, 28)
    assert statement.revenue == Decimal("391035000000")
    assert statement.weighted_average_shares_outstanding == Decimal("15343783000")
    assert (
        statement.weighted_average_shares_outstanding_diluted == Decimal("15408095000")
    )


def test_fmp_shaped_balance_sheet_cash_flow_metrics_ratios_validate():
    balance_sheet = BalanceSheet(
        date=date(2024, 9, 28),
        symbol="AAPL",
        total_assets="364980000000",
        total_liabilities="308030000000",
        total_equity="56950000000",
        net_debt="76686000000",
    )
    assert balance_sheet.total_assets == Decimal("364980000000")
    assert balance_sheet.net_debt == Decimal("76686000000")

    cash_flow = CashFlowStatement(
        date=date(2024, 9, 28),
        symbol="AAPL",
        operating_cash_flow="118254000000",
        capital_expenditure="-9447000000",
        free_cash_flow="108807000000",
    )
    assert cash_flow.operating_cash_flow == Decimal("118254000000")
    assert cash_flow.capital_expenditure == Decimal("-9447000000")

    metrics = KeyMetrics.model_validate(
        {
            "symbol": "AAPL",
            "date": "2024-09-28",
            "market_cap": "3400000000000",
            "enterprise_value_over_ebitda": "25.14",
            "debt_to_equity": "1.87",
        }
    )
    assert metrics.date == date(2024, 9, 28)
    assert metrics.enterprise_value_over_ebitda == Decimal("25.14")

    ratios = FinancialRatios.model_validate(
        {
            "symbol": "AAPL",
            "date": "2024-09-28",
            "gross_profit_margin": "0.4621",
            "return_on_equity": "1.6466",
            "book_value_per_share": "3.85",
        }
    )
    assert ratios.gross_profit_margin == Decimal("0.4621")
    assert ratios.book_value_per_share == Decimal("3.85")


def test_polygon_shaped_options_contract_and_chain_validate():
    contract = OptionsContract(
        contract_ticker="O:AAPL250117C00150000",
        symbol="AAPL",
        strike_price="150",
        expiration_date=date(2025, 1, 17),
        contract_type="call",
        shares_per_contract=100,
        primary_exchange="BATO",
        active=True,
    )
    assert contract.contract_ticker == "O:AAPL250117C00150000"
    assert contract.symbol == "AAPL"
    assert contract.strike_price == Decimal("150")
    assert contract.expiration_date == date(2025, 1, 17)
    assert contract.contract_type == "call"

    greeks = OptionsGreeks(
        delta="0.5314", gamma="0.0128", theta="-0.0731", vega="0.3412", rho="0.0318"
    )
    quote = OptionsQuote(
        implied_volatility="0.2417",
        open_interest=8421,
        day_volume=1875,
        day_open="9.75",
        day_close="10.60",
        greeks=greeks,
    )
    assert quote.implied_volatility == Decimal("0.2417")
    assert quote.open_interest == 8421
    assert quote.day_volume == 1875
    assert quote.greeks is not None
    assert quote.greeks.delta == Decimal("0.5314")
    assert quote.greeks.vega == Decimal("0.3412")

    chain = OptionsChain(
        underlying_symbol="AAPL",
        as_of=date(2024, 12, 2),
        contracts=[OptionsChainEntry(contract=contract, quote=quote)],
    )
    assert chain.underlying_symbol == "AAPL"
    assert len(chain.contracts) == 1
    entry_greeks = chain.contracts[0].quote.greeks
    assert entry_greeks is not None
    assert entry_greeks.theta == Decimal("-0.0731")


def test_new_public_names_are_provider_agnostic():
    for name in (*NEW_TYPE_NAMES, *NEW_EXCEPTION_NAMES, *NEW_GATEWAY_METHODS):
        lowered = name.lower()
        assert not any(token in lowered for token in PROVIDER_TOKENS), name


# --------------------------------------------------------------------------- #
# Gateway ABC: non-breaking defaults keep existing implementations concrete.
# --------------------------------------------------------------------------- #


@patch("src.market.eodhd.APIClient")
def test_eodhd_gateway_stays_concrete_and_defaults_raise(mock_api_client_cls):
    gateway = EodhdGateway(api_key="test_key")
    mock_api_client_cls.assert_called_once_with("test_key")

    with pytest.raises(MarketDataProviderError, match="not supported"):
        gateway.lookup_symbol("AAPL")
    with pytest.raises(MarketDataProviderError, match="not supported"):
        gateway.get_company_profile("AAPL")
    with pytest.raises(MarketDataProviderError, match="not supported"):
        gateway.get_income_statement("AAPL")
    with pytest.raises(MarketDataProviderError, match="not supported"):
        gateway.get_balance_sheet("AAPL")
    with pytest.raises(MarketDataProviderError, match="not supported"):
        gateway.get_cash_flow_statement("AAPL")
    with pytest.raises(MarketDataProviderError, match="not supported"):
        gateway.get_key_metrics("AAPL")
    with pytest.raises(MarketDataProviderError, match="not supported"):
        gateway.get_financial_ratios("AAPL")
    with pytest.raises(MarketDataProviderError, match="not supported"):
        gateway.get_options_chain("AAPL")


def test_market_data_exceptions_are_provider_agnostic():
    not_found = MarketDataNotFoundError("ZZZZ")
    assert not_found.symbol == "ZZZZ"
    assert "ZZZZ" in str(not_found)

    assert str(MarketDataProviderError()) == "The market data provider is unavailable."
    assert "provider" in str(MarketDataConfigurationError())


# --------------------------------------------------------------------------- #
# Stub: deterministic fundamentals/options, not-found and failure paths.
# --------------------------------------------------------------------------- #


def test_stub_company_profile_and_lookup_are_deterministic():
    gateway = StubEodhdGateway(api_key="stub_key")

    profile = gateway.get_company_profile("AAPL")
    assert isinstance(profile, CompanyProfile)
    assert profile.symbol == "AAPL"
    assert profile.company_name == "Apple Inc."
    assert profile.market_cap == Decimal("3400000000000")
    assert gateway.get_company_profile("aapl") == profile

    results = gateway.lookup_symbol("app")
    assert all(isinstance(result, SymbolLookupResult) for result in results)
    assert [result.symbol for result in results] == ["AAPL"]

    all_results = gateway.lookup_symbol("")
    assert {result.symbol for result in all_results} >= {"AAPL", "MSFT"}
    assert gateway.lookup_symbol("no-such-company") == []


def test_stub_statements_metrics_and_ratios():
    gateway = StubEodhdGateway(api_key="stub_key")

    income = gateway.get_income_statement("MSFT")
    assert len(income) == 2
    assert all(isinstance(item, IncomeStatement) for item in income)
    assert income[0].date == date(2024, 6, 30)
    assert income[0].revenue == Decimal("245122000000")

    balance_sheets = gateway.get_balance_sheet("AAPL")
    assert len(balance_sheets) == 2
    assert all(isinstance(item, BalanceSheet) for item in balance_sheets)
    assert balance_sheets[0].total_assets == Decimal("364980000000")

    cash_flows = gateway.get_cash_flow_statement("AAPL", limit=1)
    assert len(cash_flows) == 1
    assert isinstance(cash_flows[0], CashFlowStatement)
    assert cash_flows[0].free_cash_flow == Decimal("108807000000")

    metrics = gateway.get_key_metrics("AAPL")
    assert isinstance(metrics, KeyMetrics)
    assert metrics.market_cap == Decimal("3400000000000")

    ratios = gateway.get_financial_ratios("MSFT")
    assert isinstance(ratios, FinancialRatios)
    assert ratios.net_profit_margin == Decimal("0.3596")


def test_stub_options_chain_and_expiration_filter():
    gateway = StubEodhdGateway(api_key="stub_key")

    chain = gateway.get_options_chain("AAPL")
    assert isinstance(chain, OptionsChain)
    assert chain.underlying_symbol == "AAPL"
    assert chain.as_of == date(2024, 12, 2)
    assert len(chain.contracts) == 4

    first = chain.contracts[0]
    assert isinstance(first, OptionsChainEntry)
    assert first.contract.contract_ticker == "O:AAPL250117C00150000"
    assert first.contract.strike_price == Decimal("150")
    assert first.contract.contract_type == "call"
    assert first.quote.implied_volatility == Decimal("0.2812")
    assert first.quote.open_interest == 12453
    assert first.quote.day_volume == 3120
    first_greeks = first.quote.greeks
    assert first_greeks is not None
    assert first_greeks.delta == Decimal("0.9412")
    assert first_greeks.gamma == Decimal("0.0031")
    assert first_greeks.theta == Decimal("-0.0412")
    assert first_greeks.vega == Decimal("0.1287")

    assert {entry.contract.contract_type for entry in chain.contracts} == {
        "call",
        "put",
    }

    filtered = gateway.get_options_chain("AAPL", expiration=date(2025, 1, 17))
    assert len(filtered.contracts) == 4
    empty = gateway.get_options_chain("AAPL", expiration=date(2026, 1, 16))
    assert empty.contracts == []

    # A known symbol without options data returns an empty (not missing) chain.
    msft_chain = gateway.get_options_chain("MSFT")
    assert msft_chain.contracts == []


def test_stub_unknown_symbol_raises_not_found():
    gateway = StubEodhdGateway(api_key="stub_key")

    with pytest.raises(MarketDataNotFoundError):
        gateway.get_company_profile("ZZZZ")
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_income_statement("ZZZZ")
    with pytest.raises(MarketDataNotFoundError):
        gateway.get_options_chain("ZZZZ")

    # The unknown_symbols knob marks an otherwise-known symbol as missing.
    overriding = StubEodhdGateway(api_key="stub_key", unknown_symbols={"AAPL"})
    with pytest.raises(MarketDataNotFoundError):
        overriding.get_company_profile("AAPL")
    assert overriding.get_company_profile("MSFT").symbol == "MSFT"


def test_stub_failure_symbol_raises_provider_error():
    gateway = StubEodhdGateway(api_key="stub_key", fail_on_symbols={"AAPL"})

    with pytest.raises(MarketDataProviderError):
        gateway.get_company_profile("AAPL")
    with pytest.raises(MarketDataProviderError):
        gateway.get_options_chain("AAPL")

    # Unaffected symbols keep working.
    assert gateway.get_company_profile("MSFT").symbol == "MSFT"


def test_stub_price_and_search_behaviour_unchanged():
    gateway = StubEodhdGateway(api_key="stub_key")

    results = gateway.search("AAPL")
    assert results[0].code == "AAPL"

    prices = gateway.get_prices(
        security_id=uuid4(),
        symbol="AAPL",
        exchange="US",
        from_date=date(2024, 1, 2),
        to_date=date(2024, 1, 5),
    )
    assert len(prices) == 4


def test_stub_prices_without_security_id_are_unlabelled():
    """A provider-agnostic read passes no security id; prices stay unlabelled."""
    gateway = StubEodhdGateway(api_key="stub_key")

    prices = gateway.get_prices(
        symbol="AAPL",
        exchange="US",
        from_date=date(2024, 1, 2),
        to_date=date(2024, 1, 5),
    )

    assert len(prices) == 4
    assert all(price.security_id is None for price in prices)


def test_stub_price_on_date_without_security_id_is_unlabelled():
    """A provider-agnostic single-date read passes no security id."""
    gateway = StubEodhdGateway(api_key="stub_key")

    price = gateway.get_price_on_date("AAPL", "US", date(2024, 1, 2))

    assert price is not None
    assert price.security_id is None


def test_stub_intraday_prices_without_security_id_are_unlabelled():
    """A provider-agnostic intraday read passes no security id."""
    gateway = StubEodhdGateway(api_key="stub_key")

    prices = gateway.get_intraday_prices(
        symbol="AAPL",
        exchange="US",
        from_datetime=datetime(2026, 7, 28, 10, 0, tzinfo=UTC),
        to_datetime=datetime(2026, 7, 28, 14, 0, tzinfo=UTC),
        interval="1h",
    )

    assert len(prices) == 5
    assert all(price.security_id is None for price in prices)
