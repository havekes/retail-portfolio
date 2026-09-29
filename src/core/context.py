from contextvars import ContextVar, Token

from opentelemetry import trace

request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_trace_id() -> str | None:
    """Retrieve the active OpenTelemetry trace ID as a 32-character hex string."""
    span_ctx = trace.get_current_span().get_span_context()
    if span_ctx.is_valid:
        return trace.format_trace_id(span_ctx.trace_id)
    return None


def get_request_id() -> str | None:
    """Retrieve the current correlation/request ID for the context."""
    return get_trace_id() or request_id_ctx_var.get()


def set_request_id(request_id: str | None) -> Token[str | None]:
    """Set the correlation/request ID for the current context."""
    return request_id_ctx_var.set(request_id)


__all__ = [
    "get_request_id",
    "get_trace_id",
    "request_id_ctx_var",
    "set_request_id",
]
