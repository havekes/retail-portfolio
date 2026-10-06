"""Authenticated intake for browser-reported exceptions.

The frontend error reporter (`frontend/src/lib/api/errorReporter.ts`) POSTs
unhandled browser errors, unhandled promise rejections and SvelteKit
``handleError`` failures to ``/api/v1/observability/exceptions``. The handler
funnels them through the very same :func:`capture_exception` sink as backend and
worker failures (F-OBS-T17) with ``service_name="frontend"``, so one HyperDX
query over ``exception.type``/``deploy_id`` covers the whole stack and the
records inherit the backend ``deploy_id``/``release`` tags.

The request model is a trust boundary: the browser payload is attacker
controllable, so every field is length-capped and screened before it becomes a
telemetry attribute. :mod:`src.observability.redaction` runs afterwards on the
way out (`capture_exception` -> `_record_on_span`). Intake is also rate limited
per authenticated user so a runaway SPA loop cannot flood the error inbox
(F-OBS-FIX-T03).
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from src.auth.api import current_user
from src.auth.api_types import User
from src.config.limiter import limiter
from src.observability.exceptions import capture_exception

observability_router = APIRouter(prefix="/observability")

MAX_NAME_LENGTH = 100
MAX_MESSAGE_LENGTH = 500
MAX_STACK_LENGTH = 4000
MAX_ROUTE_LENGTH = 300
MAX_CORRELATION_ID_LENGTH = 64

# Free-form browser strings are only accepted when they match a strict shape:
# an error class name, a W3C trace id, or a pathname (no query/hash/absolute URL).
_SAFE_ERROR_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.]{1,100}$")
_TRACE_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_ROUTE_PATTERN = re.compile(r"^/[^\s?#]*$")


class FrontendError(Exception):
    """Marker exception class for browser-reported failures.

    OpenTelemetry derives ``exception.type`` from the exception class, so the
    real browser error name/message/stack are attached as explicit attributes
    by :func:`capture_frontend_exception` instead.
    """


class FrontendExceptionRequest(BaseModel):
    """Sanitised exception report sent by the browser error reporter."""

    name: str = Field(default="Error", max_length=MAX_NAME_LENGTH)
    message: str = Field(default="", max_length=MAX_MESSAGE_LENGTH)
    stack: str | None = Field(default=None, max_length=MAX_STACK_LENGTH)
    correlation_id: str | None = Field(
        default=None, max_length=MAX_CORRELATION_ID_LENGTH
    )
    route: str | None = Field(default=None, max_length=MAX_ROUTE_LENGTH)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        candidate = value.strip()
        if _SAFE_ERROR_NAME_PATTERN.match(candidate):
            return candidate
        return "Error"

    @field_validator("message", "stack")
    @classmethod
    def _normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("correlation_id")
    @classmethod
    def _normalize_correlation_id(cls, value: str | None) -> str | None:
        """Keep a W3C trace id only; anything else is dropped, never echoed."""
        if value is None:
            return None
        candidate = value.strip().lower().replace("-", "")
        if _TRACE_ID_PATTERN.match(candidate):
            return candidate
        return None

    @field_validator("route")
    @classmethod
    def _normalize_route(cls, value: str | None) -> str | None:
        """Accept a pathname only — never a query string, hash or absolute URL."""
        if value is None:
            return None
        candidate = value.strip()
        if _ROUTE_PATTERN.match(candidate):
            return candidate
        return None


def _preview(payload: FrontendExceptionRequest) -> str:
    """Return a short single-line message/first-stack-frame preview."""
    parts = [payload.message] if payload.message else []
    if payload.stack:
        parts.append(payload.stack.splitlines()[0].strip())
    return " | ".join(part for part in parts if part)[:MAX_MESSAGE_LENGTH]


@observability_router.post(
    "/exceptions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Record a browser exception in the shared error inbox",
)
@limiter.limit("30/minute")
async def capture_frontend_exception(
    request: Request,  # noqa: ARG001
    payload: FrontendExceptionRequest,
    user: Annotated[User, Depends(current_user)],
) -> Response:
    """Forward one browser-side exception to the OTel error inbox.

    Returns ``204`` with no body on purpose: the browser only needs an
    acknowledgement, and echoing the payload back would reflect
    attacker-controlled content.

    Rate limited to 30/minute per authenticated user (IP fallback for a
    missing/invalid token; see :func:`src.config.limiter.user_or_ip_key_func`):
    a real user never reports that often, but a runaway SPA loop would.
    """
    attributes: dict[str, Any] = {
        "error_name": payload.name,
        "preview": _preview(payload),
        # Override the SDK-derived values so the inbox groups and displays the
        # browser error, not this request's own Python traceback.
        "exception.type": payload.name,
        "exception.message": payload.message or payload.name,
    }
    if payload.stack:
        attributes["exception.stacktrace"] = payload.stack
    if payload.correlation_id:
        attributes["correlation_id"] = payload.correlation_id
    if payload.route:
        attributes["route"] = payload.route

    capture_exception(
        FrontendError(payload.message or payload.name),
        service_name="frontend",
        user_id=user.id,
        extra_attributes=attributes,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = [
    "FrontendError",
    "FrontendExceptionRequest",
    "observability_router",
]
