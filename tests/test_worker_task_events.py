"""``huey.task`` wide events: one record per worker task execution.

Each test drives a real Huey execution in immediate mode with an in-memory span
exporter attached, so the assertions cover the signal path production uses
(``SIGNAL_EXECUTING`` -> terminal signal) instead of the helpers in isolation.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode, format_trace_id

from src.config.settings import Settings
from src.integration.brokers.exception import ExternalAPIError, SessionExpiredError
from src.observability import (
    HUEY_TASK_EVENT,
    STATUS_INTERRUPTED,
    STATUS_SUCCESS,
    UNKNOWN_ERROR_SLUG,
    bootstrap_observability,
    emit_task_event,
    error_slug_for_error,
    record_task_start,
    reset_observability,
)
from src.worker import huey

# A fixed, valid W3C traceparent: trace id 4bf92f...4736 / span id 00f067aa0ba902b7
TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
PARENT_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
PARENT_SPAN_ID = "00f067aa0ba902b7"


@huey.task()
def sample_success_task(value: int = 1) -> int:
    """Probe task that completes successfully."""
    return value


@huey.task()
def sample_failure_task() -> None:
    """Probe task that always raises."""
    raise RuntimeError("sample task exploded")


@huey.task()
def sample_traced_task(
    request_id: str | None = None,
    traceparent: str | None = None,
) -> None:
    """Probe task accepting the propagated context kwargs, like a real task."""


@pytest.fixture()
def exporter() -> Iterator[InMemorySpanExporter]:
    """Bootstrap a worker tracer that exports to memory, and reset afterwards."""
    span_exporter = InMemorySpanExporter()
    bootstrap_observability(
        service_name="worker",
        settings=Settings(environment="test"),
        span_processor=SimpleSpanProcessor(span_exporter),
    )
    try:
        yield span_exporter
    finally:
        reset_observability()


@pytest.fixture(autouse=True)
def _immediate_mode() -> Iterator[None]:
    """Run enqueued tasks synchronously and restore the previous Huey mode."""
    original_immediate = huey.immediate
    huey.immediate = True
    try:
        yield
    finally:
        huey.immediate = original_immediate


def _event_spans(
    span_exporter: InMemorySpanExporter, name: str = HUEY_TASK_EVENT
) -> list[Any]:
    return [span for span in span_exporter.get_finished_spans() if span.name == name]


def _event_span(
    span_exporter: InMemorySpanExporter, name: str = HUEY_TASK_EVENT
) -> Any:
    spans = _event_spans(span_exporter, name)
    assert len(spans) == 1, f"expected one {name!r} span, got {len(spans)}"
    return spans[0]


def _event_attributes(
    span_exporter: InMemorySpanExporter, name: str = HUEY_TASK_EVENT
) -> dict[str, Any]:
    return dict(_event_span(span_exporter, name).attributes or {})


def _probe_task(task_id: str) -> Any:
    return sample_success_task.task_class(args=(), kwargs={}, id=task_id)


# --------------------------------------------------------------------------- #
# Success and failure through the real Huey signal handlers
# --------------------------------------------------------------------------- #


def test_task_success_emits_event_with_status_and_duration(exporter):
    sample_success_task(42)

    attributes = _event_attributes(exporter)
    assert attributes["event.name"] == HUEY_TASK_EVENT
    assert attributes["task_name"] == "sample_success_task"
    assert attributes["task_id"]
    assert attributes["queue"] == "retail-portfolio"
    assert attributes["status"] == "success"
    assert attributes["retries"] == 0
    assert float(attributes["duration_ms"]) >= 0
    assert "error_slug" not in attributes

    span = _event_span(exporter)
    assert span.status.status_code is not StatusCode.ERROR


def test_task_failure_emits_event_with_error_slug(exporter):
    sample_failure_task()

    attributes = _event_attributes(exporter)
    assert attributes["task_name"] == "sample_failure_task"
    assert attributes["status"] == "failed"
    assert attributes["error_slug"] == "runtime_error"

    span = _event_span(exporter)
    assert span.status.status_code is StatusCode.ERROR


def test_task_event_shares_enqueue_trace(exporter):
    """The event re-attaches the propagated context after the task body ran."""
    sample_traced_task(traceparent=TRACEPARENT)

    span = _event_span(exporter)
    assert format_trace_id(span.context.trace_id) == PARENT_TRACE_ID
    assert _event_attributes(exporter)["parent_span_id"] == PARENT_SPAN_ID


def test_task_event_without_traceparent_roots_its_own_trace(exporter):
    sample_success_task()

    span = _event_span(exporter)
    assert span.context.trace_id != 0
    assert "parent_span_id" not in _event_attributes(exporter)


# --------------------------------------------------------------------------- #
# Helper guards: duration bookkeeping and None tasks
# --------------------------------------------------------------------------- #


def test_emit_task_event_without_recorded_start_omits_duration(exporter):
    emit_task_event(_probe_task("task-no-start"), STATUS_INTERRUPTED)

    attributes = _event_attributes(exporter)
    assert attributes["status"] == STATUS_INTERRUPTED
    assert attributes["task_id"] == "task-no-start"
    assert "duration_ms" not in attributes


def test_recorded_start_is_consumed_by_the_first_emission(exporter):
    task = _probe_task("task-consumed")
    record_task_start(task)

    emit_task_event(task, STATUS_SUCCESS)
    emit_task_event(task, STATUS_SUCCESS)

    spans = _event_spans(exporter)
    assert len(spans) == 2
    assert "duration_ms" in dict(spans[0].attributes or {})
    assert "duration_ms" not in dict(spans[1].attributes or {})


def test_emit_task_event_skips_none_task(exporter):
    record_task_start(None)
    emit_task_event(None, STATUS_SUCCESS)

    assert exporter.get_finished_spans() == ()


# --------------------------------------------------------------------------- #
# Failure slug classification
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ExternalAPIError("gateway timeout"), "external_api_error"),
        (SessionExpiredError("expired"), "session_expired_error"),
        (RuntimeError("boom"), "runtime_error"),
        (None, UNKNOWN_ERROR_SLUG),
    ],
    ids=["external_api_error", "session_expired_error", "runtime_error", "no_error"],
)
def test_error_slug_for_error(error: BaseException | None, expected: str) -> None:
    assert error_slug_for_error(error) == expected
