import logging

import svcs
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.auth.api import UserApi
from src.ws.manager import ws_manager

logger = logging.getLogger(__name__)
ws_router = APIRouter()


@ws_router.websocket("/api/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):
    token = websocket.cookies.get("auth_token") or websocket.headers.get(
        "sec-websocket-protocol"
    )
    if not token:
        await websocket.close(code=1008)
        return

    registry = websocket.app.state.svcs_registry
    async with svcs.Container(registry) as services:
        user_api = await services.aget(UserApi)
        try:
            user = await user_api.get_current_user_from_token(token)
        except Exception:  # noqa: BLE001
            await websocket.close(code=1008)
            return

        await ws_manager.connect(
            websocket,
            user.id,
            subprotocol=token
            if websocket.headers.get("sec-websocket-protocol")
            else None,
        )
        try:
            while True:
                # We just want to keep the connection alive
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, user.id)
