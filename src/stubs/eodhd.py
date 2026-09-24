"""EODHD API stubs for testing and local development."""

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

import pandas as pd

from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    EodhdSearchResult,
    FinancialRatios,
    HistoricalPrice,
    IncomeStatement,
    IntradayHistoricalPrice,
    KeyMetrics,
    OptionsChain,
    OptionsChainEntry,
    OptionsContract,
    OptionsQuote,
    SecuritySearchResult,
    SymbolLookupResult,
)
from src.market.exception import MarketDataNotFoundError, MarketDataProviderError
from src.market.gateway import MarketGateway
from src.market.schema import SecuritySchema
from src.stubs.market_fixtures import (
    KNOWN_SYMBOLS,
    OPTIONS_CHAINS,
    STUB_AS_OF_DATE,
)

MAX_INTRADAY_STEPS = 10000
MARKET_CLOSE_HOUR = 16

# --------------------------------------------------------------------------- #
# Deterministic fundamentals fixtures for the stub gateway.
#
# Payloads are offline, static dicts shaped like the reference provider
# responses so the stub mirrors the public contract exactly. Only the
# fundamentals capabilities use these; prices/search remain generated. The
# shared options-chain fixtures live in ``src.stubs.market_fixtures``.
# --------------------------------------------------------------------------- #

_SYMBOL_LOOKUPS: dict[str, dict[str, Any]] = {
    "AAPL": {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ Global Select",
        "exchange_short_name": "NASDAQ",
        "currency": "USD",
        "security_type": "Common Stock",
        "country": "US",
    },
    "MSFT": {
        "symbol": "MSFT",
        "name": "Microsoft Corporation",
        "exchange": "NASDAQ Global Select",
        "exchange_short_name": "NASDAQ",
        "currency": "USD",
        "security_type": "Common Stock",
        "country": "US",
    },
    "RY": {
        "symbol": "RY",
        "name": "Royal Bank of Canada",
        "exchange": "Toronto Stock Exchange",
        "exchange_short_name": "TSX",
        "currency": "CAD",
        "security_type": "Common Stock",
        "country": "CA",
    },
    "TD": {
        "symbol": "TD",
        "name": "Toronto-Dominion Bank",
        "exchange": "Toronto Stock Exchange",
        "exchange_short_name": "TSX",
        "currency": "CAD",
        "security_type": "Common Stock",
        "country": "CA",
    },
}

_COMPANY_PROFILES: dict[str, dict[str, Any]] = {
    "AAPL": {
        "symbol": "AAPL",
        "company_name": "Apple Inc.",
        "market_cap": "3400000000000",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "beta": "1.24",
        "price": "229.87",
        "website": "https://www.apple.com",
        "description": (
            "Apple Inc. designs, manufactures, and markets smartphones, "
            "personal computers, tablets, wearables, and accessories."
        ),
        "ceo": "Tim Cook",
        "full_time_employees": 164000,
        "exchange_short_name": "NASDAQ",
        "exchange": "NASDAQ Global Select",
        "currency": "USD",
        "ipo_date": "1980-12-12",
        "cik": "0000320193",
        "isin": "US0378331005",
        "image": "https://images.example.com/AAPL.png",
        "is_actively_trading": True,
    },
    "MSFT": {
        "symbol": "MSFT",
        "company_name": "Microsoft Corporation",
        "market_cap": "3100000000000",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "beta": "0.91",
        "price": "417.11",
        "website": "https://www.microsoft.com",
        "description": (
            "Microsoft Corporation develops and licenses software, services, "
            "devices, and solutions worldwide."
        ),
        "ceo": "Satya Nadella",
        "full_time_employees": 228000,
        "exchange_short_name": "NASDAQ",
        "exchange": "NASDAQ Global Select",
        "currency": "USD",
        "ipo_date": "1986-03-13",
        "cik": "0000789019",
        "isin": "US5949181045",
        "image": "https://images.example.com/MSFT.png",
        "is_actively_trading": True,
    },
}

_INCOME_STATEMENTS: dict[str, list[dict[str, Any]]] = {
    "AAPL": [
        {
            "date": "2024-09-28",
            "symbol": "AAPL",
            "reported_currency": "USD",
            "cik": "0000320193",
            "filling_date": "2024-11-01",
            "accepted_date": "2024-11-01 06:01:36",
            "fiscal_year": "2024",
            "period": "FY",
            "revenue": "391035000000",
            "cost_of_revenue": "210352000000",
            "gross_profit": "180683000000",
            "research_and_development_expenses": "31370000000",
            "selling_general_and_administrative_expenses": "26097000000",
            "operating_expenses": "57467000000",
            "operating_income": "123216000000",
            "interest_expense": "0",
            "other_income_expense": "-12830000000",
            "income_tax_expense": "29749000000",
            "net_income": "93736000000",
            "eps": "6.11",
            "eps_diluted": "6.08",
            "weighted_average_shares_outstanding": "15343783000",
            "weighted_average_shares_outstanding_diluted": "15408095000",
        },
        {
            "date": "2023-09-30",
            "symbol": "AAPL",
            "reported_currency": "USD",
            "cik": "0000320193",
            "filling_date": "2023-11-03",
            "accepted_date": "2023-11-03 06:01:15",
            "fiscal_year": "2023",
            "period": "FY",
            "revenue": "383285000000",
            "cost_of_revenue": "214137000000",
            "gross_profit": "169148000000",
            "research_and_development_expenses": "29915000000",
            "selling_general_and_administrative_expenses": "24932000000",
            "operating_expenses": "54847000000",
            "operating_income": "114301000000",
            "interest_expense": "3933000000",
            "other_income_expense": "-565000000",
            "income_tax_expense": "16741000000",
            "net_income": "96995000000",
            "eps": "6.16",
            "eps_diluted": "6.13",
            "weighted_average_shares_outstanding": "15744231000",
            "weighted_average_shares_outstanding_diluted": "15812547000",
        },
    ],
    "MSFT": [
        {
            "date": "2024-06-30",
            "symbol": "MSFT",
            "reported_currency": "USD",
            "cik": "0000789019",
            "filling_date": "2024-07-30",
            "accepted_date": "2024-07-30 16:06:16",
            "fiscal_year": "2024",
            "period": "FY",
            "revenue": "245122000000",
            "cost_of_revenue": "74114000000",
            "gross_profit": "171008000000",
            "research_and_development_expenses": "29510000000",
            "selling_general_and_administrative_expenses": "30620000000",
            "operating_expenses": "60130000000",
            "operating_income": "109433000000",
            "interest_expense": "2269000000",
            "other_income_expense": "-1568000000",
            "income_tax_expense": "10945000000",
            "net_income": "88136000000",
            "eps": "11.86",
            "eps_diluted": "11.8",
            "weighted_average_shares_outstanding": "7440000000",
            "weighted_average_shares_outstanding_diluted": "7469000000",
        },
        {
            "date": "2023-06-30",
            "symbol": "MSFT",
            "reported_currency": "USD",
            "cik": "0000789019",
            "filling_date": "2023-07-27",
            "accepted_date": "2023-07-27 16:04:57",
            "fiscal_year": "2023",
            "period": "FY",
            "revenue": "211915000000",
            "cost_of_revenue": "65863000000",
            "gross_profit": "146052000000",
            "research_and_development_expenses": "27195000000",
            "selling_general_and_administrative_expenses": "29641000000",
            "operating_expenses": "56836000000",
            "operating_income": "88523000000",
            "interest_expense": "1968000000",
            "other_income_expense": "288000000",
            "income_tax_expense": "16950000000",
            "net_income": "72361000000",
            "eps": "9.72",
            "eps_diluted": "9.68",
            "weighted_average_shares_outstanding": "7447000000",
            "weighted_average_shares_outstanding_diluted": "7472000000",
        },
    ],
}

_BALANCE_SHEETS: dict[str, list[dict[str, Any]]] = {
    "AAPL": [
        {
            "date": "2024-09-28",
            "symbol": "AAPL",
            "reported_currency": "USD",
            "cik": "0000320193",
            "fiscal_year": "2024",
            "period": "FY",
            "total_assets": "364980000000",
            "current_assets": "152987000000",
            "total_liabilities": "308030000000",
            "current_liabilities": "176392000000",
            "total_debt": "106629000000",
            "cash_and_cash_equivalents": "29943000000",
            "inventory": "7286000000",
            "receivables": "33410000000",
            "payables": "68960000000",
            "goodwill": "0",
            "retained_earnings": "-19154000000",
            "total_equity": "56950000000",
            "common_stock": "83276000000",
            "net_debt": "76686000000",
        },
        {
            "date": "2023-09-30",
            "symbol": "AAPL",
            "reported_currency": "USD",
            "cik": "0000320193",
            "fiscal_year": "2023",
            "period": "FY",
            "total_assets": "352583000000",
            "current_assets": "143566000000",
            "total_liabilities": "290437000000",
            "current_liabilities": "145308000000",
            "total_debt": "111088000000",
            "cash_and_cash_equivalents": "29965000000",
            "inventory": "6331000000",
            "receivables": "29508000000",
            "payables": "62611000000",
            "goodwill": "0",
            "retained_earnings": "-2144000000",
            "total_equity": "62146000000",
            "common_stock": "73812000000",
            "net_debt": "81123000000",
        },
    ],
    "MSFT": [
        {
            "date": "2024-06-30",
            "symbol": "MSFT",
            "reported_currency": "USD",
            "cik": "0000789019",
            "fiscal_year": "2024",
            "period": "FY",
            "total_assets": "512163000000",
            "current_assets": "159734000000",
            "total_liabilities": "243686000000",
            "current_liabilities": "125286000000",
            "total_debt": "97383000000",
            "cash_and_cash_equivalents": "18315000000",
            "inventory": "1246000000",
            "receivables": "56924000000",
            "payables": "21996000000",
            "goodwill": "119220000000",
            "retained_earnings": "173140000000",
            "total_equity": "268477000000",
            "common_stock": "100923000000",
            "net_debt": "79068000000",
        },
        {
            "date": "2023-06-30",
            "symbol": "MSFT",
            "reported_currency": "USD",
            "cik": "0000789019",
            "fiscal_year": "2023",
            "period": "FY",
            "total_assets": "411976000000",
            "current_assets": "184257000000",
            "total_liabilities": "205753000000",
            "current_liabilities": "104149000000",
            "total_debt": "84983000000",
            "cash_and_cash_equivalents": "34704000000",
            "inventory": "2500000000",
            "receivables": "48688000000",
            "payables": "18095000000",
            "goodwill": "67886000000",
            "retained_earnings": "118848000000",
            "total_equity": "206223000000",
            "common_stock": "93718000000",
            "net_debt": "50279000000",
        },
    ],
}

_CASH_FLOW_STATEMENTS: dict[str, list[dict[str, Any]]] = {
    "AAPL": [
        {
            "date": "2024-09-28",
            "symbol": "AAPL",
            "reported_currency": "USD",
            "cik": "0000320193",
            "fiscal_year": "2024",
            "period": "FY",
            "net_income": "93736000000",
            "operating_cash_flow": "118254000000",
            "investing_cash_flow": "2935000000",
            "financing_cash_flow": "-121983000000",
            "capital_expenditure": "-9447000000",
            "free_cash_flow": "108807000000",
            "dividends_paid": "-15234000000",
            "stock_based_compensation": "11688000000",
            "cash_change": "-7943000000",
        },
        {
            "date": "2023-09-30",
            "symbol": "AAPL",
            "reported_currency": "USD",
            "cik": "0000320193",
            "fiscal_year": "2023",
            "period": "FY",
            "net_income": "96995000000",
            "operating_cash_flow": "110543000000",
            "investing_cash_flow": "3705000000",
            "financing_cash_flow": "-108488000000",
            "capital_expenditure": "-10959000000",
            "free_cash_flow": "99584000000",
            "dividends_paid": "-15025000000",
            "stock_based_compensation": "10833000000",
            "cash_change": "5760000000",
        },
    ],
    "MSFT": [
        {
            "date": "2024-06-30",
            "symbol": "MSFT",
            "reported_currency": "USD",
            "cik": "0000789019",
            "fiscal_year": "2024",
            "period": "FY",
            "net_income": "88136000000",
            "operating_cash_flow": "118548000000",
            "investing_cash_flow": "-97415000000",
            "financing_cash_flow": "-37706000000",
            "capital_expenditure": "-44477000000",
            "free_cash_flow": "74071000000",
            "dividends_paid": "-21771000000",
            "stock_based_compensation": "10755000000",
            "cash_change": "-16573000000",
        },
        {
            "date": "2023-06-30",
            "symbol": "MSFT",
            "reported_currency": "USD",
            "cik": "0000789019",
            "fiscal_year": "2023",
            "period": "FY",
            "net_income": "72361000000",
            "operating_cash_flow": "87582000000",
            "investing_cash_flow": "-22680000000",
            "financing_cash_flow": "-43939000000",
            "capital_expenditure": "-28107000000",
            "free_cash_flow": "59475000000",
            "dividends_paid": "-19800000000",
            "stock_based_compensation": "9611000000",
            "cash_change": "20963000000",
        },
    ],
}

_KEY_METRICS: dict[str, dict[str, Any]] = {
    "AAPL": {
        "symbol": "AAPL",
        "date": "2024-09-28",
        "fiscal_year": "2024",
        "period": "FY",
        "market_cap": "3400000000000",
        "enterprise_value": "3476686000000",
        "pe_ratio": "36.28",
        "peg_ratio": "2.11",
        "price_to_sales_ratio": "8.69",
        "price_to_book_ratio": "59.71",
        "enterprise_value_over_ebitda": "25.14",
        "ev_to_sales": "8.89",
        "dividend_yield": "0.0044",
        "payout_ratio": "0.16",
        "current_ratio": "0.87",
        "quick_ratio": "0.83",
        "debt_to_equity": "1.87",
        "working_capital": "-23405000000",
    },
    "MSFT": {
        "symbol": "MSFT",
        "date": "2024-06-30",
        "fiscal_year": "2024",
        "period": "FY",
        "market_cap": "3100000000000",
        "enterprise_value": "3179068000000",
        "pe_ratio": "35.18",
        "peg_ratio": "2.31",
        "price_to_sales_ratio": "12.65",
        "price_to_book_ratio": "11.55",
        "enterprise_value_over_ebitda": "23.48",
        "ev_to_sales": "12.97",
        "dividend_yield": "0.0072",
        "payout_ratio": "0.25",
        "current_ratio": "1.27",
        "quick_ratio": "1.26",
        "debt_to_equity": "0.36",
        "working_capital": "34448000000",
    },
}

_FINANCIAL_RATIOS: dict[str, dict[str, Any]] = {
    "AAPL": {
        "symbol": "AAPL",
        "date": "2024-09-28",
        "fiscal_year": "2024",
        "period": "FY",
        "gross_profit_margin": "0.4621",
        "operating_profit_margin": "0.3151",
        "net_profit_margin": "0.2397",
        "return_on_assets": "0.2568",
        "return_on_equity": "1.6466",
        "return_on_capital_employed": "0.5708",
        "interest_coverage": "0.0",
        "quick_ratio": "0.8261",
        "current_ratio": "0.8673",
        "debt_to_equity": "1.8727",
        "price_earnings_ratio": "36.28",
        "book_value_per_share": "3.85",
        "dividend_yield": "0.0044",
    },
    "MSFT": {
        "symbol": "MSFT",
        "date": "2024-06-30",
        "fiscal_year": "2024",
        "period": "FY",
        "gross_profit_margin": "0.6976",
        "operating_profit_margin": "0.4464",
        "net_profit_margin": "0.3596",
        "return_on_assets": "0.1720",
        "return_on_equity": "0.3283",
        "return_on_capital_employed": "0.2876",
        "interest_coverage": "48.23",
        "quick_ratio": "1.2567",
        "current_ratio": "1.2749",
        "debt_to_equity": "0.3628",
        "price_earnings_ratio": "35.18",
        "book_value_per_share": "36.12",
        "dividend_yield": "0.0072",
    },
}


class StubEodhdAPIClient:
    """Stub implementation of eodhd.APIClient."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def get_historical_data(
        self,
        symbol: str,
        interval: str = "d",
        iso8601_start: str = "",
        iso8601_end: str = "",
        results: int = 300,
    ) -> pd.DataFrame:
        """Get historical price data for a symbol."""
        _ = interval, results  # Unused in stub mode
        start_date = date.fromisoformat(iso8601_start)
        end_date = date.fromisoformat(iso8601_end)

        price_data = self._generate_price_data(symbol, start_date, end_date)

        return pd.DataFrame(price_data)

    def _generate_price_data(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Generate realistic price data for a symbol."""
        random.seed(hash(symbol) % 2**32)

        base_prices = {
            "US:AAPL": 175.0,
            "US:MSFT": 380.0,
            "US:NFLX": 450.0,
            "TO:RY": 120.0,
            "TO:XYR": 120.50,
            "TO:RYT": 95.0,
            "US:GOOGL": 140.0,
            "US:TSLA": 200.0,
            "US:AMZN": 180.0,
            "TO:TD": 85.0,
        }

        base_price = base_prices.get(symbol, 100.0)
        days = (end_date - start_date).days + 1

        # Pre-seed for deterministic but varied-looking data
        prices = []
        current_price = base_price

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            # Use deterministic pseudo-randomness based on index for speed
            # but still allow some "movement"
            change = (hash(f"{symbol}-{i}") % 100 - 50) / 2500.0  # +/- 2%
            current_price *= 1 + change

            prices.append(
                {
                    "date": current_date.isoformat(),
                    "open": round(current_price * 0.995, 2),
                    "high": round(current_price * 1.01, 2),
                    "low": round(current_price * 0.99, 2),
                    "close": round(current_price, 2),
                    "adjusted_close": round(current_price, 2),
                    "volume": 1000000 + (hash(f"{symbol}-{i}") % 1000000),
                }
            )

        return prices

    def get_intraday_historical_data(
        self,
        symbol: str,
        interval: str = "1h",
        from_unix_time: int | str | None = None,
        to_unix_time: int | str | None = None,
    ) -> list[dict[str, Any]]:
        """Get intraday 1-hour resolution price data for a symbol."""
        _ = interval
        if from_unix_time is not None:
            start_ts = int(from_unix_time)
            start_dt = datetime.fromtimestamp(start_ts, tz=UTC)
        else:
            start_dt = datetime.now(tz=UTC) - timedelta(days=7)

        if to_unix_time is not None:
            end_ts = int(to_unix_time)
            end_dt = datetime.fromtimestamp(end_ts, tz=UTC)
        else:
            end_dt = datetime.now(tz=UTC)

        return self._generate_intraday_price_data(symbol, start_dt, end_dt)

    def _generate_intraday_price_data(
        self, symbol: str, start_dt: datetime, end_dt: datetime
    ) -> list[dict[str, Any]]:
        """Generate realistic 1-hour intraday candle data for a symbol."""
        base_prices = {
            "US:AAPL": 175.0,
            "AAPL.US": 175.0,
            "US:MSFT": 380.0,
            "MSFT.US": 380.0,
            "US:NFLX": 450.0,
            "TO:RY": 120.0,
            "RY.TSX": 120.0,
            "TO:XYR": 120.50,
            "TO:RYT": 95.0,
            "US:GOOGL": 140.0,
            "US:TSLA": 200.0,
            "US:AMZN": 180.0,
            "TO:TD": 85.0,
        }
        base_price = base_prices.get(symbol, 100.0)

        current_dt = start_dt.replace(minute=0, second=0, microsecond=0)
        prices = []
        current_price = base_price

        step_count = 0
        while current_dt <= end_dt:
            ts = int(current_dt.timestamp())
            change = (hash(f"{symbol}-{ts}") % 100 - 50) / 2500.0
            current_price *= 1 + change

            if current_dt.hour == MARKET_CLOSE_HOUR:
                prices.append(
                    {
                        "timestamp": ts,
                        "gmtoffset": 0,
                        "datetime": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": round(current_price, 2),
                        "high": round(current_price, 2),
                        "low": round(current_price, 2),
                        "close": round(current_price, 2),
                        "volume": 0,
                    }
                )
            else:
                prices.append(
                    {
                        "timestamp": ts,
                        "gmtoffset": 0,
                        "datetime": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": round(current_price * 0.998, 2),
                        "high": round(current_price * 1.005, 2),
                        "low": round(current_price * 0.995, 2),
                        "close": round(current_price, 2),
                        "volume": 10000 + (hash(f"{symbol}-{ts}") % 50000),
                    }
                )
            current_dt += timedelta(hours=1)
            step_count += 1
            if step_count > MAX_INTRADAY_STEPS:
                break

        return prices


class StubEodhdGateway(MarketGateway):
    """Stub EODHD gateway for testing.

    Prices and search are generated deterministically; the fundamentals and
    options capabilities return static, offline fixtures for a small set of
    known symbols (AAPL, MSFT). Unknown symbols raise
    ``MarketDataNotFoundError`` and symbols listed in ``fail_on_symbols``
    raise ``MarketDataProviderError``.
    """

    _client: StubEodhdAPIClient
    _api_key: str
    _unknown_symbols: frozenset[str]
    _fail_on_symbols: frozenset[str]

    def __init__(
        self,
        api_key: str,
        *,
        unknown_symbols: set[str] | None = None,
        fail_on_symbols: set[str] | None = None,
    ) -> None:
        self._api_key = api_key
        self._client = StubEodhdAPIClient(api_key)
        self._unknown_symbols = frozenset(
            symbol.upper() for symbol in (unknown_symbols or ())
        )
        self._fail_on_symbols = frozenset(
            symbol.upper() for symbol in (fail_on_symbols or ())
        )

    def _resolve_symbol(self, symbol: str) -> str:
        """Normalize a symbol and enforce the stub's failure/not-found paths."""
        normalized = symbol.strip().upper()
        if normalized in self._fail_on_symbols:
            msg = f"Market data provider failure for symbol '{normalized}'."
            raise MarketDataProviderError(msg)
        if normalized in self._unknown_symbols or normalized not in KNOWN_SYMBOLS:
            raise MarketDataNotFoundError(normalized)
        return normalized

    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search for securities."""
        clean_query = query.strip()
        known = [
            SecuritySearchResult(
                code="AAPL",
                exchange="NASDAQ",
                name="Apple Inc.",
                currency="USD",
                security_type="Common Stock",
                isin="US0378331005",
                country="US",
            ),
            SecuritySearchResult(
                code="MSFT",
                exchange="NASDAQ",
                name="Microsoft Corporation",
                currency="USD",
                security_type="Common Stock",
                isin="US5949181045",
                country="US",
            ),
            SecuritySearchResult(
                code="RY",
                exchange="TSX",
                name="Royal Bank of Canada",
                currency="CAD",
                security_type="Common Stock",
                isin="CA7800625089",
                country="CA",
            ),
            SecuritySearchResult(
                code="TD",
                exchange="TSX",
                name="Toronto-Dominion Bank",
                currency="CAD",
                security_type="Common Stock",
                isin="CA8911605092",
                country="CA",
            ),
        ]

        if not clean_query:
            return known

        query_upper = clean_query.upper()
        if "." in query_upper:
            symbol_part, exchange_part = query_upper.split(".", 1)
        elif ":" in query_upper:
            parts = query_upper.split(":", 1)
            if parts[0] in ("US", "TO", "TSX", "NASDAQ", "NYSE"):
                exchange_part, symbol_part = parts[0], parts[1]
            else:
                symbol_part, exchange_part = parts[0], parts[1]
        else:
            symbol_part = query_upper
            exchange_part = "US"

        for k in known:
            if k.code == symbol_part:
                return [k, *[item for item in known if item.code != symbol_part]]

        is_ca = exchange_part in ("TSX", "TO", "V", "NEO", "CN")
        currency = "CAD" if is_ca else "USD"
        country = "CA" if is_ca else "US"
        generated = SecuritySearchResult(
            code=symbol_part,
            exchange=exchange_part or ("TSX" if is_ca else "NASDAQ"),
            name=f"{symbol_part} Inc.",
            currency=currency,
            security_type="Common Stock",
            isin=f"{country}{symbol_part:0<10}"[:12],
            country=country,
        )
        return [generated, *known]

    def get_price_on_date(
        self,
        security_id: UUID,
        symbol: str,
        exchange: str,
        date: date,
    ) -> HistoricalPrice | None:
        """Get price for a security on a specific date."""
        eodhd_symbol = f"{symbol}.{exchange}"
        data = self._client.get_historical_data(
            symbol=eodhd_symbol,
            interval="d",
            iso8601_start=date.isoformat(),
            iso8601_end=date.isoformat(),
        )

        try:
            price = data.iloc[0]
            return HistoricalPrice(
                security_id=security_id,
                date=date,
                open=Decimal(str(price["open"])),
                high=Decimal(str(price["high"])),
                low=Decimal(str(price["low"])),
                close=Decimal(str(price["close"])),
                adjusted_close=Decimal(str(price["adjusted_close"])),
                volume=int(price["volume"]),
            )
        except IndexError, KeyError:
            return None

    def get_prices(
        self,
        security_id: UUID,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        """Get historical prices for a security."""
        eodhd_symbol = f"{symbol}.{exchange}"
        data = self._client.get_historical_data(
            symbol=eodhd_symbol,
            interval="d",
            iso8601_start=from_date.isoformat(),
            iso8601_end=to_date.isoformat(),
        )

        prices: list[HistoricalPrice] = []
        for _, row in data.iterrows():
            price_date = date.fromisoformat(row["date"])
            prices.append(
                HistoricalPrice(
                    security_id=security_id,
                    date=price_date,
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    adjusted_close=Decimal(str(row["adjusted_close"])),
                    volume=int(float(row["volume"])),
                )
            )

        return prices

    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        security_id: UUID,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
    ) -> list[IntradayHistoricalPrice]:
        """Get intraday prices for a security."""
        if interval != "1h":
            msg = f"Unsupported interval '{interval}'. Only '1h' interval is supported."
            raise ValueError(msg)

        eodhd_symbol = f"{symbol}.{exchange}"
        if from_datetime.tzinfo is None:
            from_datetime = from_datetime.replace(tzinfo=UTC)
        if to_datetime.tzinfo is None:
            to_datetime = to_datetime.replace(tzinfo=UTC)

        from_unix = int(from_datetime.timestamp())
        to_unix = int(to_datetime.timestamp())

        data = self._client.get_intraday_historical_data(
            symbol=eodhd_symbol,
            interval=interval,
            from_unix_time=from_unix,
            to_unix_time=to_unix,
        )

        prices: list[IntradayHistoricalPrice] = []
        for row in data:
            dt = datetime.fromtimestamp(int(row["timestamp"]), tz=UTC)
            open_val = Decimal(str(row["open"]))
            high_val = Decimal(str(row["high"]))
            low_val = Decimal(str(row["low"]))
            close_val = Decimal(str(row["close"]))
            volume_val = int(row["volume"])
            if open_val == high_val == low_val == close_val and volume_val == 0:
                continue
            prices.append(
                IntradayHistoricalPrice(
                    security_id=security_id,
                    timestamp=dt,
                    open=open_val,
                    high=high_val,
                    low=low_val,
                    close=close_val,
                    volume=volume_val,
                )
            )

        return prices

    # ------------------------------------------------------------------ #
    # Fundamentals / options capabilities (static deterministic fixtures).
    # ------------------------------------------------------------------ #

    def lookup_symbol(self, query: str) -> list[SymbolLookupResult]:
        """Look up symbols/companies matching a free-text query."""
        clean_query = query.strip().upper()
        matches = [
            payload
            for payload in _SYMBOL_LOOKUPS.values()
            if not clean_query
            or clean_query in payload["symbol"].upper()
            or clean_query in payload["name"].upper()
        ]
        return [SymbolLookupResult(**payload) for payload in matches]

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        """Get the company profile for a symbol."""
        normalized = self._resolve_symbol(symbol)
        return CompanyProfile(**_COMPANY_PROFILES[normalized])

    def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[IncomeStatement]:
        """Get income statements for a symbol."""
        _ = period
        normalized = self._resolve_symbol(symbol)
        return [
            IncomeStatement(**payload)
            for payload in _INCOME_STATEMENTS[normalized][:limit]
        ]

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[BalanceSheet]:
        """Get balance sheets for a symbol."""
        _ = period
        normalized = self._resolve_symbol(symbol)
        return [
            BalanceSheet(**payload) for payload in _BALANCE_SHEETS[normalized][:limit]
        ]

    def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[CashFlowStatement]:
        """Get cash-flow statements for a symbol."""
        _ = period
        normalized = self._resolve_symbol(symbol)
        return [
            CashFlowStatement(**payload)
            for payload in _CASH_FLOW_STATEMENTS[normalized][:limit]
        ]

    def get_key_metrics(self, symbol: str) -> KeyMetrics:
        """Get the key metrics / valuation snapshot for a symbol."""
        normalized = self._resolve_symbol(symbol)
        return KeyMetrics(**_KEY_METRICS[normalized])

    def get_financial_ratios(
        self,
        symbol: str,
        period: str = "annual",
    ) -> FinancialRatios:
        """Get financial ratios for a symbol."""
        _ = period
        normalized = self._resolve_symbol(symbol)
        return FinancialRatios(**_FINANCIAL_RATIOS[normalized])

    def get_options_chain(
        self,
        symbol: str,
        *,
        expiration: date | None = None,
        contract_type: Literal["call", "put"] | None = None,
        strike_min: Decimal | None = None,
        strike_max: Decimal | None = None,
    ) -> OptionsChain:
        """Get the options chain for an underlying symbol.

        Honours the provider-agnostic filters (expiry, option type and strike
        range). A known symbol without options still returns an empty chain
        rather than raising.
        """
        normalized = self._resolve_symbol(symbol)
        entries: list[OptionsChainEntry] = []
        for payload in OPTIONS_CHAINS.get(normalized, []):
            contract = payload["contract"]
            if (
                expiration is not None
                and contract["expiration_date"] != expiration.isoformat()
            ):
                continue
            if contract_type is not None and contract["contract_type"] != contract_type:
                continue
            strike = Decimal(contract["strike_price"])
            if strike_min is not None and strike < strike_min:
                continue
            if strike_max is not None and strike > strike_max:
                continue
            entries.append(
                OptionsChainEntry(
                    contract=OptionsContract(**contract),
                    quote=OptionsQuote(**payload["quote"]),
                )
            )
        return OptionsChain(
            underlying_symbol=normalized,
            as_of=STUB_AS_OF_DATE,
            contracts=entries,
        )
