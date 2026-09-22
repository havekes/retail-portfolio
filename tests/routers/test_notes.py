import pytest
from unittest.mock import AsyncMock, patch, MagicMock, ANY
from src.market.model import SecurityModel
from src.market.task import _generate_note_title
from src.market.ai_service import AIService
from src.market.repository import SecurityNoteRepository
from src.market.repository_sqlalchemy import SqlAlchemySecurityNoteRepository
import uuid

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
async def test_create_note_triggers_title_generation(auth_client, test_user, test_security, db_session):
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
async def test_update_note_triggers_title_generation(auth_client, test_user, test_security, db_session):
    # 1. Create a note first
    with (
        patch("src.market.router.generate_note_title_task"),
        patch("src.market.router.generate_note_summary_task"),
    ):
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
async def test_delete_note_triggers_summary_regeneration(auth_client, test_user, test_security):
    # 1. Create a note first (title/summary dispatch suppressed)
    with (
        patch("src.market.router.generate_note_title_task"),
        patch("src.market.router.generate_note_summary_task"),
    ):
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
        response = await auth_client.delete(
            f"/api/v1/market/securities/{test_security.id}/notes/{note_id}"
        )
        assert response.status_code == 200

        mock_summary_task.assert_called_once_with(
            test_security.id, test_user.id, request_id=ANY
        )
        # Deleting only regenerates the summary, no title task
        mock_title_task.assert_not_called()

    response = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/notes"
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
