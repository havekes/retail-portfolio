"""Trace-context propagation across Huey task boundaries.

Covers the W3C trace context captured at enqueue time (``capture_task_context``)
and restored by the worker (``restore_task_context``): trace continuity across
the enqueue/dequeue boundary, root traces when there is nothing to continue,
periodic tasks, chained tasks and safe cleanup on early returns and exceptions.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from src.config.settings import Settings
from src.core.context import (
    get_request_id,
    get_trace_id,
    get_traceparent,
    request_id_ctx_var,
    set_request_id,
)
from src.market.alert_service import AlertEvaluationService
from src.market.repository import IntradayPriceRepository, PriceAlertRepository
from src.market.service import MarketService
from src.market.task import (
    _check_and_dispatch_price_alerts,
    _hourly_intraday_price_update,
    check_and_dispatch_price_alerts,
    daily_price_update,
    generate_note_title_task,
    hourly_intraday_price_update,
)
from src.observability import (
    bootstrap_observability,
    capture_task_context,
    reset_observability,
    restore_task_context,
)
from src.observability.bootstrap import get_tracer
from src.worker import huey

# A fixed, valid W3C traceparent: trace id 4bf92f...4736 / span id 00f067aa0ba902b7
TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
PARENT_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
PARENT_SPAN_ID = "00f067aa0ba902b7"


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
def _isolated_context() -> Iterator[None]:
    """Start each test with no correlation id and leave Huey in immediate mode."""
    token = set_request_id(None)
    try:
        yield
    finally:
        request_id_ctx_var.reset(token)
        huey.immediate = True


def _run_in_fresh_thread(fn: Callable[[], Any]) -> Any:
    """Run ``fn`` in a new thread, which starts with an empty contextvars context."""
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:
            box["error"] = exc

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


def _drain_queue() -> None:
    while huey.dequeue() is not None:
        pass


def _take_task(task_name: str) -> Any:
    while True:
        task = huey.dequeue()
        if task is None:
            msg = f"{task_name} was not enqueued"
            raise AssertionError(msg)
        if str(task.name).endswith(task_name):
            return task


def _span(span_exporter: InMemorySpanExporter, name: str) -> Any:
    matches = [span for span in span_exporter.get_finished_spans() if span.name == name]
    assert len(matches) == 1, f"expected one {name!r} span, got {len(matches)}"
    return matches[0]


# --------------------------------------------------------------------------- #
# capture_task_context
# --------------------------------------------------------------------------- #


def test_capture_task_context_without_ambient_context():
    """A bare context yields nothing to propagate (task will root its own trace)."""
    captured: dict[str, str | None] = {}

    def capture() -> None:
        captured.update(capture_task_context())

    _run_in_fresh_thread(capture)

    assert captured == {"request_id": None, "traceparent": None}


def test_capture_task_context_continues_active_span(exporter):
    """The captured traceparent points at the active span's trace."""
    tracer = get_tracer("test.tasks")
    with tracer.start_as_current_span("http.request") as span:
        trace_id = trace.format_trace_id(span.get_span_context().trace_id)
        captured = capture_task_context()

    assert captured["request_id"] == trace_id
    traceparent = captured["traceparent"]
    assert traceparent is not None
    assert traceparent.split("-")[1] == trace_id


# --------------------------------------------------------------------------- #
# restore_task_context
# --------------------------------------------------------------------------- #


def test_restore_task_context_keeps_explicit_request_id(exporter):
    """An explicit request_id stays bound, while the trace keeps its own id."""
    with restore_task_context(
        "explicit_task", request_id="explicit-rid", traceparent=TRACEPARENT
    ):
        assert request_id_ctx_var.get() == "explicit-rid"
        assert get_trace_id() == PARENT_TRACE_ID

    assert request_id_ctx_var.get() is None
    assert get_trace_id() is None
    assert get_traceparent() is None


def test_restore_task_context_is_visible_inside_asyncio_run(exporter):
    """The restored span survives the asyncio.run() boundary used by thread workers."""

    async def read_trace_id() -> str | None:
        return get_trace_id()

    with restore_task_context("async_task", traceparent=TRACEPARENT):
        inner_trace_id = asyncio.run(read_trace_id())

    assert inner_trace_id == PARENT_TRACE_ID
    span = _span(exporter, "async_task")
    assert trace.format_trace_id(span.context.trace_id) == PARENT_TRACE_ID
    assert trace.format_span_id(span.parent.span_id) == PARENT_SPAN_ID


def test_restore_task_context_records_error_and_resets(exporter):
    """Exceptions mark the task span as failed and still reset the context."""
    with pytest.raises(ValueError, match="boom"):
        with restore_task_context("failing_task", traceparent=TRACEPARENT):
            raise ValueError("boom")

    span = _span(exporter, "failing_task")
    assert span.status.status_code is StatusCode.ERROR
    assert "boom" in (span.status.description or "")
    assert request_id_ctx_var.get() is None
    assert get_traceparent() is None


# --------------------------------------------------------------------------- #
# Enqueue -> worker continuity
# --------------------------------------------------------------------------- #


def test_task_enqueued_in_request_span_runs_in_same_trace(exporter):
    """AC: a task enqueued inside a request span continues that trace."""
    tracer = get_tracer("test.tasks")
    huey.immediate = False

    try:
        _drain_queue()
        with tracer.start_as_current_span("http.request") as request_span:
            request_context = request_span.get_span_context()
            parent_trace_id = trace.format_trace_id(request_context.trace_id)
            parent_span_id = trace.format_span_id(request_context.span_id)
            generate_note_title_task(4242, **capture_task_context())

        task = _take_task("generate_note_title_task")
        traceparent = task.kwargs["traceparent"]
        assert traceparent is not None
        assert traceparent.split("-")[1] == parent_trace_id

        # The worker thread has no ambient context: only the kwargs carry it.
        def execute() -> None:
            huey.execute(task)

        _run_in_fresh_thread(execute)
    finally:
        huey.immediate = True

    task_span = _span(exporter, "generate_note_title_task")
    assert trace.format_trace_id(task_span.context.trace_id) == parent_trace_id
    assert task_span.parent is not None
    assert trace.format_span_id(task_span.parent.span_id) == parent_span_id

    request_span = _span(exporter, "http.request")
    assert trace.format_trace_id(request_span.context.trace_id) == parent_trace_id


def test_task_enqueued_without_ambient_context_roots_new_trace(exporter):
    """AC: nothing to continue means the worker starts a fresh root trace."""
    huey.immediate = False
    captured: dict[str, str | None] = {}

    try:
        _drain_queue()

        def enqueue() -> None:
            captured.update(capture_task_context())
            generate_note_title_task(9999, **capture_task_context())

        _run_in_fresh_thread(enqueue)

        task = _take_task("generate_note_title_task")
        assert task.kwargs["traceparent"] is None

        def execute() -> None:
            huey.execute(task)

        _run_in_fresh_thread(execute)
    finally:
        huey.immediate = True

    assert captured == {"request_id": None, "traceparent": None}

    task_span = _span(exporter, "generate_note_title_task")
    assert task_span.parent is None
    assert task_span.context.trace_id != 0


# --------------------------------------------------------------------------- #
# Periodic tasks
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("invoke_periodic", "task_name"),
    [
        (daily_price_update, "daily_price_update"),
        (hourly_intraday_price_update, "hourly_intraday_price_update"),
    ],
    ids=["daily", "hourly"],
)
def test_periodic_task_roots_its_own_trace(exporter, invoke_periodic, task_name):
    """AC: periodic tasks have no enqueuer, so they root a fresh trace."""
    huey.immediate = True
    observed: dict[str, str | None] = {}

    def fake_asyncio_run(coro: Any) -> None:
        coro.close()
        observed["trace_id"] = get_trace_id()
        observed["request_id"] = get_request_id()
        observed["traceparent"] = get_traceparent()

    with patch("src.market.task.asyncio.run", side_effect=fake_asyncio_run):
        invoke_periodic()

    span = _span(exporter, task_name)
    assert span.parent is None
    assert trace.format_trace_id(span.context.trace_id) == observed["trace_id"]
    # request_id is unified with the trace id so logs correlate with the span
    assert observed["request_id"] == observed["trace_id"]

    traceparent = observed["traceparent"]
    assert traceparent is not None
    assert traceparent.split("-")[1] == observed["trace_id"]

    assert request_id_ctx_var.get() is None


# --------------------------------------------------------------------------- #
# Chained stages
# --------------------------------------------------------------------------- #


def _market_container(market_service: AsyncMock) -> AsyncMock:
    container = AsyncMock()
    container.aget.return_value = market_service
    container.__aenter__.return_value = container
    return container


@pytest.mark.asyncio
async def test_chained_tasks_share_one_trace(exporter):
    """Stage 1 -> Stage 2 -> Stage 3 all stay in the enqueuer's trace."""
    tracer = get_tracer("test.tasks")
    with tracer.start_as_current_span("http.request") as request_span:
        parent_trace_id = trace.format_trace_id(
            request_span.get_span_context().trace_id
        )
        stage1_kwargs = capture_task_context()

    market_service = AsyncMock(spec=MarketService)
    market_service.update_intraday_prices_for_all_securities.return_value = {
        "success": 1,
        "failure": 0,
    }

    # Stage 1 (worker side) enqueues Stage 2 with its own context.
    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=_market_container(market_service)),
        patch("src.market.task.recalculate_all_account_totals_task"),
        patch("src.market.task.check_and_dispatch_price_alerts") as mock_stage2,
        restore_task_context("hourly_intraday_price_update", **stage1_kwargs),
    ):
        await _hourly_intraday_price_update()

    stage2_kwargs = mock_stage2.call_args.kwargs

    alert = MagicMock()
    alert.alert_id = 7
    alert_repo = AsyncMock(spec=PriceAlertRepository)
    alert_repo.get_active_alerts_for_evaluation.return_value = [alert]
    intraday_repo = AsyncMock(spec=IntradayPriceRepository)
    intraday_repo.get_latest_intraday_close_by_security.return_value = {}
    alert_service = AsyncMock(spec=AlertEvaluationService)
    alert_service.evaluate = MagicMock(return_value=[alert])

    async def aget(service_type: type) -> Any:
        if service_type is PriceAlertRepository:
            return alert_repo
        if service_type is IntradayPriceRepository:
            return intraday_repo
        return alert_service

    stage2_container = AsyncMock()
    stage2_container.aget.side_effect = aget
    stage2_container.__aenter__.return_value = stage2_container

    # Stage 2 (worker side) enqueues Stage 3 with its own context.
    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=stage2_container),
        patch("src.market.task.alert_email_dispatch_task") as mock_stage3,
        restore_task_context("check_and_dispatch_price_alerts", **stage2_kwargs),
    ):
        await _check_and_dispatch_price_alerts()

    stage3_kwargs = mock_stage3.call_args.kwargs

    stage1_span = _span(exporter, "hourly_intraday_price_update")
    stage2_span = _span(exporter, "check_and_dispatch_price_alerts")

    assert trace.format_trace_id(stage1_span.context.trace_id) == parent_trace_id
    assert trace.format_trace_id(stage2_span.context.trace_id) == parent_trace_id
    assert stage2_span.parent is not None
    assert stage2_span.parent.span_id == stage1_span.context.span_id

    for kwargs in (stage1_kwargs, stage2_kwargs, stage3_kwargs):
        traceparent = kwargs["traceparent"]
        assert traceparent is not None
        assert traceparent.split("-")[1] == parent_trace_id

    stage3_traceparent = stage3_kwargs["traceparent"]
    assert stage3_traceparent is not None
    assert stage3_traceparent.split("-")[2] == trace.format_span_id(
        stage2_span.context.span_id
    )


# --------------------------------------------------------------------------- #
# Early returns
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("invoke", "task_name"),
    [
        (
            lambda: generate_note_title_task(4242, traceparent=TRACEPARENT),
            "generate_note_title_task",
        ),
        (
            lambda: check_and_dispatch_price_alerts(traceparent=TRACEPARENT),
            "check_and_dispatch_price_alerts",
        ),
    ],
    ids=["generate_note_title_task", "check_and_dispatch_price_alerts"],
)
def test_registry_none_early_return_still_cleans_up(exporter, invoke, task_name):
    """huey.svcs_registry is None in some paths: span ends, context is reset."""
    huey.immediate = True

    with patch("src.market.task.huey.svcs_registry", None):
        invoke()

    span = _span(exporter, task_name)
    assert trace.format_trace_id(span.context.trace_id) == PARENT_TRACE_ID
    assert trace.format_span_id(span.parent.span_id) == PARENT_SPAN_ID
    assert span.end_time is not None

    assert request_id_ctx_var.get() is None
    assert get_traceparent() is None
    assert get_request_id() is None
