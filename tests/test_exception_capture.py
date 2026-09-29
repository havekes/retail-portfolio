"""Tests for sink-agnostic OpenTelemetry exception capture (error inbox)."""

from __future__ import annotations

import socket
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode, format_trace_id, get_current_span
from starlette.requests import Request

from src.config.settings import Settings
from src.config.settings import settings as app_settings
from src.core.middleware import RequestIdMiddleware
from src.main import catch_all_exception_handler, cors_exception_middleware
from src.observability import (
    REDACTED_MASK,
    bootstrap_observability,
    capture_exception,
    get_tracer,
    reset_observability,
    should_capture_telemetry,
)
from src.observability.exceptions import get_parent_context, is_safe_user_id
from src.worker import capture_worker_task_error, huey

DEPLOY_ID = "deploy-test-abc123"


@pytest.fixture(autouse=True)
def _cleanup_observability():
    yield
    reset_observability()


def _bootstrap_with_exporter(
    service_name: str = "backend", deploy_id: str = DEPLOY_ID
) -> tuple[InMemorySpanExporter, Settings]:
    """Attach an in-memory exporter so capture is enabled under ENVIRONMENT=test."""
    exporter = InMemorySpanExporter()
    settings = Settings(environment="test", deploy_id=deploy_id)
    bootstrap_observability(
        service_name=service_name,
        settings=settings,
        span_processor=SimpleSpanProcessor(exporter),
    )
    return exporter, settings


def _build_app(*, with_safety_net: bool) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    if with_safety_net:
        app.middleware("http")(cors_exception_middleware)
    app.add_exception_handler(Exception, catch_all_exception_handler)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("backend exploded")

    return app


def _exception_events(span: Any) -> list[Any]:
    return [event for event in span.events if event.name == "exception"]


def _span_attributes(span: Any) -> dict[str, Any]:
    return dict(span.attributes or {})


def _event_attributes(event: Any) -> dict[str, Any]:
    return dict(event.attributes or {})


@huey.task()
def failing_capture_probe_task(request_id: str | None = None) -> None:
    raise RuntimeError(f"worker exploded for {request_id}")


# --------------------------------------------------------------------------- #
# AC1 — unhandled backend exceptions land in the error inbox
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_unhandled_backend_exception_captured_with_metadata(monkeypatch):
    monkeypatch.setattr(app_settings, "deploy_id", DEPLOY_ID)
    exporter, settings = _bootstrap_with_exporter()
    app = _build_app(with_safety_net=False)
    trace_id = uuid.uuid4().hex

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/boom", headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"}
        )

    assert response.status_code == 500

    # The request boundary also emits its own `http.request` wide event, so the
    # single exception record is selected explicitly.
    spans = [
        span
        for span in exporter.get_finished_spans()
        if span.name == "backend.exception"
    ]
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "backend.exception"
    assert span.attributes is not None
    assert span.attributes["service"] == "backend"
    assert span.attributes["service.name"] == "backend"
    assert span.attributes["deploy_id"] == settings.deploy_id
    assert span.attributes["release"] == settings.deploy_id
    assert span.attributes["trace_id"] == trace_id
    assert format_trace_id(span.context.trace_id) == trace_id
    assert span.status.status_code == StatusCode.ERROR

    events = _exception_events(span)
    assert len(events) == 1
    event_attributes = _event_attributes(events[0])
    assert event_attributes["exception.type"] == "RuntimeError"
    assert event_attributes["exception.message"] == "backend exploded"
    # ASGI plumbing flattens the traceback to the frame that re-raised it, but
    # a stack trace must still be attached to the exception record.
    stacktrace = event_attributes["exception.stacktrace"]
    assert stacktrace.startswith("Traceback (most recent call last):")
    assert "RuntimeError: backend exploded" in stacktrace
    # Tags ride the exception event too, so ClickHouse can group by them.
    assert event_attributes["deploy_id"] == settings.deploy_id
    assert event_attributes["trace_id"] == trace_id


@pytest.mark.anyio
async def test_cors_safety_net_captures_and_deduplicates():
    exporter, _ = _bootstrap_with_exporter()
    app = _build_app(with_safety_net=True)
    trace_id = uuid.uuid4().hex

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/boom", headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"}
        )

    assert response.status_code == 500
    spans = [
        span
        for span in exporter.get_finished_spans()
        if span.name == "backend.exception"
    ]
    # Middleware safety net and FastAPI handler must not double-report.
    assert len(spans) == 1
    assert spans[0].attributes is not None
    assert spans[0].attributes["service.name"] == "backend"
    assert spans[0].attributes["trace_id"] == trace_id


@pytest.mark.anyio
async def test_backend_handler_and_safety_net_share_one_capture():
    exporter, _ = _bootstrap_with_exporter()
    exception = RuntimeError("one failure, one record")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/boom",
        "headers": [],
    }
    request = Request(scope)

    await catch_all_exception_handler(request, exception)

    async def _raise(_request):
        raise exception

    await cors_exception_middleware(request, _raise)

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert _event_attributes(_exception_events(spans[0])[0])["exception.message"] == (
        "one failure, one record"
    )


# --------------------------------------------------------------------------- #
# AC2 — failing Huey tasks land in the error inbox with task metadata
# --------------------------------------------------------------------------- #


def test_failing_huey_task_captured_with_task_name_and_trace_id(monkeypatch):
    monkeypatch.setattr(app_settings, "deploy_id", DEPLOY_ID)
    exporter, settings = _bootstrap_with_exporter(service_name="worker")
    trace_id = uuid.uuid4().hex
    original_immediate = huey.immediate
    huey.immediate = True
    try:
        failing_capture_probe_task(request_id=trace_id)
    finally:
        huey.immediate = original_immediate

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "worker.exception"
    assert span.attributes is not None
    assert span.attributes["service"] == "worker"
    assert span.attributes["service.name"] == "worker"
    assert span.attributes["deploy_id"] == settings.deploy_id
    assert span.attributes["release"] == settings.deploy_id
    assert span.attributes["task_name"] == "failing_capture_probe_task"
    assert span.attributes["task.id"]
    assert span.attributes["trace_id"] == trace_id
    assert format_trace_id(span.context.trace_id) == trace_id

    events = _exception_events(span)
    assert len(events) == 1
    assert _event_attributes(events[0])["exception.type"] == "RuntimeError"


def test_worker_signal_without_exception_falls_back_gracefully():
    exporter, _ = _bootstrap_with_exporter(service_name="worker")
    task = failing_capture_probe_task.task_class(
        args=(), kwargs={"request_id": uuid.uuid4().hex}, id="task-fallback-1"
    )

    capture_worker_task_error(None, task, None)

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes is not None
    assert spans[0].attributes["task_name"] == "failing_capture_probe_task"
    assert spans[0].attributes["task_id"] == "task-fallback-1"
    events = _exception_events(spans[0])
    assert len(events) == 1
    assert _event_attributes(events[0])["exception.type"] == "RuntimeError"


# --------------------------------------------------------------------------- #
# AC3 — captured payloads contain no credentials or emails
# --------------------------------------------------------------------------- #


def test_exception_payload_redaction():
    exporter, _ = _bootstrap_with_exporter()
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJleGMifQ.secret_exc_sig"
    broker_session = "ws_sess_exc_secret_123"
    query_token = "secret_exc_query_token"
    query_password = "secret_exc_query_password"
    email = "failing-user@example.com"
    attribute_password = "secret_exc_attribute_password"

    message = (
        f"call to https://api.eodhd.com/v1/eod?api_token={query_token}"
        f"&password={query_password} failed with Bearer {jwt}"
        f" using session {broker_session} for {email}"
    )
    exception = RuntimeError(message)

    capture_exception(
        exception,
        service_name="backend",
        extra_attributes={
            "authorization": f"Bearer {jwt}",
            "password": attribute_password,
            "user_email": email,
        },
    )

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    events = _exception_events(span)
    assert len(events) == 1

    payload = f"{_span_attributes(span)}{_event_attributes(events[0])}"
    for secret in (
        jwt,
        broker_session,
        query_token,
        query_password,
        email,
        attribute_password,
    ):
        assert secret not in payload, f"leaked {secret!r} into telemetry"

    event_attributes = _event_attributes(events[0])
    assert event_attributes["exception.type"] == "RuntimeError"
    assert REDACTED_MASK in event_attributes["exception.message"]
    assert REDACTED_MASK in event_attributes["exception.stacktrace"]
    assert _span_attributes(span)["authorization"] == REDACTED_MASK
    assert _span_attributes(span)["password"] == REDACTED_MASK
    assert _span_attributes(span)["user_email"] == REDACTED_MASK


def test_user_id_safe_capture_and_email_rejection():
    exporter, _ = _bootstrap_with_exporter()
    user_uuid = uuid.uuid4()

    capture_exception(RuntimeError("numeric user"), user_id=user_uuid)
    capture_exception(RuntimeError("email user"), user_id="operator@example.com")

    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    assert spans[0].attributes is not None
    assert spans[0].attributes["user_id"] == str(user_uuid)
    assert spans[1].attributes is not None
    assert "user_id" not in spans[1].attributes
    assert "operator@example.com" not in str(_span_attributes(spans[1]))

    assert is_safe_user_id(user_uuid) == str(user_uuid)
    assert is_safe_user_id(42) == "42"
    assert is_safe_user_id("user-123_abc") == "user-123_abc"
    assert is_safe_user_id(uuid.uuid4().hex) is not None
    assert is_safe_user_id("operator@example.com") is None
    assert is_safe_user_id(" spaced ") is None
    assert is_safe_user_id("") is None
    assert is_safe_user_id(None) is None
    assert is_safe_user_id(True) is None
    assert is_safe_user_id({"id": 1}) is None
    assert is_safe_user_id("x" * 128) is None


# --------------------------------------------------------------------------- #
# AC4 — ENVIRONMENT=test is a hermetic kill switch
# --------------------------------------------------------------------------- #


def test_test_env_kill_switch_no_capture_and_no_egress(monkeypatch):
    reset_observability()
    settings = Settings(
        environment="test", otel_exporter_otlp_endpoint="http://clickstack:4318"
    )

    egress_attempts: list[Any] = []

    def _forbid_egress(*args: Any, **kwargs: Any) -> Any:
        egress_attempts.append((args, kwargs))
        raise AssertionError("network egress attempted without a test exporter")

    monkeypatch.setattr(socket, "socket", _forbid_egress)
    monkeypatch.setattr(socket, "create_connection", _forbid_egress)

    assert should_capture_telemetry(settings) is False

    exception = RuntimeError("must not be captured")
    capture_exception(exception, service_name="backend", settings=settings)

    assert egress_attempts == []
    assert getattr(exception, "_otel_captured", False) is False


def test_should_capture_telemetry_true_with_attached_exporter():
    _bootstrap_with_exporter()
    assert should_capture_telemetry(Settings(environment="test")) is True
    # Telemetry enabled outside tests is captured without any test exporter.
    assert (
        should_capture_telemetry(
            Settings(
                environment="dev", otel_exporter_otlp_endpoint="http://clickstack:4318"
            )
        )
        is True
    )


def test_otel_sdk_disabled_kill_switch(monkeypatch):
    reset_observability()
    monkeypatch.setenv("OTEL_SDK_DISABLED", "1")
    settings = Settings(
        environment="dev",
        otel_exporter_otlp_endpoint="http://clickstack:4318",
    )

    assert should_capture_telemetry(settings) is False

    exception = RuntimeError("disabled sdk")
    capture_exception(exception, service_name="backend", settings=settings)
    assert getattr(exception, "_otel_captured", False) is False


# --------------------------------------------------------------------------- #
# Robustness and helpers
# --------------------------------------------------------------------------- #


def test_exception_capture_resilience():
    exporter, _ = _bootstrap_with_exporter()

    class ExplodingTask:
        @property
        def name(self) -> str:
            raise ValueError("name unavailable")

    # Malformed task metadata must not escape as a secondary exception.
    capture_exception(RuntimeError("exploding task"), task=ExplodingTask())
    capture_exception(
        RuntimeError("bad settings"),
        settings=object(),  # ty: ignore[invalid-argument-type]
    )
    capture_exception(
        RuntimeError("odd user"),
        user_id=object(),
        extra_attributes={"token": object()},
    )

    # The healthy call after the malformed ones is still recorded.
    capture_exception(RuntimeError("healthy afterwards"))
    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    messages = [
        _event_attributes(event)["exception.message"]
        for span in spans
        for event in _exception_events(span)
    ]
    assert messages[-1] == "healthy afterwards"


def test_capture_inside_active_span_records_on_that_span():
    exporter, _ = _bootstrap_with_exporter()
    tracer = get_tracer("test.exception.capture")

    with tracer.start_as_current_span("active.operation") as span:
        capture_exception(RuntimeError("inside active span"), service_name="backend")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "active.operation"
    assert spans[0].status.status_code == StatusCode.ERROR
    attributes = _span_attributes(spans[0])
    assert attributes["service.name"] == "backend"
    assert attributes["trace_id"] == format_trace_id(spans[0].context.trace_id)
    events = _exception_events(spans[0])
    assert len(events) == 1
    assert _event_attributes(events[0])["exception.message"] == "inside active span"
    assert span.is_recording() is False  # the ambient span was closed by its context


def test_get_parent_context_from_traceparent_and_trace_id():
    trace_id = uuid.uuid4().hex
    headers_context = get_parent_context(
        trace_id_str=None,
        headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"},
    )
    assert headers_context is not None
    header_span = get_current_span(headers_context)
    assert format_trace_id(header_span.get_span_context().trace_id) == trace_id

    uuid_context = get_parent_context(trace_id_str=str(uuid.UUID(trace_id)))
    assert uuid_context is not None
    uuid_span = get_current_span(uuid_context)
    assert format_trace_id(uuid_span.get_span_context().trace_id) == trace_id

    assert get_parent_context(trace_id_str="not-a-trace-id") is None
    assert get_parent_context() is None
