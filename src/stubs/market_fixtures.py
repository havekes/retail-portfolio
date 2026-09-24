"""Shared deterministic stub fixtures for market data gateways.

Offline, static payloads shaped like the reference provider responses so the
stub gateways mirror the public contract exactly. Kept in one module so
``StubEodhdGateway`` and ``StubPolygonGateway`` share the same options-chain
fixtures (and the symbol universe they resolve against) without duplicating
values. No network access, no timestamps.
"""

from datetime import date
from typing import Any

# Fixed "as of" timestamp for stub options chains so responses are reproducible.
STUB_AS_OF_DATE = date(2024, 12, 2)

# Symbol universe the stub gateways recognise. Symbols outside this set raise
# ``MarketDataNotFoundError``.
KNOWN_SYMBOLS = ("AAPL", "MSFT")

OPTIONS_CHAINS: dict[str, list[dict[str, Any]]] = {
    "AAPL": [
        {
            "contract": {
                "contract_ticker": "O:AAPL250117C00150000",
                "symbol": "AAPL",
                "strike_price": "150",
                "expiration_date": "2025-01-17",
                "contract_type": "call",
                "shares_per_contract": 100,
                "primary_exchange": "BATO",
                "active": True,
            },
            "quote": {
                "implied_volatility": "0.2812",
                "open_interest": 12453,
                "day_volume": 3120,
                "day_open": "78.10",
                "day_high": "82.45",
                "day_low": "77.90",
                "day_close": "81.30",
                "greeks": {
                    "delta": "0.9412",
                    "gamma": "0.0031",
                    "theta": "-0.0412",
                    "vega": "0.1287",
                    "rho": "0.0521",
                },
            },
        },
        {
            "contract": {
                "contract_ticker": "O:AAPL250117C00230000",
                "symbol": "AAPL",
                "strike_price": "230",
                "expiration_date": "2025-01-17",
                "contract_type": "call",
                "shares_per_contract": 100,
                "primary_exchange": "BATO",
                "active": True,
            },
            "quote": {
                "implied_volatility": "0.2417",
                "open_interest": 8421,
                "day_volume": 1875,
                "day_open": "9.75",
                "day_high": "11.20",
                "day_low": "9.55",
                "day_close": "10.60",
                "greeks": {
                    "delta": "0.5314",
                    "gamma": "0.0128",
                    "theta": "-0.0731",
                    "vega": "0.3412",
                    "rho": "0.0318",
                },
            },
        },
        {
            "contract": {
                "contract_ticker": "O:AAPL250117P00150000",
                "symbol": "AAPL",
                "strike_price": "150",
                "expiration_date": "2025-01-17",
                "contract_type": "put",
                "shares_per_contract": 100,
                "primary_exchange": "BATO",
                "active": True,
            },
            "quote": {
                "implied_volatility": "0.3142",
                "open_interest": 5210,
                "day_volume": 640,
                "day_open": "0.52",
                "day_high": "0.61",
                "day_low": "0.47",
                "day_close": "0.49",
                "greeks": {
                    "delta": "-0.0588",
                    "gamma": "0.0031",
                    "theta": "-0.0187",
                    "vega": "0.1287",
                    "rho": "-0.0121",
                },
            },
        },
        {
            "contract": {
                "contract_ticker": "O:AAPL250117P00200000",
                "symbol": "AAPL",
                "strike_price": "200",
                "expiration_date": "2025-01-17",
                "contract_type": "put",
                "shares_per_contract": 100,
                "primary_exchange": "BATO",
                "active": True,
            },
            "quote": {
                "implied_volatility": "0.2688",
                "open_interest": 15102,
                "day_volume": 4021,
                "day_open": "3.10",
                "day_high": "3.55",
                "day_low": "2.95",
                "day_close": "3.20",
                "greeks": {
                    "delta": "-0.2287",
                    "gamma": "0.0121",
                    "theta": "-0.0512",
                    "vega": "0.3189",
                    "rho": "-0.0210",
                },
            },
        },
    ],
}
