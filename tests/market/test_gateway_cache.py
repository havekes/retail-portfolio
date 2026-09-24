"""Offline tests for the gateway-level Redis cache wrapper.

Everything here runs against the autouse in-memory ``fake_redis_manager``
fixture — no Redis server, no network. The wrapper's cache I/O runs on a
shared background event loop (see ``src.market.cache``), so both the
no-running-loop path (plain sync tests) and the running-loop / worker-thread
paths are exercised.
"""

import asyncio
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

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
    OptionsChain,
    SecuritySearchResult,
    SymbolLookupResult,
)
from src.market.cache import (
    CacheOpTimeoutError,
    CachedMarketGateway,
    _cache_key,
    _run_cache_op,
)
from src.market.gateway import MarketGateway
from src.stubs.eodhd import StubEodhdGateway
from tests.fixtures.redis import FakeRedis

PRICES_TTL = 3_600
SEARCH_TTL = 1_209_600
STATEMENTS_TTL = 86_400
METRICS_TTL = 86_400
OPTIONS_TTL = 1_800
OVERRIDE_TTL = 5


class RecordingGateway(StubEodhdGateway):
    """Stub gateway that counts how often each capability is invoked."""

    def __init__(self) -> None:
        super().__init__(api_key="stub_key")
        self.calls: dict[str, int] = defaultdict(int)

    def search(self, query: str):
        self.calls["search"] += 1
        return super().search(query)

    def get_price_on_date(self, security_id, symbol, exchange, date):
        self.calls["get_price_on_date"] += 1
        return super().get_price_on_date(security_id, symbol, exchange, date)

    def get_prices(self, security_id, symbol, exchange, from_date, to_date):
        self.calls["get_prices"] += 1
        return super().get_prices(security_id, symbol, exchange, from_date, to_date)

    def get_intraday_prices(
        self, security_id, symbol, exchange, from_datetime, to_datetime, interval="1h"
    ):
        self.calls["get_intraday_prices"] += 1
        return super().get_intraday_prices(
            security_id, symbol, exchange, from_datetime, to_datetime, interval
        )

    def lookup_symbol(self, query: str) -> list[SymbolLookupResult]:
        self.calls["lookup_symbol"] += 1
        return super().lookup_symbol(query)

    def get_company_profile(self, symbol: str) -> CompanyProfile:
        self.calls["get_company_profile"] += 1
        return super().get_company_profile(symbol)

    def get_income_statement(self, symbol, period="annual", limit=5):
        self.calls["get_income_statement"] += 1
        return super().get_income_statement(symbol, period, limit)

    def get_balance_sheet(self, symbol, period="annual", limit=5):
        self.calls["get_balance_sheet"] += 1
        return super().get_balance_sheet(symbol, period, limit)

    def get_cash_flow_statement(self, symbol, period="annual", limit=5):
        self.calls["get_cash_flow_statement"] += 1
        return super().get_cash_flow_statement(symbol, period, limit)

    def get_key_metrics(self, symbol: str) -> KeyMetrics:
        self.calls["get_key_metrics"] += 1
        return super().get_key_metrics(symbol)

    def get_financial_ratios(self, symbol, period="annual"):
        self.calls["get_financial_ratios"] += 1
        return super().get_financial_ratios(symbol, period)

    def get_options_chain(
        self,
        symbol,
        *,
        expiration=None,
        contract_type=None,
        strike_min=None,
        strike_max=None,
    ) -> OptionsChain:
        self.calls["get_options_chain"] += 1
        return super().get_options_chain(
            symbol,
            expiration=expiration,
            contract_type=contract_type,
            strike_min=strike_min,
            strike_max=strike_max,
        )


class NullPriceGateway(MarketGateway):
    """Minimal gateway that never finds a price on a date."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = defaultdict(int)

    def search(self, query: str):
        self.calls["search"] += 1
        return []

    def get_price_on_date(self, security_id, symbol, exchange, date):
        self.calls["get_price_on_date"] += 1
        return None

    def get_prices(self, security_id, symbol, exchange, from_date, to_date):
        self.calls["get_prices"] += 1
        return []

    def get_intraday_prices(
        self, security_id, symbol, exchange, from_datetime, to_datetime, interval="1h"
    ):
        self.calls["get_intraday_prices"] += 1
        return []


@pytest.fixture
def inner() -> RecordingGateway:
    return RecordingGateway()


@pytest.fixture
def gateway(inner: RecordingGateway) -> CachedMarketGateway:
    return CachedMarketGateway(inner=inner)


def _gateway_keys(storage: FakeRedis) -> list[str]:
    return sorted(key for key in storage.data if key.startswith("market:gw:"))


# --------------------------------------------------------------------------- #
# AC1: a second identical call is served from cache.
# --------------------------------------------------------------------------- #


def test_full_surface_round_trips_typed_results(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    sid = uuid4()
    frm = date(2024, 1, 2)
    to = date(2024, 1, 5)
    from_dt = datetime(2024, 1, 2, tzinfo=UTC)
    to_dt = datetime(2024, 1, 5, tzinfo=UTC)

    cases = [
        ("search", lambda: gateway.search("aapl"), True, SecuritySearchResult),
        ("lookup_symbol", lambda: gateway.lookup_symbol("aapl"), True, SymbolLookupResult),
        (
            "get_price_on_date",
            lambda: gateway.get_price_on_date(sid, "AAPL", "US", frm),
            False,
            HistoricalPrice,
        ),
        (
            "get_prices",
            lambda: gateway.get_prices(sid, "AAPL", "US", frm, to),
            True,
            HistoricalPrice,
        ),
        (
            "get_intraday_prices",
            lambda: gateway.get_intraday_prices(sid, "AAPL", "US", from_dt, to_dt),
            True,
            IntradayHistoricalPrice,
        ),
        (
            "get_income_statement",
            lambda: gateway.get_income_statement("AAPL"),
            True,
            IncomeStatement,
        ),
        (
            "get_balance_sheet",
            lambda: gateway.get_balance_sheet("AAPL"),
            True,
            BalanceSheet,
        ),
        (
            "get_cash_flow_statement",
            lambda: gateway.get_cash_flow_statement("AAPL"),
            True,
            CashFlowStatement,
        ),
        ("get_key_metrics", lambda: gateway.get_key_metrics("AAPL"), False, KeyMetrics),
        (
            "get_financial_ratios",
            lambda: gateway.get_financial_ratios("AAPL"),
            False,
            FinancialRatios,
        ),
        (
            "get_company_profile",
            lambda: gateway.get_company_profile("AAPL"),
            False,
            CompanyProfile,
        ),
        (
            "get_options_chain",
            lambda: gateway.get_options_chain("AAPL"),
            False,
            OptionsChain,
        ),
    ]

    for method, call, is_list, model in cases:
        first = call()
        second = call()
        assert first == second, method
        if is_list:
            assert isinstance(first, list), method
            assert all(isinstance(item, model) for item in first), method
        else:
            assert isinstance(first, model), method
        assert inner.calls[method] == 1, method

    assert len(_gateway_keys(mock_redis_storage)) == len(cases)


def test_get_prices_second_call_hits_cache(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    sid = uuid4()
    first = gateway.get_prices(sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))
    second = gateway.get_prices(sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))

    assert inner.calls["get_prices"] == 1
    assert second == first
    assert all(isinstance(price, HistoricalPrice) for price in second)
    keys = _gateway_keys(mock_redis_storage)
    assert len(keys) == 1
    assert keys[0].startswith("market:gw:get_prices:")


def test_get_price_on_date_none_is_cached_as_sentinel() -> None:
    null_gateway = NullPriceGateway()
    gateway = CachedMarketGateway(inner=null_gateway)
    sid = uuid4()

    assert gateway.get_price_on_date(sid, "AAPL", "US", date(2024, 1, 2)) is None
    assert gateway.get_price_on_date(sid, "AAPL", "US", date(2024, 1, 2)) is None

    # A cached "no price" is not a cache miss: the provider is hit exactly once.
    assert null_gateway.calls["get_price_on_date"] == 1


# --------------------------------------------------------------------------- #
# AC2: equivalent inputs share a key; different arguments do not.
# --------------------------------------------------------------------------- #


def test_cache_key_is_deterministic_and_order_independent() -> None:
    sid = uuid4()
    params = {
        "security_id": sid,
        "symbol": "AAPL",
        "exchange": "US",
        "from_date": date(2024, 1, 2),
        "to_date": date(2024, 1, 5),
    }
    reordered = {
        "to_date": date(2024, 1, 5),
        "from_date": date(2024, 1, 2),
        "exchange": "US",
        "symbol": "AAPL",
        "security_id": sid,
    }
    key = _cache_key("get_prices", **params)
    assert key == _cache_key("get_prices", **reordered)
    assert key.startswith("market:gw:get_prices:")

    different = dict(params, to_date=date(2024, 2, 5))
    assert _cache_key("get_prices", **different) != key


def test_positional_and_keyword_calls_share_a_key(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    sid = uuid4()
    first = gateway.get_prices(sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))
    second = gateway.get_prices(
        security_id=sid,
        symbol="AAPL",
        exchange="US",
        from_date=date(2024, 1, 2),
        to_date=date(2024, 1, 5),
    )

    assert second == first
    assert inner.calls["get_prices"] == 1
    assert len(_gateway_keys(mock_redis_storage)) == 1


def test_equivalent_datetime_and_date_bounds_share_a_key(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    sid = uuid4()
    first = gateway.get_prices(sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))
    second = gateway.get_prices(
        sid,
        "AAPL",
        "US",
        datetime(2024, 1, 2, 15, 30),  # noqa: DTZ001
        datetime(2024, 1, 5, 9, 0),  # noqa: DTZ001
    )

    assert second == first
    assert inner.calls["get_prices"] == 1
    assert len(_gateway_keys(mock_redis_storage)) == 1


def test_different_arguments_produce_different_keys(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    sid = uuid4()
    gateway.get_prices(sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))
    gateway.get_prices(sid, "AAPL", "US", date(2024, 2, 2), date(2024, 2, 5))

    assert inner.calls["get_prices"] == 2
    assert len(_gateway_keys(mock_redis_storage)) == 2


def test_search_query_normalization_shares_a_key(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    gateway.search("  AAPL  ")
    gateway.search("aapl")

    assert inner.calls["search"] == 1
    assert len(_gateway_keys(mock_redis_storage)) == 1


def test_distinct_intraday_windows_on_same_day_produce_different_keys(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    sid = uuid4()
    gateway.get_intraday_prices(
        sid,
        "AAPL",
        "US",
        datetime(2024, 1, 2, 9, 0, tzinfo=UTC),
        datetime(2024, 1, 2, 11, 0, tzinfo=UTC),
    )
    gateway.get_intraday_prices(
        sid,
        "AAPL",
        "US",
        datetime(2024, 1, 2, 14, 0, tzinfo=UTC),
        datetime(2024, 1, 2, 16, 0, tzinfo=UTC),
    )

    assert inner.calls["get_intraday_prices"] == 2
    assert len(_gateway_keys(mock_redis_storage)) == 2


def test_options_filters_change_the_key(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    gateway.get_options_chain("AAPL")
    gateway.get_options_chain("AAPL", expiration=date(2025, 1, 17))
    gateway.get_options_chain("AAPL", contract_type="call")

    assert inner.calls["get_options_chain"] == 3
    assert len(_gateway_keys(mock_redis_storage)) == 3


def test_equivalent_decimal_strike_bounds_share_a_key(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    gateway.get_options_chain("AAPL", strike_min=Decimal("10.50"))
    gateway.get_options_chain("AAPL", strike_min=Decimal("10.5"))

    assert inner.calls["get_options_chain"] == 1
    assert len(_gateway_keys(mock_redis_storage)) == 1


# --------------------------------------------------------------------------- #
# AC3: per-data-class TTLs are applied and configurable.
# --------------------------------------------------------------------------- #


def test_default_ttls_are_sane() -> None:
    assert settings.gateway_ttl_search_seconds == SEARCH_TTL
    assert settings.gateway_ttl_prices_seconds == PRICES_TTL
    assert settings.gateway_ttl_statements_seconds == STATEMENTS_TTL
    assert settings.gateway_ttl_metrics_seconds == METRICS_TTL
    assert settings.gateway_ttl_options_seconds == OPTIONS_TTL


def _install_recording_setex(
    monkeypatch: pytest.MonkeyPatch, storage: FakeRedis
) -> list[int]:
    recorded: list[int] = []
    original = storage.setex

    async def recording_setex(key: str, ttl: int, value: str) -> bool:
        recorded.append(ttl)
        return await original(key, ttl, value)

    monkeypatch.setattr(storage, "setex", recording_setex)
    return recorded


def test_per_data_class_ttls_are_applied(
    gateway: CachedMarketGateway, mock_redis_storage: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _install_recording_setex(monkeypatch, mock_redis_storage)
    sid = uuid4()

    gateway.search("aapl")
    gateway.get_prices(sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))
    gateway.get_income_statement("AAPL")
    gateway.get_key_metrics("AAPL")
    gateway.get_options_chain("AAPL")

    assert recorded == [SEARCH_TTL, PRICES_TTL, STATEMENTS_TTL, METRICS_TTL, OPTIONS_TTL]


def test_ttl_is_read_from_settings_at_call_time(
    gateway: CachedMarketGateway, mock_redis_storage: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded = _install_recording_setex(monkeypatch, mock_redis_storage)
    monkeypatch.setattr(settings, "gateway_ttl_options_seconds", OVERRIDE_TTL)

    gateway.get_options_chain("AAPL")

    assert recorded == [OVERRIDE_TTL]


# --------------------------------------------------------------------------- #
# AC4: Redis failures degrade to the provider without raising.
# --------------------------------------------------------------------------- #


def test_redis_get_failure_falls_through_to_provider(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_get(key: str):
        raise RedisConnectionError("Connection timed out")

    monkeypatch.setattr(mock_redis_storage, "get", failing_get)

    result = gateway.get_key_metrics("AAPL")

    assert isinstance(result, KeyMetrics)
    assert inner.calls["get_key_metrics"] == 1


def test_redis_set_failure_does_not_raise_and_stays_uncached(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_setex(key: str, ttl: int, value: str) -> bool:
        raise RedisConnectionError("Write failure")

    monkeypatch.setattr(mock_redis_storage, "setex", failing_setex)

    first = gateway.get_key_metrics("AAPL")
    second = gateway.get_key_metrics("AAPL")

    assert isinstance(first, KeyMetrics)
    assert first == second
    assert inner.calls["get_key_metrics"] == 2
    assert _gateway_keys(mock_redis_storage) == []


def test_corrupted_payload_is_treated_as_a_miss(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    gateway.get_company_profile("AAPL")
    keys = _gateway_keys(mock_redis_storage)
    assert len(keys) == 1
    mock_redis_storage.data[keys[0]] = "{not json"

    result = gateway.get_company_profile("AAPL")

    assert isinstance(result, CompanyProfile)
    assert inner.calls["get_company_profile"] == 2
    # The wrapper rewrote a valid payload after the fall-through.
    assert json.loads(mock_redis_storage.data[keys[0]])["symbol"] == "AAPL"


def test_payload_with_wrong_shape_is_treated_as_a_miss(
    gateway: CachedMarketGateway, inner: RecordingGateway, mock_redis_storage: FakeRedis
) -> None:
    gateway.get_prices(uuid4(), "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))
    keys = _gateway_keys(mock_redis_storage)
    assert len(keys) == 1
    mock_redis_storage.data[keys[0]] = json.dumps({"not": "a list"})

    result = gateway.get_prices(uuid4(), "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))

    assert isinstance(result, list)
    assert inner.calls["get_prices"] == 2


def test_stalled_cache_op_times_out_and_falls_through_to_provider(
    gateway: CachedMarketGateway,
    inner: RecordingGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def hanging_get(key: str) -> str | None:
        await asyncio.sleep(999)
        return None

    monkeypatch.setattr(CachedMarketGateway, "_async_get", staticmethod(hanging_get))
    # Keep the regression test fast; production uses the 5s module default.
    monkeypatch.setattr("src.market.cache._CACHE_OP_TIMEOUT", 0.05)

    result = gateway.get_key_metrics("AAPL")

    assert isinstance(result, KeyMetrics)
    assert inner.calls["get_key_metrics"] == 1


def test_cache_bridge_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.market.cache._CACHE_OP_TIMEOUT", 0.05)

    async def hang() -> None:
        await asyncio.sleep(999)

    with pytest.raises(CacheOpTimeoutError):
        _run_cache_op(hang())


# --------------------------------------------------------------------------- #
# Transparency + sync/async bridge paths.
# --------------------------------------------------------------------------- #


def test_wrapper_is_a_market_gateway(inner: RecordingGateway) -> None:
    assert isinstance(CachedMarketGateway(inner=inner), MarketGateway)


@pytest.mark.anyio
async def test_called_from_running_event_loop_does_not_deadlock(
    gateway: CachedMarketGateway, inner: RecordingGateway
) -> None:
    sid = uuid4()
    first = gateway.get_prices(sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))
    second = gateway.get_prices(sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5))

    assert second == first
    assert inner.calls["get_prices"] == 1


@pytest.mark.anyio
async def test_called_from_worker_thread_does_not_deadlock(
    gateway: CachedMarketGateway, inner: RecordingGateway
) -> None:
    sid = uuid4()
    first = await asyncio.to_thread(
        gateway.get_prices, sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5)
    )
    second = await asyncio.to_thread(
        gateway.get_prices, sid, "AAPL", "US", date(2024, 1, 2), date(2024, 1, 5)
    )

    assert second == first
    assert inner.calls["get_prices"] == 1
