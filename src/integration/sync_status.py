import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator

import redis.asyncio as aioredis

from src.account.api_types import AccountId
from src.auth.api_types import UserId
from src.config.settings import settings


class RedisManager:
    _redis_url: str
    _clients: dict[asyncio.AbstractEventLoop, aioredis.Redis]

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._clients = {}

    async def close(self) -> None:
        for client in list(self._clients.values()):
            await client.aclose()
        self._clients.clear()

    @contextlib.asynccontextmanager
    async def client(self) -> AsyncIterator[aioredis.Redis]:
        loop = asyncio.get_running_loop()

        # Clean up closed loops to prevent memory/connection leaks
        for active_loop in list(self._clients.keys()):
            if active_loop.is_closed():
                client_to_close = self._clients.pop(active_loop, None)
                if client_to_close is not None:
                    with contextlib.suppress(Exception):
                        await client_to_close.aclose()

        if loop not in self._clients:
            self._clients[loop] = aioredis.from_url(
                self._redis_url, decode_responses=True
            )

        yield self._clients[loop]


redis_manager = RedisManager(settings.redis_url)


def _key(user_id: UserId) -> str:
    return f"account_syncs:active:{user_id}"


async def mark_sync_started(user_id: UserId, account_id: AccountId) -> None:
    async with redis_manager.client() as client:
        await client.sadd(_key(user_id), str(account_id))
        await client.expire(_key(user_id), settings.sync_ttl_seconds)


async def mark_sync_finished(user_id: UserId, account_id: AccountId) -> None:
    async with redis_manager.client() as client:
        await client.srem(_key(user_id), str(account_id))


async def get_active_syncs(user_id: UserId) -> list[AccountId]:
    async with redis_manager.client() as client:
        members = await client.smembers(_key(user_id))
        return [uuid.UUID(str(m)) for m in members]
