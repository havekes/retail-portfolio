"""Wide-event tests for the `http.request` HTTP boundary event (F-OBS-T12).

The suite is hermetic: spans are collected with an in-memory exporter installed
on the process tracer provider, exactly as ``tests/test_events.py`` does. The
middleware emission rides the real app from ``src.main`` (as in
``tests/test_request_id.py``), so route templates, status codes and the
auth-token resolution exercise the production wiring.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind

from src.config.settings import Settings
from src.core.middleware import RequestIdMiddleware
from src.main import app
from src.observability import (
    bootstrap_observability,
    instrument_auto,
    reset_observability,
    uninstrument_auto,
)

DEPLOY_ID = "deploy-test-http-events"
EVENT_NAME = "http.request"


def _bootstrap_with_exporter(exporter: InMemorySpanExporter) -> None:
    """Rebind the process provider (and app instrumentation) to the exporter."""
    reset_observability()
    bootstrap_observability(
        service_name="backend",
        settings=Settings(environment="test", deploy_id=DEPLOY_ID),
        span_processor=SimpleSpanProcessor(exporter),
    )
    instrument_auto(app)


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    """Provide a fresh in-memory exporter that each test bootstraps into."""
    return InMemorySpanExporter()


@pytest.fixture(autouse=True)
def _restore_observability():
    """Restore the import-time, exporter-less instrumentation after each test."""
    yield
    uninstrument_auto(app)
    reset_observability()
    instrument_auto(app)


def _http_request_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return [
        span for span in exporter.get_finished_spans() if span.name == EVENT_NAME
    ]


def _single_http_request_span(exporter: InMemorySpanExporter) -> ReadableSpan:
    spans = _http_request_spans(exporter)
    assert len(spans) == 1, [
        (span.name, dict(span.attributes or {})) for span in spans
    ]
    return spans[0]


def _attributes(span: ReadableSpan) -> dict[str, Any]:
    assert span.attributes is not None
    return dict(span.attributes)


def _server_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return [
        span
        for span in exporter.get_finished_spans()
        if span.kind == SpanKind.SERVER
    ]


def _assert_envelope(attributes: dict[str, Any]) -> None:
    assert attributes["event.name"] == EVENT_NAME
    assert attributes["service.name"] == "backend"
    assert attributes["deploy_id"] == DEPLOY_ID
    assert attributes["environment"] == "test"
    assert len(str(attributes["trace_id"])) == 32
    assert len(str(attributes["span_id"])) == 16
    assert str(attributes["timestamp"]).startswith("20")
    assert isinstance(attributes["timestamp_unix_millis"], int)


def _raising_app() -> FastAPI:
    """Minimal app whose only route raises, to exercise the 500 branch."""
    probe_app = FastAPI()
    probe_app.add_middleware(RequestIdMiddleware)

    @probe_app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("http.request probe exploded")

    return probe_app


# --------------------------------------------------------------------------- #
# AC1 — success and 5xx requests each emit exactly one documented event
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_http_request_event_for_successful_request(
    client: AsyncClient,
    span_exporter: InMemorySpanExporter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A 200 request yields one http.request event with the documented fields."""
    _bootstrap_with_exporter(span_exporter)

    with caplog.at_level(logging.INFO):
        response = await client.get("/api/ping")

    assert response.status_code == 200

    span = _single_http_request_span(span_exporter)
    attributes = _attributes(span)
    _assert_envelope(attributes)

    assert attributes["route"] == "/api/ping"
    assert attributes["method"] == "GET"
    assert attributes["status"] == 200
    assert isinstance(attributes["status"], int)
    assert isinstance(attributes["duration_ms"], float)
    assert attributes["duration_ms"] >= 0
    assert isinstance(attributes["client_host"], str)
    assert attributes["client_host"]
    # GET carries no request body and the JSON body is not chunked.
    assert "request_bytes" not in attributes
    assert isinstance(attributes["response_bytes"], int)
    # Anonymous request: no credential was presented.
    assert "user_id" not in attributes

    # The access log stays exactly as it was: one line per request, not zero.
    access_records = [
        record for record in caplog.records if record.name == "src.core.middleware"
    ]
    assert len(access_records) == 1
    assert "200" in access_records[0].getMessage()


@pytest.mark.anyio
async def test_http_request_event_for_failing_request(
    span_exporter: InMemorySpanExporter, caplog: pytest.LogCaptureFixture
) -> None:
    """An unhandled exception yields one http.request event with status 500."""
    _bootstrap_with_exporter(span_exporter)
    probe_app = _raising_app()

    transport = ASGITransport(app=probe_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with caplog.at_level(logging.INFO):
            response = await client.get("/boom")

    assert response.status_code == 500

    span = _single_http_request_span(span_exporter)
    attributes = _attributes(span)
    _assert_envelope(attributes)

    assert attributes["route"] == "/boom"
    assert attributes["method"] == "GET"
    assert attributes["status"] == 500
    assert isinstance(attributes["duration_ms"], float)
    assert "user_id" not in attributes

    access_records = [
        record for record in caplog.records if record.name == "src.core.middleware"
    ]
    assert len(access_records) == 1
    assert "500" in access_records[0].getMessage()


# --------------------------------------------------------------------------- #
# AC1 — authenticated user id and identifier-free route templates
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_http_request_event_resolves_user_id_and_route_template(
    client: AsyncClient, test_user: Any, span_exporter: InMemorySpanExporter
) -> None:
    """The auth cookie yields user_id; identifier-bearing paths are templated."""
    _bootstrap_with_exporter(span_exporter)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "testpass"},
    )
    assert login_response.status_code == 200
    assert "auth_token" in client.cookies

    listed = await client.get("/api/v1/auth/passkeys")
    assert listed.status_code == 200

    passkey_id = uuid.uuid4()
    missing = await client.delete(f"/api/v1/auth/passkeys/{passkey_id}")
    assert missing.status_code == 404

    spans = _http_request_spans(span_exporter)
    by_route = {_attributes(span)["route"]: _attributes(span) for span in spans}
    assert set(by_route) == {
        "/auth/login",
        "/auth/passkeys",
        "/auth/passkeys/{passkey_id}",
    }

    authenticated = by_route["/auth/passkeys"]
    assert authenticated["user_id"] == str(test_user.id)
    assert authenticated["status"] == 200

    templated = by_route["/auth/passkeys/{passkey_id}"]
    assert templated["status"] == 404
    assert templated["user_id"] == str(test_user.id)
    # The raw identifier must never reach the event.
    assert str(passkey_id) not in str(templated)

    # No credential or PII value may ride the request record either.
    for span in _http_request_spans(span_exporter):
        attributes = _attributes(span)
        assert test_user.email not in str(attributes)
        assert "testpass" not in str(attributes)
        # A JWT (cookie or bearer) must never be copied into any field.
        assert "eyJ" not in str(attributes)

    # Unmatched routes (404) are labelled, never recorded as the raw path.
    unmatched_response = await client.get("/api/definitely-not-a-route-1234")
    assert unmatched_response.status_code == 404

    matched_spans = [
        span
        for span in _http_request_spans(span_exporter)
        if _attributes(span)["route"] == "unmatched"
    ]
    assert len(matched_spans) == 1
    assert "definitely-not-a-route-1234" not in str(_attributes(matched_spans[0]))


# --------------------------------------------------------------------------- #
# Envelope wiring — the event rides the server span's trace
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_http_request_event_shares_server_trace(
    client: AsyncClient, span_exporter: InMemorySpanExporter
) -> None:
    """The event is a child of the auto-instrumented server span."""
    _bootstrap_with_exporter(span_exporter)

    response = await client.get("/api/ping")
    assert response.status_code == 200

    server_spans = _server_spans(span_exporter)
    assert len(server_spans) == 1
    server_span = server_spans[0]

    event = _single_http_request_span(span_exporter)
    attributes = _attributes(event)
    assert event.context.trace_id == server_span.context.trace_id
    assert attributes["parent_span_id"] == format(
        server_span.context.span_id, "016x"
    )
    assert attributes["trace_id"] == format(server_span.context.trace_id, "032x")


@pytest.mark.anyio
async def test_http_request_event_is_additive_to_access_log(
    client: AsyncClient,
    span_exporter: InMemorySpanExporter,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Every request emits exactly one event and still exactly one access line."""
    _bootstrap_with_exporter(span_exporter)

    with caplog.at_level(logging.INFO):
        await client.get("/api/ping")
        await client.get("/api/definitely-not-a-route-1234")

    assert len(_http_request_spans(span_exporter)) == 2
    access_records = [
        record for record in caplog.records if record.name == "src.core.middleware"
    ]
    assert len(access_records) == 2
    assert caplog.text.count('"GET /api/ping" 200') == 1
    assert caplog.text.count('"GET /api/definitely-not-a-route-1234" 404') == 1
