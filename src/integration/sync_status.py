import contextlib
import uuid
from collections.abc import AsyncIterator

import redis.asyncio as aioredis

from src.account.api_types import AccountId
from src.auth.api_types import UserId
from src.config.settings import settings


class RedisManager:
    _client: aioredis.Redis | None

    def __init__(self, redis_url: str) -> None:
        self._client = aioredis.from_url(redis_url, decode_responses=True)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @contextlib.asynccontextmanager
    async def client(self) -> AsyncIterator[aioredis.Redis]:
        if self._client is None:
            error = "RedisManager is not initialized"
            raise SystemError(error)

        yield self._client


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
