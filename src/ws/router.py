import hashlib
import json
import logging
from uuid import UUID

import redis.asyncio as aioredis
import svcs
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from itsdangerous import URLSafeTimedSerializer

from src.auth.api import UserApi
from src.config.settings import settings
from src.ws.manager import ws_manager

logger = logging.getLogger(__name__)
ws_router = APIRouter()


async def _check_ticket_not_replayed(ticket: str, redis_url: str) -> bool:
    """Atomically check if a ticket has already been used and mark it as used.

    Returns True if the ticket is new (first use), False if it was already used.
    """
    ticket_hash = hashlib.sha256(ticket.encode()).hexdigest()
    key = f"ws-ticket-used:{ticket_hash}"
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        acquired = await redis_client.set(key, "1", nx=True, ex=30)
    except Exception:
        logger.exception("Failed to check ticket replay status")
        return True
    else:
        return acquired is not None
    finally:
        await redis_client.aclose()


@ws_router.websocket("/api/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):
    ticket = websocket.query_params.get("ticket")
    token = websocket.cookies.get("auth_token") or websocket.headers.get(
        "sec-websocket-protocol"
    )

    user_id: UUID | None = None

    if ticket:
        if not await _check_ticket_not_replayed(ticket, settings.redis_url):
            logger.warning("WebSocket ticket replay attempt detected")
            await websocket.close(code=1008)
            return

        serializer = URLSafeTimedSerializer(settings.secret_key)
        try:
            payload = json.loads(serializer.loads(ticket, max_age=30, salt="ws-ticket"))
            user_id = UUID(str(payload["user_id"]))
        except Exception:  # noqa: BLE001
            await websocket.close(code=1008)
            return
    elif token:
        registry = websocket.app.state.svcs_registry
        async with svcs.Container(registry) as services:
            user_api = await services.aget(UserApi)
            try:
                user = await user_api.get_current_user_from_token(token)
                user_id = user.id
            except Exception:  # noqa: BLE001
                await websocket.close(code=1008)
                return

    if not user_id:
        await websocket.close(code=1008)
        return

    await ws_manager.connect(
        websocket,
        user_id,
        subprotocol=token if websocket.headers.get("sec-websocket-protocol") else None,
    )
    try:
        while True:
            # We just want to keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
