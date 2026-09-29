"""Trace-context propagation across Huey task boundaries.

Captures the ambient W3C trace context (``traceparent``) plus the correlation ID
at enqueue time and restores it inside the worker, so
``http.request -> huey.task -> downstream work`` shares a single trace ID.

Tasks that are enqueued without any ambient context simply start a fresh root
trace, and explicit ``request_id`` values keep working unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import Token

from opentelemetry import context, propagate
from opentelemetry.context import Context

from src.core.context import (
    get_request_id,
    get_trace_id,
    get_traceparent,
    request_id_ctx_var,
    set_request_id,
)
from src.observability.bootstrap import get_tracer

TASK_TRACER_NAME = "src.observability.tasks"


def capture_task_context(request_id: str | None = None) -> dict[str, str | None]:
    """Capture the current trace context as Huey task keyword arguments.

    Splat the result into the enqueue call, e.g.
    ``generate_note_title_task(note_id, **capture_task_context())``. The returned
    mapping always carries both keys; ``None`` values simply mean "nothing to
    propagate" and leave the task to root its own trace.

    ``request_id`` defaults to the ambient correlation ID and can be overridden
    by callers that already resolved one.
    """
    return {
        "request_id": request_id if request_id is not None else get_request_id(),
        "traceparent": get_traceparent(),
    }


@contextmanager
def restore_task_context(
    task_name: str,
    request_id: str | None = None,
    traceparent: str | None = None,
) -> Iterator[None]:
    """Restore the enqueue-time context while a Huey task body executes.

    Continues the propagated trace when a ``traceparent`` is supplied and roots a
    new trace otherwise (for example periodic tasks). The task span is always
    created -- including on early returns -- and is closed together with any
    attached context, so consecutive tasks in the same worker thread never leak
    a parent context into each other.
    """
    otel_token: Token[Context] | None = None
    request_id_token: Token[str | None] | None = None

    try:
        if traceparent:
            extracted = propagate.extract({"traceparent": traceparent})
            otel_token = context.attach(extracted)

        tracer = get_tracer(TASK_TRACER_NAME)
        with tracer.start_as_current_span(task_name) as span:
            span.set_attribute("messaging.system", "huey")
            span.set_attribute("messaging.destination.name", task_name)

            effective_request_id = request_id or get_trace_id()
            if effective_request_id:
                request_id_token = set_request_id(effective_request_id)
                span.set_attribute("request_id", effective_request_id)

            yield
    finally:
        if request_id_token is not None:
            request_id_ctx_var.reset(request_id_token)
        if otel_token is not None:
            context.detach(otel_token)


__all__ = [
    "TASK_TRACER_NAME",
    "capture_task_context",
    "restore_task_context",
]
