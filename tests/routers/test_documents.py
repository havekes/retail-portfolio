import pytest
from uuid import uuid4
from src.market.model import SecurityModel

@pytest.mark.anyio
async def test_upload_document_success(auth_client, db_session, test_user):
    """Test successful document upload."""
    # Create a test security
    security_id = uuid4()
    security = SecurityModel(
        id=security_id,
        symbol="AAPL",
        exchange="US",
        name="Apple Inc.",
        currency="USD",
    )
    db_session.add(security)
    await db_session.commit()

    # Prepare file for upload
    file_content = b"test content"
    files = {"file": ("test.txt", file_content, "text/plain")}

    # Perform upload
    response = await auth_client.post(
        f"/api/market/securities/{security_id}/documents",
        files=files
    )

    assert response.status_code == 200
    result = response.json()
    assert result["filename"] == "test.txt"
    assert result["file_size"] == len(file_content)
    assert result["file_type"] == "text/plain"
    assert "id" in result
    assert "file_path" in result
    assert "data/uploads" in result["file_path"]

@pytest.mark.anyio
async def test_get_documents_success(auth_client, db_session, test_user):
    """Test retrieving documents after upload."""
    # Create a test security
    security_id = uuid4()
    security = SecurityModel(
        id=security_id,
        symbol="MSFT",
        exchange="US",
        name="Microsoft Corp",
        currency="USD",
    )
    db_session.add(security)
    await db_session.commit()

    # Upload a document
    file_content = b"test content"
    files = {"file": ("test.txt", file_content, "text/plain")}
    await auth_client.post(
        f"/api/market/securities/{security_id}/documents",
        files=files
    )

    # Get documents
    response = await auth_client.get(f"/api/market/securities/{security_id}/documents")
    assert response.status_code == 200
    result = response.json()
    assert len(result) == 1
    assert result[0]["filename"] == "test.txt"
