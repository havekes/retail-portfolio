"""FMP API stubs for testing and local development.

Offline, deterministic fixtures used by ``StubFmpGateway``. No network access:
prices are generated from static sample bars and search/lookup return a small
fixed set of known instruments.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.market.api_types import (
    BalanceSheet,
    CashFlowStatement,
    CompanyProfile,
    FinancialRatios,
    HistoricalPrice,
    IncomeStatement,
    IntradayHistoricalPrice,
    KeyMetrics,
    SecuritySearchResult,
    SymbolLookupResult,
)
from src.market.exception import MarketDataNotFoundError, MarketDataProviderError
from src.market.gateway import MarketGateway

_KNOWN_SYMBOLS: dict[str, dict[str, str]] = {
    "AAPL": {
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "exchange_short_name": "NASDAQ",
        "currency": "USD",
        "security_type": "Common Stock",
        "country": "US",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "exchange": "NASDAQ",
        "exchange_short_name": "NASDAQ",
        "currency": "USD",
        "security_type": "Common Stock",
        "country": "US",
    },
    "RY": {
        "name": "Royal Bank of Canada",
        "exchange": "Toronto Stock Exchange",
        "exchange_short_name": "TSX",
        "currency": "CAD",
        "security_type": "Common Stock",
        "country": "CA",
    },
    "VOD": {
        "name": "Vodafone Group Plc",
        "exchange": "London Stock Exchange",
        "exchange_short_name": "LSE",
        "currency": "GBP",
        "security_type": "Common Stock",
        "country": "GB",
    },
}

_BASE_PRICES: dict[str, float] = {
    "AAPL": 175.0,
    "MSFT": 380.0,
    "RY": 120.0,
    "VOD": 8.5,
}

_VALID_PERIODS = frozenset({"annual", "quarter"})

# --------------------------------------------------------------------------- #
# Deterministic fundamentals fixtures for the stub gateway.
#
# Static, offline dicts shaped like the T01 unified types for every symbol in
# ``_KNOWN_SYMBOLS``. Values are stable (no timestamps or hashing involved) so
# stub-mode reads are reproducible.
# --------------------------------------------------------------------------- #

_FUNDAMENTAL_PROFILES: dict[str, dict[str, Any]] = {
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
    "RY": {
        "symbol": "RY",
        "company_name": "Royal Bank of Canada",
        "market_cap": "170000000000",
        "sector": "Financial Services",
        "industry": "Banks - Diversified",
        "beta": "0.89",
        "price": "135.20",
        "website": "https://www.rbc.com",
        "description": (
            "Royal Bank of Canada provides diversified financial services worldwide."
        ),
        "ceo": "Dave McKay",
        "full_time_employees": 91000,
        "exchange_short_name": "TSX",
        "exchange": "Toronto Stock Exchange",
        "currency": "CAD",
        "ipo_date": "1995-01-01",
        "cik": "0001007264",
        "isin": "CA7800871021",
        "image": "https://images.example.com/RY.png",
        "is_actively_trading": True,
    },
    "VOD": {
        "symbol": "VOD",
        "company_name": "Vodafone Group Plc",
        "market_cap": "22000000000",
        "sector": "Communication Services",
        "industry": "Telecom Services",
        "beta": "0.72",
        "price": "8.15",
        "website": "https://www.vodafone.com",
        "description": (
            "Vodafone Group Plc provides mobile and fixed telecommunication "
            "services across Europe and Africa."
        ),
        "ceo": "Margherita Della Valle",
        "full_time_employees": 93000,
        "exchange_short_name": "LSE",
        "exchange": "London Stock Exchange",
        "currency": "GBP",
        "ipo_date": "1988-10-01",
        "cik": "0000839923",
        "isin": "GB00BH4HKS39",
        "image": "https://images.example.com/VOD.png",
        "is_actively_trading": True,
    },
}

_FUNDAMENTAL_INCOME_STATEMENTS: dict[str, list[dict[str, Any]]] = {
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
    "RY": [
        {
            "date": "2024-10-31",
            "symbol": "RY",
            "reported_currency": "CAD",
            "cik": "0001007264",
            "fiscal_year": "2024",
            "period": "FY",
            "revenue": "56000000000",
            "cost_of_revenue": "0",
            "gross_profit": "56000000000",
            "research_and_development_expenses": "0",
            "selling_general_and_administrative_expenses": "22000000000",
            "operating_expenses": "22000000000",
            "operating_income": "18500000000",
            "interest_expense": "0",
            "other_income_expense": "0",
            "income_tax_expense": "3700000000",
            "net_income": "14800000000",
            "eps": "10.52",
            "eps_diluted": "10.48",
            "weighted_average_shares_outstanding": "1407000000",
            "weighted_average_shares_outstanding_diluted": "1412000000",
        },
    ],
    "VOD": [
        {
            "date": "2024-03-31",
            "symbol": "VOD",
            "reported_currency": "EUR",
            "cik": "0000839923",
            "fiscal_year": "2024",
            "period": "FY",
            "revenue": "36700000000",
            "cost_of_revenue": "24100000000",
            "gross_profit": "12600000000",
            "research_and_development_expenses": "0",
            "selling_general_and_administrative_expenses": "9400000000",
            "operating_expenses": "9400000000",
            "operating_income": "3200000000",
            "interest_expense": "1700000000",
            "other_income_expense": "0",
            "income_tax_expense": "800000000",
            "net_income": "1200000000",
            "eps": "0.42",
            "eps_diluted": "0.41",
            "weighted_average_shares_outstanding": "2860000000",
            "weighted_average_shares_outstanding_diluted": "2920000000",
        },
    ],
}

_FUNDAMENTAL_BALANCE_SHEETS: dict[str, list[dict[str, Any]]] = {
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
    "RY": [
        {
            "date": "2024-10-31",
            "symbol": "RY",
            "reported_currency": "CAD",
            "cik": "0001007264",
            "fiscal_year": "2024",
            "period": "FY",
            "total_assets": "2100000000000",
            "current_assets": "0",
            "total_liabilities": "1950000000000",
            "current_liabilities": "0",
            "total_debt": "430000000000",
            "cash_and_cash_equivalents": "90000000000",
            "inventory": "0",
            "receivables": "14000000000",
            "payables": "0",
            "goodwill": "12000000000",
            "retained_earnings": "70000000000",
            "total_equity": "150000000000",
            "common_stock": "30000000000",
            "net_debt": "340000000000",
        },
    ],
    "VOD": [
        {
            "date": "2024-03-31",
            "symbol": "VOD",
            "reported_currency": "EUR",
            "cik": "0000839923",
            "fiscal_year": "2024",
            "period": "FY",
            "total_assets": "144000000000",
            "current_assets": "28000000000",
            "total_liabilities": "84000000000",
            "current_liabilities": "32000000000",
            "total_debt": "47000000000",
            "cash_and_cash_equivalents": "12000000000",
            "inventory": "1000000000",
            "receivables": "8000000000",
            "payables": "11000000000",
            "goodwill": "26000000000",
            "retained_earnings": "0",
            "total_equity": "60000000000",
            "common_stock": "5000000000",
            "net_debt": "35000000000",
        },
    ],
}

_FUNDAMENTAL_CASH_FLOW_STATEMENTS: dict[str, list[dict[str, Any]]] = {
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
    "RY": [
        {
            "date": "2024-10-31",
            "symbol": "RY",
            "reported_currency": "CAD",
            "cik": "0001007264",
            "fiscal_year": "2024",
            "period": "FY",
            "net_income": "14800000000",
            "operating_cash_flow": "31000000000",
            "investing_cash_flow": "-18000000000",
            "financing_cash_flow": "-11000000000",
            "capital_expenditure": "-3000000000",
            "free_cash_flow": "28000000000",
            "dividends_paid": "-7000000000",
            "stock_based_compensation": "800000000",
            "cash_change": "2000000000",
        },
    ],
    "VOD": [
        {
            "date": "2024-03-31",
            "symbol": "VOD",
            "reported_currency": "EUR",
            "cik": "0000839923",
            "fiscal_year": "2024",
            "period": "FY",
            "net_income": "1200000000",
            "operating_cash_flow": "11400000000",
            "investing_cash_flow": "-6000000000",
            "financing_cash_flow": "-5000000000",
            "capital_expenditure": "-6000000000",
            "free_cash_flow": "5400000000",
            "dividends_paid": "-2500000000",
            "stock_based_compensation": "300000000",
            "cash_change": "400000000",
        },
    ],
}

_FUNDAMENTAL_KEY_METRICS: dict[str, dict[str, Any]] = {
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
    "RY": {
        "symbol": "RY",
        "date": "2024-10-31",
        "fiscal_year": "2024",
        "period": "FY",
        "market_cap": "170000000000",
        "enterprise_value": "510000000000",
        "pe_ratio": "11.48",
        "peg_ratio": "1.31",
        "price_to_sales_ratio": "3.04",
        "price_to_book_ratio": "1.13",
        "enterprise_value_over_ebitda": "12.40",
        "ev_to_sales": "9.11",
        "dividend_yield": "0.0352",
        "payout_ratio": "0.47",
        "current_ratio": "0.0",
        "quick_ratio": "0.0",
        "debt_to_equity": "2.87",
        "working_capital": "-150000000000",
    },
    "VOD": {
        "symbol": "VOD",
        "date": "2024-03-31",
        "fiscal_year": "2024",
        "period": "FY",
        "market_cap": "22000000000",
        "enterprise_value": "57000000000",
        "pe_ratio": "18.33",
        "peg_ratio": "1.92",
        "price_to_sales_ratio": "0.60",
        "price_to_book_ratio": "0.37",
        "enterprise_value_over_ebitda": "5.00",
        "ev_to_sales": "1.55",
        "dividend_yield": "0.0920",
        "payout_ratio": "1.68",
        "current_ratio": "0.88",
        "quick_ratio": "0.84",
        "debt_to_equity": "0.78",
        "working_capital": "-4000000000",
    },
}

_FUNDAMENTAL_FINANCIAL_RATIOS: dict[str, dict[str, Any]] = {
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
    "RY": {
        "symbol": "RY",
        "date": "2024-10-31",
        "fiscal_year": "2024",
        "period": "FY",
        "gross_profit_margin": "1.0",
        "operating_profit_margin": "0.3304",
        "net_profit_margin": "0.2643",
        "return_on_assets": "0.0070",
        "return_on_equity": "0.0987",
        "return_on_capital_employed": "0.0434",
        "interest_coverage": "0.0",
        "quick_ratio": "0.0",
        "current_ratio": "0.0",
        "debt_to_equity": "2.8667",
        "price_earnings_ratio": "11.48",
        "book_value_per_share": "119.62",
        "dividend_yield": "0.0352",
    },
    "VOD": {
        "symbol": "VOD",
        "date": "2024-03-31",
        "fiscal_year": "2024",
        "period": "FY",
        "gross_profit_margin": "0.3433",
        "operating_profit_margin": "0.0872",
        "net_profit_margin": "0.0327",
        "return_on_assets": "0.0083",
        "return_on_equity": "0.0200",
        "return_on_capital_employed": "0.0276",
        "interest_coverage": "1.88",
        "quick_ratio": "0.8412",
        "current_ratio": "0.8750",
        "debt_to_equity": "0.7833",
        "price_earnings_ratio": "18.33",
        "book_value_per_share": "22.03",
        "dividend_yield": "0.0920",
    },
}


def _validate_period(period: str) -> str:
    """Validate an FMP statement period, mirroring the real gateway."""
    if period not in _VALID_PERIODS:
        msg = f"Unsupported period '{period}'. Expected 'annual' or 'quarter'."
        raise ValueError(msg)
    return period


class StubFmpGateway(MarketGateway):
    """Deterministic FMP gateway stub for testing and local development.

    Prices and search are generated offline from static sample bars. Unknown
    symbols raise ``MarketDataNotFoundError`` and symbols listed in
    ``fail_on_symbols`` raise ``MarketDataProviderError`` — mirroring the
    failure paths of the real gateway without any outbound I/O.
    """

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
            message = f"Market data provider failure for symbol '{normalized}'."
            raise MarketDataProviderError(message)
        if normalized in self._unknown_symbols or normalized not in _KNOWN_SYMBOLS:
            raise MarketDataNotFoundError(normalized)
        return normalized

    def _generate_prices(
        self,
        security_id: UUID,
        symbol: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        base_price = _BASE_PRICES.get(symbol, 100.0)
        current = base_price
        prices: list[HistoricalPrice] = []
        days = (to_date - from_date).days
        for offset in range(days + 1):
            current_date = from_date + timedelta(days=offset)
            change = (hash(f"{symbol}-{offset}") % 100 - 50) / 2500.0
            current *= 1 + change
            prices.append(
                HistoricalPrice(
                    security_id=security_id,
                    date=current_date,
                    open=Decimal(str(round(current * 0.995, 2))),
                    high=Decimal(str(round(current * 1.01, 2))),
                    low=Decimal(str(round(current * 0.99, 2))),
                    close=Decimal(str(round(current, 2))),
                    adjusted_close=Decimal(str(round(current, 2))),
                    volume=1_000_000 + (hash(f"{symbol}-{offset}") % 1_000_000),
                )
            )
        return prices

    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search for securities by ticker or name."""
        clean_query = query.strip().upper()
        return [
            SecuritySearchResult(
                code=symbol,
                exchange=payload["exchange_short_name"],
                name=payload["name"],
                currency=payload["currency"],
                security_type=payload["security_type"],
                isin=None,
                country=payload["country"],
            )
            for symbol, payload in _KNOWN_SYMBOLS.items()
            if not clean_query
            or clean_query in symbol
            or clean_query in payload["name"].upper()
        ]

    def get_price_on_date(
        self,
        security_id: UUID,
        symbol: str,
        exchange: str,
        date: date,
    ) -> HistoricalPrice | None:
        """Get the price for a security on a specific date."""
        _ = exchange  # Price generation is symbol-driven in stub mode.
        normalized = self._resolve_symbol(symbol)
        prices = self._generate_prices(
            security_id, normalized, from_date=date, to_date=date
        )
        return prices[0] if prices else None

    def get_prices(
        self,
        security_id: UUID,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        """Get historical prices for a security within a date range."""
        _ = exchange  # Price generation is symbol-driven in stub mode.
        normalized = self._resolve_symbol(symbol)
        return self._generate_prices(
            security_id, normalized, from_date=from_date, to_date=to_date
        )

    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        security_id: UUID,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
    ) -> list[IntradayHistoricalPrice]:
        """Get intraday prices for a security (deterministic hourly bars)."""
        _ = exchange  # Price generation is symbol-driven in stub mode.
        if interval != "1h":
            msg = f"Unsupported interval '{interval}'. Only '1h' interval is supported."
            raise ValueError(msg)

        normalized = self._resolve_symbol(symbol)
        if from_datetime.tzinfo is None:
            from_datetime = from_datetime.replace(tzinfo=UTC)
        if to_datetime.tzinfo is None:
            to_datetime = to_datetime.replace(tzinfo=UTC)

        prices: list[IntradayHistoricalPrice] = []
        current_dt = from_datetime.replace(minute=0, second=0, microsecond=0)
        step = 0
        while current_dt <= to_datetime:
            current = _BASE_PRICES.get(normalized, 100.0) + step / 100
            prices.append(
                IntradayHistoricalPrice(
                    security_id=security_id,
                    timestamp=current_dt,
                    open=Decimal(str(round(current * 0.998, 2))),
                    high=Decimal(str(round(current * 1.005, 2))),
                    low=Decimal(str(round(current * 0.995, 2))),
                    close=Decimal(str(round(current, 2))),
                    volume=10_000 + (hash(f"{normalized}-{step}") % 50_000),
                )
            )
            current_dt += timedelta(hours=1)
            step += 1

        return prices

    def lookup_symbol(self, query: str) -> list[SymbolLookupResult]:
        """Look up symbols/companies matching a free-text query."""
        clean_query = query.strip().upper()
        return [
            SymbolLookupResult(
                symbol=symbol,
                name=payload["name"],
                exchange=payload["exchange"],
                exchange_short_name=payload["exchange_short_name"],
                currency=payload["currency"],
                security_type=payload["security_type"],
                country=payload["country"],
            )
            for symbol, payload in _KNOWN_SYMBOLS.items()
            if not clean_query
            or clean_query in symbol
            or clean_query in payload["name"].upper()
        ]

    # ------------------------------------------------------------------ #
    # Fundamentals capabilities (static deterministic fixtures).
    # ------------------------------------------------------------------ #

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        """Get the company profile for a symbol."""
        normalized = self._resolve_symbol(symbol)
        return CompanyProfile(**_FUNDAMENTAL_PROFILES[normalized])

    def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[IncomeStatement]:
        """Get income statements for a symbol."""
        _validate_period(period)
        normalized = self._resolve_symbol(symbol)
        return [
            IncomeStatement(**row)
            for row in _FUNDAMENTAL_INCOME_STATEMENTS[normalized][:limit]
        ]

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[BalanceSheet]:
        """Get balance sheets for a symbol."""
        _validate_period(period)
        normalized = self._resolve_symbol(symbol)
        return [
            BalanceSheet(**row)
            for row in _FUNDAMENTAL_BALANCE_SHEETS[normalized][:limit]
        ]

    def get_cash_flow_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> list[CashFlowStatement]:
        """Get cash-flow statements for a symbol."""
        _validate_period(period)
        normalized = self._resolve_symbol(symbol)
        return [
            CashFlowStatement(**row)
            for row in _FUNDAMENTAL_CASH_FLOW_STATEMENTS[normalized][:limit]
        ]

    def get_key_metrics(self, symbol: str) -> KeyMetrics:
        """Get the key metrics / valuation snapshot for a symbol."""
        normalized = self._resolve_symbol(symbol)
        return KeyMetrics(**_FUNDAMENTAL_KEY_METRICS[normalized])

    def get_financial_ratios(
        self,
        symbol: str,
        period: str = "annual",
    ) -> FinancialRatios:
        """Get financial ratios for a symbol."""
        _validate_period(period)
        normalized = self._resolve_symbol(symbol)
        return FinancialRatios(**_FUNDAMENTAL_FINANCIAL_RATIOS[normalized])
