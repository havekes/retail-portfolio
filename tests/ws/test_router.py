import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import svcs
from fastapi.testclient import TestClient
from itsdangerous import URLSafeTimedSerializer
from starlette.websockets import WebSocketDisconnect
from stockholm import Currency, Money

from src.account.api_types import AccountTotals
from src.auth.api import UserApi
from src.auth.api_types import User
from src.config.database import sessionmanager
from src.config.services import register_services
from src.config.settings import settings
from src.main import app
from src.ws.api_types import AccountTotalsUpdatedMessage, WsEventType
from src.ws.router import _check_ticket_not_replayed

WS_POLICY_VIOLATION = 1008


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
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/ws"),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_websocket_ticket_replayed(client):
    with (
        patch("src.ws.router._check_ticket_not_replayed", return_value=False),
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/ws?ticket=replayed_ticket"),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_websocket_ticket_invalid_signature(client):
    with (
        patch("src.ws.router._check_ticket_not_replayed", return_value=True),
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/ws?ticket=invalid_ticket_payload"),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_websocket_ticket_valid(client, user_id):
    serializer = URLSafeTimedSerializer(settings.secret_key)
    payload = json.dumps({"user_id": str(user_id)})
    valid_ticket = serializer.dumps(payload, salt="ws-ticket")

    with (
        patch("src.ws.router._check_ticket_not_replayed", return_value=True),
        client.websocket_connect(f"/api/ws?ticket={valid_ticket}") as websocket,
    ):
        assert websocket is not None


def test_websocket_token_cookie_valid(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    client.cookies = {"auth_token": "valid_token"}
    with (
        patch("svcs.Container", return_value=mock_container),
        client.websocket_connect("/api/ws") as websocket,
    ):
        assert websocket is not None
    mock_user_api.get_current_user_from_token.assert_called_once_with("valid_token")


def test_websocket_token_header_valid(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    with patch("svcs.Container", return_value=mock_container):
        client.cookies.set("dummy", "value")
        with client.websocket_connect(
            "/api/ws",
            headers={"sec-websocket-protocol": "valid_token"},
            subprotocols=["valid_token"],
        ) as websocket:
            assert websocket is not None
        mock_user_api.get_current_user_from_token.assert_called_once_with("valid_token")


def test_websocket_token_invalid(client):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.side_effect = Exception("Invalid token")
    mock_container = make_mock_svcs_container(mock_user_api)

    client.cookies = {"auth_token": "bad_token"}
    with (
        patch("svcs.Container", return_value=mock_container),
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/ws"),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_account_totals_updated_message_serialization():
    account_id = uuid4()
    msg = AccountTotalsUpdatedMessage(
        account_id=account_id,
        totals=AccountTotals(
            cost=Money(100, Currency.USD),
            value=Money(150, Currency.USD),
        ),
    )
    dumped = msg.model_dump(mode="json")
    assert dumped["type"] == WsEventType.ACCOUNT_TOTALS_UPDATED
    assert dumped["account_id"] == str(account_id)
    assert "cost" in dumped["totals"]
    assert "value" in dumped["totals"]


def test_websocket_with_custom_request_id(client, user_id):
    serializer = URLSafeTimedSerializer(settings.secret_key)
    payload = json.dumps({"user_id": str(user_id)})
    valid_ticket = serializer.dumps(payload, salt="ws-ticket")

    with (
        patch("src.ws.router._check_ticket_not_replayed", return_value=True),
        client.websocket_connect(
            f"/api/ws?ticket={valid_ticket}",
            headers={"X-Request-ID": "custom-req-id-123"},
        ) as websocket,
    ):
        assert websocket is not None
