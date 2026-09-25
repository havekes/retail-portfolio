"""Tests for the service-to-service shared-secret dependency.

These tests exercise `require_service_token` through a throwaway FastAPI app so
no svcs container, database, Redis, or JWT machinery is involved.
"""

from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.auth.api import require_service_token
from src.config.settings import settings

_SERVICE_TOKEN = "test-service-token-value"

app = FastAPI()


@app.get("/protected")
async def protected(_svc: Annotated[None, Depends(require_service_token)]) -> dict:
    return {"ok": True}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def configured_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the settings singleton, not a fresh `Settings()` (root .env pollutes)."""
    monkeypatch.setattr(settings, "market_data_service_token", _SERVICE_TOKEN)


def test_valid_service_token_passes(client: TestClient) -> None:
    response = client.get("/protected", headers={"X-Service-Token": _SERVICE_TOKEN})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_missing_service_token_unauthorized(client: TestClient) -> None:
    response = client.get("/protected")

    assert response.status_code == 401


def test_wrong_service_token_unauthorized(client: TestClient) -> None:
    response = client.get("/protected", headers={"X-Service-Token": "wrong-token"})

    assert response.status_code == 401


def test_blank_service_token_unauthorized(client: TestClient) -> None:
    response = client.get("/protected", headers={"X-Service-Token": "   "})

    assert response.status_code == 401


def test_non_ascii_service_token_unauthorized(client: TestClient) -> None:
    """A non-ASCII header must yield 401, never a ``TypeError`` -> 500.

    Starlette decodes header bytes as latin-1, so a non-ASCII token reaches the
    dependency as a ``str``; comparing bytes avoids ``compare_digest``'s
    ``TypeError`` on non-ASCII ``str`` operands.
    """
    # Raw bytes: httpx refuses a non-ASCII ``str`` header before it reaches the
    # server, so send the latin-1 bytes Starlette will decode.
    response = client.get(
        "/protected", headers={b"X-Service-Token": b"tok\xe9n"}
    )

    assert response.status_code == 401


def test_no_cookie_fallback(client: TestClient) -> None:
    """A user JWT cookie must not satisfy the service-token dependency."""
    response = client.get("/protected", cookies={"auth_token": "some-jwt-token"})

    assert response.status_code == 401


def test_empty_configured_token_never_matches(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dev/test may leave the token blank; a request must still be rejected."""
    monkeypatch.setattr(settings, "market_data_service_token", "")

    response = client.get("/protected")

    assert response.status_code == 401
