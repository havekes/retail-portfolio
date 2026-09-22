"""Redis labels mapping background note tasks to their huey task ids.

The router records the huey task id returned at dispatch under a small Redis
key (``note-title:{user_id}:{note_id}`` / ``note-summary:{user_id}:{security_id}``)
so a later delete can revoke the queued task. Labels are replace-on-write and
carry a TTL as a recovery mechanism for lost deletes.

Revocation is best-effort: every Redis/huey failure is logged and swallowed,
because the task bodies themselves re-check the database before persisting
(see ``src.market.task``).
"""

import logging

from src.auth.api_types import UserId
from src.core.redis import redis_manager
from src.market.api_types import SecurityId
from src.worker import huey

logger = logging.getLogger(__name__)

WORKER_TASK_LABEL_TTL = 3600


def note_title_label(user_id: UserId, note_id: int) -> str:
    """Redis key holding the queued title task id for a single note."""
    return f"note-title:{user_id}:{note_id}"


def note_summary_label(user_id: UserId, security_id: SecurityId) -> str:
    """Redis key holding the queued summary task id for (user, security)."""
    return f"note-summary:{user_id}:{security_id}"


async def record_task_label(
    label: str, task_id: str, ttl: int = WORKER_TASK_LABEL_TTL
) -> None:
    """Store (or replace) the task id for *label*; never raises."""
    try:
        async with redis_manager.client() as redis:
            await redis.set(label, task_id, ex=ttl)
    except Exception:
        logger.warning("Failed to record task label %s", label, exc_info=True)


async def revoke_labelled_task(label: str) -> str | None:
    """Revoke the queued task recorded under *label*.

    Returns the revoked huey task id, or ``None`` when there is no label.
    A queued task is skipped at pop time; an already-executing task is
    unaffected (its own checkpoint guards discard the result). All failures
    are logged and swallowed — revocation is best-effort only.
    """
    try:
        async with redis_manager.client() as redis:
            raw_task_id = await redis.get(label)
            if not raw_task_id:
                return None
            task_id = (
                raw_task_id.decode() if isinstance(raw_task_id, bytes) else raw_task_id
            )
            await redis.delete(label)
    except Exception:
        logger.warning("Failed to read task label %s", label, exc_info=True)
        return None

    try:
        huey.revoke_by_id(task_id)
    except Exception:
        logger.warning(
            "Failed to revoke task %s from label %s", task_id, label, exc_info=True
        )

    return task_id
