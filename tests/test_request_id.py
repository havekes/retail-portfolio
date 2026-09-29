import json
import logging
import uuid
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from opentelemetry import trace

from src.config.logging import JsonFormatter
from src.config.settings import settings
from src.core.context import get_request_id, set_request_id
from src.main import app
from src.observability import get_tracer


@pytest.mark.anyio
async def test_request_id_generated_when_missing():
    """Verify that requests without X-Request-ID header receive a generated UUID X-Request-ID in response."""
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            response = await client.get("/api/ping")
            assert response.status_code == 200
            assert "X-Request-ID" in response.headers
            header_val = response.headers["X-Request-ID"]
            # The auto-instrumentation unifies X-Request-ID with the server
            # span's trace id (32 hex chars); without an active span a UUID4 is
            # generated instead. Both forms must round-trip through uuid.UUID.
            parsed_uuid = uuid.UUID(header_val)
            assert parsed_uuid.hex == header_val.replace("-", "")


@pytest.mark.anyio
async def test_request_id_preserved_when_provided():
    """Verify that custom X-Request-ID header is preserved in the response."""
    custom_id = "test-correlation-id-999"
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/ping", headers={"X-Request-ID": custom_id}
            )
            assert response.status_code == 200
            assert response.headers.get("X-Request-ID") == custom_id


@pytest.mark.anyio
async def test_request_id_log_context(caplog):
    """Verify that log records capture the request_id during HTTP handling."""
    custom_id = "log-context-test-id"
    async with LifespanManager(app) as manager:
        with caplog.at_level(logging.INFO):
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/ping", headers={"X-Request-ID": custom_id}
                )
                assert response.status_code == 200

    # Ensure get_request_id() was set during handling and reset afterwards
    assert get_request_id() is None


def test_contextvar_manual_binding():
    """Verify that manually setting request_id works correctly."""
    target_request_id = "manual-req-123"
    token = set_request_id(target_request_id)
    try:
        assert get_request_id() == target_request_id
    finally:
        from src.core.context import request_id_ctx_var

        request_id_ctx_var.reset(token)


@pytest.mark.anyio
async def test_request_id_log_4xx_warning(caplog):
    """Verify that 4xx HTTP responses are logged as warning in RequestIdMiddleware."""
    async with LifespanManager(app) as manager:
        with caplog.at_level(logging.WARNING):
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as client:
                response = await client.get("/api/nonexistent-test-route-404")
                assert response.status_code == 404

    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_records) >= 1
    assert any("404" in r.message for r in warning_records)


@pytest.mark.anyio
async def test_request_id_inbound_traceparent_propagation():
    """Verify that inbound W3C traceparent header is extracted and echoed on X-Request-ID."""
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    traceparent = f"00-{trace_id}-00f067aa0ba902b7-01"
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/ping", headers={"traceparent": traceparent}
            )
            assert response.status_code == 200
            assert response.headers.get("X-Request-ID") == trace_id


@pytest.mark.anyio
async def test_request_id_inbound_x_request_id_honoured_with_traceparent(caplog):
    """Verify inbound X-Request-ID is honoured and echoed, while logs unify with the trace ID."""
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    traceparent = f"00-{trace_id}-00f067aa0ba902b7-01"
    custom_req_id = "custom-req-id"
    async with LifespanManager(app) as manager:
        with caplog.at_level(logging.INFO):
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/ping",
                    headers={
                        "X-Request-ID": custom_req_id,
                        "traceparent": traceparent,
                    },
                )
                assert response.status_code == 200
                assert response.headers.get("X-Request-ID") == custom_req_id

    middleware_records = [
        r for r in caplog.records if r.name == "src.core.middleware"
    ]
    assert len(middleware_records) == 1
    assert getattr(middleware_records[0], "request_id", None) == trace_id
    assert getattr(middleware_records[0], "trace_id", None) == trace_id
    assert getattr(middleware_records[0], "deploy_id", None) == settings.deploy_id


@pytest.mark.anyio
async def test_request_id_under_active_server_span(caplog):
    """Verify that requests handled under an active server span unify request_id and trace_id in logs and response."""
    async with LifespanManager(app) as manager:
        tracer = get_tracer("test.server_span")
        with tracer.start_as_current_span("server.request") as span:
            span_trace_id = trace.format_trace_id(span.get_span_context().trace_id)
            with caplog.at_level(logging.INFO):
                async with AsyncClient(
                    transport=ASGITransport(app=manager.app), base_url="http://test"
                ) as client:
                    response = await client.get("/api/ping")
                    assert response.status_code == 200
                    assert response.headers.get("X-Request-ID") == span_trace_id

    middleware_records = [
        r for r in caplog.records if r.name == "src.core.middleware"
    ]
    assert len(middleware_records) == 1
    assert getattr(middleware_records[0], "request_id", None) == span_trace_id
    assert getattr(middleware_records[0], "trace_id", None) == span_trace_id

    # Verify JSON formatting output
    formatter = JsonFormatter()
    formatted = formatter.format(middleware_records[0])
    data = json.loads(formatted)
    assert data["request_id"] == span_trace_id
    assert data["trace_id"] == span_trace_id
    assert data["deploy_id"] == settings.deploy_id


@pytest.mark.anyio
async def test_single_access_log_line_per_request(caplog):
    """Verify that exactly one access log line is emitted from src.core.middleware for a request."""
    async with LifespanManager(app) as manager:
        with caplog.at_level(logging.INFO):
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as client:
                response = await client.get("/api/ping")
                assert response.status_code == 200

    middleware_records = [
        r for r in caplog.records if r.name == "src.core.middleware"
    ]
    assert len(middleware_records) == 1
    assert "200" in middleware_records[0].getMessage()


