"""Polygon-backed market data gateway.

Implements the options-chain capability declared as optional on
``MarketGateway``, mapping the Polygon options snapshot endpoint directly onto
the provider-agnostic options types (``OptionsContract``, ``OptionsQuote``,
``OptionsGreeks``, ``OptionsChainEntry`` and ``OptionsChain``).

The gateway mirrors the plain ``requests`` HTTP conventions of
``src/market/eodhd.py``: a single ``requests.get(..., timeout=10)`` per page
(``next_url`` pagination is followed to the end). All outbound HTTP goes
through ``requests.get`` so tests can patch it
(``@patch("src.market.polygon.requests.get")``) and make zero network calls.

Error translation is provider-agnostic: an unknown underlying or empty chain
becomes ``MarketDataNotFoundError``, credential failures (HTTP 401/403) become
``MarketDataConfigurationError`` and transport/status/decoding failures become
``MarketDataProviderError``. Raw upstream URLs, response bodies and the
provider name are never echoed to callers (they are logged only).
"""

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import quote, urlencode

import requests

from src.config.settings import settings
from src.market.api_types import (
    HistoricalPrice,
    IntradayHistoricalPrice,
    OptionsChain,
    OptionsChainEntry,
    OptionsContract,
    OptionsGreeks,
    OptionsQuote,
    SecurityId,
    SecuritySearchResult,
)
from src.market.exception import (
    MarketDataConfigurationError,
    MarketDataNotFoundError,
    MarketDataProviderError,
)
from src.market.gateway import MarketGateway

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.polygon.io"
DEFAULT_TIMEOUT_SECONDS = 10
_OPTIONS_SNAPSHOT_PATH = "/v3/snapshot/options"
_PAGE_LIMIT = 250

_HTTP_OK = 200
_HTTP_NOT_FOUND = 404
_HTTP_UNAUTHORIZED = frozenset({401, 403})

_PROVIDER_ERROR_MESSAGE = "The market data provider is unavailable."
_CONFIGURATION_ERROR_MESSAGE = "Market data provider configuration is invalid."
_CAPABILITY_NOT_SUPPORTED = "capability not supported by this provider"

# OCC option ticker: an optional ``O:`` prefix, the underlying symbol, a
# six-digit ``YYMMDD`` expiry, a ``C``/``P`` option type and an eight-digit
# strike. Used to recover the underlying symbol from ``details.ticker``.
_OCC_TICKER_PATTERN = re.compile(
    r"^(?:O:)?(?P<underlying>[A-Z0-9.]+?)(?P<expiry>\d{6})(?P<type>[CP])(?P<strike>\d{8})$"
)


def _split_occ_ticker(ticker: str) -> str:
    """Return the underlying symbol embedded in an OCC option ticker.

    ``O:AAPL250117C00150000`` -> ``AAPL``. Returns an empty string when the
    ticker is not in OCC form, letting the caller fall back to the requested
    underlying.
    """
    match = _OCC_TICKER_PATTERN.match(ticker.strip().upper())
    if match is None:
        return ""
    return match.group("underlying")


def _to_decimal(value: object) -> Decimal | None:
    """Coerce a Polygon scalar to ``Decimal`` or ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc


def _to_required_decimal(value: object) -> Decimal:
    """Coerce a required Polygon scalar to ``Decimal``.

    A missing or unparseable value is a malformed payload and raises a
    provider-agnostic error rather than returning ``None``.
    """
    result = _to_decimal(value)
    if result is None:
        raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE)
    return result


def _to_int(value: object) -> int | None:
    """Coerce a Polygon scalar to ``int`` or ``None`` (tolerates ``"1875.0"``)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError) as exc:
        raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc


def _to_date(value: object) -> date:
    """Coerce a Polygon ``YYYY-MM-DD`` scalar to ``date``.

    The expiry is required on an options contract; a missing or unparseable
    value is a malformed payload and raises a provider-agnostic error.
    """
    text = "" if value is None else str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc


class PolygonGateway(MarketGateway):
    """Market data gateway backed by the Polygon HTTP API."""

    _api_key: str
    _base_url: str

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

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

        ``expiration`` and ``contract_type`` are pushed to the snapshot
        endpoint as query parameters; the strike range is applied locally over
        the parsed contracts (Polygon's snapshot strike-range parameters are
        unstable, so filtering locally keeps behaviour deterministic). An
        unknown underlying (HTTP 404) or a chain that resolves to no contracts
        raises ``MarketDataNotFoundError``.
        """
        underlying = symbol.strip().upper()

        params = {"limit": str(_PAGE_LIMIT), "apiKey": self._api_key}
        if expiration is not None:
            params["expiration_date"] = expiration.isoformat()
        if contract_type is not None:
            params["contract_type"] = contract_type

        path = f"{_OPTIONS_SNAPSHOT_PATH}/{quote(underlying)}"
        url = f"{self._base_url}{path}?{urlencode(params)}"

        entries: list[OptionsChainEntry] = []
        payload = self._request_json(url, underlying)
        entries.extend(self._parse_entries(payload, underlying))

        next_url = payload.get("next_url") if isinstance(payload, dict) else None
        while isinstance(next_url, str) and next_url:
            page = self._request_json(self._with_api_key(next_url), underlying)
            entries.extend(self._parse_entries(page, underlying))
            next_url = page.get("next_url") if isinstance(page, dict) else None

        entries = self._apply_strike_range(entries, strike_min, strike_max)

        if not entries:
            raise MarketDataNotFoundError(underlying)

        return OptionsChain(
            underlying_symbol=underlying,
            as_of=None,
            contracts=entries,
        )

    def _with_api_key(self, url: str) -> str:
        """Append the API key to a paginated ``next_url`` if absent."""
        if "apiKey=" in url:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{urlencode({'apiKey': self._api_key})}"

    def _request_json(self, url: str, symbol: str) -> object:
        """GET ``url`` and return parsed JSON, translating upstream failures.

        Raw URLs and response bodies never reach callers; they are logged only.
        """
        try:
            response = requests.get(url, timeout=DEFAULT_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            logger.exception("Options chain request failed")
            raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc

        status = response.status_code
        if status == _HTTP_NOT_FOUND:
            raise MarketDataNotFoundError(symbol)
        if status in _HTTP_UNAUTHORIZED:
            logger.error("Options chain request was unauthorized (status %s)", status)
            raise MarketDataConfigurationError(_CONFIGURATION_ERROR_MESSAGE)
        if status != _HTTP_OK:
            logger.error("Options chain request failed (status %s)", status)
            raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE)

        try:
            return response.json()
        except ValueError as exc:
            logger.exception("Options chain response was not valid JSON")
            raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc

    def _parse_entries(
        self, payload: object, fallback_symbol: str
    ) -> list[OptionsChainEntry]:
        """Translate a snapshot page into provider-agnostic chain entries."""
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            logger.error("Options snapshot payload was not a results object")
            raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE)

        entries: list[OptionsChainEntry] = []
        for item in results:
            if not isinstance(item, dict):
                logger.error("Options snapshot entry was not an object")
                raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE)
            try:
                entries.append(self._parse_entry(item, fallback_symbol))
            except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
                logger.exception("Malformed options snapshot entry")
                raise MarketDataProviderError(_PROVIDER_ERROR_MESSAGE) from exc
        return entries

    def _parse_entry(
        self, item: dict[str, object], fallback_symbol: str
    ) -> OptionsChainEntry:
        """Translate a single snapshot result into a contract + quote."""
        details = item["details"]
        greeks_payload = item.get("greeks")
        day_payload = item.get("day")

        if not isinstance(details, dict):
            msg = "options snapshot entry is missing contract details"
            raise TypeError(msg)

        ticker = str(details["ticker"])
        contract = OptionsContract(
            contract_ticker=ticker,
            symbol=_split_occ_ticker(ticker) or fallback_symbol,
            strike_price=_to_required_decimal(details["strike_price"]),
            expiration_date=_to_date(details["expiration_date"]),
            contract_type=details["contract_type"],
        )

        greeks: OptionsGreeks | None = None
        if isinstance(greeks_payload, dict):
            greeks = OptionsGreeks(
                delta=_to_decimal(greeks_payload.get("delta")),
                gamma=_to_decimal(greeks_payload.get("gamma")),
                theta=_to_decimal(greeks_payload.get("theta")),
                vega=_to_decimal(greeks_payload.get("vega")),
                rho=_to_decimal(greeks_payload.get("rho")),
            )

        day = day_payload if isinstance(day_payload, dict) else {}
        options_quote = OptionsQuote(
            implied_volatility=_to_decimal(item.get("implied_volatility")),
            open_interest=_to_int(item.get("open_interest")),
            day_volume=_to_int(day.get("volume")),
            day_open=_to_decimal(day.get("open")),
            day_high=_to_decimal(day.get("high")),
            day_low=_to_decimal(day.get("low")),
            day_close=_to_decimal(day.get("close")),
            greeks=greeks,
        )

        return OptionsChainEntry(contract=contract, quote=options_quote)

    def _apply_strike_range(
        self,
        entries: list[OptionsChainEntry],
        strike_min: Decimal | None,
        strike_max: Decimal | None,
    ) -> list[OptionsChainEntry]:
        """Filter entries to the requested strike range (inclusive)."""
        filtered = entries
        if strike_min is not None:
            filtered = [
                entry for entry in filtered if entry.contract.strike_price >= strike_min
            ]
        if strike_max is not None:
            filtered = [
                entry for entry in filtered if entry.contract.strike_price <= strike_max
            ]
        return filtered

    # ------------------------------------------------------------------ #
    # Unsupported capabilities.
    #
    # This gateway only serves options chains (T04); prices, search and
    # intraday reads are not part of its scope. The abstract methods are
    # implemented to raise the same provider-agnostic capability error as the
    # ABC defaults, keeping the class concrete.
    # ------------------------------------------------------------------ #

    def search(self, query: str) -> list[SecuritySearchResult]:
        """Search is not supported by this gateway."""
        _ = query
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_price_on_date(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        date: date,
    ) -> HistoricalPrice | None:
        """Single-date prices are not supported by this gateway."""
        _ = security_id, symbol, exchange, date
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_prices(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        """Historical prices are not supported by this gateway."""
        _ = security_id, symbol, exchange, from_date, to_date
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)

    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
    ) -> list[IntradayHistoricalPrice]:
        """Intraday prices are not supported by this gateway."""
        _ = security_id, symbol, exchange, from_datetime, to_datetime, interval
        raise MarketDataProviderError(_CAPABILITY_NOT_SUPPORTED)


def polygon_gateway_factory() -> MarketGateway:
    """Build the Polygon-backed gateway from settings."""
    return PolygonGateway(api_key=settings.polygon_api_key)
