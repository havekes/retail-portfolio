"""FMP-backed market data gateway.

Mirrors the structure of ``src/market/eodhd.py`` but is built on a thin,
injectable ``httpx``-based HTTP client so every outbound call is mockable in
tests (``httpx.MockTransport``) and no test ever dials the network.

Besides prices and symbol mapping (T02), the gateway implements the
fundamentals capabilities declared as optional on ``MarketGateway``: company
profile, income statement, balance sheet, cash-flow statement, key metrics and
financial ratios. Each capability is a direct field translation of the matching
FMP endpoint response, tolerating missing or extra fields.

Error translation is provider-agnostic: upstream not-found becomes
``MarketDataNotFoundError``, credential/quota failures become
``MarketDataConfigurationError`` and transport/status failures become
``MarketDataProviderError``; raw FMP response text is never echoed to callers
(it is logged only).
"""

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from src.config.settings import settings
from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPrice,
    IncomeStatement,
    IntradayHistoricalPrice,
    KeyMetrics,
    SecurityId,
    SecuritySearchResult,
    SymbolLookupResult,
)
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)
from src.market.gateway import MarketGateway

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://financialmodelingprep.com"
DEFAULT_TIMEOUT_SECONDS = 10.0
_INTRADAY_NOT_SUPPORTED = "capability not supported by this provider"

# Internal exchange code -> FMP ticker suffix. FMP appends a market suffix for
# non-US listings (``RY.TO``, ``VOD.L``); US/primary venues use the bare ticker.
# Unknown exchange codes pass the symbol through unchanged, matching the
# pass-through precedent set by ``SecurityApi``.
FMP_EXCHANGE_SUFFIXES: dict[str, str] = {
    "TSX": ".TO",
    "LSE": ".L",
}

# US/primary venues that need no suffix. Kept explicit so the pass-through is a
# documented decision rather than an accident of an empty mapping.
FMP_US_EXCHANGES = frozenset({"NYSE", "NASDAQ", "NYSEARCA", "AMEX"})

_NOT_FOUND_DETAIL = "The upstream provider has no data for this symbol."
_PROVIDER_ERROR_MESSAGE = "The market data provider is unavailable."
_CONFIGURATION_ERROR_MESSAGE = "Market data provider configuration is invalid."

_VALID_PERIODS = frozenset({"annual", "quarter"})

# Case-insensitive substrings of FMP's HTTP-200 ``Error Message`` bodies that
# signal a credential/quota problem rather than a missing symbol. Kept as a
# tuple of plain substrings so future FMP wording variants only need one entry.
_CONFIGURATION_ERROR_TOKENS = (
    "invalid api key",
    "limit rate",
    "limit reach",
    "requests count exceeds",
)


def map_to_fmp_ticker(symbol: str, exchange: str) -> str:
    """Map an internal ``(symbol, exchange)`` pair to an FMP ticker.

    US/primary-venue exchanges (NYSE, NASDAQ, NYSEARCA, AMEX) and unknown
    exchange codes return the bare symbol unchanged. Known non-US exchanges
    append FMP's market suffix (``TSX`` -> ``.TO``, ``LSE`` -> ``.L``).
    """
    clean_symbol = symbol.strip().upper()
    clean_exchange = exchange.strip().upper()
    if clean_exchange in FMP_US_EXCHANGES:
        return clean_symbol
    suffix = FMP_EXCHANGE_SUFFIXES.get(clean_exchange)
    if suffix is None:
        return clean_symbol
    return f"{clean_symbol}{suffix}"


# --------------------------------------------------------------------------- #
# Scalar coercion helpers.
#
# FMP payloads mix strings, numbers and blanks and occasionally omit fields.
# These helpers map missing/blank values to ``None`` and translate unparseable
# values into a provider-agnostic error so raw upstream text never escapes.
# --------------------------------------------------------------------------- #


def _to_decimal(value: object) -> Decimal | None:
    """Coerce an FMP scalar to ``Decimal`` or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc


def _to_date(value: object) -> date | None:
    """Coerce an FMP date (or datetime) scalar to ``date`` or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc


def _to_datetime(value: object) -> datetime | None:
    """Coerce an FMP datetime scalar to ``datetime`` or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc


def _to_int(value: object) -> int | None:
    """Coerce an FMP scalar to ``int`` or ``None`` (tolerates ``"164000.0"``)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError) as exc:
        raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc


def _to_str(value: object) -> str | None:
    """Coerce an FMP scalar to a non-blank ``str`` or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_bool(value: object) -> bool | None:
    """Coerce an FMP scalar to ``bool`` or ``None`` (tolerates ``"true"``)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _pick(row: dict[str, object], *keys: str) -> object:
    """Return the first present, non-``None`` value among ``keys``.

    FMP has shipped both legacy and stable spellings for a handful of fields
    (e.g. ``weightedAverageSharesOutstanding`` / ``weightedAverageShsOut``);
    accepting both keeps the translation a faithful field copy.
    """
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


def _first_dict_row(payload: object) -> dict[str, object] | None:
    """Return the first dict row of a list payload, or ``None``."""
    rows = payload if isinstance(payload, list) else []
    return next((row for row in rows if isinstance(row, dict)), None)


def _validate_period(period: str) -> str:
    """Validate an FMP statement period, raising a provider-agnostic error."""
    if period not in _VALID_PERIODS:
        msg = f"Unsupported period '{period}'. Expected 'annual' or 'quarter'."
        raise ValueError(msg)
    return period


class FmpHttpClient:
    """Thin, sync HTTP wrapper around the FMP API.

    Owns timeouts and status handling so callers (and T03's fundamentals
    methods) can reuse it. A client or transport may be injected so tests can
    drive it with ``httpx.MockTransport``.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)

    def get_json(self, path: str, params: dict[str, str] | None = None) -> object:
        """GET ``path`` with the API key appended and return parsed JSON.

        Raises ``httpx`` exceptions on transport/timeout failures and
        ``httpx.HTTPStatusError`` on non-2xx responses. The gateway translates
        those into provider-agnostic errors.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        request_params = dict(params or {})
        request_params["apikey"] = self.api_key

        response = self._client.get(url, params=request_params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


class FmpGateway(MarketGateway):
    """Market data gateway backed by the FMP HTTP API."""

    _client: FmpHttpClient
    _api_key: str

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | FmpHttpClient | None = None,
    ) -> None:
        self._api_key = api_key
        if isinstance(client, FmpHttpClient):
            self._client = client
            self._api_key = client.api_key
        else:
            self._client = FmpHttpClient(
                api_key=api_key, base_url=base_url, client=client
            )

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> object:
        """GET ``path`` translating transport/status failures to provider errors.

        Raw upstream response text never reaches callers; it is logged only.
        """
        try:
            return self._client.get_json(path, params)
        except httpx.HTTPStatusError as exc:
            logger.exception(
                "FMP request to %s failed with status %s",
                path,
                exc.response.status_code,
            )
            raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.exception("FMP request to %s failed", path)
            raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc

    def _fetch_historical(
        self,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> object:
        """Fetch the raw historical payload, translating upstream failures."""
        ticker = map_to_fmp_ticker(symbol, exchange)
        params = {"from": from_date.isoformat(), "to": to_date.isoformat()}
        return self._get_json(f"api/v3/historical-price-full/{ticker}", params)

    def _raise_for_error_payload(
        self, payload: object, symbol: str, exchange: str
    ) -> None:
        """Translate FMP's HTTP-200 ``Error Message`` bodies.

        FMP quirk: errors arrive as HTTP 200 with an ``Error Message`` body.
        Credential/quota messages become ``MarketDataConfigurationError``;
        every other error payload keeps the historical not-found mapping. The
        raw upstream text is logged only and never echoed to callers.
        """
        if not (isinstance(payload, dict) and "Error Message" in payload):
            return
        raw_message = str(payload.get("Error Message") or "")
        logger.error(
            "FMP returned an error payload for %s.%s: %s",
            symbol,
            exchange,
            raw_message,
        )
        lowered = raw_message.lower()
        if any(token in lowered for token in _CONFIGURATION_ERROR_TOKENS):
            raise MarketDataConfigurationError(_CONFIGURATION_ERROR_MESSAGE)
        error_symbol = f"{symbol}.{exchange}" if exchange else symbol
        raise MarketDataNotFoundError(error_symbol, detail=_NOT_FOUND_DETAIL)

    def _parse_historical(
        self,
        payload: object,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
    ) -> list[HistoricalPrice]:
        """Translate an FMP historical payload into provider-agnostic prices."""
        self._raise_for_error_payload(payload, symbol, exchange)

        rows: object = payload.get("historical") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            error_symbol = f"{symbol}.{exchange}"
            raise MarketDataNotFoundError(error_symbol, detail=_NOT_FOUND_DETAIL)

        prices: list[HistoricalPrice] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                prices.append(
                    HistoricalPrice(
                        security_id=security_id,
                        date=date.fromisoformat(str(row["date"])),
                        open=Decimal(str(row["open"])),
                        high=Decimal(str(row["high"])),
                        low=Decimal(str(row["low"])),
                        close=Decimal(str(row["close"])),
                        adjusted_close=Decimal(str(row["adjClose"])),
                        volume=int(row["volume"]),
                    )
                )
            except (KeyError, ValueError, InvalidOperation, TypeError) as exc:
                logger.exception("Malformed FMP historical row for %s", symbol)
                raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc

        return sorted(prices, key=lambda price: price.date)

    def get_price_on_date(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        date: date,
    ) -> HistoricalPrice | None:
        prices = self._fetch_prices(
            security_id, symbol, exchange, from_date=date, to_date=date
        )
        return prices[0] if prices else None

    def get_prices(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        return self._fetch_prices(
            security_id, symbol, exchange, from_date=from_date, to_date=to_date
        )

    def _fetch_prices(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        payload = self._fetch_historical(symbol, exchange, from_date, to_date)
        return self._parse_historical(payload, security_id, symbol, exchange)

    def search(self, query: str) -> list[SecuritySearchResult]:
        payload = self._get_json("api/v3/symbol-search", {"query": query})
        results = payload if isinstance(payload, list) else []
        return [
            SecuritySearchResult(
                code=result.get("symbol") or "",
                exchange=result.get("exchangeShortName")
                or result.get("exchange")
                or "",
                name=result.get("name") or "",
                currency=result.get("currency") or "",
                security_type=result.get("type") or "",
                isin=result.get("isin"),
                country=result.get("country") or "",
            )
            for result in results
            if isinstance(result, dict)
        ]

    def lookup_symbol(self, query: str) -> list[SymbolLookupResult]:
        """Look up symbols/companies matching a free-text query."""
        payload = self._get_json("api/v3/symbol-search", {"query": query})
        results = payload if isinstance(payload, list) else []
        return [
            SymbolLookupResult(
                symbol=result["symbol"],
                name=result.get("name") or "",
                exchange=result.get("exchange"),
                exchange_short_name=result.get("exchangeShortName"),
                currency=result.get("currency"),
                security_type=result.get("type"),
                country=result.get("country"),
            )
            for result in results
            if isinstance(result, dict)
        ]

    # ------------------------------------------------------------------ #
    # Fundamentals capabilities.
    #
    # Each capability is a ``_fetch_`` / ``_parse_`` pair: the fetch builds the
    # FMP endpoint call (with period/limit params) and the parse translates the
    # payload into the T01 unified types. Profile/key-metrics/ratios return a
    # single object (first row); statements return every row. The gateway
    # contract only carries ``symbol`` for these methods, so tickers are mapped
    # with a neutral exchange (pass-through) as in T02.
    # ------------------------------------------------------------------ #

    def _fetch_company_profile(self, symbol: str) -> object:
        ticker = map_to_fmp_ticker(symbol, "")
        return self._get_json(f"api/v3/profile/{ticker}")

    def _parse_company_profile(self, payload: object, symbol: str) -> CompanyProfile:
        self._raise_for_error_payload(payload, symbol, "")
        row = _first_dict_row(payload)
        if row is None:
            raise MarketDataNotFoundError(symbol, detail=_NOT_FOUND_DETAIL)
        return CompanyProfile(
            symbol=_to_str(row.get("symbol")) or symbol,
            company_name=_to_str(row.get("companyName")) or "",
            market_cap=_to_decimal(row.get("marketCap")),
            sector=_to_str(row.get("sector")),
            industry=_to_str(row.get("industry")),
            beta=_to_decimal(row.get("beta")),
            price=_to_decimal(row.get("price")),
            website=_to_str(row.get("website")),
            description=_to_str(row.get("description")),
            ceo=_to_str(row.get("ceo")),
            full_time_employees=_to_int(row.get("fullTimeEmployees")),
            exchange_short_name=_to_str(row.get("exchangeShortName")),
            exchange=_to_str(row.get("exchange")),
            currency=_to_str(row.get("currency")),
            ipo_date=_to_date(row.get("ipoDate")),
            cik=_to_str(row.get("cik")),
            isin=_to_str(row.get("isin")),
            image=_to_str(row.get("image")),
            is_actively_trading=_to_bool(row.get("isActivelyTrading")),
        )

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        payload = self._fetch_company_profile(symbol)
        return self._parse_company_profile(payload, symbol)

    def _fetch_income_statement(self, symbol: str, period: str, limit: int) -> object:
        ticker = map_to_fmp_ticker(symbol, "")
        params = {"period": period, "limit": str(limit)}
        return self._get_json(f"api/v3/income-statement/{ticker}", params)

    def _parse_income_statement(
        self, payload: object, symbol: str
    ) -> list[IncomeStatement]:
        self._raise_for_error_payload(payload, symbol, "")
        statements: list[IncomeStatement] = []
        for row in payload if isinstance(payload, list) else []:
            if not isinstance(row, dict):
                continue
            row_date = _to_date(row.get("date"))
            if row_date is None:
                continue
            statements.append(
                IncomeStatement(
                    date=row_date,
                    symbol=_to_str(row.get("symbol")) or symbol,
                    reported_currency=_to_str(row.get("reportedCurrency")),
                    cik=_to_str(row.get("cik")),
                    filling_date=_to_date(row.get("fillingDate")),
                    accepted_date=_to_datetime(row.get("acceptedDate")),
                    fiscal_year=_to_str(_pick(row, "fiscalYear", "calendarYear")),
                    period=_to_str(row.get("period")),
                    revenue=_to_decimal(row.get("revenue")),
                    cost_of_revenue=_to_decimal(row.get("costOfRevenue")),
                    gross_profit=_to_decimal(row.get("grossProfit")),
                    research_and_development_expenses=_to_decimal(
                        row.get("researchAndDevelopmentExpenses")
                    ),
                    selling_general_and_administrative_expenses=_to_decimal(
                        row.get("sellingGeneralAndAdministrativeExpenses")
                    ),
                    operating_expenses=_to_decimal(row.get("operatingExpenses")),
                    operating_income=_to_decimal(row.get("operatingIncome")),
                    interest_expense=_to_decimal(row.get("interestExpense")),
                    other_income_expense=_to_decimal(
                        _pick(row, "otherIncomeExpense", "totalOtherIncomeExpensesNet")
                    ),
                    income_tax_expense=_to_decimal(row.get("incomeTaxExpense")),
                    net_income=_to_decimal(row.get("netIncome")),
                    eps=_to_decimal(row.get("eps")),
                    eps_diluted=_to_decimal(row.get("epsDiluted")),
                    weighted_average_shares_outstanding=_to_decimal(
                        _pick(
                            row,
                            "weightedAverageSharesOutstanding",
                            "weightedAverageShsOut",
                        )
                    ),
                    weighted_average_shares_outstanding_diluted=_to_decimal(
                        _pick(
                            row,
                            "weightedAverageSharesOutstandingDiluted",
                            "weightedAverageShsOutDil",
                        )
                    ),
                )
            )
        if not statements:
            raise MarketDataNotFoundError(symbol, detail=_NOT_FOUND_DETAIL)
        return statements

    def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[IncomeStatement]:
        validated_period = _validate_period(period)
        payload = self._fetch_income_statement(symbol, validated_period, limit)
        return self._parse_income_statement(payload, symbol)

    def _fetch_balance_sheet(self, symbol: str, period: str, limit: int) -> object:
        ticker = map_to_fmp_ticker(symbol, "")
        params = {"period": period, "limit": str(limit)}
        return self._get_json(f"api/v3/balance-sheet-statement/{ticker}", params)

    def _parse_balance_sheet(self, payload: object, symbol: str) -> list[BalanceSheet]:
        self._raise_for_error_payload(payload, symbol, "")
        sheets: list[BalanceSheet] = []
        for row in payload if isinstance(payload, list) else []:
            if not isinstance(row, dict):
                continue
            row_date = _to_date(row.get("date"))
            if row_date is None:
                continue
            sheets.append(
                BalanceSheet(
                    date=row_date,
                    symbol=_to_str(row.get("symbol")) or symbol,
                    reported_currency=_to_str(row.get("reportedCurrency")),
                    cik=_to_str(row.get("cik")),
                    fiscal_year=_to_str(_pick(row, "fiscalYear", "calendarYear")),
                    period=_to_str(row.get("period")),
                    total_assets=_to_decimal(row.get("totalAssets")),
                    current_assets=_to_decimal(
                        _pick(row, "currentAssets", "totalCurrentAssets")
                    ),
                    total_liabilities=_to_decimal(row.get("totalLiabilities")),
                    current_liabilities=_to_decimal(
                        _pick(row, "currentLiabilities", "totalCurrentLiabilities")
                    ),
                    total_debt=_to_decimal(row.get("totalDebt")),
                    cash_and_cash_equivalents=_to_decimal(
                        row.get("cashAndCashEquivalents")
                    ),
                    inventory=_to_decimal(row.get("inventory")),
                    receivables=_to_decimal(
                        _pick(row, "receivables", "netReceivables")
                    ),
                    payables=_to_decimal(_pick(row, "payables", "accountPayables")),
                    goodwill=_to_decimal(row.get("goodwill")),
                    retained_earnings=_to_decimal(row.get("retainedEarnings")),
                    total_equity=_to_decimal(
                        _pick(row, "totalEquity", "totalStockholdersEquity")
                    ),
                    common_stock=_to_decimal(row.get("commonStock")),
                    net_debt=_to_decimal(row.get("netDebt")),
                )
            )
        if not sheets:
            raise MarketDataNotFoundError(symbol, detail=_NOT_FOUND_DETAIL)
        return sheets

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[BalanceSheet]:
        validated_period = _validate_period(period)
        payload = self._fetch_balance_sheet(symbol, validated_period, limit)
        return self._parse_balance_sheet(payload, symbol)

    def _fetch_cash_flow_statement(
        self, symbol: str, period: str, limit: int
    ) -> object:
        ticker = map_to_fmp_ticker(symbol, "")
        params = {"period": period, "limit": str(limit)}
        return self._get_json(f"api/v3/cash-flow-statement/{ticker}", params)

    def _parse_cash_flow_statement(
        self, payload: object, symbol: str
    ) -> list[CashFlowStatement]:
        self._raise_for_error_payload(payload, symbol, "")
        statements: list[CashFlowStatement] = []
        for row in payload if isinstance(payload, list) else []:
            if not isinstance(row, dict):
                continue
            row_date = _to_date(row.get("date"))
            if row_date is None:
                continue
            statements.append(
                CashFlowStatement(
                    date=row_date,
                    symbol=_to_str(row.get("symbol")) or symbol,
                    reported_currency=_to_str(row.get("reportedCurrency")),
                    cik=_to_str(row.get("cik")),
                    fiscal_year=_to_str(_pick(row, "fiscalYear", "calendarYear")),
                    period=_to_str(row.get("period")),
                    net_income=_to_decimal(row.get("netIncome")),
                    operating_cash_flow=_to_decimal(
                        _pick(
                            row,
                            "operatingCashFlow",
                            "netCashProvidedByOperatingActivities",
                        )
                    ),
                    investing_cash_flow=_to_decimal(
                        _pick(
                            row,
                            "investingCashFlow",
                            "netCashUsedForInvestingActivites",
                            "netCashUsedForInvestingActivities",
                        )
                    ),
                    financing_cash_flow=_to_decimal(
                        _pick(
                            row,
                            "financingCashFlow",
                            "netCashUsedProvidedByFinancingActivities",
                        )
                    ),
                    capital_expenditure=_to_decimal(row.get("capitalExpenditure")),
                    free_cash_flow=_to_decimal(row.get("freeCashFlow")),
                    dividends_paid=_to_decimal(row.get("dividendsPaid")),
                    stock_based_compensation=_to_decimal(
                        row.get("stockBasedCompensation")
                    ),
                    cash_change=_to_decimal(
                        _pick(row, "cashChange", "netChangeInCash")
                    ),
                )
            )
        if not statements:
            raise MarketDataNotFoundError(symbol, detail=_NOT_FOUND_DETAIL)
        return statements

    def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[CashFlowStatement]:
        validated_period = _validate_period(period)
        payload = self._fetch_cash_flow_statement(symbol, validated_period, limit)
        return self._parse_cash_flow_statement(payload, symbol)

    def _fetch_key_metrics(self, symbol: str) -> object:
        ticker = map_to_fmp_ticker(symbol, "")
        return self._get_json(f"api/v3/key-metrics/{ticker}")

    def _parse_key_metrics(self, payload: object, symbol: str) -> KeyMetrics:
        self._raise_for_error_payload(payload, symbol, "")
        row = _first_dict_row(payload)
        row_date = _to_date(row.get("date")) if row is not None else None
        if row is None or row_date is None:
            raise MarketDataNotFoundError(symbol, detail=_NOT_FOUND_DETAIL)
        return KeyMetrics(
            symbol=_to_str(row.get("symbol")) or symbol,
            date=row_date,
            fiscal_year=_to_str(_pick(row, "fiscalYear", "calendarYear")),
            period=_to_str(row.get("period")),
            market_cap=_to_decimal(row.get("marketCap")),
            enterprise_value=_to_decimal(row.get("enterpriseValue")),
            pe_ratio=_to_decimal(row.get("peRatio")),
            peg_ratio=_to_decimal(row.get("pegRatio")),
            price_to_sales_ratio=_to_decimal(row.get("priceToSalesRatio")),
            price_to_book_ratio=_to_decimal(row.get("priceToBookRatio")),
            enterprise_value_over_ebitda=_to_decimal(
                row.get("enterpriseValueOverEBITDA")
            ),
            ev_to_sales=_to_decimal(row.get("evToSales")),
            dividend_yield=_to_decimal(row.get("dividendYield")),
            payout_ratio=_to_decimal(row.get("payoutRatio")),
            current_ratio=_to_decimal(row.get("currentRatio")),
            quick_ratio=_to_decimal(row.get("quickRatio")),
            debt_to_equity=_to_decimal(_pick(row, "debtToEquity", "debtEquityRatio")),
            working_capital=_to_decimal(row.get("workingCapital")),
        )

    def get_key_metrics(self, symbol: str) -> KeyMetrics:
        payload = self._fetch_key_metrics(symbol)
        return self._parse_key_metrics(payload, symbol)

    def _fetch_financial_ratios(self, symbol: str, period: str) -> object:
        ticker = map_to_fmp_ticker(symbol, "")
        return self._get_json(f"api/v3/ratios/{ticker}", {"period": period})

    def _parse_financial_ratios(self, payload: object, symbol: str) -> FinancialRatios:
        self._raise_for_error_payload(payload, symbol, "")
        row = _first_dict_row(payload)
        row_date = _to_date(row.get("date")) if row is not None else None
        if row is None or row_date is None:
            raise MarketDataNotFoundError(symbol, detail=_NOT_FOUND_DETAIL)
        return FinancialRatios(
            symbol=_to_str(row.get("symbol")) or symbol,
            date=row_date,
            fiscal_year=_to_str(_pick(row, "fiscalYear", "calendarYear")),
            period=_to_str(row.get("period")),
            gross_profit_margin=_to_decimal(row.get("grossProfitMargin")),
            operating_profit_margin=_to_decimal(row.get("operatingProfitMargin")),
            net_profit_margin=_to_decimal(row.get("netProfitMargin")),
            return_on_assets=_to_decimal(row.get("returnOnAssets")),
            return_on_equity=_to_decimal(row.get("returnOnEquity")),
            return_on_capital_employed=_to_decimal(row.get("returnOnCapitalEmployed")),
            interest_coverage=_to_decimal(row.get("interestCoverage")),
            quick_ratio=_to_decimal(row.get("quickRatio")),
            current_ratio=_to_decimal(row.get("currentRatio")),
            debt_to_equity=_to_decimal(_pick(row, "debtToEquity", "debtEquityRatio")),
            price_earnings_ratio=_to_decimal(row.get("priceEarningsRatio")),
            book_value_per_share=_to_decimal(row.get("bookValuePerShare")),
            dividend_yield=_to_decimal(row.get("dividendYield")),
        )

    def get_financial_ratios(
        self,
        symbol: str,
        period: str = "annual",
    ) -> FinancialRatios:
        validated_period = _validate_period(period)
        payload = self._fetch_financial_ratios(symbol, validated_period)
        return self._parse_financial_ratios(payload, symbol)

    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
    ) -> list[IntradayHistoricalPrice]:
        # Intraday reads are not part of this ticket; the price-alert path uses
        # EODHD. Kept concrete so the gateway satisfies the ABC, raising the
        # same provider-agnostic capability error as the ABC defaults.
        _ = security_id, symbol, exchange, from_datetime, to_datetime, interval
        raise MarketDataProviderError(_INTRADAY_NOT_SUPPORTED)


def fmp_gateway_factory() -> MarketGateway:
    if settings.stub_external_api:
        from src.stubs.fmp import StubFmpGateway  # noqa: PLC0415

        return StubFmpGateway(api_key=settings.fmp_api_key)
    return FmpGateway(api_key=settings.fmp_api_key)
