import logging
import time
import uuid
from typing import Any

from opentelemetry import context, propagate, trace
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.core.context import request_id_ctx_var, set_request_id
from src.observability import emit_event

logger = logging.getLogger(__name__)

#: Route label used when no route matched the request (404 and friends). The
#: raw URL path is never used: the dictionary forbids identifier-bearing paths.
UNMATCHED_ROUTE = "unmatched"


def _route_template(request: Request) -> str:
    """Return the matched route template, never the raw identifier-bearing path."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path else UNMATCHED_ROUTE


def _header_bytes(headers: Any, name: str) -> int | None:
    """Return a numeric content-length header value, or ``None`` when unknown."""
    raw = headers.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except TypeError, ValueError:
        return None


def _resolve_user_id(request: Request) -> str | None:
    """
    Resolve the authenticated user id from the request credentials, if any.

    Uses the JWT-only ``UserApi.decode_token`` helper: this boundary has no
    service container, and emitting the event must not trigger a database
    round-trip. Any decode failure leaves the request anonymous.
    """
    token = request.cookies.get("auth_token")
    if not token:
        scheme, _, credentials = (request.headers.get("authorization") or "").partition(
            " "
        )
        if scheme.lower() == "bearer":
            token = credentials.strip()
    if not token:
        return None

    # Imported lazily so the core middleware does not pull the auth stack (and
    # its SQLAlchemy/webauthn dependencies) into every import of the app.
    from src.auth.api import UserApi  # noqa: PLC0415

    try:
        return UserApi.decode_token(token).user_id
    except Exception:
        logger.debug("Could not resolve user_id for http.request", exc_info=True)
        return None


def _emit_http_request_event(
    request: Request,
    status_code: int,
    duration_ms: float,
    response: Response | None = None,
) -> None:
    """
    Emit one ``http.request`` wide event for a finished request.

    Purely additive to the access log: the log record (format, level and
    ``extra``) is untouched. Telemetry failures must never break a response, so
    any emission error is swallowed at debug level.
    """
    try:
        fields: dict[str, Any] = {
            "route": _route_template(request),
            "method": request.method,
            "status": int(status_code),
            "duration_ms": float(duration_ms),
            "client_host": request.client.host if request.client else "unknown",
        }
        request_bytes = _header_bytes(request.headers, "content-length")
        if request_bytes is not None:
            fields["request_bytes"] = request_bytes
        if response is not None:
            response_bytes = _header_bytes(response.headers, "content-length")
            if response_bytes is not None:
                fields["response_bytes"] = response_bytes
        user_id = _resolve_user_id(request)
        if user_id:
            fields["user_id"] = user_id
        emit_event("http.request", **fields)
    except Exception:
        logger.debug("Failed to emit http.request event", exc_info=True)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every HTTP request has an X-Request-ID header,
    attaches it to request state, and sets it in contextvars for log correlation.
    Also logs the request entry and exit within the context.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        otel_token: object | None = None
        current_span = trace.get_current_span()
        span_ctx = current_span.get_span_context()

        if not span_ctx.is_valid:
            extracted_ctx = propagate.extract(request.headers)
            extracted_span = trace.get_current_span(extracted_ctx)
            extracted_span_ctx = extracted_span.get_span_context()
            if extracted_span_ctx.is_valid:
                otel_token = context.attach(extracted_ctx)
                span_ctx = extracted_span_ctx

        active_trace_id = (
            trace.format_trace_id(span_ctx.trace_id) if span_ctx.is_valid else None
        )
        header_request_id = (request.headers.get("X-Request-ID") or "").strip() or None
        request_id = header_request_id or active_trace_id or str(uuid.uuid4())

        request.state.request_id = request_id
        token = set_request_id(request_id)

        start_time = time.time()
        try:
            response = await call_next(request)
        except Exception:
            process_time = time.time() - start_time
            host = request.client.host if request.client else "unknown"
            logger.exception(
                '%s - "%s %s" 500 - %.3fs',
                host,
                request.method,
                request.url.path,
                process_time,
                extra={"duration_ms": int(process_time * 1000)},
            )
            _emit_http_request_event(
                request,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                process_time * 1000,
            )
            raise
        else:
            process_time = time.time() - start_time
            host = request.client.host if request.client else "unknown"
            is_4xx = (
                status.HTTP_400_BAD_REQUEST
                <= response.status_code
                < status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            log_fn = logger.warning if is_4xx else logger.info
            log_fn(
                '%s - "%s %s" %d - %.3fs',
                host,
                request.method,
                request.url.path,
                response.status_code,
                process_time,
                extra={"duration_ms": int(process_time * 1000)},
            )
            _emit_http_request_event(
                request,
                response.status_code,
                process_time * 1000,
                response=response,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx_var.reset(token)
            if otel_token is not None:
                context.detach(otel_token)
