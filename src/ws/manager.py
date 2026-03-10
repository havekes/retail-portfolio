import asyncio
import logging
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from src.auth.api_types import UserId

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[UserId, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: UserId):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: UserId):
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            except ValueError:
                pass

    async def send_personal_message(self, message: dict[str, Any], user_id: UserId):
        if user_id in self.active_connections:
            connections = self.active_connections[user_id]
            for connection in connections:
                if connection.client_state == WebSocketState.CONNECTED:
                    try:
                        await connection.send_json(message)
                    except Exception:
                        logger.exception("Failed to send message to user %s", user_id)


ws_manager = ConnectionManager()
