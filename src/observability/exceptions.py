"""Sink-agnostic OpenTelemetry exception capture for the error inbox.

Unhandled backend and worker exceptions are recorded as plain OpenTelemetry
exception records (span events plus error status) on spans tagged with the
service, deploy/release and unified correlation id. The records ride the
existing OTLP pipeline into the ClickStack collector and are grouped in
HyperDX by querying ``exception.type`` / ``deploy_id`` — no dedicated error
tracking sink is involved.
"""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from opentelemetry import propagate, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    Status,
    StatusCode,
    TraceFlags,
    set_span_in_context,
)

from src.config.settings import Settings
from src.config.settings import settings as app_settings
from src.core.context import get_request_id
from src.observability.bootstrap import get_tracer, is_telemetry_enabled
from src.observability.redaction import RedactingSpanProcessor, redact_event_fields

if TYPE_CHECKING:
    from opentelemetry.context import Context
    from opentelemetry.trace import Span
    from starlette.requests import Request

logger = logging.getLogger(__name__)

TRACER_NAME = "src.observability.exceptions"

# Marker set on an exception once it has been recorded, so the middleware
# safety net and the FastAPI handler cannot double-report the same failure.
CAPTURED_FLAG = "_otel_captured"

_TRACE_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_SAFE_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_safe_user_id(user_id: Any) -> str | None:
    """Return a normalized user id when it is safe to attach to telemetry.

    Emails, whitespace, over-long or otherwise non-identifier values are
    rejected so no personally identifiable data reaches the error inbox.
    """
    if user_id is None or isinstance(user_id, bool):
        return None

    if isinstance(user_id, (int, uuid.UUID)):
        return str(user_id)

    if not isinstance(user_id, str):
        return None

    candidate = user_id.strip()
    rejected = (
        not candidate
        or candidate != user_id
        or "@" in candidate
        or any(char.isspace() for char in candidate)
    )
    if rejected:
        return None
    if _UUID_PATTERN.match(candidate) or _SAFE_USER_ID_PATTERN.match(candidate):
        return candidate
    return None


def _generate_span_id() -> int:
    """Return a non-zero random span id for a synthesized remote parent."""
    return secrets.randbits(64) or 1


def get_parent_context(
    trace_id_str: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> Context | None:
    """Resolve a parent context from W3C traceparent headers or a trace id.

    ``headers`` win when they carry a valid ``traceparent``; otherwise a
    remote, sampled ``SpanContext`` is synthesized from a 32 hex character
    trace id or its UUID form so the emitted span joins that trace.
    """
    if headers:
        extracted = propagate.extract(dict(headers))
        if trace.get_current_span(extracted).get_span_context().is_valid:
            return extracted

    if not trace_id_str:
        return None

    normalized = str(trace_id_str).strip()
    if _UUID_PATTERN.match(normalized):
        normalized = normalized.replace("-", "")
    if not _TRACE_ID_PATTERN.match(normalized):
        return None

    trace_id = int(normalized, 16)
    if trace_id == 0:
        return None

    span_context = SpanContext(
        trace_id=trace_id,
        span_id=_generate_span_id(),
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    return set_span_in_context(NonRecordingSpan(span_context))


def _has_recording_span_processor() -> bool:
    """True when the active provider received an explicit recording processor."""
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        return False

    active_processor = getattr(provider, "_active_span_processor", None)
    processors = getattr(active_processor, "_span_processors", ()) or ()
    return any(
        not isinstance(processor, RedactingSpanProcessor) for processor in processors
    )


def should_capture_telemetry(settings: Settings | None = None) -> bool:
    """Return True only when exception records can actually be delivered.

    Telemetry being enabled is sufficient outside tests. Under
    ``ENVIRONMENT=test`` the SDK is deliberately left unconfigured, so capture
    stays disabled unless a test attached a recording span processor (for
    example an in-memory exporter). This keeps tests hermetic: no exporter, no
    sockets, no network egress.
    """
    effective_settings = settings or app_settings
    if is_telemetry_enabled(effective_settings):
        return True
    if effective_settings.environment.lower() != "test":
        return False
    return _has_recording_span_processor()


def _resolve_task_metadata(task: Any | None) -> tuple[str | None, str | None]:
    """Return ``(task_name, task_id)`` for a Huey task, when available."""
    if task is None:
        return None, None

    name = getattr(task, "name", None)
    task_id = getattr(task, "id", None)
    return (
        str(name) if name else None,
        str(task_id) if task_id else None,
    )


def _resolve_user_id(
    user_id: Any | None, request: Request | None, task: Any | None
) -> str | None:
    """Resolve a safe user id from explicit input, request state or task args."""
    safe_user_id = is_safe_user_id(user_id)
    if safe_user_id:
        return safe_user_id

    if request is not None:
        state = getattr(request, "state", None)
        safe_user_id = is_safe_user_id(getattr(state, "user_id", None))
        if safe_user_id:
            return safe_user_id

    if task is not None:
        kwargs = getattr(task, "kwargs", None)
        if isinstance(kwargs, Mapping):
            safe_user_id = is_safe_user_id(kwargs.get("user_id"))
            if safe_user_id:
                return safe_user_id

        args = getattr(task, "args", None) or ()
        if args:
            safe_user_id = is_safe_user_id(args[0])
            if safe_user_id:
                return safe_user_id

    return None


def _resolve_parent_context(
    request: Request | None, task: Any | None
) -> Context | None:
    """Link a synthesized error span to the originating trace context."""
    if trace.get_current_span().get_span_context().is_valid:
        # An ambient (possibly remote) context is already attached; the new
        # span will simply inherit it.
        return None

    headers: Mapping[str, str] | None = None
    trace_id_str: str | None = None

    if request is not None:
        headers = getattr(request, "headers", None)
        state = getattr(request, "state", None)
        request_id = getattr(state, "request_id", None)
        if isinstance(request_id, str) and request_id.strip():
            trace_id_str = request_id.strip()

    if trace_id_str is None and task is not None:
        kwargs = getattr(task, "kwargs", None)
        if isinstance(kwargs, Mapping):
            task_request_id = kwargs.get("request_id")
            if isinstance(task_request_id, str) and task_request_id.strip():
                trace_id_str = task_request_id.strip()

    if trace_id_str is None:
        trace_id_str = get_request_id()

    return get_parent_context(trace_id_str=trace_id_str, headers=headers)


def _record_on_span(
    span: Span, exc: BaseException, attributes: Mapping[str, Any]
) -> None:
    """Attach error attributes, the exception record and error status."""
    resolved = dict(attributes)
    span_context = span.get_span_context()
    if span_context.is_valid:
        resolved["trace_id"] = trace.format_trace_id(span_context.trace_id)

    redacted = redact_event_fields(resolved)
    for key, value in redacted.items():
        span.set_attribute(key, value)
    span.record_exception(exc, attributes=redacted)
    span.set_status(Status(StatusCode.ERROR))


def capture_exception(  # noqa: PLR0913
    exc: BaseException,
    *,
    service_name: str = "backend",
    request: Request | None = None,
    task: Any | None = None,
    user_id: Any | None = None,
    extra_attributes: Mapping[str, Any] | None = None,
    settings: Settings | None = None,
) -> None:
    """Record an unhandled exception so it appears in the error inbox.

    Produces only standard OpenTelemetry exception records and span
    attributes, so the sink can be swapped without touching call sites.
    Recording is idempotent per exception instance and never raises: telemetry
    must not mask or replace the original failure.
    """
    try:
        if not should_capture_telemetry(settings):
            return
        if getattr(exc, CAPTURED_FLAG, False):
            return
        setattr(exc, CAPTURED_FLAG, True)

        effective_settings = settings or app_settings
        task_name, task_id = _resolve_task_metadata(task)
        safe_user_id = _resolve_user_id(user_id, request, task)
        parent_context = _resolve_parent_context(request, task)

        attributes: dict[str, Any] = {
            "service": service_name,
            "service.name": service_name,
            "deploy_id": effective_settings.deploy_id,
            "release": effective_settings.deploy_id,
        }
        if task_name:
            attributes["task_name"] = task_name
            attributes["task.name"] = task_name
        if task_id:
            attributes["task_id"] = task_id
            attributes["task.id"] = task_id
        if safe_user_id:
            attributes["user_id"] = safe_user_id
        if extra_attributes:
            attributes.update(extra_attributes)

        current_span = trace.get_current_span()
        if current_span.is_recording():
            _record_on_span(current_span, exc, attributes)
            return

        tracer = get_tracer(TRACER_NAME)
        with tracer.start_as_current_span(
            f"{service_name}.exception", context=parent_context
        ) as span:
            _record_on_span(span, exc, attributes)
    except Exception as error:  # noqa: BLE001
        logger.debug("Exception capture failed: %s", error)


__all__ = [
    "CAPTURED_FLAG",
    "TRACER_NAME",
    "capture_exception",
    "get_parent_context",
    "is_safe_user_id",
    "should_capture_telemetry",
]
