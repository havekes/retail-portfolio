import logging
import time
import uuid
from typing import Any

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.core.context import request_id_ctx_var, set_request_id

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every HTTP request has an X-Request-ID header,
    attaches it to request state, and sets it in contextvars for log correlation.
    Also logs the request entry and exit within the context.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        header_request_id = request.headers.get("X-Request-ID")
        request_id = header_request_id or str(uuid.uuid4())

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
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx_var.reset(token)
