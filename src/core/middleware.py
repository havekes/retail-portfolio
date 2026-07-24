import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.core.context import request_id_ctx_var, set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every HTTP request has an X-Request-ID header,
    attaches it to request state, and sets it in contextvars for log correlation.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        header_request_id = request.headers.get("X-Request-ID")
        request_id = header_request_id or str(uuid.uuid4())

        request.state.request_id = request_id
        token = set_request_id(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx_var.reset(token)
