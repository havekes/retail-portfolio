"""Auto-instrumentation tests for FastAPI, SQLAlchemy, Redis and httpx.

The suite is hermetic: no network, DNS or Redis I/O happens. Outbound HTTP is
answered by an httpx transport whose connection pool is replaced with an
offline stub (the httpx instrumentation wraps ``AsyncHTTPTransport``, not
``MockTransport``), Redis commands go to a stub connection, and spans are
collected with an in-memory exporter that is installed by the fixture.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
import pytest
import redis.asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind
from sqlalchemy import create_engine, text

from src.main import app
from src.observability import (
    bootstrap_observability,
    is_telemetry_enabled,
    reset_observability,
)
from src.observability.instrumentation import (
    instrument_auto,
    instrument_fastapi,
    instrument_redis,
    instrument_sqlalchemy,
    uninstrument_auto,
)

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
PARENT_SPAN_ID = "00f067aa0ba902b7"
TRACEPARENT = f"00-{TRACE_ID}-{PARENT_SPAN_ID}-01"


# --------------------------------------------------------------------------- #
# Offline doubles for the instrumented I/O clients
# --------------------------------------------------------------------------- #


class _AsyncBytes:
    """Async iterable of byte chunks, standing in for a response body."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator[bytes]:
        async def _generate() -> AsyncIterator[bytes]:
            for chunk in self._chunks:
                yield chunk

        return _generate()


class _StubPoolResponse:
    """The slice of ``httpcore.Response`` that httpx's transport reads."""

    status = 200
    headers = [(b"content-type", b"application/json")]
    extensions = {"http_version": b"HTTP/1.1"}

    def __init__(self, body: bytes) -> None:
        self.stream = _AsyncBytes([body])


class _OfflineAsyncPool:
    """Connection pool stand-in that answers without opening a socket."""

    def __init__(
        self, body: bytes, captured_headers: dict[str, str] | None = None
    ) -> None:
        self._body = body
        self.captured_headers = captured_headers if captured_headers is not None else {}

    async def handle_async_request(self, request: Any) -> _StubPoolResponse:
        # httpcore hands the pool byte-pair headers rather than httpx's str map.
        for key, value in request.headers:
            str_key = key.decode("latin-1") if isinstance(key, bytes) else key
            str_value = value.decode("latin-1") if isinstance(value, bytes) else value
            self.captured_headers[str_key] = str_value
        return _StubPoolResponse(self._body)

    async def aclose(self) -> None:
        return None

    async def __aenter__(self) -> _OfflineAsyncPool:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def _offline_async_transport(
    body: bytes = b'{"ok": true}',
    captured_headers: dict[str, str] | None = None,
) -> httpx.AsyncHTTPTransport:
    """A real instrumented httpx transport backed by an offline stub pool."""
    transport = httpx.AsyncHTTPTransport()
    transport._pool = cast(  # noqa: SLF001
        "Any", _OfflineAsyncPool(body, captured_headers)
    )
    return transport


class _StubRedisRetry:
    async def call_with_retry(
        self, target: Any, failure_callback: Any, **kwargs: Any
    ) -> Any:
        return await target()


class _StubRedisConnection:
    """Redis connection stand-in that answers commands without a socket."""

    host = "localhost"
    port = 6379
    db = 0

    def __init__(self) -> None:
        self.retry = _StubRedisRetry()

    async def send_command(self, *args: Any, **kwargs: Any) -> None:
        return None

    async def read_response(self, **kwargs: Any) -> bytes:
        return b"+PONG"

    async def disconnect(self) -> None:
        return None

    def _close(self) -> None:
        """``Redis.__del__`` closes the borrowed connection synchronously."""
        return None


def _offline_redis_client() -> redis.asyncio.Redis:
    """A real redis client whose connection never leaves the process."""
    client = redis.asyncio.Redis(host="localhost", port=6379)
    client.connection = cast("Any", _StubRedisConnection())
    return client


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def span_exporter():
    """
    Install an in-memory exporter and (re)bind the auto-instrumentation to it.

    ``instrument_auto`` re-instruments rather than no-ops, so the server
    middleware, database, Redis and httpx instrumentations all resolve their
    tracer against the provider installed by ``bootstrap_observability``.
    """
    reset_observability()
    exporter = InMemorySpanExporter()
    bootstrap_observability(span_processor=SimpleSpanProcessor(exporter))
    instrument_auto(app)

    yield exporter

    uninstrument_auto(app)
    reset_observability()
    instrument_auto(app)


def _finished_spans(exporter: InMemorySpanExporter) -> list[Any]:
    return list(exporter.get_finished_spans())


def _server_span(exporter: InMemorySpanExporter) -> Any:
    server_spans = [s for s in _finished_spans(exporter) if s.kind == SpanKind.SERVER]
    assert len(server_spans) == 1, [s.name for s in server_spans]
    return server_spans[0]


def _child_spans(exporter: InMemorySpanExporter, parent: Any) -> list[Any]:
    return [
        span
        for span in _finished_spans(exporter)
        if span.parent is not None and span.parent.span_id == parent.context.span_id
    ]


# --------------------------------------------------------------------------- #
# Acceptance criteria
# --------------------------------------------------------------------------- #


def test_main_app_is_instrumented_at_import() -> None:
    """``src.main`` must wire the auto-instrumentation before serving requests."""
    assert getattr(app, "_is_instrumented_by_opentelemetry", False) is True


@pytest.mark.anyio
async def test_fastapi_server_span_created_with_attributes(test_engine):
    """AC1/AC2: a real request yields a server span with its DB query as a child."""
    exporter = InMemorySpanExporter()

    async with LifespanManager(app) as manager:
        # The lifespan bootstraps (and on exit shuts down) the process provider,
        # so the exporter processor is installed after it has started.
        reset_observability()
        bootstrap_observability(span_processor=SimpleSpanProcessor(exporter))
        instrument_auto(app)

        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            response = await client.get("/api/ping")

        assert response.status_code == 200

        span = _server_span(exporter)
        attributes = dict(span.attributes or {})
        assert span.name == "GET /api/ping"
        assert attributes["http.route"] == "/api/ping"
        assert attributes["http.target"] == "/api/ping"
        assert attributes["http.method"] == "GET"
        assert attributes["http.status_code"] == 200

        children = _child_spans(exporter, span)
        db_spans = [
            child
            for child in children
            if dict(child.attributes or {}).get("db.system") == "postgresql"
        ]
        assert db_spans, [child.name for child in children]
        assert all(child.parent.span_id == span.context.span_id for child in db_spans)

    uninstrument_auto(app)
    reset_observability()
    instrument_auto(app)


@pytest.mark.anyio
async def test_database_httpx_and_redis_child_spans(span_exporter):
    """AC2: outbound httpx, DB and Redis work in a request becomes child spans."""
    engine = create_engine("sqlite://")
    redis_client = _offline_redis_client()
    http_client = httpx.AsyncClient(transport=_offline_async_transport())

    probe_app = FastAPI()

    @probe_app.get("/probe")
    async def probe() -> dict[str, Any]:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        outbound = await http_client.get("http://indicator-service/compute")
        await redis_client.execute_command("GET", "probe-key")
        return {"status": outbound.status_code}

    instrument_fastapi(probe_app)
    instrument_sqlalchemy(engine)
    instrument_redis()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=probe_app), base_url="http://test"
        ) as client:
            response = await client.get("/probe")
    finally:
        await http_client.aclose()

    assert response.status_code == 200
    assert response.json() == {"status": 200}

    server_span = _server_span(span_exporter)
    children = _child_spans(span_exporter, server_span)
    assert children, "no child spans were recorded for the request"

    def _attributes(span: Any) -> dict[str, Any]:
        return dict(span.attributes or {})

    db_spans = [s for s in children if _attributes(s).get("db.system") == "sqlite"]
    assert [s.name for s in db_spans if s.name == "SELECT"] == ["SELECT"]
    select_span = next(s for s in db_spans if s.name == "SELECT")
    assert _attributes(select_span)["db.statement"] == "SELECT 1"

    http_spans = [
        s
        for s in children
        if _attributes(s).get("http.url") == "http://indicator-service/compute"
    ]
    assert len(http_spans) == 1
    assert http_spans[0].kind == SpanKind.CLIENT
    assert _attributes(http_spans[0])["http.status_code"] == 200

    redis_spans = [s for s in children if _attributes(s).get("db.system") == "redis"]
    assert len(redis_spans) == 1
    assert redis_spans[0].kind == SpanKind.CLIENT

    trace_ids = {
        span.context.trace_id for span in (*db_spans, *http_spans, *redis_spans)
    }
    assert trace_ids == {server_span.context.trace_id}


@pytest.mark.anyio
async def test_outbound_httpx_span_carries_traceparent_header(span_exporter):
    """The httpx leg to indicator-service carries the W3C traceparent header."""
    captured: dict[str, str] = {}
    client = httpx.AsyncClient(
        transport=_offline_async_transport(captured_headers=captured)
    )
    try:
        response = await client.post("http://indicator-service/compute", json={})
    finally:
        await client.aclose()

    assert response.status_code == 200

    httpx_spans = [
        span
        for span in _finished_spans(span_exporter)
        if dict(span.attributes or {}).get("http.url")
        == "http://indicator-service/compute"
    ]
    assert len(httpx_spans) == 1, [span.name for span in _finished_spans(span_exporter)]

    traceparent = captured.get("traceparent")
    assert traceparent is not None, captured
    parts = traceparent.split("-")
    assert parts[1] == f"{httpx_spans[0].context.trace_id:032x}"
    assert parts[2] == f"{httpx_spans[0].context.span_id:016x}"


@pytest.mark.anyio
async def test_inbound_traceparent_continuation(span_exporter):
    """AC3: an inbound traceparent header is continued, not replaced."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/health/live", headers={"traceparent": TRACEPARENT}
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == TRACE_ID

    span = _server_span(span_exporter)
    assert f"{span.context.trace_id:032x}" == TRACE_ID
    assert span.parent is not None
    assert f"{span.parent.span_id:016x}" == PARENT_SPAN_ID


@pytest.mark.anyio
async def test_single_access_log_line_with_auto_instrumentation(
    span_exporter, caplog
):
    """AC4: RequestIdMiddleware stays the only per-request access logger."""
    with caplog.at_level(logging.INFO):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health/live")

    assert response.status_code == 200

    access_records = [r for r in caplog.records if r.name == "src.core.middleware"]
    assert len(access_records) == 1
    assert "200" in access_records[0].getMessage()

    # The access log runs *inside* the server span: the correlation id it logs
    # is the trace id of the exported server span.
    server_span = _server_span(span_exporter)
    assert getattr(access_records[0], "trace_id", None) == (
        f"{server_span.context.trace_id:032x}"
    )

    # No other logger may duplicate the access log line.
    access_suffixes = [
        r for r in caplog.records if '"GET /health/live" 200' in r.getMessage()
    ]
    assert len(access_suffixes) == 1


@pytest.mark.anyio
async def test_redis_command_creates_client_span(span_exporter):
    """Redis commands emit a client span without opening a socket."""
    redis_client = _offline_redis_client()
    await redis_client.execute_command("GET", "cache-key")

    redis_spans = [
        span
        for span in _finished_spans(span_exporter)
        if dict(span.attributes or {}).get("db.system") == "redis"
    ]
    assert len(redis_spans) == 1
    assert redis_spans[0].kind == SpanKind.CLIENT
    assert redis_spans[0].name == "GET"


def test_telemetry_disabled_under_test_env(span_exporter):
    """AC5: no OTLP exporter runs under ENVIRONMENT=test."""
    assert is_telemetry_enabled() is False

    provider = trace.get_tracer_provider()
    assert isinstance(provider, TracerProvider)
    processors = provider._active_span_processor._span_processors  # noqa: SLF001
    assert not any(isinstance(p, BatchSpanProcessor) for p in processors)
    assert any(isinstance(p, SimpleSpanProcessor) for p in processors)
