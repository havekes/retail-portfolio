import json
import logging
import uuid
from typing import Annotated
from uuid import UUID

import svcs
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from huey_dashboard.api.endpoints import tasks
from huey_dashboard.core.dependencies import get_websocket_manager
from huey_dashboard.services.websocket_manager import WebSocketManager
from itsdangerous import URLSafeTimedSerializer

from src.auth.api import UserApi, current_user
from src.config.settings import settings
from src.core.context import request_id_ctx_var, set_request_id
from src.ws.router import _check_ticket_not_replayed

logger = logging.getLogger(__name__)

worker_dashboard_router = APIRouter(prefix="/worker/api")

worker_dashboard_router.include_router(
    tasks.router,
    prefix="/tasks",
    tags=["worker-dashboard"],
    dependencies=[Depends(current_user)],
)


async def _authenticate_ticket(ticket: str) -> UUID | None:
    """Validate ticket replay status and unpack user ID payload."""
    if not await _check_ticket_not_replayed(ticket, settings.redis_url):
        logger.warning("WebSocket ticket replay attempt detected")
        return None

    serializer = URLSafeTimedSerializer(settings.secret_key)
    try:
        payload = json.loads(serializer.loads(ticket, max_age=30, salt="ws-ticket"))
    except Exception:  # noqa: BLE001
        return None
    else:
        return UUID(str(payload["user_id"]))


async def _authenticate_token(
    token: str,
    websocket: WebSocket,
) -> tuple[UUID | None, str | None]:
    """Validate session token and return user ID and optional subprotocol."""
    registry = getattr(websocket.app.state, "svcs_registry", None)
    if not registry:
        return None, None

    async with svcs.Container(registry) as services:
        user_api = await services.aget(UserApi)
        try:
            user = await user_api.get_current_user_from_token(token)
        except Exception:  # noqa: BLE001
            return None, None
        else:
            subprotocol = (
                token if websocket.headers.get("sec-websocket-protocol") else None
            )
            return user.id, subprotocol


async def _authenticate_websocket(
    websocket: WebSocket,
) -> tuple[UUID | None, str | None]:
    """Validate ticket or token and return user ID and subprotocol."""
    ticket = websocket.query_params.get("ticket")
    if ticket:
        user_id = await _authenticate_ticket(ticket)
        return user_id, None

    token = websocket.cookies.get("auth_token") or websocket.headers.get(
        "sec-websocket-protocol"
    )
    if token:
        return await _authenticate_token(token, websocket)

    return None, None


@worker_dashboard_router.websocket("/updates")
@worker_dashboard_router.websocket("/updates/")
async def worker_dashboard_websocket_endpoint(
    websocket: WebSocket,
    manager: Annotated[WebSocketManager, Depends(get_websocket_manager)],
) -> None:
    header_request_id = websocket.headers.get("X-Request-ID")
    request_id = header_request_id or str(uuid.uuid4())
    req_token = set_request_id(request_id)

    try:
        user_id, subprotocol = await _authenticate_websocket(websocket)
        if not user_id:
            await websocket.close(code=1008)
            return

        if subprotocol:
            await websocket.accept(subprotocol=subprotocol)
            manager.active_connections.append(websocket)
            logger.debug(
                "WebSocket client connected with subprotocol (%d total active)",
                len(manager.active_connections),
            )
        else:
            await manager.connect(websocket)

        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Message received: {data}")
        except WebSocketDisconnect:
            manager.disconnect(websocket)
    finally:
        request_id_ctx_var.reset(req_token)
