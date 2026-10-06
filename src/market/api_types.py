from datetime import date, datetime
from decimal import Decimal
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict
from stockholm.currency import Currency

type SecurityId = UUID
type WatchlistId = UUID

# Canonical exchanges accepted by the data plane and mapped to provider suffixes.
# US primary venues require no suffix; non-US venues (TSX, LSE) map to provider
# suffixes.
SupportedExchange = Literal["NYSE", "NASDAQ", "NYSEARCA", "AMEX", "TSX", "LSE"]


class Security(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: SecurityId
    symbol: str
    exchange: str
    currency: Currency
    name: str
    isin: str | None
    is_active: bool
    updated_at: datetime


class Price(BaseModel):
    id: int
    security_id: SecurityId
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: Decimal
    currency: Currency


class EodhdSearchResult(BaseModel):
    code: str
    currency: str
    exchange: str
    name: str
    type: str
    country: str
    isin: str
    is_primary: str
    previous_close: str
    previous_close_date: str


class HistoricalPrice(BaseModel):
    id: int | None = None
    security_id: SecurityId | None = None
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: int


class IntradayHistoricalPrice(BaseModel):
    id: int | None = None
    security_id: SecurityId | None = None
    timestamp: AwareDatetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class IntradayPrice(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    security_id: SecurityId
    timestamp: AwareDatetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class SecuritySearchResult(BaseModel):
    """Public-facing security search result."""

    code: str
    exchange: str
    name: str
    currency: str
    security_type: str
    isin: str | None
    country: str


# --------------------------------------------------------------------------- #
# Fundamentals
#
# Provider-agnostic public types for company profiles, financial statements,
# key metrics, and financial ratios. Money-like values use ``Decimal``.
# --------------------------------------------------------------------------- #


class CompanyProfile(BaseModel):
    """Company profile and overview details."""

    symbol: str
    company_name: str
    market_cap: Decimal | None = None
    sector: str | None = None
    industry: str | None = None
    beta: Decimal | None = None
    price: Decimal | None = None
    website: str | None = None
    description: str | None = None
    ceo: str | None = None
    full_time_employees: int | None = None
    exchange_short_name: str | None = None
    exchange: str | None = None
    currency: str | None = None
    ipo_date: date | None = None
    cik: str | None = None
    isin: str | None = None
    image: str | None = None
    is_actively_trading: bool | None = None


class IncomeStatement(BaseModel):
    """Income statement for a reporting period."""

    date: date
    symbol: str
    reported_currency: str | None = None
    cik: str | None = None
    filing_date: date | None = None
    accepted_date: datetime | None = None
    fiscal_year: str | None = None
    period: str | None = None
    revenue: Decimal | None = None
    cost_of_revenue: Decimal | None = None
    gross_profit: Decimal | None = None
    research_and_development_expenses: Decimal | None = None
    selling_general_and_administrative_expenses: Decimal | None = None
    operating_expenses: Decimal | None = None
    operating_income: Decimal | None = None
    interest_expense: Decimal | None = None
    other_income_expense: Decimal | None = None
    income_tax_expense: Decimal | None = None
    net_income: Decimal | None = None
    eps: Decimal | None = None
    eps_diluted: Decimal | None = None
    weighted_average_shares_outstanding: Decimal | None = None
    weighted_average_shares_outstanding_diluted: Decimal | None = None


class BalanceSheet(BaseModel):
    """Balance sheet for a reporting period."""

    date: date
    symbol: str
    reported_currency: str | None = None
    cik: str | None = None
    fiscal_year: str | None = None
    period: str | None = None
    total_assets: Decimal | None = None
    current_assets: Decimal | None = None
    total_liabilities: Decimal | None = None
    current_liabilities: Decimal | None = None
    total_debt: Decimal | None = None
    cash_and_cash_equivalents: Decimal | None = None
    inventory: Decimal | None = None
    receivables: Decimal | None = None
    payables: Decimal | None = None
    goodwill: Decimal | None = None
    retained_earnings: Decimal | None = None
    total_equity: Decimal | None = None
    common_stock: Decimal | None = None
    net_debt: Decimal | None = None


class CashFlowStatement(BaseModel):
    """Cash-flow statement for a reporting period."""

    date: date
    symbol: str
    reported_currency: str | None = None
    cik: str | None = None
    fiscal_year: str | None = None
    period: str | None = None
    net_income: Decimal | None = None
    operating_cash_flow: Decimal | None = None
    investing_cash_flow: Decimal | None = None
    financing_cash_flow: Decimal | None = None
    capital_expenditure: Decimal | None = None
    free_cash_flow: Decimal | None = None
    dividends_paid: Decimal | None = None
    stock_based_compensation: Decimal | None = None
    cash_change: Decimal | None = None


class KeyMetrics(BaseModel):
    """Key metrics and valuation snapshot for a symbol."""

    symbol: str
    date: date
    fiscal_year: str | None = None
    period: str | None = None
    market_cap: Decimal | None = None
    enterprise_value: Decimal | None = None
    pe_ratio: Decimal | None = None
    peg_ratio: Decimal | None = None
    price_to_sales_ratio: Decimal | None = None
    price_to_book_ratio: Decimal | None = None
    enterprise_value_over_ebitda: Decimal | None = None
    ev_to_sales: Decimal | None = None
    dividend_yield: Decimal | None = None
    payout_ratio: Decimal | None = None
    current_ratio: Decimal | None = None
    quick_ratio: Decimal | None = None
    debt_to_equity: Decimal | None = None
    working_capital: Decimal | None = None


class FinancialRatios(BaseModel):
    """Financial ratios for a symbol and reporting period."""

    symbol: str
    date: date
    fiscal_year: str | None = None
    period: str | None = None
    gross_profit_margin: Decimal | None = None
    operating_profit_margin: Decimal | None = None
    net_profit_margin: Decimal | None = None
    return_on_assets: Decimal | None = None
    return_on_equity: Decimal | None = None
    return_on_capital_employed: Decimal | None = None
    interest_coverage: Decimal | None = None
    quick_ratio: Decimal | None = None
    current_ratio: Decimal | None = None
    debt_to_equity: Decimal | None = None
    price_earnings_ratio: Decimal | None = None
    book_value_per_share: Decimal | None = None
    dividend_yield: Decimal | None = None


class CompanyFundamentals(BaseModel):
    """Company details plus key metrics and ratios overview.

    Aggregate returned by ``GET /api/v1/market/data/fundamentals/{symbol}``:
    the canonical ``profile``, ``key_metrics`` and ``ratios`` objects, each
    field-for-field. Profile is required; key metrics and ratios are nullable
    when not reported by upstream providers (e.g. ETFs, recent IPOs).
    """

    profile: CompanyProfile
    key_metrics: KeyMetrics | None = None
    ratios: FinancialRatios | None = None


class SymbolLookupResult(BaseModel):
    """Symbol / company lookup result.

    Mirrors the reference symbol-search / ``stock-screener`` shape:
    ``symbol``, ``name``, ``exchange``, ``exchangeShortName``, ``currency``,
    ``type`` (``security_type``), ``country``.
    """

    symbol: str
    name: str
    exchange: str | None = None
    exchange_short_name: str | None = None
    currency: str | None = None
    security_type: str | None = None
    country: str | None = None


# --------------------------------------------------------------------------- #
# Options
#
# Provider-agnostic public types modelled on the public options reference and
# snapshot shapes: contract ticker, strike price, expiration date, contract
# type, greeks delta/gamma/theta/vega/rho, implied volatility, open interest
# and day volume. Reference field names are kept.
# --------------------------------------------------------------------------- #


class OptionsContract(BaseModel):
    """An options contract reference record.

    Mirrors the options contracts reference endpoint
    (``/v3/reference/options/contracts/``): ``contract_ticker``,
    ``underlying_ticker`` (exposed as ``symbol``), ``strike_price``,
    ``expiration_date``, ``contract_type`` (``call`` / ``put``),
    ``shares_per_contract``, ``primary_exchange``, ``active``.
    """

    contract_ticker: str
    symbol: str
    strike_price: Decimal
    expiration_date: date
    contract_type: Literal["call", "put"]
    shares_per_contract: int = 100
    primary_exchange: str | None = None
    active: bool = True


class OptionsGreeks(BaseModel):
    """Option greeks from a snapshot.

    Mirrors the ``greeks`` object of the options snapshot endpoint:
    ``delta``, ``gamma``, ``theta``, ``vega``, ``rho``.
    """

    delta: Decimal | None = None
    gamma: Decimal | None = None
    theta: Decimal | None = None
    vega: Decimal | None = None
    rho: Decimal | None = None


class OptionsQuote(BaseModel):
    """Market snapshot for a single options contract.

    Mirrors the options snapshot endpoint (``/v3/snapshot/options/``):
    ``implied_volatility``, ``open_interest``, ``day_volume``, OHLC day
    fields (``day_open`` / ``day_high`` / ``day_low`` / ``day_close``) and the
    nested ``greeks`` object.
    """

    implied_volatility: Decimal | None = None
    open_interest: Decimal | int | None = None
    day_volume: int | None = None
    day_open: Decimal | None = None
    day_high: Decimal | None = None
    day_low: Decimal | None = None
    day_close: Decimal | None = None
    greeks: OptionsGreeks | None = None


class OptionsChainEntry(BaseModel):
    """A single contract plus its snapshot quote (flat snapshot shape)."""

    contract: OptionsContract
    quote: OptionsQuote


class OptionsChain(BaseModel):
    """Options chain for an underlying symbol.

    Aggregate of the flat snapshot shape: the ``underlying_symbol``, an
    optional ``as_of`` date, and one ``OptionsChainEntry`` per contract.
    """

    underlying_symbol: str
    as_of: date | None = None
    contracts: list[OptionsChainEntry] = []


class OptionExpirations(BaseModel):
    """Available option expiration dates for an underlying symbol."""

    underlying_symbol: str
    expirations: list[date] = []
    truncated: bool = False
