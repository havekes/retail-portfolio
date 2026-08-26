import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import svcs
from fastapi.testclient import TestClient
from huey_dashboard.models.task import TaskInfo
from huey_dashboard.services.websocket_manager import WebSocketManager
from itsdangerous import URLSafeTimedSerializer
from starlette.websockets import WebSocketDisconnect

from src.auth.api import UserApi
from src.auth.api_types import User
from src.config.database import sessionmanager
from src.config.services import register_services
from src.config.settings import settings
from src.main import app

WS_POLICY_VIOLATION = 1008


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def dummy_user(user_id):
    return User(
        id=user_id,
        email="worker-admin@example.com",
    )


@pytest.fixture
def mock_task_db():
    mock_db = AsyncMock()
    mock_db.get_all_tasks.return_value = [
        TaskInfo(id="task-1", name="sync_broker_task", status="complete"),
        TaskInfo(id="task-2", name="fetch_prices_task", status="pending"),
    ]

    async def get_task_side_effect(task_id: str):
        if task_id == "task-1":
            return TaskInfo(id="task-1", name="sync_broker_task", status="complete")
        return None

    mock_db.get_task.side_effect = get_task_side_effect
    return mock_db


@pytest.fixture
def mock_huey():
    mock = MagicMock()
    mock.pending.return_value = []
    mock.scheduled.return_value = []
    return mock


@pytest.fixture
def ws_manager_instance():
    return WebSocketManager()


@pytest.fixture(autouse=True)
def setup_huey_dashboard_state(mock_huey, mock_task_db, ws_manager_instance):
    app.state.huey_dashboard = {
        "huey": mock_huey,
        "db": mock_task_db,
        "manager": ws_manager_instance,
        "redis": None,
    }
    yield
    app.state.huey_dashboard = None


@pytest.fixture
def client():
    if not hasattr(app.state, "svcs_registry") or app.state.svcs_registry is None:
        registry = svcs.Registry()
        register_services(registry, sessionmanager)
        app.state.svcs_registry = registry

    with TestClient(app) as c:
        yield c


def make_mock_svcs_container(user_api_mock):
    mock_container = AsyncMock()
    mock_container.aget.return_value = user_api_mock
    mock_container.__aenter__.return_value = mock_container
    mock_container.__aexit__.return_value = None
    return mock_container


# --- REST API Tests ---


def test_tasks_list_unauthenticated(client):
    response = client.get("/worker/api/tasks/")
    assert response.status_code == 401


def test_task_detail_unauthenticated(client):
    response = client.get("/worker/api/tasks/task-1")
    assert response.status_code == 401


def test_tasks_list_authenticated_header(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    with patch("svcs.Container", return_value=mock_container):
        response = client.get(
            "/worker/api/tasks/",
            headers={"Authorization": "Bearer valid_token"},
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "task-1"
    assert data[0]["name"] == "sync_broker_task"
    assert data[1]["id"] == "task-2"


def test_tasks_list_authenticated_cookie(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    client.cookies = {"auth_token": "valid_token"}
    with patch("svcs.Container", return_value=mock_container):
        response = client.get("/worker/api/tasks/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_task_detail_authenticated_found(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    with patch("svcs.Container", return_value=mock_container):
        response = client.get(
            "/worker/api/tasks/task-1",
            headers={"Authorization": "Bearer valid_token"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "task-1"
    assert data["name"] == "sync_broker_task"
    assert data["status"] == "complete"


def test_task_detail_authenticated_not_found(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    with patch("svcs.Container", return_value=mock_container):
        response = client.get(
            "/worker/api/tasks/nonexistent-task",
            headers={"Authorization": "Bearer valid_token"},
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


# --- WebSocket Tests ---


def test_websocket_no_auth(client):
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/worker/api/updates"),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_websocket_trailing_slash_no_auth(client):
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/worker/api/updates/"),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_websocket_ticket_replayed(client):
    with (
        patch(
            "src.worker_dashboard.router._check_ticket_not_replayed", return_value=False
        ),
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/worker/api/updates?ticket=replayed_ticket"),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_websocket_ticket_invalid_signature(client):
    with (
        patch(
            "src.worker_dashboard.router._check_ticket_not_replayed", return_value=True
        ),
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/worker/api/updates?ticket=invalid_ticket_payload"),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_websocket_ticket_valid(client, user_id):
    serializer = URLSafeTimedSerializer(settings.secret_key)
    payload = json.dumps({"user_id": str(user_id)})
    valid_ticket = serializer.dumps(payload, salt="ws-ticket")

    with (
        patch(
            "src.worker_dashboard.router._check_ticket_not_replayed", return_value=True
        ),
        client.websocket_connect(
            f"/worker/api/updates?ticket={valid_ticket}"
        ) as websocket,
    ):
        assert websocket is not None
        websocket.send_text("ping")
        response = websocket.receive_text()
        assert response == "Message received: ping"


def test_websocket_trailing_slash_ticket_valid(client, user_id):
    serializer = URLSafeTimedSerializer(settings.secret_key)
    payload = json.dumps({"user_id": str(user_id)})
    valid_ticket = serializer.dumps(payload, salt="ws-ticket")

    with (
        patch(
            "src.worker_dashboard.router._check_ticket_not_replayed", return_value=True
        ),
        client.websocket_connect(
            f"/worker/api/updates/?ticket={valid_ticket}"
        ) as websocket,
    ):
        assert websocket is not None
        websocket.send_text("ping_slash")
        response = websocket.receive_text()
        assert response == "Message received: ping_slash"


def test_websocket_token_cookie_valid(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    client.cookies = {"auth_token": "valid_token"}
    with (
        patch("svcs.Container", return_value=mock_container),
        client.websocket_connect("/worker/api/updates") as websocket,
    ):
        assert websocket is not None
        websocket.send_text("hello_cookie")
        response = websocket.receive_text()
        assert response == "Message received: hello_cookie"
    mock_user_api.get_current_user_from_token.assert_called_once_with("valid_token")


def test_websocket_token_cookie_invalid(client):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.side_effect = Exception("Invalid token")
    mock_container = make_mock_svcs_container(mock_user_api)

    client.cookies = {"auth_token": "bad_token"}
    with (
        patch("svcs.Container", return_value=mock_container),
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/worker/api/updates"),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION


def test_websocket_token_header_valid(client, dummy_user):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.return_value = dummy_user
    mock_container = make_mock_svcs_container(mock_user_api)

    with patch("svcs.Container", return_value=mock_container):
        with client.websocket_connect(
            "/worker/api/updates",
            headers={"sec-websocket-protocol": "valid_token"},
            subprotocols=["valid_token"],
        ) as websocket:
            assert websocket is not None
            websocket.send_text("hello_header")
            response = websocket.receive_text()
            assert response == "Message received: hello_header"
        mock_user_api.get_current_user_from_token.assert_called_once_with("valid_token")


def test_websocket_token_header_invalid(client):
    mock_user_api = AsyncMock(spec=UserApi)
    mock_user_api.get_current_user_from_token.side_effect = Exception("Invalid token")
    mock_container = make_mock_svcs_container(mock_user_api)

    with (
        patch("svcs.Container", return_value=mock_container),
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect(
            "/worker/api/updates",
            headers={"sec-websocket-protocol": "invalid_token"},
            subprotocols=["invalid_token"],
        ),
    ):
        pass
    assert exc_info.value.code == WS_POLICY_VIOLATION
