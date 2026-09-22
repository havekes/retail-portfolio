"""Unit tests for the note-task Redis labels and revoke helper.

Redis is the shared in-memory fake from `tests/fixtures/redis.py` (autouse);
huey revoke/is_revoked round-trips run against the real in-memory huey storage
so the revoked-task mechanism of the pinned huey 3.4.0 is exercised directly.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from huey import MemoryHuey

from src.market.task_labels import (
    WORKER_TASK_LABEL_TTL,
    note_summary_label,
    note_title_label,
    record_task_label,
    revoke_labelled_task,
)
from src.worker import huey


def test_label_formats() -> None:
    user_id = uuid4()
    security_id = uuid4()
    assert note_title_label(user_id, 42) == f"note-title:{user_id}:42"
    assert (
        note_summary_label(user_id, security_id)
        == f"note-summary:{user_id}:{security_id}"
    )


def test_revoke_by_id_skips_queued_task() -> None:
    """Verify the pinned huey's revoke mechanism in isolation."""
    local_huey = MemoryHuey("test-revoke")
    calls: list[int] = []

    @local_huey.task()
    def sample_task() -> None:
        calls.append(1)

    result = sample_task()
    local_huey.revoke_by_id(result.id)
    assert local_huey.is_revoked(result.id) is True

    task = local_huey.dequeue()
    assert task is not None
    local_huey.execute(task)

    assert calls == []


@pytest.mark.anyio
async def test_record_and_revoke_round_trip(mock_redis_storage) -> None:
    label = note_title_label(uuid4(), 7)
    task_id = f"task-{uuid4()}"

    await record_task_label(label, task_id)
    assert mock_redis_storage.data[label] == task_id

    revoked = await revoke_labelled_task(label)
    assert revoked == task_id
    assert label not in mock_redis_storage.data
    assert huey.is_revoked(task_id) is True


@pytest.mark.anyio
async def test_record_replaces_previous_task_id(mock_redis_storage) -> None:
    label = note_summary_label(uuid4(), uuid4())

    await record_task_label(label, "first")
    await record_task_label(label, "second")

    assert mock_redis_storage.data[label] == "second"


@pytest.mark.anyio
async def test_record_uses_ttl(mock_redis_storage, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    original_set = mock_redis_storage.set

    async def spy(key: str, value: str, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return await original_set(key, value, **kwargs)

    monkeypatch.setattr(mock_redis_storage, "set", spy)

    await record_task_label("some-label", "tid")

    assert captured["ex"] == WORKER_TASK_LABEL_TTL


@pytest.mark.anyio
async def test_revoke_without_label_returns_none() -> None:
    assert await revoke_labelled_task("absent-label") is None


@pytest.mark.anyio
async def test_revoke_is_best_effort_when_redis_fails(
    mock_redis_storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        msg = "redis down"
        raise RuntimeError(msg)

    monkeypatch.setattr(mock_redis_storage, "get", boom)

    assert await revoke_labelled_task("some-label") is None


@pytest.mark.anyio
async def test_record_is_best_effort_when_redis_fails(
    mock_redis_storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        msg = "redis down"
        raise RuntimeError(msg)

    monkeypatch.setattr(mock_redis_storage, "set", boom)

    await record_task_label("some-label", "tid")


@pytest.mark.anyio
async def test_revoke_returns_id_even_when_huey_revoke_fails(
    mock_redis_storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    label = note_title_label(uuid4(), 11)
    await record_task_label(label, "task-id")

    def boom(*_args: Any, **_kwargs: Any) -> None:
        msg = "huey error"
        raise RuntimeError(msg)

    monkeypatch.setattr(huey, "revoke_by_id", boom)

    assert await revoke_labelled_task(label) == "task-id"
