import asyncio
import logging
from typing import Any

from fastapi import FastAPI
from huey_dashboard import (
    AsyncRedis,
    TaskDatabase,
    WebSocketManager,
    create_async_engine,
    register_signal_handlers,
)

logger = logging.getLogger(__name__)


async def init_worker_dashboard(
    app: FastAPI,
    huey: Any,
    db_url: str,
    redis_url: str | None = None,
    *,
    bind_signals: bool = False,
) -> None:
    """Initialize the Huey Dashboard components and register state on FastAPI app."""
    engine = create_async_engine(db_url)
    db = TaskDatabase(engine)
    manager = WebSocketManager()

    async_redis: AsyncRedis | None = None
    if redis_url:
        async_redis = AsyncRedis.from_url(redis_url)

    app.state.huey_dashboard = {
        "huey": huey,
        "redis": async_redis,
        "manager": manager,
        "db": db,
    }

    await db.ensure_table()

    if bind_signals:
        main_loop = asyncio.get_running_loop()
        register_signal_handlers(huey, db, async_redis, loop=main_loop)

    if async_redis:
        await manager.start_pubsub_listener(async_redis)


async def close_worker_dashboard(app: FastAPI) -> None:
    """Clean up worker dashboard background tasks and Redis connections."""
    state = getattr(app.state, "huey_dashboard", None)
    if isinstance(state, dict):
        manager = state.get("manager")
        if manager and hasattr(manager, "stop_pubsub_listener"):
            res = manager.stop_pubsub_listener()
            if asyncio.iscoroutine(res):
                await res
        redis_client = state.get("redis")
        if redis_client and hasattr(redis_client, "aclose"):
            res = redis_client.aclose()
            if asyncio.iscoroutine(res):
                await res
