import logging
import uuid

from src.account.api_types import AccountId
from src.auth.api_types import UserId
from src.config.settings import settings
from src.core.redis import RedisManager, redis_manager

logger = logging.getLogger(__name__)


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
