import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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
async def test_create_note_triggers_title_generation(auth_client, test_security, db_session):
    mock_title = "AI Generated Title"
    
    # Setup mock container for the background task
    mock_ai_service = AsyncMock(spec=AIService)
    mock_ai_service.generate_note_title.return_value = mock_title
    
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
        patch("src.market.router.generate_note_title_task") as mock_task
    ):
        note_data = {"content": "This is a test note content"}
        response = await auth_client.post(
            f"/api/market/securities/{test_security.id}/notes",
            json=note_data
        )
        
        assert response.status_code == 200
        created_note_id = response.json()["id"]
        
        # Verify the task was called
        mock_task.assert_called_once_with(created_note_id)
        
        # Manually run the async part of the task with our mocked container
        await _generate_note_title(created_note_id)
        
        # Fetch notes to verify title was generated
        response = await auth_client.get(f"/api/market/securities/{test_security.id}/notes")
        assert response.status_code == 200
        notes = response.json()
        assert len(notes) == 1
        assert notes[0]["title"] == mock_title

@pytest.mark.anyio
async def test_update_note_triggers_title_generation(auth_client, test_security, db_session):
    # 1. Create a note first
    with patch("src.market.router.generate_note_title_task"):
        note_data = {"content": "Initial content"}
        response = await auth_client.post(
            f"/api/market/securities/{test_security.id}/notes",
            json=note_data
        )
    assert response.status_code == 200
    note_id = response.json()["id"]
    
    # 2. Update the note and check title generation
    mock_title = "Updated AI Title"
    
    # Setup mock container for the background task
    mock_ai_service = AsyncMock(spec=AIService)
    mock_ai_service.generate_note_title.return_value = mock_title
    
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
        patch("src.market.router.generate_note_title_task") as mock_task
    ):
        update_data = {"content": "Updated content"}
        response = await auth_client.put(
            f"/api/market/securities/{test_security.id}/notes/{note_id}",
            json=update_data
        )
        assert response.status_code == 200
        
        # Verify the task was called
        mock_task.assert_called_once_with(note_id)
        
        # Manually run the async part of the task
        await _generate_note_title(note_id)
        
        # Fetch notes to verify title was updated
        response = await auth_client.get(f"/api/market/securities/{test_security.id}/notes")
        assert response.status_code == 200
        notes = response.json()
        assert len(notes) == 1
        assert notes[0]["title"] == mock_title
