from datetime import date, datetime
from decimal import Decimal
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict
from stockholm.currency import Currency

type SecurityId = UUID
type WatchlistId = UUID


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
    security_id: SecurityId
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal
    volume: int


class IntradayHistoricalPrice(BaseModel):
    id: int | None = None
    security_id: SecurityId
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
# Provider-agnostic public types. Field names and structure mirror the public
# fundamentals reference responses (profile, income statement, balance sheet,
# cash-flow statement, key metrics, ratios) so provider mapping is a direct
# field translation. Field names are snake_case renderings of the reference
# JSON keys; each class docstring records the endpoint and the source keys it
# is modelled on. Money-like values use ``Decimal``.
# --------------------------------------------------------------------------- #


class CompanyProfile(BaseModel):
    """Company profile / details.

    Mirrors the ``/profile-v3/`` endpoint (``/profile/`` on the stable API):
    ``symbol``, ``companyName``, ``marketCap``, ``sector``, ``industry``,
    ``beta``, ``price``, ``website``, ``description``, ``ceo``,
    ``fullTimeEmployees``, ``exchangeShortName``, ``exchange``, ``currency``,
    ``ipoDate``, ``cik``, ``isin``, ``image``, ``isActivelyTrading``.
    """

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
    """Income statement for a reporting period.

    Mirrors the ``/income-statement/`` endpoint: ``date``, ``symbol``,
    ``reportedCurrency``, ``cik``, ``fillingDate``, ``acceptedDate``,
    ``fiscalYear``, ``period``, ``revenue``, ``costOfRevenue``,
    ``grossProfit``, ``researchAndDevelopmentExpenses``,
    ``sellingGeneralAndAdministrativeExpenses``, ``operatingExpenses``,
    ``operatingIncome``, ``interestExpense``, ``otherIncomeExpense``,
    ``incomeTaxExpense``, ``netIncome``, ``eps``, ``epsDiluted``,
    ``weightedAverageSharesOutstanding``,
    ``weightedAverageSharesOutstandingDiluted``.
    """

    date: date
    symbol: str
    reported_currency: str | None = None
    cik: str | None = None
    filling_date: date | None = None
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
    """Balance sheet for a reporting period.

    Mirrors the ``/balance-sheet-statement/`` endpoint. Header fields
    (``date``, ``symbol``, ``reportedCurrency``, ``cik``, ``fiscalYear``,
    ``period``) plus ``totalAssets``, ``currentAssets``, ``totalLiabilities``,
    ``currentLiabilities``, ``totalDebt``, ``cashAndCashEquivalents``,
    ``inventory``, ``receivables``, ``payables``, ``goodwill``,
    ``retainedEarnings``, ``totalEquity``, ``commonStock``, ``netDebt``.
    """

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
    """Cash-flow statement for a reporting period.

    Mirrors the ``/cash-flow-statement/`` endpoint. Header fields
    (``date``, ``symbol``, ``reportedCurrency``, ``cik``, ``fiscalYear``,
    ``period``) plus ``netIncome``, ``operatingCashFlow``,
    ``investingCashFlow``, ``financingCashFlow``, ``capitalExpenditure``,
    ``freeCashFlow``, ``dividendsPaid``, ``stockBasedCompensation``,
    ``cashChange``.
    """

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
    """Key metrics / valuation snapshot for a symbol.

    Mirrors the ``/key-metrics/`` endpoint. Header fields (``date``,
    ``symbol``, ``fiscalYear``, ``period``) plus ``marketCap``,
    ``enterpriseValue``, ``peRatio``, ``pegRatio``, ``priceToSalesRatio``,
    ``priceToBookRatio``, ``enterpriseValueOverEBITDA``, ``evToSales``,
    ``dividendYield``, ``payoutRatio``, ``currentRatio``, ``quickRatio``,
    ``debtToEquity``, ``workingCapital``.
    """

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
    """Financial ratios for a symbol / period.

    Mirrors the ``/ratios/`` endpoint (``/ratios/:period=v3/``). Header fields
    (``date``, ``symbol``, ``fiscalYear``, ``period``) plus
    ``grossProfitMargin``, ``operatingProfitMargin``, ``netProfitMargin``,
    ``returnOnAssets``, ``returnOnEquity``, ``returnOnCapitalEmployed``,
    ``interestCoverage``, ``quickRatio``, ``currentRatio``, ``debtToEquity``,
    ``priceEarningsRatio``, ``bookValuePerShare``, ``dividendYield``.
    """

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
    """Company details plus the key metrics and ratios overview.

    Aggregate returned by ``GET /api/v1/market/data/fundamentals/{symbol}``
    (the T10 MCP contract): the T01 FMP-shaped ``profile``, ``key_metrics`` and
    ``ratios`` objects, each field-for-field. Kept required (not optional) so a
    response always carries the full overview.
    """

    profile: CompanyProfile
    key_metrics: KeyMetrics
    ratios: FinancialRatios


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
