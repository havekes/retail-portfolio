"""Tests for the browser exception intake endpoint (F-OBS-T19).

The endpoint is a trust boundary: the browser payload is attacker controllable,
so these tests pin both the happy path (one capture, ``service_name="frontend"``,
correlation id + route attributes) and the screening of hostile input. No
tracing backend, Redis or HTTP egress is involved. Since F-OBS-FIX-T03 the
endpoint is additionally rate limited per authenticated user; those tests use the
in-memory limiter storage that ``ENVIRONMENT=test`` selects.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import jwt
import pytest
from fastapi import APIRouter, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from src.auth.api import current_user
from src.auth.api_types import User
from src.config.limiter import limiter, user_or_ip_key_func
from src.config.settings import Settings
from src.config.settings import settings as app_settings
from src.main import app
from src.observability import bootstrap_observability, reset_observability
from src.observability import router as router_module

DEPLOY_ID = "deploy-frontend-test-1"
CORRELATION_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
ENDPOINT = "/api/v1/observability/exceptions"

VALID_PAYLOAD: dict[str, Any] = {
    "name": "TypeError",
    "message": "Cannot read properties of undefined (reading 'id')",
    "stack": (
        "TypeError: Cannot read properties of undefined (reading 'id')\n"
        "    at renderPortfolio (/app/src/routes/portfolios/+page.svelte:42:9)"
    ),
    "correlation_id": CORRELATION_ID.upper(),
    "route": "/portfolios",
}


@pytest.fixture(autouse=True)
def _cleanup_observability():
    yield
    reset_observability()


@pytest.fixture
def frontend_user() -> User:
    return User(
        id=UUID("11111111-2222-3333-4444-555555555555"), email="ops@example.com"
    )


@pytest.fixture
def authenticated_app(frontend_user: User):
    """Real app with the auth dependency replaced by a fixed user."""
    app.dependency_overrides[current_user] = lambda: frontend_user
    yield app
    app.dependency_overrides.pop(current_user, None)


async def _post(payload: dict[str, Any], target: FastAPI = app):
    transport = ASGITransport(app=target)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(ENDPOINT, json=payload)


def _build_uninstrumented_app(frontend_user: User) -> FastAPI:
    """Uninstrumented app with the same v1 wiring as ``src.main``.

    Without the FastAPI auto-instrumentation the capture cannot land on an
    ambient server span, so the emitted record is the standalone
    ``frontend.exception`` span — the shape asserted in the T17 tests.
    """
    test_app = FastAPI()
    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(router_module.observability_router)
    test_app.include_router(v1)
    test_app.dependency_overrides[current_user] = lambda: frontend_user
    return test_app


def _bootstrap_with_exporter() -> tuple[InMemorySpanExporter, Settings]:
    """Attach an in-memory exporter so capture is enabled under ENVIRONMENT=test."""
    exporter = InMemorySpanExporter()
    settings = Settings(environment="test", deploy_id=DEPLOY_ID)
    bootstrap_observability(
        service_name="backend",
        settings=settings,
        span_processor=SimpleSpanProcessor(exporter),
    )
    return exporter, settings


# --------------------------------------------------------------------------- #
# AC1 — the endpoint requires authentication
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_frontend_exception_requires_authentication():
    response = await _post(VALID_PAYLOAD)

    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# AC2 — a browser report becomes one capture_exception call for the frontend
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_frontend_exception_calls_capture_with_frontend_service(
    authenticated_app: FastAPI, frontend_user: User, monkeypatch
):
    calls: list[tuple[Any, dict[str, Any]]] = []

    def _record(exc: BaseException, **kwargs: Any) -> None:
        calls.append((exc, kwargs))

    monkeypatch.setattr(router_module, "capture_exception", _record)

    response = await _post(VALID_PAYLOAD, target=authenticated_app)

    assert response.status_code == 204
    assert response.content == b""

    assert len(calls) == 1
    exc, kwargs = calls[0]
    assert isinstance(exc, router_module.FrontendError)
    assert kwargs["service_name"] == "frontend"
    assert kwargs["user_id"] == frontend_user.id

    attributes = kwargs["extra_attributes"]
    # The trace id is normalised to lowercase hex regardless of input casing.
    assert attributes["correlation_id"] == CORRELATION_ID
    assert attributes["route"] == "/portfolios"
    assert attributes["error_name"] == "TypeError"
    assert attributes["exception.type"] == "TypeError"
    assert attributes["exception.message"] == VALID_PAYLOAD["message"]
    assert attributes["exception.stacktrace"] == VALID_PAYLOAD["stack"]
    assert "reading" in attributes["preview"]


# --------------------------------------------------------------------------- #
# AC3 — the inbound payload is screened, never trusted
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_frontend_exception_drops_hostile_values(
    authenticated_app: FastAPI, monkeypatch
):
    calls: list[dict[str, Any]] = []

    def _record(exc: BaseException, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(router_module, "capture_exception", _record)

    response = await _post(
        {
            "name": "<script>alert(1)</script>",
            "message": "boom",
            "correlation_id": "not-a-trace-id",
            "route": "https://evil.example.com/steal?token=secret",
        },
        target=authenticated_app,
    )

    assert response.status_code == 204
    assert len(calls) == 1
    attributes = calls[0]["extra_attributes"]
    # Unsafe values are replaced or dropped, never echoed back as telemetry.
    assert attributes["error_name"] == "Error"
    assert attributes["exception.type"] == "Error"
    assert "correlation_id" not in attributes
    assert "route" not in attributes
    assert "https://evil.example.com" not in str(attributes)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "override",
    [
        {"message": "x" * 501},
        {"stack": "y" * 4001},
        {"name": "z" * 101},
        {"route": "/" + "a" * 300},
        {"correlation_id": "c" * 65},
    ],
)
async def test_frontend_exception_rejects_oversized_fields(
    authenticated_app: FastAPI, override: dict[str, str]
):
    response = await _post({**VALID_PAYLOAD, **override}, target=authenticated_app)

    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# AC1 — the report lands in the error inbox with the deploy/release tags
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_frontend_exception_lands_in_error_inbox_with_deploy_tags(
    frontend_user: User, monkeypatch
):
    monkeypatch.setattr(app_settings, "deploy_id", DEPLOY_ID)
    exporter, _ = _bootstrap_with_exporter()
    test_app = _build_uninstrumented_app(frontend_user)

    response = await _post(VALID_PAYLOAD, target=test_app)
    assert response.status_code == 204

    spans = [
        span
        for span in exporter.get_finished_spans()
        if span.name == "frontend.exception"
    ]
    assert len(spans) == 1
    span = spans[0]
    attributes = dict(span.attributes or {})

    assert attributes["service"] == "frontend"
    assert attributes["service.name"] == "frontend"
    assert attributes["deploy_id"] == DEPLOY_ID
    assert attributes["release"] == DEPLOY_ID
    assert attributes["user_id"] == str(frontend_user.id)
    assert attributes["correlation_id"] == CORRELATION_ID
    assert attributes["route"] == "/portfolios"

    events = [event for event in span.events if event.name == "exception"]
    assert len(events) == 1
    event_attributes = dict(events[0].attributes or {})
    assert event_attributes["exception.type"] == "TypeError"
    assert event_attributes["exception.message"] == VALID_PAYLOAD["message"]
    assert str(event_attributes["exception.stacktrace"]).startswith("TypeError")
    assert event_attributes["deploy_id"] == DEPLOY_ID


# --------------------------------------------------------------------------- #
# Robustness
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_frontend_exception_minimal_payload_is_accepted(
    authenticated_app: FastAPI, monkeypatch
):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        router_module,
        "capture_exception",
        lambda exc, **kwargs: calls.append(kwargs),
    )

    response = await _post({"name": "Error"}, target=authenticated_app)

    assert response.status_code == 204
    assert len(calls) == 1
    attributes = calls[0]["extra_attributes"]
    assert attributes["error_name"] == "Error"
    assert "correlation_id" not in attributes
    assert "route" not in attributes
    assert "exception.stacktrace" not in attributes


def test_frontend_exception_request_model_defaults():
    payload = router_module.FrontendExceptionRequest()

    assert payload.name == "Error"
    assert payload.message == ""
    assert payload.stack is None
    assert payload.correlation_id is None
    assert payload.route is None


# --------------------------------------------------------------------------- #
# F-OBS-FIX-T03 — intake is rate limited per authenticated user
# --------------------------------------------------------------------------- #

# Kept in sync with the ``@limiter.limit("30/minute")`` decorator on
# ``capture_frontend_exception``.
RATE_LIMIT_MAX = 30


@pytest.fixture
def reset_limiter():
    """Isolate slowapi's in-memory counters from neighbouring tests."""
    limiter.reset()
    yield
    # The cap is 30/minute on one key: without the teardown reset the following
    # tests in this module (and suite) would inherit a spent budget.
    limiter.reset()


@pytest.mark.anyio
async def test_frontend_exception_is_rate_limited_after_the_cap(
    authenticated_app: FastAPI, monkeypatch, reset_limiter
):
    monkeypatch.setattr(
        router_module, "capture_exception", lambda exc, **kwargs: None
    )

    transport = ASGITransport(app=authenticated_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(RATE_LIMIT_MAX):
            response = await client.post(ENDPOINT, json=VALID_PAYLOAD)
            assert response.status_code == 204

        # The decorator is only applied when the endpoint takes a `Request`
        # parameter — without it this would stay 204 forever.
        response = await client.post(ENDPOINT, json=VALID_PAYLOAD)

    assert response.status_code == 429


def _build_request(
    headers: dict[str, str] | None = None,
    client_ip: str = "192.168.1.100",
) -> Request:
    """Build a bare ``Request`` so the limiter key function can be probed."""
    header_list = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": ENDPOINT,
        "headers": header_list,
        "client": (client_ip, 12345),
    }
    return Request(scope)


def test_frontend_exception_limit_key_is_the_authenticated_user():
    """The 30/minute budget is per user, not per client IP.

    ``get_remote_address`` is constant under ``ASGITransport``, so requesting the
    same budget through varying IPs cannot tell user keying and IP keying apart;
    the honest pin is the key function itself.
    """
    token = jwt.encode(
        {"user_id": "user-rl-1"}, app_settings.secret_key, algorithm="HS256"
    )
    first = _build_request(
        headers={"Authorization": f"Bearer {token}"}, client_ip="10.0.0.1"
    )
    second = _build_request(
        headers={"Authorization": f"Bearer {token}"}, client_ip="10.0.0.2"
    )

    assert user_or_ip_key_func(first) == "user:user-rl-1"
    assert user_or_ip_key_func(second) == "user:user-rl-1"

    # ... and that key function is the one the endpoint's limiter is built with.
    assert app.state.limiter is limiter
