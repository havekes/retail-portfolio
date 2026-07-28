import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from starlette.websockets import WebSocketState

from src.ws.manager import ConnectionManager


@pytest.fixture
def cm():
    """Create a fresh ConnectionManager instance for testing."""
    return ConnectionManager()


def test_manager_init(cm):
    assert cm.active_connections == {}
    assert cm._clients == {}
    assert cm._pubsub_task is None


def test_get_redis_client_no_loop(cm):
    assert cm.get_redis_client() is None


@pytest.mark.asyncio
async def test_get_redis_client_cleans_closed_loops(cm):
    loop = asyncio.get_running_loop()
    closed_loop = MagicMock()
    closed_loop.is_closed.return_value = True
    fake_client = MagicMock()
    cm._clients[closed_loop] = fake_client

    active_client = MagicMock()
    cm._clients[loop] = active_client

    client = cm.get_redis_client()
    assert client == active_client
    assert closed_loop not in cm._clients
    assert loop in cm._clients


@pytest.mark.asyncio
async def test_init_redis(cm):
    loop = asyncio.get_running_loop()

    closed_loop = MagicMock()
    closed_loop.is_closed.return_value = True
    closed_client = AsyncMock()
    closed_client.aclose.side_effect = Exception("aclose error")
    cm._clients[closed_loop] = closed_client

    mock_redis = AsyncMock()
    with (
        patch("redis.asyncio.from_url", return_value=mock_redis),
        patch.object(cm, "_listen_for_messages", new=AsyncMock()),
    ):
        await cm._orig_init_redis("redis://localhost:6379", run_listener=True)

        assert closed_client.aclose.called
        assert cm._clients[loop] == mock_redis
        assert cm._pubsub_task is not None
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_init_redis_restarts_done_listener(cm):
    loop = asyncio.get_running_loop()
    mock_redis = AsyncMock()

    async def dummy():
        pass

    done_task = asyncio.create_task(dummy())
    await done_task
    cm._pubsub_task = done_task

    with (
        patch("redis.asyncio.from_url", return_value=mock_redis),
        patch.object(cm, "_listen_for_messages", new=AsyncMock()),
    ):
        await cm._orig_init_redis("redis://localhost:6379", run_listener=True)
        assert cm._pubsub_task is not done_task


@pytest.mark.asyncio
async def test_close(cm):
    loop = asyncio.get_running_loop()
    mock_client = AsyncMock()
    mock_client.aclose.side_effect = Exception("aclose fail")
    cm._clients[loop] = mock_client

    async def slow_task():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass

    cm._pubsub_task = asyncio.create_task(slow_task())

    await cm._orig_close()
    assert cm._pubsub_task is None
    assert len(cm._clients) == 0
    assert mock_client.aclose.called


@pytest.mark.asyncio
async def test_connect_and_disconnect(cm):
    user_id = uuid4()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await cm.connect(ws1, user_id, subprotocol="proto1")
    ws1.accept.assert_called_once_with(subprotocol="proto1")
    assert cm.active_connections[user_id] == [ws1]

    await cm.connect(ws2, user_id)
    assert cm.active_connections[user_id] == [ws1, ws2]

    cm.disconnect(ws1, user_id)
    assert cm.active_connections[user_id] == [ws2]

    cm.disconnect(ws1, user_id)

    cm.disconnect(ws2, user_id)
    assert user_id not in cm.active_connections

    cm.disconnect(ws1, user_id)


@pytest.mark.asyncio
async def test_send_to_local_connections(cm):
    user_id = uuid4()
    ws_connected = AsyncMock()
    ws_connected.client_state = WebSocketState.CONNECTED

    ws_disconnected = AsyncMock()
    ws_disconnected.client_state = WebSocketState.DISCONNECTED

    ws_error = AsyncMock()
    ws_error.client_state = WebSocketState.CONNECTED
    ws_error.send_json.side_effect = Exception("Send failed")

    cm.active_connections[user_id] = [ws_connected, ws_disconnected, ws_error]

    msg = {"type": "test"}
    await cm._send_to_local_connections(user_id, msg)

    ws_connected.send_json.assert_called_once_with(msg)
    ws_disconnected.send_json.assert_not_called()
    ws_error.send_json.assert_called_once_with(msg)

    other_user = uuid4()
    await cm._send_to_local_connections(other_user, msg)


@pytest.mark.asyncio
async def test_send_personal_message_redis_success(cm):
    user_id = uuid4()
    mock_redis = AsyncMock()
    loop = asyncio.get_running_loop()
    cm._clients[loop] = mock_redis

    msg = {"content": "hello"}
    await cm._orig_send_personal_message(msg, user_id)

    expected_payload = json.dumps({"user_id": str(user_id), "message": msg})
    mock_redis.publish.assert_called_once_with("ws_messages", expected_payload)


@pytest.mark.asyncio
async def test_send_personal_message_redis_fallback_on_init_failure(cm):
    user_id = uuid4()
    msg = {"content": "hello"}

    with (
        patch.object(cm, "get_redis_client", return_value=None),
        patch.object(cm, "_orig_init_redis", side_effect=Exception("Redis init failed")),
        patch.object(cm, "_send_to_local_connections", new=AsyncMock()) as mock_send_local,
    ):
        await cm._orig_send_personal_message(msg, user_id)
        mock_send_local.assert_called_once_with(user_id, msg)


@pytest.mark.asyncio
async def test_send_personal_message_redis_fallback_on_publish_failure(cm):
    user_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.publish.side_effect = Exception("Publish error")
    loop = asyncio.get_running_loop()
    cm._clients[loop] = mock_redis
    msg = {"content": "hello"}

    with patch.object(cm, "_send_to_local_connections", new=AsyncMock()) as mock_send_local:
        await cm._orig_send_personal_message(msg, user_id)
        mock_send_local.assert_called_once_with(user_id, msg)


@pytest.mark.asyncio
async def test_send_personal_message_sync_with_loop(cm):
    user_id = uuid4()
    msg = {"content": "hello"}
    with patch.object(cm, "send_personal_message", new=AsyncMock()) as mock_send:
        cm._orig_send_personal_message_sync(msg, user_id)


def test_send_personal_message_sync_no_loop(cm):
    user_id = uuid4()
    msg = {"content": "hello"}
    with (
        patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")),
        patch("asyncio.run") as mock_asyncio_run,
    ):
        cm._orig_send_personal_message_sync(msg, user_id)
        assert mock_asyncio_run.called


@pytest.mark.asyncio
async def test_listen_for_messages_no_redis(cm):
    with patch.object(cm, "get_redis_client", return_value=None):
        await cm._listen_for_messages()


class MockPubSub:
    def __init__(self, generator_func):
        self.generator_func = generator_func
        self.subscribe = AsyncMock()
        self.unsubscribe = AsyncMock()
        self.aclose = AsyncMock()

    def listen(self):
        return self.generator_func()


@pytest.mark.asyncio
async def test_listen_for_messages_processes_messages(cm):
    user_id = uuid4()
    msg_payload = {"type": "ping"}

    messages = [
        {"type": "subscribe", "data": "ws_messages"},
        {
            "type": "message",
            "data": json.dumps({"user_id": str(user_id), "message": msg_payload}),
        },
        {"type": "message", "data": "invalid json"},
    ]

    async def gen():
        for m in messages:
            yield m

    mock_pubsub = MockPubSub(gen)
    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with (
        patch.object(cm, "get_redis_client", return_value=mock_redis),
        patch.object(cm, "_send_to_local_connections", new=AsyncMock()) as mock_local_send,
    ):
        await cm._listen_for_messages()

        mock_pubsub.subscribe.assert_called_once_with("ws_messages")
        mock_local_send.assert_called_once_with(user_id, msg_payload)


@pytest.mark.asyncio
async def test_listen_for_messages_cancelled(cm):
    async def gen():
        yield {"type": "subscribe"}
        raise asyncio.CancelledError()

    mock_pubsub = MockPubSub(gen)
    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with patch.object(cm, "get_redis_client", return_value=mock_redis):
        await cm._listen_for_messages()
        mock_pubsub.unsubscribe.assert_called_once_with("ws_messages")
        mock_pubsub.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_listen_for_messages_restarts_on_error(cm):
    call_count = 0

    async def gen():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("PubSub Error")
        return

    mock_pubsub = MockPubSub(gen)
    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    with (
        patch.object(cm, "get_redis_client", return_value=mock_redis),
        patch("asyncio.sleep", new=AsyncMock()) as mock_sleep,
    ):
        await cm._listen_for_messages()
        mock_sleep.assert_called_once_with(5)
        assert cm._pubsub_task is not None
        # Clean up created task
        if cm._pubsub_task:
            cm._pubsub_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cm._pubsub_task
