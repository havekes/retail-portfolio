import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import svcs
from fastapi.testclient import TestClient
from itsdangerous import URLSafeTimedSerializer
from starlette.websockets import WebSocketDisconnect

from src.auth.api import UserApi
from src.auth.api_types import User
from src.config.database import sessionmanager
from src.config.services import register_services
from src.config.settings import settings
from src.main import app
from src.ws.router import _check_ticket_not_replayed


@pytest.fixture
def client():
    if not hasattr(app.state, "svcs_registry") or app.state.svcs_registry is None:
        registry = svcs.Registry()
        register_services(registry, sessionmanager)
        app.state.svcs_registry = registry

    with TestClient(app) as c:
        yield c


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def dummy_user(user_id):
    return User(
        id=user_id,
        email="test@example.com",
        first_name="Test",
        last_name="User",
        is_active=True,
    )


def make_mock_svcs_container(user_api_mock):
    mock_container = AsyncMock()
    mock_container.aget.return_value = user_api_mock
    mock_container.__aenter__.return_value = mock_container
    mock_container.__aexit__.return_value = None
    return mock_container


# --- Unit tests for _check_ticket_not_replayed ---

@pytest.mark.asyncio
async def test_check_ticket_not_replayed_first_use():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = "OK"

    with patch("redis.asyncio.from_url", return_value=mock_redis):
        result = await _check_ticket_not_replayed("ticket123", "redis://localhost:6379")
        assert result is True
        mock_redis.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_check_ticket_not_replayed_already_used():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = None

    with patch("redis.asyncio.from_url", return_value=mock_redis):
        result = await _check_ticket_not_replayed("ticket123", "redis://localhost:6379")
        assert result is False
        mock_redis.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_check_ticket_not_replayed_exception_handled():
    mock_redis = AsyncMock()
    mock_redis.set.side_effect = Exception("Redis connection error")

    with patch("redis.asyncio.from_url", return_value=mock_redis):
        result = await _check_ticket_not_replayed("ticket123", "redis://localhost:6379")
        assert result is True
        mock_redis.aclose.assert_called_once()


# --- Router integration tests using TestClient ---

def test_websocket_no_auth(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/ws"):
            pass
    assert exc_info.value.code == 1008


def test_websocket_ticket_replayed(client):
    with patch("src.ws.router._check_ticket_not_replayed", return_value=False):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/ws?ticket=replayed_ticket"):
                pass
        assert exc_info.value.code == 1008


def test_websocket_ticket_invalid_signature(client):
    with patch("src.ws.router._check_ticket_not_replayed", return_value=True):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/ws?ticket=invalid_ticket_payload"):
                pass
        assert exc_info.value.code == 1008


def test_websocket_ticket_valid(client, user_id):
    serializer = URLSafeTimedSerializer(settings.secret_key)
    valid_ticket = serializer.dumps(json.dumps({"user_id": str(user_id)}), salt="ws-ticket")

    with patch("src.ws.router._check_ticket_not_replayed", return_value=True):
        with client.websocket_connect(f"/api/ws?ticket={valid_ticket}") as websocket:
            assert websocket is not None


def test_websocket_token_cookie_valid(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    with patch("svcs.Container", return_value=mock_container):
        with client.websocket_connect("/api/ws", cookies={"auth_token": "valid_token"}) as websocket:
            assert websocket is not None
        mock_user_api.get_current_user_from_token.assert_called_once_with("valid_token")


def test_websocket_token_header_valid(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    with patch("svcs.Container", return_value=mock_container):
        client.cookies.set("dummy", "value")  # or header
        with client.websocket_connect(
            "/api/ws",
            headers={"sec-websocket-protocol": "valid_token"},
            subprotocols=["valid_token"]
        ) as websocket:
            assert websocket is not None
        mock_user_api.get_current_user_from_token.assert_called_once_with("valid_token")


def test_websocket_token_invalid(client):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.side_effect = Exception("Invalid token")
    mock_container = make_mock_svcs_container(mock_user_api)

    with patch("svcs.Container", return_value=mock_container):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/ws", cookies={"auth_token": "bad_token"}):
                pass
        assert exc_info.value.code == 1008


def test_websocket_with_custom_request_id(client, user_id):
    serializer = URLSafeTimedSerializer(settings.secret_key)
    valid_ticket = serializer.dumps(json.dumps({"user_id": str(user_id)}), salt="ws-ticket")

    with patch("src.ws.router._check_ticket_not_replayed", return_value=True):
        with client.websocket_connect(
            f"/api/ws?ticket={valid_ticket}",
            headers={"X-Request-ID": "custom-req-id-123"}
        ) as websocket:
            assert websocket is not None
