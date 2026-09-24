import pytest
from unittest.mock import AsyncMock, patch, MagicMock, ANY
from src.main import app
from src.market.model import SecurityModel
from src.market.task import _generate_note_title
from src.market.ai_service import AIService
from src.market.repository import SecurityNoteRepository
from src.market.repository_sqlalchemy import SqlAlchemySecurityNoteRepository
from src.market.task_labels import note_summary_label, note_title_label
from src.worker import huey
import uuid


def _task_result(task_id: str, name: str) -> MagicMock:
    """Minimal stand-in for a huey Result with the fields the router reads."""
    return MagicMock(id=task_id, task=MagicMock(name=name))

@pytest.fixture
async def test_security(db_session):
    security_id = uuid.uuid4()
    security = SecurityModel(
        id=security_id,
        symbol="AAPL",
        exchange="NASDAQ",
        currency="USD",
        name="Apple Inc",
        is_active=True
    )
    db_session.add(security)
    await db_session.commit()
    return security

@pytest.mark.anyio
async def test_create_note_triggers_title_generation(auth_client, test_user, test_security, db_session, mock_redis_storage):
    mock_title = "AI Generated Title"
    mock_summary = "The note describes a test scenario."

    # Setup mock container for the background task
    mock_ai_service = AsyncMock(spec=AIService)
    mock_ai_service.generate_note_title_and_summary.return_value = (mock_title, mock_summary)
    
    note_repo = SqlAlchemySecurityNoteRepository(db_session)
    
    async def mock_aget(service_type):
        if service_type == AIService:
            return mock_ai_service
        if service_type == SecurityNoteRepository:
            return note_repo
        raise ValueError(f"Unexpected service type: {service_type}")

    mock_container = MagicMock()
    mock_container.aget = AsyncMock(side_effect=mock_aget)
    mock_container.__aenter__ = AsyncMock(return_value=mock_container)
    mock_container.__aexit__ = AsyncMock(return_value=None)
    
    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.router.generate_note_title_task") as mock_task,
        patch("src.market.router.generate_note_summary_task") as mock_summary_task,
    ):
        mock_task.return_value = _task_result("title-task-id", "generate_note_title_task")
        mock_summary_task.return_value = _task_result("summary-task-id", "generate_note_summary_task")
        note_data = {"content": "This is a test note content"}
        response = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/notes",
            json=note_data
        )
        
        assert response.status_code == 200
        created_note_id = response.json()["id"]
        
        # Verify the task was called
        mock_task.assert_called_once_with(created_note_id, request_id=ANY)
        # Summary regeneration is dispatched exactly once for the (security, user)
        mock_summary_task.assert_called_once_with(
            test_security.id, test_user.id, request_id=ANY
        )

        # Task ids are recorded under their Redis labels for later revocation
        assert (
            mock_redis_storage.data[note_title_label(test_user.id, created_note_id)]
            == "title-task-id"
        )
        assert (
            mock_redis_storage.data[note_summary_label(test_user.id, test_security.id)]
            == "summary-task-id"
        )
        
        # Manually run the async part of the task with our mocked container
        await _generate_note_title(created_note_id)
        
        # Fetch notes to verify title was generated
        response = await auth_client.get(f"/api/v1/market/securities/{test_security.id}/notes")
        assert response.status_code == 200
        notes = response.json()
        assert len(notes["items"]) == 1
        assert notes["items"][0]["title"] == mock_title
        assert notes["items"][0]["summary"] == mock_summary

@pytest.mark.anyio
async def test_update_note_triggers_title_generation(auth_client, test_user, test_security, db_session, mock_redis_storage):
    # 1. Create a note first
    with (
        patch("src.market.router.generate_note_title_task") as create_title_task,
        patch("src.market.router.generate_note_summary_task") as create_summary_task,
    ):
        create_title_task.return_value = _task_result("title-before", "generate_note_title_task")
        create_summary_task.return_value = _task_result("summary-before", "generate_note_summary_task")
        note_data = {"content": "Initial content"}
        response = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/notes",
            json=note_data
        )
    assert response.status_code == 200
    note_id = response.json()["id"]
    
    # 2. Update the note and check title generation
    mock_title = "Updated AI Title"
    mock_summary = "The updated note describes changed content."

    # Setup mock container for the background task
    mock_ai_service = AsyncMock(spec=AIService)
    mock_ai_service.generate_note_title_and_summary.return_value = (mock_title, mock_summary)
    
    note_repo = SqlAlchemySecurityNoteRepository(db_session)
    
    async def mock_aget(service_type):
        if service_type == AIService:
            return mock_ai_service
        if service_type == SecurityNoteRepository:
            return note_repo
        raise ValueError(f"Unexpected service type: {service_type}")

    mock_container = MagicMock()
    mock_container.aget = AsyncMock(side_effect=mock_aget)
    mock_container.__aenter__ = AsyncMock(return_value=mock_container)
    mock_container.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.market.task.huey.svcs_registry", MagicMock()),
        patch("src.market.task.Container", return_value=mock_container),
        patch("src.market.router.generate_note_title_task") as mock_task,
        patch("src.market.router.generate_note_summary_task") as mock_summary_task,
    ):
        mock_task.return_value = _task_result("title-after", "generate_note_title_task")
        mock_summary_task.return_value = _task_result("summary-after", "generate_note_summary_task")
        update_data = {"content": "Updated content"}
        response = await auth_client.put(
            f"/api/v1/market/securities/{test_security.id}/notes/{note_id}",
            json=update_data
        )
        assert response.status_code == 200
        
        # Verify the task was called
        mock_task.assert_called_once_with(note_id, request_id=ANY)
        mock_summary_task.assert_called_once_with(
            test_security.id, test_user.id, request_id=ANY
        )

        # Labels are replace-on-write, pointing at the newest task id
        assert (
            mock_redis_storage.data[note_title_label(test_user.id, note_id)]
            == "title-after"
        )
        assert (
            mock_redis_storage.data[note_summary_label(test_user.id, test_security.id)]
            == "summary-after"
        )
        
        # Manually run the async part of the task
        await _generate_note_title(note_id)
        
        # Fetch notes to verify title was updated
        response = await auth_client.get(f"/api/v1/market/securities/{test_security.id}/notes")
        assert response.status_code == 200
        notes = response.json()
        assert len(notes["items"]) == 1
        assert notes["items"][0]["title"] == mock_title
        assert notes["items"][0]["summary"] == mock_summary


@pytest.mark.anyio
async def test_delete_note_triggers_summary_regeneration(auth_client, test_user, test_security, mock_redis_storage):
    # 1. Create a note first (title/summary dispatch suppressed)
    with (
        patch("src.market.router.generate_note_title_task") as create_title_task,
        patch("src.market.router.generate_note_summary_task") as create_summary_task,
    ):
        create_title_task.return_value = _task_result("title-create", "generate_note_title_task")
        create_summary_task.return_value = _task_result("summary-create", "generate_note_summary_task")
        response = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/notes",
            json={"content": "Content to delete"}
        )
    assert response.status_code == 200
    note_id = response.json()["id"]

    # 2. Delete the note and check the summary task is dispatched
    with (
        patch("src.market.router.generate_note_title_task") as mock_title_task,
        patch("src.market.router.generate_note_summary_task") as mock_summary_task,
    ):
        mock_summary_task.return_value = _task_result("summary-fresh", "generate_note_summary_task")
        response = await auth_client.delete(
            f"/api/v1/market/securities/{test_security.id}/notes/{note_id}"
        )
        assert response.status_code == 200

        mock_summary_task.assert_called_once_with(
            test_security.id, test_user.id, request_id=ANY
        )
        # Deleting only regenerates the summary, no title task
        mock_title_task.assert_not_called()

        # The stale labels were consumed; the summary label now points at the
        # freshly dispatched task.
        assert note_title_label(test_user.id, note_id) not in mock_redis_storage.data
        assert (
            mock_redis_storage.data[note_summary_label(test_user.id, test_security.id)]
            == "summary-fresh"
        )

    response = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/notes"
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.anyio
async def test_delete_note_revokes_queued_title_task_and_marks_cancelled(
    auth_client, test_user, test_security, mock_redis_storage
):
    """AC1: revoking the queued title task happens at delete time."""
    with (
        patch("src.market.router.generate_note_title_task") as create_title_task,
        patch("src.market.router.generate_note_summary_task") as create_summary_task,
    ):
        # Dispatch is stubbed here; labels are asserted in the other tests.
        create_title_task.return_value = _task_result("title-create", "generate_note_title_task")
        create_summary_task.return_value = _task_result("summary-create", "generate_note_summary_task")
        response = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/notes",
            json={"content": "Content to delete"},
        )
    assert response.status_code == 200
    note_id = response.json()["id"]

    title_task_id = f"title-task-{uuid.uuid4()}"
    with (
        patch("src.market.router.generate_note_summary_task") as delete_summary_task,
        patch("src.market.router.record_task_label") as mock_record,
    ):
        delete_summary_task.return_value = _task_result("summary-fresh", "generate_note_summary_task")

        async def _record(label, task_id, ttl=None):
            mock_redis_storage.data[label] = task_id

        mock_record.side_effect = _record
        # Re-dispatch the title task for the same note so a label exists.
        with patch("src.market.router.generate_note_title_task") as title_task:
            title_task.return_value = _task_result(title_task_id, "generate_note_title_task")
            response = await auth_client.put(
                f"/api/v1/market/securities/{test_security.id}/notes/{note_id}",
                json={"content": "Updated content"},
            )
            assert response.status_code == 200

        assert mock_redis_storage.data[note_title_label(test_user.id, note_id)] == title_task_id

        response = await auth_client.delete(
            f"/api/v1/market/securities/{test_security.id}/notes/{note_id}"
        )
        assert response.status_code == 200

    # The stale title label was deleted and the queued task is revoked.
    assert note_title_label(test_user.id, note_id) not in mock_redis_storage.data
    assert huey.is_revoked(title_task_id) is True

@pytest.mark.anyio
async def test_delete_note_marks_revoked_task_cancelled_in_dashboard(
    auth_client, test_user, test_security, mock_redis_storage
):
    """The backend writes a visible `cancelled` row for each revoked task."""
    with patch("src.market.router.generate_note_summary_task") as create_summary_task:
        create_summary_task.return_value = _task_result("summary-create", "generate_note_summary_task")
        response = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/notes",
            json={"content": "Content to delete"},
        )
    assert response.status_code == 200
    note_id = response.json()["id"]

    title_task_id = f"title-task-{uuid.uuid4()}"
    summary_task_id = f"summary-task-{uuid.uuid4()}"
    mock_db = AsyncMock()
    app.state.huey_dashboard = {"db": mock_db}

    try:
        with patch("src.market.router.generate_note_summary_task") as delete_summary_task:
            delete_summary_task.return_value = _task_result(
                "summary-fresh", "generate_note_summary_task"
            )
            mock_redis_storage.data[note_title_label(test_user.id, note_id)] = title_task_id
            mock_redis_storage.data[
                note_summary_label(test_user.id, test_security.id)
            ] = summary_task_id

            response = await auth_client.delete(
                f"/api/v1/market/securities/{test_security.id}/notes/{note_id}"
            )
            assert response.status_code == 200
    finally:
        app.state.huey_dashboard = None

    cancelled = {
        call.args[0].id: call.args[0]
        for call in mock_db.upsert_task.await_args_list
    }
    assert set(cancelled) == {title_task_id, summary_task_id}
    assert cancelled[title_task_id].status == "cancelled"
    assert cancelled[title_task_id].name == "generate_note_title_task"
    assert cancelled[summary_task_id].status == "cancelled"
    assert cancelled[summary_task_id].name == "generate_note_summary_task"


@pytest.mark.anyio
async def test_delete_survives_missing_dashboard_db(
    auth_client, test_user, test_security, mock_redis_storage
):
    """A delete never fails because dashboard bookkeeping is unavailable."""
    with patch("src.market.router.generate_note_summary_task") as create_summary_task:
        create_summary_task.return_value = _task_result("summary-create", "generate_note_summary_task")
        response = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/notes",
            json={"content": "Content to delete"},
        )
    note_id = response.json()["id"]

    app.state.huey_dashboard = None
    mock_redis_storage.data[note_title_label(test_user.id, note_id)] = "some-task"

    try:
        response = await auth_client.delete(
            f"/api/v1/market/securities/{test_security.id}/notes/{note_id}"
        )
    finally:
        app.state.huey_dashboard = None

    assert response.status_code == 200


@pytest.mark.anyio
async def test_get_notes_cleans_legacy_reasoning_markers_on_read(
    auth_client, test_user, test_security, db_session, mock_redis_storage
):
    """Legacy rows written before the cleaner must not render reasoning/markdown."""
    with (
        patch("src.market.router.generate_note_title_task") as title_task,
        patch("src.market.router.generate_note_summary_task") as summary_task,
    ):
        title_task.return_value = _task_result("title-legacy", "generate_note_title_task")
        summary_task.return_value = _task_result(
            "summary-legacy", "generate_note_summary_task"
        )
        response = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/notes",
            json={"content": "Legacy content"},
        )
    assert response.status_code == 200
    note_id = response.json()["id"]

    note_repo = SqlAlchemySecurityNoteRepository(db_session)
    await note_repo.update_title_and_summary(
        note_id,
        "<thought>draft title that must never render</thought>## Real title",
        "<thought>draft summary that must never render</thought>A one-sentence summary.",
    )

    response = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/notes"
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["title"] == "Real title"
    assert item["summary"] == "A one-sentence summary."
    assert "<thought" not in item["title"]
    assert "<thought" not in item["summary"]
    assert "#" not in item["title"]
