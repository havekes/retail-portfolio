# WebSockets Module (`src/ws`)

This module provides the WebSocket messaging system for real-time notifications (e.g., broker account synchronization updates) between the backend and frontend clients.

## Architecture

The module uses a **Redis Pub/Sub** backend to broadcast messages. This allows the application to scale horizontally across multiple process/container instances and safely interact with WebSockets from separate concurrent worker threads (e.g., Huey workers).

```mermaid
graph TD
    subgraph FastAPI Instance (Main Loop)
        Client[Browser / Frontend Client] <-->|WebSocket Connection| Router[ws/router.py]
        Router <--> ws_manager[ws_manager]
        ws_manager <-->|Main Loop Redis Client| Redis[(Redis Pub/Sub Channel 'ws_messages')]
        ws_manager -->|Local connections dict| Client
    end

    subgraph Huey Workers (Concurrent Threads)
        Worker1[Huey Worker Thread 1] -->|Worker 1 Redis Client| Redis
        Worker2[Huey Worker Thread 2] -->|Worker 2 Redis Client| Redis
    end

    Redis -->|Subscribe / Broadcast| ws_manager
```

## Key Components

### 1. Connection Manager (`src/ws/manager.py`)

- **`ConnectionManager`**: Manages local WebSocket connections (`active_connections: dict[UserId, list[WebSocket]]`) and handles per-event-loop Redis clients (`_clients: dict[asyncio.AbstractEventLoop, aioredis.Redis]`).
  - When initialized in the main ASGI loop (`run_listener=True`), it starts a background task (`_listen_for_messages`) that subscribes to the `"ws_messages"` Redis channel.
  - Any backend worker thread can call `ws_manager.send_personal_message(...)`. It automatically acquires/initializes a Redis client for its specific event loop and publishes the message. When received by the main loop listener, it delivers the payload to local WebSocket connections.
- Exposes `ws_manager = ConnectionManager()` as the global singleton instance.

### 2. WebSocket Router (`src/ws/router.py`)

- Exposes the `/api/ws` WebSocket endpoint.
- Handles client authentication via a URL-safe signed ticket (to prevent replay attacks) or auth cookies.
- Connects new clients via `ws_manager.connect(...)` and cleans them up via `ws_manager.disconnect(...)` when they disconnect.

### 3. API Types (`src/ws/api_types.py`)

Defines Pydantic schemas and event type enums for WebSocket messages, ensuring consistent serialization:
- `WsEventType`: Defines event types such as `sync_started`, `sync_finished`, and `sync_failed`.
- `WsMessage`: Base WebSocket message schema.
- `AccountSyncMessage`: WebSocket schema for sync-specific messages.

## Usage

### Publishing WebSocket Messages

From an async context (e.g. background sync tasks):
```python
from src.ws.manager import ws_manager
from src.ws.api_types import AccountSyncMessage, WsEventType

await ws_manager.send_personal_message(
    AccountSyncMessage(
        type=WsEventType.ACCOUNT_SYNC_STARTED, 
        account_id=account.id
    ).model_dump(mode="json"),
    user_id,
)
```

From a synchronous context:
```python
from src.ws.manager import ws_manager

ws_manager.send_personal_message_sync(message_dict, user_id)
```
