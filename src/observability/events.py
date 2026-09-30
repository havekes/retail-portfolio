from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span, StatusCode

from src.observability.bootstrap import get_tracer
from src.observability.redaction import redact_event_fields

#: Tracer name used for every wide-event span.
EVENTS_TRACER_NAME = "observability.events"

#: The canonical wide-event catalog. Every catalog event is emitted as one span
#: named after the event and carrying the shared envelope attributes.
CATALOG_EVENTS: frozenset[str] = frozenset(
    {
        "alert.evaluated",
        "auth.event",
        "http.request",
        "huey.task",
        "market.cache.accessed",
        "market.data.fetched",
        "portfolio.sync.completed",
        "portfolio.sync.failed",
        "ws.delivery",
    }
)

#: Envelope attribute names, queryable in HyperDX/ClickHouse.
ATTRIBUTE_EVENT_NAME = "event.name"
ATTRIBUTE_TRACE_ID = "trace_id"
ATTRIBUTE_SPAN_ID = "span_id"
ATTRIBUTE_PARENT_SPAN_ID = "parent_span_id"
ATTRIBUTE_SERVICE_NAME = "service.name"
ATTRIBUTE_DEPLOY_ID = "deploy_id"
ATTRIBUTE_ENVIRONMENT = "environment"
ATTRIBUTE_TIMESTAMP = "timestamp"
ATTRIBUTE_TIMESTAMP_UNIX_MILLIS = "timestamp_unix_millis"

#: Field values that mark an event as a failure worth retaining unconditionally.
FAILURE_OUTCOMES: frozenset[str] = frozenset({"error", "failed", "failure"})

#: Span status description set when an integer ``status`` is a 5xx.
HTTP_ERROR_STATUS_REASON = "http_status_5xx"

#: Lowest integer HTTP status treated as a server failure.
HTTP_SERVER_ERROR_STATUS = 500

_PRIMITIVE_TYPES: tuple[type, ...] = (bool, int, float, str)
_RESOURCE_ATTRIBUTE_KEYS: tuple[tuple[str, str], ...] = (
    (ATTRIBUTE_SERVICE_NAME, "service.name"),
    (ATTRIBUTE_DEPLOY_ID, "deploy_id"),
    (ATTRIBUTE_ENVIRONMENT, "deployment.environment"),
)


@dataclass(frozen=True)
class EventEnvelope:
    """
    The stable wide-event envelope shared by every catalog event.

    ``to_dict()`` returns the envelope plus a nested ``fields`` mapping for
    logging/assertions; ``to_attributes()`` returns the flat, OpenTelemetry-safe
    attribute set applied to the exported span (non-primitive values are
    JSON-serialized, ``None`` values are dropped).
    """

    event_name: str
    timestamp: datetime
    trace_id: str
    span_id: str
    service_name: str
    deploy_id: str
    environment: str
    fields: dict[str, Any] = field(default_factory=dict)

    @property
    def timestamp_unix_millis(self) -> int:
        """Timestamp as Unix epoch milliseconds."""
        return int(self.timestamp.timestamp() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Return the envelope as a plain, JSON-friendly mapping."""
        return {
            ATTRIBUTE_EVENT_NAME: self.event_name,
            ATTRIBUTE_TIMESTAMP: self.timestamp.isoformat(),
            ATTRIBUTE_TIMESTAMP_UNIX_MILLIS: self.timestamp_unix_millis,
            ATTRIBUTE_TRACE_ID: self.trace_id,
            ATTRIBUTE_SPAN_ID: self.span_id,
            ATTRIBUTE_SERVICE_NAME: self.service_name,
            ATTRIBUTE_DEPLOY_ID: self.deploy_id,
            ATTRIBUTE_ENVIRONMENT: self.environment,
            "fields": dict(self.fields),
        }

    def to_attributes(self) -> dict[str, Any]:
        """Return the flat span attributes for this envelope."""
        attributes: dict[str, Any] = {
            ATTRIBUTE_EVENT_NAME: self.event_name,
            ATTRIBUTE_TIMESTAMP: self.timestamp.isoformat(),
            ATTRIBUTE_TIMESTAMP_UNIX_MILLIS: self.timestamp_unix_millis,
            ATTRIBUTE_TRACE_ID: self.trace_id,
            ATTRIBUTE_SPAN_ID: self.span_id,
            ATTRIBUTE_SERVICE_NAME: self.service_name,
            ATTRIBUTE_DEPLOY_ID: self.deploy_id,
            ATTRIBUTE_ENVIRONMENT: self.environment,
        }
        attributes.update(_to_span_attributes(self.fields))
        return attributes


def _get_sdk_resource_attributes() -> dict[str, str]:
    """
    Read the envelope resource attributes from the bootstrapped SDK Resource.

    Reuses the resource built by ``bootstrap_observability`` instead of
    re-reading ``Settings`` on every emission.
    """
    provider: Any = trace.get_tracer_provider()
    resource: Any = getattr(provider, "resource", None)
    resource_attributes: Any = getattr(resource, "attributes", None) or {}
    return {
        attribute: str(resource_attributes.get(source, ""))
        for attribute, source in _RESOURCE_ATTRIBUTE_KEYS
    }


def _to_attribute_value(value: Any) -> Any | None:
    """Convert an arbitrary field value into an OpenTelemetry-safe attribute."""
    if value is None:
        return None
    if isinstance(value, _PRIMITIVE_TYPES):
        return value
    if isinstance(value, list | tuple):
        if not value:
            return []
        items = [_to_attribute_value(item) for item in value]
        resolved = [item for item in items if item is not None]
        if len(resolved) == len(items) and len({type(item) for item in resolved}) == 1:
            return resolved
    try:
        return json.dumps(value, default=str)
    except TypeError, ValueError:
        return str(value)


def _to_span_attributes(fields: dict[str, Any]) -> dict[str, Any]:
    """Convert a field mapping into span attributes, dropping ``None`` values."""
    attributes: dict[str, Any] = {}
    for key, value in fields.items():
        converted = _to_attribute_value(value)
        if converted is not None:
            attributes[key] = converted
    return attributes


def _error_reason(fields: dict[str, Any]) -> str | None:
    """Return the failure reason for an event, if it carries one."""
    error_slug = fields.get("error_slug")
    if error_slug:
        return str(error_slug)
    for key in ("status", "outcome"):
        value = fields.get(key)
        if isinstance(value, str) and value.strip().lower() in FAILURE_OUTCOMES:
            return value.strip().lower()
    status = fields.get("status")
    # ``bool`` subclasses ``int``; a boolean status is never an HTTP 5xx.
    if (
        isinstance(status, int)
        and not isinstance(status, bool)
        and status >= HTTP_SERVER_ERROR_STATUS
    ):
        return HTTP_ERROR_STATUS_REASON
    return None


def _mark_parent_event(parent_span: Span, name: str, fields: dict[str, Any]) -> None:
    """Record the event marker on the active parent span, if there is one."""
    if parent_span.get_span_context().is_valid and parent_span.is_recording():
        parent_span.add_event(name, _to_span_attributes(fields))


def emit_event(name: str, **fields: Any) -> EventEnvelope:
    """
    Emit one wide event through the OpenTelemetry pipeline.

    Starts and immediately ends one span named ``name`` carrying the shared
    envelope attributes plus the redacted ``fields``. When an active recording
    span exists, the event also becomes a child span and a marker event on that
    parent, so it shows up in the trace waterfall.
    """
    sanitized_fields = redact_event_fields(fields)
    resource_attributes = _get_sdk_resource_attributes()
    timestamp = datetime.now(UTC)

    parent_span = trace.get_current_span()
    parent_context = parent_span.get_span_context()
    parent_span_id = (
        format(parent_context.span_id, "016x") if parent_context.is_valid else ""
    )

    tracer = get_tracer(EVENTS_TRACER_NAME)
    span = tracer.start_span(name)
    try:
        span_context = span.get_span_context()
        envelope = EventEnvelope(
            event_name=name,
            timestamp=timestamp,
            trace_id=format(span_context.trace_id, "032x"),
            span_id=format(span_context.span_id, "016x"),
            service_name=resource_attributes[ATTRIBUTE_SERVICE_NAME],
            deploy_id=resource_attributes[ATTRIBUTE_DEPLOY_ID],
            environment=resource_attributes[ATTRIBUTE_ENVIRONMENT],
            fields=sanitized_fields,
        )
        attributes = envelope.to_attributes()
        if parent_span_id:
            attributes[ATTRIBUTE_PARENT_SPAN_ID] = parent_span_id
        for key, value in attributes.items():
            span.set_attribute(key, value)

        error_reason = _error_reason(sanitized_fields)
        if error_reason is not None:
            span.set_status(StatusCode.ERROR, error_reason)

        _mark_parent_event(parent_span, name, sanitized_fields)
        return envelope
    finally:
        span.end()
