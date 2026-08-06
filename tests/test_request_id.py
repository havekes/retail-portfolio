import logging
import uuid
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from src.core.context import get_request_id, set_request_id
from src.main import app


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
            # Verify valid UUID format
            parsed_uuid = uuid.UUID(header_val)
            assert str(parsed_uuid) == header_val


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

