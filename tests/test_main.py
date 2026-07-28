import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from src.config.settings import settings
from src.core.exception import AuthorizationError, EntityNotFoundError
from src.main import (
    authorization_error_handler,
    catch_all_exception_handler,
    cors_exception_middleware,
    entity_not_found_error_handler,
)


@pytest.mark.anyio
async def test_health_live(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.anyio
async def test_health_ready(monkeypatch, client):
    # Setup mock for redis client context manager
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True

    @asynccontextmanager
    async def mock_client():
        yield mock_redis

    monkeypatch.setattr("src.main.redis_manager.client", mock_client)

    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.anyio
async def test_ping(client):
    response = await client.get("/api/ping")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_catch_all_exception_handler_dev_logging(monkeypatch):
    monkeypatch.setattr(settings, "environment", "dev")
    test_exc = RuntimeError("Dev 500 error")

    scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
    request = Request(scope)

    mock_logger_exception = MagicMock()
    monkeypatch.setattr("src.main.logger.exception", mock_logger_exception)

    response = await catch_all_exception_handler(request, test_exc)

    assert response.status_code == 500
    data = json.loads(response.body.decode())
    assert data["error"] == "Dev 500 error"
    mock_logger_exception.assert_called_once_with(
        "Unhandled exception caught by FastAPI handler:", exc_info=test_exc
    )


@pytest.mark.anyio
async def test_cors_middleware_dev_logging(monkeypatch):
    monkeypatch.setattr(settings, "environment", "dev")

    test_exc = RuntimeError("Middleware error")

    async def mock_call_next(request):
        raise test_exc

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [(b"origin", b"http://localhost:3000")],
    }
    request = Request(scope)

    mock_logger_exception = MagicMock()
    monkeypatch.setattr("src.main.logger.exception", mock_logger_exception)

    response = await cors_exception_middleware(request, mock_call_next)

    assert response.status_code == 500
    data = json.loads(response.body.decode())
    assert data["error"] == "Middleware error"
    mock_logger_exception.assert_called_once_with(
        "Unhandled exception in middleware safety net:", exc_info=test_exc
    )


class SampleEntityNotFoundError(EntityNotFoundError):
    entity_id = "123"
    entity_name = "Item"


@pytest.mark.anyio
async def test_entity_not_found_error_handler_dev_logging(monkeypatch):
    monkeypatch.setattr(settings, "environment", "dev")
    test_exc = SampleEntityNotFoundError()

    scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
    request = Request(scope)

    mock_logger_exception = MagicMock()
    monkeypatch.setattr("src.main.logger.exception", mock_logger_exception)

    response = await entity_not_found_error_handler(request, test_exc)

    assert response.status_code == 404
    data = json.loads(response.body.decode())
    assert data["error"] == "Entity Item with ID 123 not found."
    mock_logger_exception.assert_called_once_with("Entity Item with ID 123 not found.", exc_info=test_exc)


class SampleAuthorizationError(AuthorizationError):
    def log_message(self) -> str:
        return "User 123 unauthorized for resource 456"


@pytest.mark.anyio
async def test_authorization_error_handler_dev_logging(monkeypatch):
    monkeypatch.setattr(settings, "environment", "dev")
    test_exc = SampleAuthorizationError()

    scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
    request = Request(scope)

    mock_logger_exception = MagicMock()
    monkeypatch.setattr("src.main.logger.exception", mock_logger_exception)

    response = await authorization_error_handler(request, test_exc)

    assert response.status_code == 404
    data = json.loads(response.body.decode())
    assert data["error"] == "User is not authorized to perform this action."
    mock_logger_exception.assert_called_once_with(
        "User 123 unauthorized for resource 456", exc_info=test_exc
    )
