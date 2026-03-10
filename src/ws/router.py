from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from svcs.fastapi import DepContainer

from src.auth.api import UserApi
from src.ws.manager import ws_manager

ws_router = APIRouter()


@ws_router.websocket("/api/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    services: DepContainer,
):
    user_api = await services.aget(UserApi)
    try:
        user = await user_api.get_current_user_from_token(token)
    except Exception:  # noqa: BLE001
        await websocket.close(code=1008)
        return

    await ws_manager.connect(websocket, user.id)
    try:
        while True:
            # We just want to keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user.id)
