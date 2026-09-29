"""``huey.task`` wide events for worker task execution.

The Huey signal handlers registered in ``src.worker`` call
:func:`record_task_start` on ``SIGNAL_EXECUTING`` and :func:`emit_task_event` on
the terminal signals, so every executed task -- periodic ones included -- yields
exactly one ``huey.task`` event carrying its duration, retry counter and, on
failure, a stable ``error_slug`` plus span status ``ERROR``.

Trace continuity: the task body restores the enqueue-time context (F-OBS-T07)
only while it runs, so the terminal signals are emitted after that context was
detached. The event therefore re-attaches the ``traceparent`` carried by the task
kwargs to keep sharing the originating ``http.request`` trace id; tasks enqueued
without one (for example periodic tasks) root a fresh trace.

Every emission is guarded: broken telemetry must never break task execution or
Huey signal dispatch.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import context, propagate

from src.observability.events import emit_event

logger = logging.getLogger(__name__)

#: Catalog event emitted once per worker task execution.
HUEY_TASK_EVENT = "huey.task"

#: Task statuses reported for the terminal Huey signals.
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_INTERRUPTED = "interrupted"

#: Upper bound on tracked in-flight tasks; the oldest entries are evicted first.
MAX_IN_FLIGHT_TASKS = 1024

#: Task id -> monotonic start time, drained by the terminal signal handlers.
_TASK_START_TIMES: dict[str, float] = {}


def _task_id(task: Any) -> str | None:
    """Return the Huey task id, or ``None`` when the task has none."""
    task_id = getattr(task, "id", None)
    return str(task_id) if task_id else None


def _task_name(task: Any) -> str:
    """Return the registered Huey task name (the decorated function's name)."""
    name = getattr(task, "name", None)
    return str(name) if name else "unknown"


def _task_retries(task: Any) -> int:
    """Return Huey's retry counter: ``0`` on a first attempt."""
    retries = getattr(task, "retries", 0)
    return retries if isinstance(retries, int) else 0


def _task_traceparent(task: Any) -> str | None:
    """Return the enqueue-time W3C traceparent carried by the task, if any."""
    kwargs = getattr(task, "kwargs", None)
    if not isinstance(kwargs, Mapping):
        return None
    traceparent = kwargs.get("traceparent")
    return traceparent if isinstance(traceparent, str) and traceparent else None


def _queue_name() -> str:
    """Return the Huey queue (instance) name; the import is deferred (cycle)."""
    try:
        from src.worker import huey  # noqa: PLC0415

        name = getattr(huey, "name", None)
    except Exception as error:  # noqa: BLE001
        logger.debug("Failed to resolve the huey queue name: %s", error)
        return ""
    return str(name) if name else ""


def _evict_oldest_start() -> None:
    """Drop the oldest in-flight entry once the bounded map is full."""
    while len(_TASK_START_TIMES) >= MAX_IN_FLIGHT_TASKS:
        oldest = next(iter(_TASK_START_TIMES), None)
        if oldest is None:
            return
        _TASK_START_TIMES.pop(oldest, None)


def record_task_start(task: Any) -> None:
    """Record the monotonic start time of a task execution, keyed by task id.

    A retried attempt emits ``SIGNAL_EXECUTING`` again and overwrites its own
    entry, so the duration always covers the latest attempt only.
    """
    if task is None:
        return
    try:
        task_id = _task_id(task)
        if task_id is None:
            return
        if task_id not in _TASK_START_TIMES:
            _evict_oldest_start()
        _TASK_START_TIMES[task_id] = time.monotonic()
    except Exception as error:  # noqa: BLE001
        logger.debug("Failed to record the task start time: %s", error)


def _consume_task_start(task_id: str | None) -> float | None:
    """Pop and return the recorded start time so it can never go stale."""
    if task_id is None:
        return None
    return _TASK_START_TIMES.pop(task_id, None)


@contextmanager
def _attached_task_context(task: Any) -> Iterator[None]:
    """Attach the trace context carried by the task for the duration of a block."""
    token = None
    traceparent = _task_traceparent(task)
    if traceparent:
        try:
            token = context.attach(propagate.extract({"traceparent": traceparent}))
        except Exception as error:  # noqa: BLE001
            logger.debug("Failed to restore the task trace context: %s", error)
            token = None
    try:
        yield
    finally:
        if token is not None:
            context.detach(token)


def emit_task_event(
    task: Any,
    status: str,
    duration_ms: float | None = None,
    error_slug: str | None = None,
) -> None:
    """Emit one ``huey.task`` event for a task that reached a terminal state.

    ``duration_ms`` is derived from the start time recorded by
    :func:`record_task_start` unless supplied explicitly. A missing start entry
    (for example a task interrupted before it started executing) drops the field
    instead of reporting a stale duration.
    """
    if task is None:
        return
    try:
        task_id = _task_id(task)
        started_at = _consume_task_start(task_id)
        if duration_ms is None and started_at is not None:
            duration_ms = round((time.monotonic() - started_at) * 1000, 3)

        fields: dict[str, Any] = {
            "task_name": _task_name(task),
            "task_id": task_id,
            "queue": _queue_name(),
            "retries": _task_retries(task),
            "status": status,
            "duration_ms": duration_ms,
            "error_slug": error_slug,
        }
        with _attached_task_context(task):
            emit_event(HUEY_TASK_EVENT, **fields)
    except Exception as error:  # noqa: BLE001
        logger.debug("Failed to emit the huey.task event: %s", error)


__all__ = [
    "HUEY_TASK_EVENT",
    "MAX_IN_FLIGHT_TASKS",
    "STATUS_FAILED",
    "STATUS_INTERRUPTED",
    "STATUS_SUCCESS",
    "emit_task_event",
    "record_task_start",
]
