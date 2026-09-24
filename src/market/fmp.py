"""FMP-backed market data gateway.

Mirrors the structure of ``src/market/eodhd.py`` but is built on a thin,
injectable ``httpx``-based HTTP client so every outbound call is mockable in
tests (``httpx.MockTransport``) and no test ever dials the network.

Error translation is provider-agnostic: upstream not-found becomes
``MarketDataNotFoundError`` and transport/status failures become
``MarketDataProviderError``; raw FMP response text is never echoed to callers
(it is logged only).
"""

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from src.config.settings import settings
from src.market.api_types import (
    HistoricalPrice,
    IntradayHistoricalPrice,
    SecurityId,
    SecuritySearchResult,
    SymbolLookupResult,
)
from src.market.exception import MarketDataNotFoundError, MarketDataProviderError
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

    def _parse_historical(
        self,
        payload: object,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
    ) -> list[HistoricalPrice]:
        """Translate an FMP historical payload into provider-agnostic prices."""
        if isinstance(payload, dict) and "Error Message" in payload:
            # FMP quirk: errors arrive as HTTP 200 with an ``Error Message`` body.
            logger.error("FMP returned an error payload for %s.%s", symbol, exchange)
            error_symbol = f"{symbol}.{exchange}"
            raise MarketDataNotFoundError(error_symbol, detail=_NOT_FOUND_DETAIL)

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
                code=result["symbol"],
                exchange=result.get("exchangeShortName")
                or result.get("exchange")
                or "",
                name=result["name"],
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
