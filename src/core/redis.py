import asyncio
import contextlib
import logging
import threading
from collections.abc import AsyncIterator

import redis.asyncio as aioredis

from src.config.settings import settings

logger = logging.getLogger(__name__)


class RedisManager:
    _redis_url: str
    _clients: dict[asyncio.AbstractEventLoop, aioredis.Redis]

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._clients = {}
        self._lock = threading.Lock()

    async def close(self) -> None:
        with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            try:
                await client.aclose()
            except Exception:
                logger.debug(
                    "Failed to close Redis client during RedisManager.close",
                    exc_info=True,
                )

    @contextlib.asynccontextmanager
    async def client(self) -> AsyncIterator[aioredis.Redis]:
        loop = asyncio.get_running_loop()

        clients_to_close: list[aioredis.Redis] = []
        with self._lock:
            for active_loop in list(self._clients.keys()):
                if active_loop.is_closed():
                    c = self._clients.pop(active_loop, None)
                    if c is not None:
                        clients_to_close.append(c)

        for client_to_close in clients_to_close:
            try:
                await client_to_close.aclose()
            except Exception:
                logger.debug(
                    "Failed to close Redis client for closed loop", exc_info=True
                )

        with self._lock:
            if loop not in self._clients:
                self._clients[loop] = aioredis.from_url(
                    self._redis_url, decode_responses=True
                )
            res_client = self._clients[loop]

        yield res_client


redis_manager = RedisManager(settings.redis_url)
