import asyncio
import contextlib
import json
import logging
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from src.auth.api_types import UserId

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[UserId, list[WebSocket]] = {}
        self._redis: aioredis.Redis | None = None
        self._pubsub_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def init_redis(
        self, redis_url: str, *, run_listener: bool = True
    ):
        """Initialize Redis connection and optionally start listening for messages."""
        current_loop = asyncio.get_running_loop()
        
        # If loop changed or redis not initialized, (re)initialize
        if self._redis is None or self._loop != current_loop:
            if self._redis is not None:
                with contextlib.suppress(Exception):
                    await self._redis.close()
            
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            self._loop = current_loop
            logger.info("ConnectionManager Redis client initialized (loop: %s)", current_loop)

        if run_listener and (self._pubsub_task is None or self._pubsub_task.done()):
            if self._pubsub_task and self._pubsub_task.done():
                logger.warning("ConnectionManager Pub/Sub listener task was done. Restarting...")
            self._pubsub_task = asyncio.create_task(self._listen_for_messages())
            logger.info("ConnectionManager Pub/Sub listener started")

    async def close(self):
        """Close Redis connection and stop listening."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pubsub_task
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._loop = None

    async def _listen_for_messages(self):
        """Background task to listen for messages from Redis Pub/Sub."""
        if self._redis is None:
            return

        pubsub = self._redis.pubsub()
        await pubsub.subscribe("ws_messages")
        logger.debug("Subscribed to Redis channel 'ws_messages'")

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        user_id = UUID(data["user_id"])
                        msg_payload = data["message"]
                        logger.debug("Received message from Redis for user %s: %s", user_id, msg_payload)
                        await self._send_to_local_connections(user_id, msg_payload)
                    except Exception:
                        logger.exception("Failed to process message from Redis")
        except asyncio.CancelledError:
            logger.debug("Redis Pub/Sub listener cancelled")
            await pubsub.unsubscribe("ws_messages")
            await pubsub.close()
        except Exception:
            logger.exception("Redis Pub/Sub listener encountered an error")
            # Restart after a delay
            await asyncio.sleep(5)
            self._pubsub_task = asyncio.create_task(self._listen_for_messages())

    async def connect(self, websocket: WebSocket, user_id: UserId):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info("WebSocket connected for user %s. Total connections for user: %d", user_id, len(self.active_connections[user_id]))

    def disconnect(self, websocket: WebSocket, user_id: UserId):
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                logger.info("WebSocket disconnected for user %s", user_id)
            except ValueError:
                pass

    async def _send_to_local_connections(
        self, user_id: UserId, message: dict[str, Any]
    ):
        """Send a message to local WebSocket connections for a user."""
        if user_id in self.active_connections:
            connections = self.active_connections[user_id]
            logger.debug("Sending message to %d local connections for user %s", len(connections), user_id)
            for connection in connections:
                if connection.client_state == WebSocketState.CONNECTED:
                    try:
                        await connection.send_json(message)
                    except Exception:
                        logger.exception("Failed to send message to user %s", user_id)
        else:
            logger.debug("No local connections for user %s", user_id)

    async def send_personal_message(self, message: dict[str, Any], user_id: UserId):
        """Publish a message to Redis Pub/Sub to be delivered by any process."""
        current_loop = asyncio.get_running_loop()
        if self._redis is None or self._loop != current_loop:
            try:
                from src.config.settings import settings

                await self.init_redis(settings.redis_url, run_listener=False)
            except Exception:
                logger.exception(
                    "Failed to lazily initialize Redis in send_personal_message"
                )
                await self._send_to_local_connections(user_id, message)
                return

        payload = {
            "user_id": str(user_id),
            "message": message,
        }
        try:
            logger.debug("Publishing to Redis 'ws_messages': payload=%s", payload)
            await self._redis.publish("ws_messages", json.dumps(payload))
        except Exception:
            logger.exception("Failed to publish message to Redis: payload=%s", payload)
            await self._send_to_local_connections(user_id, message)

    def send_personal_message_sync(self, message: dict[str, Any], user_id: UserId):
        """Synchronous version of send_personal_message for non-async contexts."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(self.send_personal_message(message, user_id))
        else:
            asyncio.run(self.send_personal_message(message, user_id))


ws_manager = ConnectionManager()
