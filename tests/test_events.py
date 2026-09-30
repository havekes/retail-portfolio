from __future__ import annotations

import json
import re
import socket
from pathlib import Path
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from src.config.settings import Settings
from src.observability import (
    CATALOG_EVENTS,
    REDACTED_MASK,
    bootstrap_observability,
    emit_event,
    get_tracer,
    is_telemetry_enabled,
    reset_observability,
)
from src.observability.events import HTTP_ERROR_STATUS_REASON

FIELD_DICTIONARY_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "field-dictionary.md"
)

JWT_SAMPLE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
)


@pytest.fixture(autouse=True)
def _cleanup_observability():
    yield
    reset_observability()


def _bootstrap_with_exporter(exporter: InMemorySpanExporter) -> None:
    bootstrap_observability(
        service_name="backend",
        settings=Settings(
            environment="test",
            deploy_id="deploy-abc123",
            service_version="1.2.3",
        ),
        span_processor=SimpleSpanProcessor(exporter),
    )


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    _bootstrap_with_exporter(exporter)
    return exporter


def _event_span(exporter: InMemorySpanExporter, name: str) -> ReadableSpan:
    matches = [span for span in exporter.get_finished_spans() if span.name == name]
    assert len(matches) == 1, f"expected exactly one {name!r} record, got {len(matches)}"
    return matches[0]


def _attributes(exporter: InMemorySpanExporter, name: str) -> dict[str, Any]:
    span = _event_span(exporter, name)
    assert span.attributes is not None
    return dict(span.attributes)


def test_emit_event_produces_single_telemetry_record(
    span_exporter: InMemorySpanExporter,
) -> None:
    envelope = emit_event("portfolio.sync.completed", account_id="acct-1")

    finished = span_exporter.get_finished_spans()
    assert len(finished) == 1

    record = _event_span(span_exporter, "portfolio.sync.completed")
    attributes = _attributes(span_exporter, "portfolio.sync.completed")

    assert record.name == "portfolio.sync.completed"
    assert attributes["event.name"] == "portfolio.sync.completed"
    assert attributes["trace_id"] == envelope.trace_id
    assert len(str(attributes["trace_id"])) == 32
    assert attributes["span_id"] == envelope.span_id
    assert len(str(attributes["span_id"])) == 16
    assert attributes["service.name"] == "backend"
    assert attributes["deploy_id"] == "deploy-abc123"
    assert attributes["environment"] == "test"
    assert attributes["timestamp"] == envelope.timestamp.isoformat()
    assert str(attributes["timestamp"]).startswith("20")
    assert isinstance(attributes["timestamp_unix_millis"], int)
    assert attributes["account_id"] == "acct-1"


def test_emit_event_preserves_arbitrary_primitive_types(
    span_exporter: InMemorySpanExporter,
) -> None:
    emit_event(
        "market.data.fetched",
        symbol="AAPL",
        row_count=42,
        freshness_lag_ms=1250.5,
        cache_hit=True,
    )

    attributes = _attributes(span_exporter, "market.data.fetched")
    assert attributes["symbol"] == "AAPL"
    assert attributes["row_count"] == 42
    assert attributes["freshness_lag_ms"] == 1250.5
    assert attributes["cache_hit"] is True


def test_emit_event_serializes_nested_structures(
    span_exporter: InMemorySpanExporter,
) -> None:
    emit_event(
        "alert.evaluated",
        symbol_outcomes={"AAPL": "triggered"},
        symbols=["AAPL", "MSFT"],
        missing=None,
    )

    attributes = _attributes(span_exporter, "alert.evaluated")
    assert attributes["symbol_outcomes"] == json.dumps({"AAPL": "triggered"})
    assert attributes["symbols"] == ("AAPL", "MSFT")
    assert "missing" not in attributes


def test_emit_event_shares_active_trace_context(
    span_exporter: InMemorySpanExporter,
) -> None:
    tracer = get_tracer("tests.events")
    with tracer.start_as_current_span("parent_span") as parent:
        parent_context = parent.get_span_context()
        emit_event("http.request", route="/api/v1/portfolio", method="GET")

    event_record = _event_span(span_exporter, "http.request")
    assert event_record.context.trace_id == parent_context.trace_id
    assert event_record.parent is not None
    assert event_record.parent.span_id == parent_context.span_id

    attributes = _attributes(span_exporter, "http.request")
    assert attributes["parent_span_id"] == format(parent_context.span_id, "016x")

    parent_record = _event_span(span_exporter, "parent_span")
    assert [event.name for event in parent_record.events] == ["http.request"]


def test_emit_event_standalone_generates_valid_ids(
    span_exporter: InMemorySpanExporter,
) -> None:
    envelope = emit_event("ws.delivery", message_type="portfolio_update")

    assert re.fullmatch(r"[0-9a-f]{32}", envelope.trace_id) is not None
    assert int(envelope.trace_id, 16) != 0
    assert re.fullmatch(r"[0-9a-f]{16}", envelope.span_id) is not None
    assert int(envelope.span_id, 16) != 0

    record = _event_span(span_exporter, "ws.delivery")
    assert record.context.trace_id == int(envelope.trace_id, 16)
    assert "parent_span_id" not in _attributes(span_exporter, "ws.delivery")


def test_emit_event_applies_redaction_boundary(
    span_exporter: InMemorySpanExporter,
) -> None:
    emit_event(
        "auth.event",
        outcome="success",
        email="trader@example.com",
        password="hunter2",
        api_key="key-abc",
        session_id="sess-42",
        provider="market-data",
        broker="retail-broker",
        note="Bearer abc.def.ghi",
        jwt=JWT_SAMPLE,
    )

    attributes = _attributes(span_exporter, "auth.event")
    for sensitive_key in ("email", "password", "api_key", "session_id"):
        assert attributes[sensitive_key] == REDACTED_MASK
    assert attributes["jwt"] == REDACTED_MASK
    assert attributes["note"] == f"Bearer {REDACTED_MASK}"
    # Internal telemetry dimensions are protected and must survive redaction.
    assert attributes["provider"] == "market-data"
    assert attributes["broker"] == "retail-broker"


def test_emit_event_noop_in_test_env_without_processor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbid_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("emit_event must not perform network I/O")

    monkeypatch.setattr(socket, "create_connection", _forbid_network)

    settings = Settings(
        environment="test",
        otel_exporter_otlp_endpoint="http://clickstack:4318",
    )
    assert is_telemetry_enabled(settings) is False
    provider = bootstrap_observability(service_name="backend", settings=settings)
    assert len(provider._active_span_processor._span_processors) == 0  # noqa: SLF001

    envelope = emit_event("alert.evaluated", alerts_evaluated=3, outcome="success")

    assert envelope.event_name == "alert.evaluated"
    assert envelope.fields["alerts_evaluated"] == 3


def test_emit_event_error_status_marking(
    span_exporter: InMemorySpanExporter,
) -> None:
    emit_event("portfolio.sync.failed", error_slug="broker_timeout")
    emit_event("market.data.fetched", outcome="failure", status="failed")
    emit_event("portfolio.sync.completed", status="ok", outcome="success")

    assert (
        _event_span(span_exporter, "portfolio.sync.failed").status.status_code
        is StatusCode.ERROR
    )
    assert (
        _event_span(span_exporter, "market.data.fetched").status.status_code
        is StatusCode.ERROR
    )
    assert (
        _event_span(span_exporter, "portfolio.sync.completed").status.status_code
        is StatusCode.UNSET
    )


def test_emit_event_marks_integer_5xx_status_as_error(
    span_exporter: InMemorySpanExporter,
) -> None:
    """An int 5xx status is a failure even without a slug or failure word."""
    emit_event("http.request", route="/api/boom", method="GET", status=500)
    emit_event("http.request", route="/api/unavailable", method="GET", status=503)

    spans: dict[int, ReadableSpan] = {}
    for span in span_exporter.get_finished_spans():
        if span.name == "http.request":
            assert span.attributes is not None
            status = span.attributes["status"]
            assert isinstance(status, int)
            spans[status] = span

    assert set(spans) == {500, 503}
    for status, span in spans.items():
        assert span.status.status_code is StatusCode.ERROR, status
        assert span.status.description == HTTP_ERROR_STATUS_REASON, status


def test_emit_event_leaves_integer_status_below_500_unset(
    span_exporter: InMemorySpanExporter,
) -> None:
    """Int 2xx/4xx statuses are not treated as emitter-level failures."""
    emit_event("http.request", route="/api/ping", method="GET", status=200)
    emit_event("http.request", route="/api/missing", method="GET", status=404)

    spans = [
        span
        for span in span_exporter.get_finished_spans()
        if span.name == "http.request"
    ]
    assert len(spans) == 2
    for span in spans:
        assert span.status.status_code is StatusCode.UNSET
        assert span.status.description is None


def test_emit_event_ignores_boolean_status(
    span_exporter: InMemorySpanExporter,
) -> None:
    """`bool` subclasses `int`; a boolean status must not look like a 5xx."""
    emit_event("http.request", route="/api/ping", method="GET", status=True)

    span = _event_span(span_exporter, "http.request")
    assert span.status.status_code is StatusCode.UNSET


def test_emit_event_queryable_by_event_name(
    span_exporter: InMemorySpanExporter,
) -> None:
    emit_event("http.request", route="/api/v1/portfolio", method="GET", status=200)

    record = _event_span(span_exporter, "http.request")
    attributes = _attributes(span_exporter, "http.request")
    # HyperDX/ClickHouse query on either the span name or the event.name attribute.
    assert record.name == "http.request"
    assert attributes["event.name"] == record.name


def test_field_dictionary_covers_all_catalog_events() -> None:
    text = FIELD_DICTIONARY_PATH.read_text(encoding="utf-8")

    assert len(CATALOG_EVENTS) == 9
    for envelope_field in (
        "event.name",
        "trace_id",
        "span_id",
        "service.name",
        "deploy_id",
        "environment",
        "timestamp",
    ):
        assert envelope_field in text

    for event_name in sorted(CATALOG_EVENTS):
        assert f"## `{event_name}`" in text, f"missing section for {event_name}"
