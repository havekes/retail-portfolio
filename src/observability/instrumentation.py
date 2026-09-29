"""Automatic instrumentation for the framework and I/O boundaries.

``instrument_auto`` enables the four instrumentations that produce spans for
the boundaries a Python process owns:

* FastAPI/Starlette — inbound HTTP server spans (with ``traceparent``
  extraction, so an inbound trace is continued rather than restarted).
* SQLAlchemy — database client spans.
* Redis — cache/queue client spans.
* httpx — outbound HTTP client spans.

The I/O instrumentations are process-wide: they wrap the underlying
libraries, so anything that runs inside an active span (a request or a worker
task) records a child span automatically.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.ext.asyncio import AsyncEngine

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def instrument_fastapi(app: FastAPI) -> None:
    """
    Instrument a FastAPI application so every request produces a server span.

    The server span wraps the entire ASGI stack, so it is started before
    ``RequestIdMiddleware`` runs and every database, Redis or httpx span
    created while handling the request becomes its child.

    Re-instrumenting an already instrumented app replaces the middleware with
    one bound to the currently configured tracer provider; this keeps
    per-test providers working after the global provider is swapped.
    """
    instrumentor = FastAPIInstrumentor()
    if getattr(app, "_is_instrumented_by_opentelemetry", False):
        instrumentor.uninstrument_app(app)
    instrumentor.instrument_app(app)
    # Starlette builds and caches the middleware stack lazily on the first
    # call; drop it so the freshly bound tracer is actually used.
    app.middleware_stack = None


def _as_sync_engine(engine: AsyncEngine | Engine | None) -> Engine | None:
    """Return the sync engine of an async engine (SQLAlchemy's tracing target)."""
    if isinstance(engine, AsyncEngine):
        return engine.sync_engine
    return engine


def _resolve_process_engine() -> Engine | None:
    """Return the sync engine of the process-wide session manager, if created."""
    from src.config.database import sessionmanager  # noqa: PLC0415

    engine = sessionmanager.engine
    if engine is None:
        return None
    return engine.sync_engine


def instrument_sqlalchemy(engine: AsyncEngine | Engine | None = None) -> None:
    """
    Instrument SQLAlchemy so queries produce database client spans.

    Engines created after this call are covered by the global
    ``create_engine``/``create_async_engine`` hooks. Engines that already exist
    cannot be seen by those hooks, so one is attached explicitly: the given
    ``engine``, or the process-wide ``sessionmanager`` engine by default.
    """
    instrumentor = SQLAlchemyInstrumentor()
    if instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.uninstrument()

    target = engine if engine is not None else _resolve_process_engine()
    instrumentor.instrument(engine=_as_sync_engine(target))


def instrument_redis() -> None:
    """Instrument Redis clients so cache and queue commands produce client spans."""
    instrumentor = RedisInstrumentor()
    if instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.uninstrument()
    instrumentor.instrument()


def instrument_httpx() -> None:
    """Instrument httpx transports so outbound requests produce client spans."""
    instrumentor = HTTPXClientInstrumentor()
    if instrumentor.is_instrumented_by_opentelemetry:
        instrumentor.uninstrument()
    instrumentor.instrument()


def instrument_auto(app: FastAPI | None = None) -> None:
    """
    Instrument the framework and I/O boundaries of the current process.

    Pass ``app`` to also instrument a FastAPI application. This must run before
    the application starts serving so the server span is the outermost layer.
    """
    if app is not None:
        instrument_fastapi(app)
    instrument_sqlalchemy()
    instrument_redis()
    instrument_httpx()


def uninstrument_auto(app: FastAPI | None = None) -> None:
    """Undo :func:`instrument_auto` (used to rebind instrumentation in tests)."""
    if app is not None:
        FastAPIInstrumentor().uninstrument_app(app)

    for instrumentor in (
        SQLAlchemyInstrumentor(),
        RedisInstrumentor(),
        HTTPXClientInstrumentor(),
    ):
        if instrumentor.is_instrumented_by_opentelemetry:
            instrumentor.uninstrument()
