## Plan

**Approach:**
Extend the Redis pub/sub envelope in `ConnectionManager` (`src/ws/manager.py`) by injecting OpenTelemetry W3C trace context into an optional `carrier` dictionary during `send_personal_message` and extracting/attaching that context across `_send_to_local_connections` in `_listen_for_messages`. Maintain full backwards compatibility for envelopes without context, preserve local fallback delivery under Redis unavailability, and extend `FakeRedis` in `tests/fixtures/redis.py` with an in-memory pub/sub implementation to enable hermetic trace continuity assertions with `InMemorySpanExporter`.

**Files:**
- `src/ws/manager.py` — modify: Inject trace context via `propagate.inject` in `send_personal_message` and restore it via `propagate.extract` + `context.attach`/`detach` in `_listen_for_messages`.
- `tests/fixtures/redis.py` — modify: Add `FakePubSub` and implement `pubsub()` and fanned-out `publish()` in `FakeRedis` for in-memory Redis testing.
- `tests/ws/test_manager.py` — modify: Add unit and integration tests verifying trace context propagation across Redis pub/sub, trace continuity with `InMemorySpanExporter`, fallback delivery, and legacy envelope compatibility.

**Steps:**
1. **Extend `FakeRedis` with Pub/Sub support in `tests/fixtures/redis.py`:**
   - Define `FakePubSub` supporting `subscribe(*channels)`, `unsubscribe(*channels)`, `listen() -> AsyncIterator[dict]`, and `aclose()`.
   - Update `FakeRedis` to maintain a registry of subscribers per channel (`self._subscribers: dict[str, set[FakePubSub]]`).
   - Implement `FakeRedis.pubsub() -> FakePubSub`.
   - Update `FakeRedis.publish(channel, message)` to broadcast JSON messages to all subscribed queues and return subscriber count.
   - Update `FakeRedis.aclose()` to close active subscriber queues cleanly.

2. **Inject W3C trace context at publish in `src/ws/manager.py` (`send_personal_message`):**
   - Import `context` and `propagate` from `opentelemetry`.
   - In `ConnectionManager.send_personal_message`:
     - Construct `carrier: dict[str, str] = {}` and call `propagate.inject(carrier)`.
     - Include `payload["carrier"] = carrier` in the JSON envelope if non-empty, preserving `{"user_id": str(user_id), "message": message}` as the baseline shape.
     - Ensure local fallback paths (`_send_to_local_connections`) called when Redis is unavailable or on publish failure execute seamlessly within the caller's active trace context.

3. **Restore trace context at consumer delivery in `src/ws/manager.py` (`_listen_for_messages`):**
   - In `ConnectionManager._listen_for_messages`, when parsing incoming messages from Redis:
     - Read `carrier = data.get("carrier") or data.get("trace_carrier")`.
     - If carrier is present and a valid mapping, extract context with `propagate.extract(carrier)` and attach using `token = context.attach(extracted_ctx)`.
     - Execute `_send_to_local_connections(user_id, msg_payload)` within a `try ... finally` block, detaching the token via `context.detach(token)` when complete to prevent context leakage across messages on the long-running listener task.
     - Gracefully handle payloads with no carrier or malformed carrier dictionaries by delivering without modifying context.

4. **Add trace context propagation and continuity tests in `tests/ws/test_manager.py`:**
   - Test that `send_personal_message` injects W3C `traceparent` matching the active span into the published payload.
   - Test that `send_personal_message` without an active trace publishes legacy `{user_id, message}` envelope.
   - Test that `_listen_for_messages` restores trace context such that delivery handlers observe the producer's `trace_id` via `get_trace_id()` / `trace.get_current_span()`.
   - Test trace continuity with `InMemorySpanExporter`: span started inside `send_json` during consumer delivery shares the producer's `trace_id` and has `parent_span_id == producer_span_id`.
   - Test that messages published without carrier deliver normally without trace context.
   - Test that malformed carriers do not crash or block delivery.
   - Test local fallback delivery on Redis init or publish failure preserves the active trace context.
   - End-to-end integration test with `FakeRedis`: publish with active trace context -> receive via `FakePubSub` listener -> deliver to mock WebSocket connection -> assert trace continuity via `InMemorySpanExporter` without real Redis.

5. **Run Gate 0 and backend test suites:**
   - Run linting and type checks (`./scripts/agent-test --gate0-only`).
   - Run WebSocket tests (`./scripts/agent-test tests/ws/test_manager.py`).
   - Run full backend regression suite (`./scripts/agent-test --backend`).

**Verification:**
- **AC 1 (Active trace makes consumer delivery part of same trace):**
  - Run `./scripts/agent-test tests/ws/test_manager.py`
  - Observe passing test asserting `InMemorySpanExporter` captures child span during delivery with `delivery_span.context.trace_id == producer_span.context.trace_id` and `delivery_span.parent_span_id == producer_span.context.span_id`.
- **AC 2 (Messages without trace context deliver normally):**
  - Run `./scripts/agent-test tests/ws/test_manager.py`
  - Observe passing tests for payloads without `"carrier"` and with malformed carrier.
- **AC 3 (Fallback path when Redis is unavailable still works):**
  - Run `./scripts/agent-test tests/ws/test_manager.py`
  - Observe passing tests `test_send_personal_message_redis_fallback_on_init_failure` and `test_send_personal_message_redis_fallback_on_publish_failure` with trace context verification.
- **AC 4 (No real Redis server needed; FakeRedis covers pub/sub):**
  - Run `./scripts/agent-test tests/ws/test_manager.py`
  - Verify all tests execute hermetically using `FakeRedis` and `FakePubSub` with zero network sockets or external services.
- **AC 5 (Build and tests pass):**
  - Run `./scripts/agent-test --gate0-only` (passes ruff and mypy).
  - Run `./scripts/agent-test --backend` (full test suite passes without regressions).

**Risks / watch-outs:**
- **Context leakage across messages in event loop:** In `_listen_for_messages`, the listener processes messages indefinitely on a single task. The `context.detach(token)` call MUST be guarded in a `finally` block around `_send_to_local_connections` so that context from one message never bleeds into subsequent messages or background operations.
- **Carrier resilience:** Publishers or external clients might send non-dict carriers or malformed traceparent headers; extraction must be defensive and never raise unhandled exceptions that terminate the pub/sub listener loop.
- **Global mocks in tests:** `tests/conftest.py` patches `ConnectionManager.send_personal_message` by default. Tests verifying real pub/sub logic on `ConnectionManager` must use `cm._orig_send_personal_message` or explicitly unpatch/target the instance under test.
