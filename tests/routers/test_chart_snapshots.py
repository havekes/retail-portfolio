import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from src.market.model import ChartSnapshotModel, SecurityModel


@pytest.fixture
async def test_security(db_session):
    security = SecurityModel(
        id=uuid.uuid4(),
        symbol="AAPL",
        exchange="US",
        name="Apple Inc.",
        currency="USD",
    )
    db_session.add(security)
    await db_session.commit()
    await db_session.refresh(security)
    return security


@pytest.mark.anyio
async def test_create_chart_snapshot_success(auth_client, test_security, test_user):
    payload = {
        "drawings": {"lines": [{"x1": 10, "y1": 20, "x2": 30, "y2": 40}]},
        "data_window": {"from": 100, "to": 200},
    }
    response = await auth_client.post(
        f"/api/v1/market/securities/{test_security.id}/snapshots",
        json=payload,
    )
    assert response.status_code == 201
    data = response.json()
    assert uuid.UUID(data["id"])
    assert data["security_id"] == str(test_security.id)
    assert data["user_id"] == str(test_user.id)
    assert data["drawings"] == payload["drawings"]
    assert data["data_window"] == payload["data_window"]
    assert "captured_at" in data and data["captured_at"] is not None
    assert "created_at" in data and data["created_at"] is not None


@pytest.mark.anyio
async def test_get_chart_snapshots_ordered_by_captured_at(auth_client, test_security):
    t1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC).isoformat()
    t2 = datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC).isoformat()
    t3 = datetime(2026, 1, 3, 10, 0, 0, tzinfo=UTC).isoformat()

    # Post in unordered sequence: t2, t3, t1
    for t in [t2, t3, t1]:
        resp = await auth_client.post(
            f"/api/v1/market/securities/{test_security.id}/snapshots",
            json={
                "drawings": {"tag": t},
                "data_window": {},
                "captured_at": t,
            },
        )
        assert resp.status_code == 201

    get_resp = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/snapshots"
    )
    assert get_resp.status_code == 200
    items = get_resp.json()
    assert len(items) == 3
    # Check that captured_at is in ascending order
    captured_ats = [item["captured_at"] for item in items]
    assert captured_ats == sorted(captured_ats)
    assert items[0]["drawings"]["tag"] == t1
    assert items[1]["drawings"]["tag"] == t2
    assert items[2]["drawings"]["tag"] == t3


@pytest.mark.anyio
async def test_delete_chart_snapshot_success(auth_client, test_security):
    # Create snapshot
    resp = await auth_client.post(
        f"/api/v1/market/securities/{test_security.id}/snapshots",
        json={"drawings": {}, "data_window": {}},
    )
    assert resp.status_code == 201
    snapshot_id = resp.json()["id"]

    # Delete snapshot
    del_resp = await auth_client.delete(
        f"/api/v1/market/securities/{test_security.id}/snapshots/{snapshot_id}"
    )
    assert del_resp.status_code == 204

    # Subsequent GET returns empty list
    get_resp = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/snapshots"
    )
    assert get_resp.status_code == 200
    assert not any(item["id"] == snapshot_id for item in get_resp.json())


@pytest.mark.anyio
async def test_chart_snapshots_user_isolation(
    auth_client, other_user, client, test_security
):
    # User A (auth_client) creates a snapshot
    post_resp = await auth_client.post(
        f"/api/v1/market/securities/{test_security.id}/snapshots",
        json={"drawings": {"owned_by": "user_a"}, "data_window": {}},
    )
    assert post_resp.status_code == 201
    snapshot_id = post_resp.json()["id"]

    # Log in as User B (other_user)
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": other_user.email, "password": "otherpass"},
    )
    assert login_resp.status_code == 200
    other_token = login_resp.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # User B calls GET snapshots -> should not see User A's snapshot
    get_resp = await client.get(
        f"/api/v1/market/securities/{test_security.id}/snapshots",
        headers=other_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json() == []

    # User B attempts to delete User A's snapshot
    del_resp = await client.delete(
        f"/api/v1/market/securities/{test_security.id}/snapshots/{snapshot_id}",
        headers=other_headers,
    )
    assert del_resp.status_code == 204

    # User A verifies their snapshot is still present
    verify_resp = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/snapshots"
    )
    assert verify_resp.status_code == 200
    items = verify_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == snapshot_id


@pytest.mark.anyio
async def test_chart_snapshots_unauthenticated_rejection(client, test_security):
    fake_snapshot_id = uuid.uuid4()
    # Unauthenticated GET
    get_resp = await client.get(
        f"/api/v1/market/securities/{test_security.id}/snapshots"
    )
    assert get_resp.status_code == 401

    # Unauthenticated POST
    post_resp = await client.post(
        f"/api/v1/market/securities/{test_security.id}/snapshots",
        json={"drawings": {}, "data_window": {}},
    )
    assert post_resp.status_code == 401

    # Unauthenticated DELETE
    del_resp = await client.delete(
        f"/api/v1/market/securities/{test_security.id}/snapshots/{fake_snapshot_id}"
    )
    assert del_resp.status_code == 401


@pytest.mark.anyio
async def test_chart_snapshots_security_cascade_delete(auth_client, db_session):
    # Create security
    security = SecurityModel(
        id=uuid.uuid4(),
        symbol="CASCADE",
        exchange="US",
        name="Cascade Test Inc",
        currency="USD",
    )
    db_session.add(security)
    await db_session.commit()

    # Create snapshot via POST
    post_resp = await auth_client.post(
        f"/api/v1/market/securities/{security.id}/snapshots",
        json={"drawings": {"cascade": True}, "data_window": {}},
    )
    assert post_resp.status_code == 201
    snapshot_id = uuid.UUID(post_resp.json()["id"])

    # Verify snapshot is in DB
    result = await db_session.execute(
        select(ChartSnapshotModel).where(ChartSnapshotModel.id == snapshot_id)
    )
    assert result.scalar_one_or_none() is not None

    # Delete security from db_session
    await db_session.delete(security)
    await db_session.commit()

    # Verify snapshot was cascade-deleted
    result = await db_session.execute(
        select(ChartSnapshotModel).where(ChartSnapshotModel.id == snapshot_id)
    )
    assert result.scalar_one_or_none() is None
