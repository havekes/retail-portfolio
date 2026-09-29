# ruff: noqa: PLR2004, SLF001
"""Hermetic wide-event tests for ``market.data.fetched``.

Every test drives the shared ``record_fetch`` boundary with the stub EODHD
gateway, so the emission path exercised here is the same one the real gateway
flows through.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from src.config.settings import Settings
from src.core.enum import InstitutionEnum
from src.market.api import MarketPricesApi, SecurityApi
from src.market.api_types import (
    HistoricalPrice,
    IntradayHistoricalPrice,
    Security,
    SecurityId,
    SecuritySearchResult,
)
from src.market.gateway import MarketGateway, freshness_lag_ms
from src.market.repository import (
    IntradayPriceRepository,
    PriceRepository,
    SecurityBrokerRepository,
    SecurityRepository,
)
from src.market.repository_eodhd import EodhdPriceRepository
from src.market.schema import SecuritySchema
from src.market.service import MarketService
from src.observability import bootstrap_observability, reset_observability
from src.stubs.eodhd import StubEodhdGateway

STUB_API_KEY = "stub-library-key-123"

#: Key/token material that must never appear in an exported event.
FORBIDDEN_SUBSTRINGS = (
    "api_token",
    "api_key",
    "apikey",
    "service_token",
    "secret",
    "password",
)

#: Attribute names that would signal a leaked credential dimension.
FORBIDDEN_ATTRIBUTE_NAMES = frozenset(
    {"api_key", "api_token", "apikey", "service_token", "token", "secret", "password"}
)


@pytest.fixture(autouse=True)
def _cleanup_observability():
    yield
    reset_observability()


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    bootstrap_observability(
        service_name="backend",
        settings=Settings(
            environment="test",
            deploy_id="deploy-abc123",
            service_version="1.2.3",
        ),
        span_processor=SimpleSpanProcessor(exporter),
    )
    return exporter


def _security(**overrides: Any) -> SecuritySchema:
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "symbol": "AAPL",
        "exchange": "US",
        "currency": "USD",
        "name": "Apple Inc.",
        "isin": "US0378331005",
        "is_active": True,
        "updated_at": datetime.now(UTC),
    }
    return SecuritySchema(**{**defaults, **overrides})


def _fetch_spans(exporter: InMemorySpanExporter) -> list[Any]:
    return [
        span
        for span in exporter.get_finished_spans()
        if span.name == "market.data.fetched"
    ]


def _single_fetch_attributes(exporter: InMemorySpanExporter) -> dict[str, Any]:
    spans = _fetch_spans(exporter)
    assert len(spans) == 1, f"expected exactly one fetch event, got {len(spans)}"
    attributes = spans[0].attributes
    assert attributes is not None
    return dict(attributes)


def _assert_no_secret_material(exporter: InMemorySpanExporter) -> None:
    for span in exporter.get_finished_spans():
        attribute_sets = [span.attributes or {}]
        attribute_sets.extend(event.attributes or {} for event in span.events)
        for attributes in attribute_sets:
            for name, value in attributes.items():
                assert name not in FORBIDDEN_ATTRIBUTE_NAMES, name
                text = str(value).lower()
                for needle in FORBIDDEN_SUBSTRINGS:
                    assert needle not in text, f"{needle!r} leaked via {name!r}"


class _RaisingGateway(StubEodhdGateway):
    """Stub gateway whose fetches always fail."""

    def get_prices(
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_date: date,
        to_date: date,
    ) -> list[HistoricalPrice]:
        raise RuntimeError("provider down")

    def get_intraday_prices(  # noqa: PLR0913, PLR0917
        self,
        security_id: SecurityId,
        symbol: str,
        exchange: str,
        from_datetime: datetime,
        to_datetime: datetime,
        interval: str = "1h",
    ) -> list[IntradayHistoricalPrice]:
        raise RuntimeError("provider down")

    def search(self, query: str) -> list[SecuritySearchResult]:
        raise RuntimeError("provider down")


def _service(gateway: MarketGateway) -> MarketService:
    return MarketService(
        gateway=gateway,
        price_repository=AsyncMock(spec=PriceRepository),
        security_repository=AsyncMock(spec=SecurityRepository),
        intraday_price_repository=AsyncMock(spec=IntradayPriceRepository),
    )


@pytest.mark.anyio
async def test_repository_price_fetch_emits_success_event(
    span_exporter: InMemorySpanExporter,
) -> None:
    db_repository = AsyncMock(spec=PriceRepository)
    db_repository.get_prices.return_value = ([], 0)
    db_repository.save_prices.return_value = []
    repository = EodhdPriceRepository(
        db_repository=db_repository, gateway=StubEodhdGateway(api_key=STUB_API_KEY)
    )

    prices, _total = await repository.get_prices(
        _security(), date(2026, 9, 1), date(2026, 9, 10)
    )

    assert prices
    attributes = _single_fetch_attributes(span_exporter)
    assert attributes["event.name"] == "market.data.fetched"
    assert attributes["symbol"] == "AAPL"
    assert attributes["dataset"] == "eod"
    assert attributes["provider"] == "eodhd"
    assert attributes["exchange"] == "US"
    assert attributes["cache_state"] == "miss"
    assert attributes["outcome"] == "success"
    assert attributes["duration_ms"] > 0
    assert attributes["row_count"] == len(prices)
    assert isinstance(attributes["freshness_lag_ms"], int)
    assert attributes["freshness_lag_ms"] > 0
    _assert_no_secret_material(span_exporter)


@pytest.mark.anyio
async def test_repository_single_price_fetch_emits_event(
    span_exporter: InMemorySpanExporter,
) -> None:
    db_repository = AsyncMock(spec=PriceRepository)
    db_repository.get_price_on_date.return_value = None
    repository = EodhdPriceRepository(
        db_repository=db_repository, gateway=StubEodhdGateway(api_key=STUB_API_KEY)
    )

    await repository.get_price_on_date(_security(), date(2026, 9, 10))

    attributes = _single_fetch_attributes(span_exporter)
    assert attributes["dataset"] == "eod"
    assert attributes["outcome"] == "success"
    assert attributes["row_count"] == 1
    assert attributes["freshness_lag_ms"] > 0


@pytest.mark.anyio
async def test_repository_fetch_failure_emits_failure_and_reraises(
    span_exporter: InMemorySpanExporter,
) -> None:
    db_repository = AsyncMock(spec=PriceRepository)
    db_repository.get_prices.return_value = ([], 0)
    repository = EodhdPriceRepository(
        db_repository=db_repository, gateway=_RaisingGateway(api_key=STUB_API_KEY)
    )

    with pytest.raises(RuntimeError):
        await repository.get_prices(_security(), date(2026, 9, 1), date(2026, 9, 10))

    spans = _fetch_spans(span_exporter)
    assert len(spans) == 1
    attributes = _single_fetch_attributes(span_exporter)
    assert attributes["outcome"] == "failure"
    assert attributes["error_slug"] == "runtime_error"
    assert attributes["duration_ms"] > 0
    assert "row_count" not in attributes
    assert spans[0].status.status_code is StatusCode.ERROR


@pytest.mark.anyio
async def test_service_intraday_fetch_emits_event(
    span_exporter: InMemorySpanExporter,
) -> None:
    service = _service(StubEodhdGateway(api_key=STUB_API_KEY))

    result = await service.fetch_and_save_intraday_prices(_security(), days=2)

    assert result is True
    attributes = _single_fetch_attributes(span_exporter)
    assert attributes["dataset"] == "intraday"
    assert attributes["provider"] == "eodhd"
    assert attributes["outcome"] == "success"
    assert attributes["row_count"] > 0
    assert isinstance(attributes["freshness_lag_ms"], int)
    _assert_no_secret_material(span_exporter)


@pytest.mark.anyio
async def test_service_intraday_failure_emits_event_and_returns_false(
    span_exporter: InMemorySpanExporter,
) -> None:
    service = _service(_RaisingGateway(api_key=STUB_API_KEY))

    result = await service.fetch_and_save_intraday_prices(_security())

    assert result is False
    attributes = _single_fetch_attributes(span_exporter)
    assert attributes["dataset"] == "intraday"
    assert attributes["outcome"] == "failure"
    assert attributes["error_slug"] == "runtime_error"


@pytest.mark.anyio
async def test_service_price_history_fetch_emits_event(
    span_exporter: InMemorySpanExporter,
) -> None:
    service = _service(StubEodhdGateway(api_key=STUB_API_KEY))

    result = await service.fetch_and_save_price_history(_security())

    assert result is True
    attributes = _single_fetch_attributes(span_exporter)
    assert attributes["dataset"] == "eod"
    assert attributes["outcome"] == "success"
    assert attributes["row_count"] == (
        datetime.now(UTC).date() - date(2000, 1, 3)
    ).days + 1
    assert isinstance(attributes["freshness_lag_ms"], int)


@pytest.mark.anyio
async def test_security_api_search_emits_event(span_exporter: InMemorySpanExporter) -> None:
    security = _security(symbol="AAPL", exchange="US")
    security_repository = AsyncMock(spec=SecurityRepository)
    security_repository.get_or_create.return_value = security
    security_broker_repository = AsyncMock(spec=SecurityBrokerRepository)
    security_broker_repository.get_by_broker.return_value = None
    security_broker_repository.get_or_create.return_value = MagicMock()
    market_prices_api = AsyncMock(spec=MarketPricesApi)
    market_prices_api.get_latest_close.return_value = None

    api = SecurityApi(
        gateway=StubEodhdGateway(api_key=STUB_API_KEY),
        market_prices_api=market_prices_api,
        market_service=AsyncMock(spec=MarketService),
        price_repository=AsyncMock(spec=PriceRepository),
        security_broker_repository=security_broker_repository,
        security_repository=security_repository,
        search_cache=None,
    )

    result = await api.get_or_create_from_broker(
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        broker_symbol="AAPL",
        broker_exchange="NASDAQ",
        broker_name="Apple Inc.",
    )

    assert result.symbol == "AAPL"
    attributes = _single_fetch_attributes(span_exporter)
    assert attributes["dataset"] == "search"
    assert attributes["symbol"] == "AAPL"
    assert attributes["exchange"] == "US"
    assert attributes["provider"] == "eodhd"
    assert attributes["outcome"] == "success"
    assert attributes["row_count"] == 4

    # Provider identity stays an internal telemetry dimension: no schema gained
    # a provider field and no search payload carries one.
    assert "provider" not in Security.model_fields
    assert "provider" not in SecuritySearchResult.model_fields
    stored_broker = security_broker_repository.get_or_create.await_args.args[0]
    assert all("provider" not in item.model_dump() for item in stored_broker.search_results)
    _assert_no_secret_material(span_exporter)


def test_freshness_lag_ms_is_never_negative() -> None:
    future = datetime.now(UTC) + timedelta(hours=3)
    assert freshness_lag_ms(future) == 0
