# ruff: noqa: SLF001
import asyncio
import contextlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from opentelemetry import propagate, trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanContext
from starlette.websockets import WebSocketState

from src.config.settings import Settings
from src.core.context import get_trace_id
from src.observability import bootstrap_observability, get_tracer, reset_observability
from src.ws.manager import ConnectionManager
from tests.fixtures.redis import FakeRedis


@pytest.fixture
def cm():
    manager = ConnectionManager()
    yield manager
    # Clean up loop-scoped clients after test
    manager._clients.clear()
    if manager._pubsub_task and not manager._pubsub_task.done():
        manager._pubsub_task.cancel()


@pytest.fixture
def span_exporter() -> Iterator[InMemorySpanExporter]:
    """Install a real tracer provider exporting spans to memory."""
    exporter = InMemorySpanExporter()
    bootstrap_observability(
        service_name="backend",
        settings=Settings(environment="test"),
        span_processor=SimpleSpanProcessor(exporter),
    )
    try:
        yield exporter
    finally:
        reset_observability()


@contextmanager
def producer_span() -> Iterator[tuple[SpanContext, dict[str, str]]]:
    """Start a span and capture the W3C carrier a publisher would inject."""
    tracer = get_tracer("test.ws.producer")
    with tracer.start_as_current_span("ws.producer") as span:
        carrier: dict[str, str] = {}
        propagate.inject(carrier)
        yield span.get_span_context(), carrier


def envelope(user_id: Any, message: dict[str, Any], **extra: Any) -> str:
    return json.dumps({"user_id": str(user_id), "message": message, **extra})


def pubsub_redis(*messages: str) -> MagicMock:
    """A mocked Redis whose pub/sub listener yields ``messages`` once."""

    async def gen():
        for data in messages:
            yield {"type": "message", "data": data}

    mock_pubsub = MockPubSub(gen)
    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub
    return mock_redis


async def wait_for(predicate, timeout: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            msg = "condition not met before timeout"
            raise TimeoutError(msg)
        await asyncio.sleep(0)


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
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.sleep(10)

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
    mock_local = AsyncMock()

    with (
        patch.object(cm, "get_redis_client", return_value=None),
        patch.object(
            cm, "_orig_init_redis", side_effect=Exception("Redis init failed")
        ),
        patch.object(cm, "_send_to_local_connections", new=mock_local),
    ):
        await cm._orig_send_personal_message(msg, user_id)
        mock_local.assert_called_once_with(user_id, msg)


@pytest.mark.asyncio
async def test_send_personal_message_redis_fallback_on_publish_failure(cm):
    user_id = uuid4()
    mock_redis = AsyncMock()
    mock_redis.publish.side_effect = Exception("Publish error")
    loop = asyncio.get_running_loop()
    cm._clients[loop] = mock_redis
    msg = {"content": "hello"}
    mock_local = AsyncMock()

    with patch.object(cm, "_send_to_local_connections", new=mock_local):
        await cm._orig_send_personal_message(msg, user_id)
        mock_local.assert_called_once_with(user_id, msg)


@pytest.mark.asyncio
async def test_send_personal_message_sync_with_loop(cm):
    user_id = uuid4()
    msg = {"content": "hello"}
    with patch.object(cm, "send_personal_message", new=AsyncMock()):
        cm._orig_send_personal_message_sync(msg, user_id)
        await asyncio.sleep(0)


def test_send_personal_message_sync_no_loop(cm):
    user_id = uuid4()
    msg = {"content": "hello"}
    with (
        patch("asyncio.get_running_loop", side_effect=RuntimeError("no loop")),
        patch("asyncio.run") as mock_asyncio_run,
    ):
        cm._orig_send_personal_message_sync(msg, user_id)
        assert mock_asyncio_run.called
        args = mock_asyncio_run.call_args[0]
        if args and asyncio.iscoroutine(args[0]):
            args[0].close()


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
    mock_local = AsyncMock()

    with (
        patch.object(cm, "get_redis_client", return_value=mock_redis),
        patch.object(cm, "_send_to_local_connections", new=mock_local),
    ):
        await cm._listen_for_messages()

        mock_pubsub.subscribe.assert_called_once_with("ws_messages")
        mock_local.assert_called_once_with(user_id, msg_payload)


@pytest.mark.asyncio
async def test_listen_for_messages_cancelled(cm):
    async def gen():
        yield {"type": "subscribe"}
        raise asyncio.CancelledError

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
            err_msg = "PubSub Error"
            raise RuntimeError(err_msg)
        yield {"type": "dummy"}

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
            await cm._pubsub_task


# --------------------------------------------------------------------------- #
# Trace context propagation over Redis pub/sub (F-OBS-T08)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_send_personal_message_injects_trace_context(cm, span_exporter):
    user_id = uuid4()
    mock_redis = AsyncMock()
    cm._clients[asyncio.get_running_loop()] = mock_redis
    msg = {"content": "hello"}

    with producer_span() as (producer_ctx, injected_carrier):
        await cm._orig_send_personal_message(msg, user_id)

    channel, raw_payload = mock_redis.publish.call_args.args
    assert channel == "ws_messages"
    payload = json.loads(raw_payload)
    assert payload["user_id"] == str(user_id)
    assert payload["message"] == msg
    assert payload["carrier"] == injected_carrier

    extracted_ctx = trace.get_current_span(
        propagate.extract(payload["carrier"])
    ).get_span_context()
    assert extracted_ctx.trace_id == producer_ctx.trace_id
    assert extracted_ctx.span_id == producer_ctx.span_id


@pytest.mark.asyncio
async def test_send_personal_message_without_active_trace_publishes_legacy_envelope(
    cm, span_exporter
):
    assert get_trace_id() is None

    user_id = uuid4()
    mock_redis = AsyncMock()
    cm._clients[asyncio.get_running_loop()] = mock_redis
    msg = {"content": "hello"}

    await cm._orig_send_personal_message(msg, user_id)

    expected_payload = json.dumps({"user_id": str(user_id), "message": msg})
    mock_redis.publish.assert_called_once_with("ws_messages", expected_payload)


@pytest.mark.asyncio
async def test_listen_for_messages_restores_producer_trace_context(cm, span_exporter):
    user_id = uuid4()
    observed: list[str | None] = []

    async def record(_user_id, _message):
        observed.append(get_trace_id())

    with producer_span() as (producer_ctx, carrier):
        expected_trace_id = trace.format_trace_id(producer_ctx.trace_id)

    mock_redis = pubsub_redis(
        envelope(user_id, {"type": "ping"}, carrier=carrier),
    )

    with (
        patch.object(cm, "get_redis_client", return_value=mock_redis),
        patch.object(cm, "_send_to_local_connections", new=record),
    ):
        await cm._listen_for_messages()

    assert observed == [expected_trace_id]


@pytest.mark.asyncio
async def test_listen_for_messages_accepts_trace_carrier_alias(cm, span_exporter):
    user_id = uuid4()
    observed: list[str | None] = []

    async def record(_user_id, _message):
        observed.append(get_trace_id())

    with producer_span() as (producer_ctx, carrier):
        expected_trace_id = trace.format_trace_id(producer_ctx.trace_id)

    mock_redis = pubsub_redis(
        envelope(user_id, {"type": "ping"}, trace_carrier=carrier),
    )

    with (
        patch.object(cm, "get_redis_client", return_value=mock_redis),
        patch.object(cm, "_send_to_local_connections", new=record),
    ):
        await cm._listen_for_messages()

    assert observed == [expected_trace_id]


@pytest.mark.asyncio
async def test_delivery_span_is_child_of_producer_span(cm, span_exporter):
    user_id = uuid4()
    tracer = get_tracer("test.ws.delivery")
    ws = MagicMock()
    ws.client_state = WebSocketState.CONNECTED

    async def send_json(_payload):
        with tracer.start_as_current_span("ws.delivery"):
            pass

    ws.send_json = AsyncMock(side_effect=send_json)
    cm.active_connections[user_id] = [ws]

    with producer_span() as (producer_ctx, carrier):
        pass

    mock_redis = pubsub_redis(
        envelope(user_id, {"type": "ping"}, carrier=carrier),
    )

    with patch.object(cm, "get_redis_client", return_value=mock_redis):
        await cm._listen_for_messages()

    delivery = next(
        span
        for span in span_exporter.get_finished_spans()
        if span.name == "ws.delivery"
    )
    assert delivery.context.trace_id == producer_ctx.trace_id
    assert delivery.parent is not None
    assert delivery.parent.span_id == producer_ctx.span_id


@pytest.mark.asyncio
async def test_listen_for_messages_delivers_without_trace_context(cm, span_exporter):
    user_id = uuid4()
    observed: list[str | None] = []

    async def record(_user_id, _message):
        observed.append(get_trace_id())

    mock_redis = pubsub_redis(envelope(user_id, {"type": "ping"}))

    with (
        patch.object(cm, "get_redis_client", return_value=mock_redis),
        patch.object(cm, "_send_to_local_connections", new=record),
    ):
        await cm._listen_for_messages()

    assert observed == [None]


@pytest.mark.asyncio
async def test_listen_for_messages_tolerates_malformed_carriers(cm, span_exporter):
    user_id = uuid4()
    delivered: list[dict[str, Any]] = []

    async def record(_user_id, message):
        delivered.append(message)

    mock_redis = pubsub_redis(
        envelope(user_id, {"n": 1}),
        envelope(user_id, {"n": 2}, carrier="not-a-dict"),
        envelope(user_id, {"n": 3}, carrier={"traceparent": "garbage"}),
        envelope(user_id, {"n": 4}, carrier={"traceparent": 12345}),
        envelope(user_id, {"n": 5}, carrier=[]),
        envelope(user_id, {"n": 6}, trace_carrier=None),
    )

    with (
        patch.object(cm, "get_redis_client", return_value=mock_redis),
        patch.object(cm, "_send_to_local_connections", new=record),
    ):
        await cm._listen_for_messages()

    assert [message["n"] for message in delivered] == [1, 2, 3, 4, 5, 6]


@pytest.mark.asyncio
async def test_listen_for_messages_does_not_leak_context_between_messages(
    cm, span_exporter
):
    user_id = uuid4()
    observed: list[str | None] = []

    async def record(_user_id, _message):
        observed.append(get_trace_id())

    with producer_span() as (producer_ctx, carrier):
        expected_trace_id = trace.format_trace_id(producer_ctx.trace_id)

    mock_redis = pubsub_redis(
        envelope(user_id, {"n": 1}, carrier=carrier),
        envelope(user_id, {"n": 2}),
    )

    with (
        patch.object(cm, "get_redis_client", return_value=mock_redis),
        patch.object(cm, "_send_to_local_connections", new=record),
    ):
        await cm._listen_for_messages()

    assert observed == [expected_trace_id, None]


@pytest.mark.asyncio
async def test_send_personal_message_fallback_on_init_failure_keeps_trace(
    cm, span_exporter
):
    user_id = uuid4()
    msg = {"content": "hello"}
    observed: list[str | None] = []

    async def record(_user_id, _message):
        observed.append(get_trace_id())

    tracer = get_tracer("test.ws.producer")
    with (
        patch.object(cm, "get_redis_client", return_value=None),
        patch.object(cm, "_orig_init_redis", side_effect=Exception("Redis init failed")),
        patch.object(cm, "_send_to_local_connections", new=record),
        tracer.start_as_current_span("ws.producer") as span,
    ):
        expected_trace_id = trace.format_trace_id(span.get_span_context().trace_id)
        await cm._orig_send_personal_message(msg, user_id)

    assert observed == [expected_trace_id]


@pytest.mark.asyncio
async def test_send_personal_message_fallback_on_publish_failure_keeps_trace(
    cm, span_exporter
):
    user_id = uuid4()
    msg = {"content": "hello"}
    observed: list[str | None] = []

    async def record(_user_id, _message):
        observed.append(get_trace_id())

    mock_redis = AsyncMock()
    mock_redis.publish.side_effect = Exception("Publish error")
    cm._clients[asyncio.get_running_loop()] = mock_redis

    tracer = get_tracer("test.ws.producer")
    with (
        patch.object(cm, "_send_to_local_connections", new=record),
        tracer.start_as_current_span("ws.producer") as span,
    ):
        expected_trace_id = trace.format_trace_id(span.get_span_context().trace_id)
        await cm._orig_send_personal_message(msg, user_id)

    assert observed == [expected_trace_id]


@pytest.mark.asyncio
async def test_trace_context_survives_fake_redis_pubsub_round_trip(cm, span_exporter):
    """End-to-end: publish -> FakePubSub listener -> WebSocket delivery."""
    user_id = uuid4()
    redis = FakeRedis()
    tracer = get_tracer("test.ws.delivery")
    delivered = asyncio.Event()

    ws = MagicMock()
    ws.client_state = WebSocketState.CONNECTED

    async def send_json(_payload):
        with tracer.start_as_current_span("ws.delivery"):
            delivered.set()

    ws.send_json = AsyncMock(side_effect=send_json)
    cm.active_connections[user_id] = [ws]

    with patch.object(cm, "get_redis_client", return_value=redis):
        listener = asyncio.create_task(cm._listen_for_messages())
        try:
            await wait_for(lambda: "ws_messages" in redis._subscribers)

            with producer_span() as (producer_ctx, _carrier):
                await cm._orig_send_personal_message({"type": "ping"}, user_id)

            await asyncio.wait_for(delivered.wait(), timeout=5)
        finally:
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener

    delivery = next(
        span
        for span in span_exporter.get_finished_spans()
        if span.name == "ws.delivery"
    )
    assert delivery.context.trace_id == producer_ctx.trace_id
    assert delivery.parent is not None
    assert delivery.parent.span_id == producer_ctx.span_id
