from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.market.model import IntradayPriceModel, PriceModel
from src.market.schema import PriceSchema
from src.market.service import MarketService

"""Integration tests for market router."""

@pytest.mark.anyio
async def test_watchlists_list_empty(auth_client):
    """Test get_watchlists returns empty list when user has no watchlists."""
    response = await auth_client.get("/api/v1/market/watchlists")

    assert response.status_code == 200
    result = response.json()

    assert result == []

@pytest.mark.anyio
async def test_watchlists_list_success(auth_client, test_watchlists):
    """Test get_watchlists returns user's watchlists."""
    response = await auth_client.get("/api/v1/market/watchlists")

    assert response.status_code == 200
    result = response.json()

    assert len(result) == 2
    assert result[0]["name"] == "Test Watchlist 0"
    assert result[1]["name"] == "Test Watchlist 1"
    # Every watchlist exposes its persisted sort mode, defaulting to custom.
    assert [w["sort"] for w in result] == ["custom", "custom"]
    
    # Test new securities endpoint
    watchlist_id = result[0]["id"]
    response = await auth_client.get(f"/api/v1/market/watchlists/{watchlist_id}/securities")
    assert response.status_code == 200
    securities_result = response.json()
    assert "items" in securities_result
    assert "total" in securities_result
    assert len(securities_result["items"]) >= 0

@pytest.mark.anyio
async def test_watchlists_list_not_owned(auth_client, other_user, db_session):
    """Test get_watchlists does not return other user's watchlists."""
    from uuid import uuid4
    from src.market.model import WatchlistModel
    
    # Create a watchlist for another user
    watchlist_model = WatchlistModel(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Watchlist",
    )
    db_session.add(watchlist_model)
    await db_session.commit()
    
    response = await auth_client.get("/api/v1/market/watchlists")

    assert response.status_code == 200
    result = response.json()

    # Should still be empty for the authenticated user
    assert result == []


@pytest.mark.anyio
async def test_watchlist_add_security(auth_client, test_security):
    """Test POST /watchlists/securities/{security_id} adds a security to the watchlist."""
    response = await auth_client.post(f"/api/v1/market/watchlists/securities/{test_security.id}")
    
    assert response.status_code == 200
    result = response.json()
    assert result["name"] == "Default"
    
    # Check securities using the new endpoint
    watchlist_id = result["id"]
    securities_response = await auth_client.get(f"/api/v1/market/watchlists/{watchlist_id}/securities")
    securities_result = securities_response.json()
    assert len(securities_result["items"]) == 1
    assert securities_result["items"][0]["id"] == str(test_security.id)
    assert securities_result["items"][0]["symbol"] == test_security.symbol


@pytest.mark.anyio
async def test_watchlist_remove_security(auth_client, test_security):
    """Test DELETE /watchlists/securities/{security_id} removes a security from the watchlist."""
    # First add it
    await auth_client.post(f"/api/v1/market/watchlists/securities/{test_security.id}")
    
    # Now remove it
    response = await auth_client.delete(f"/api/v1/market/watchlists/securities/{test_security.id}")
    
    assert response.status_code == 200
    result = response.json()
    assert result["name"] == "Default"
    
    # Check securities using the new endpoint
    watchlist_id = result["id"]
    securities_response = await auth_client.get(f"/api/v1/market/watchlists/{watchlist_id}/securities")
    securities_result = securities_response.json()
    assert len(securities_result["items"]) == 0


@pytest.mark.anyio
async def test_watchlist_add_security_not_found(auth_client):
    """Test POST /watchlists/securities/{security_id} returns 404 if security not found."""
    from uuid import uuid4
    fake_id = uuid4()
    response = await auth_client.post(f"/api/v1/market/watchlists/securities/{fake_id}")
    
    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


@pytest.mark.anyio
async def test_add_security_to_watchlist(auth_client, test_watchlists, test_security):
    """POST /watchlists/{id}/securities/{sid} adds the membership, idempotently."""
    watchlist_id = str(test_watchlists[0].id)
    url = f"/api/v1/market/watchlists/{watchlist_id}/securities/{test_security.id}"

    response = await auth_client.post(url)

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == watchlist_id
    assert result["sort"] == "custom"
    assert [s["id"] for s in result["securities"]] == [str(test_security.id)]
    # Each entry carries its membership metadata.
    membership = result["securities"][0]
    assert membership["position"] == 1
    assert datetime.fromisoformat(membership["added_at"]).tzinfo is not None

    # Adding twice must not duplicate the membership row
    second_response = await auth_client.post(url)

    assert second_response.status_code == 200
    assert [s["id"] for s in second_response.json()["securities"]] == [
        str(test_security.id)
    ]

    securities_response = await auth_client.get(
        f"/api/v1/market/watchlists/{watchlist_id}/securities"
    )
    securities = securities_response.json()
    assert securities["total"] == 1
    assert len(securities["items"]) == 1


@pytest.mark.anyio
async def test_remove_security_from_watchlist(auth_client, test_watchlists, test_security):
    """DELETE /watchlists/{id}/securities/{sid} removes; non-member remove is a no-op."""
    watchlist_id = str(test_watchlists[0].id)
    url = f"/api/v1/market/watchlists/{watchlist_id}/securities/{test_security.id}"

    await auth_client.post(url)
    response = await auth_client.delete(url)

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == watchlist_id
    assert result["securities"] == []

    # Removing a non-member is a successful no-op
    second_response = await auth_client.delete(url)

    assert second_response.status_code == 200
    assert second_response.json()["securities"] == []


@pytest.mark.anyio
async def test_watchlist_membership_unknown_security(auth_client, test_watchlists):
    """POST/DELETE on a random security UUID return 404."""
    from uuid import uuid4

    watchlist_id = str(test_watchlists[0].id)
    url = f"/api/v1/market/watchlists/{watchlist_id}/securities/{uuid4()}"

    post_response = await auth_client.post(url)
    delete_response = await auth_client.delete(url)

    assert post_response.status_code == 404
    assert delete_response.status_code == 404


@pytest.mark.anyio
async def test_watchlist_membership_not_owned(
    auth_client, test_security, other_user, db_session
):
    """POST/DELETE on another user's watchlist return 404 and leave it untouched."""
    from uuid import uuid4

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from src.market.model import WatchlistModel

    other_watchlist = WatchlistModel(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Watchlist",
    )
    db_session.add(other_watchlist)
    await db_session.commit()
    other_watchlist_id = str(other_watchlist.id)

    url = (
        f"/api/v1/market/watchlists/{other_watchlist_id}/securities/{test_security.id}"
    )
    post_response = await auth_client.post(url)
    delete_response = await auth_client.delete(url)

    assert post_response.status_code == 404
    assert delete_response.status_code == 404

    # Cross-user isolation: the other user's watchlist is unchanged
    result = await db_session.execute(
        select(WatchlistModel)
        .options(selectinload(WatchlistModel.securities))
        .where(WatchlistModel.id == other_watchlist.id)
    )
    assert result.scalar_one().securities == []


@pytest.mark.anyio
async def test_watchlist_membership_cross_user_isolation(
    auth_client, test_watchlists, test_security, other_user, db_session
):
    """Caller add/remove on their own watchlist leaves another user's untouched."""
    from uuid import uuid4

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from src.market.model import WatchlistModel

    other_watchlist = WatchlistModel(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Watchlist",
    )
    db_session.add(other_watchlist)
    await db_session.commit()

    watchlist_id = str(test_watchlists[0].id)
    url = f"/api/v1/market/watchlists/{watchlist_id}/securities/{test_security.id}"
    await auth_client.post(url)
    await auth_client.delete(url)

    result = await db_session.execute(
        select(WatchlistModel)
        .options(selectinload(WatchlistModel.securities))
        .where(WatchlistModel.id == other_watchlist.id)
    )
    assert result.scalar_one().securities == []


@pytest.mark.anyio
async def test_watchlist_create(auth_client, test_user):
    """Test POST /watchlists creates a watchlist owned by the caller."""
    response = await auth_client.post(
        "/api/v1/market/watchlists", json={"name": "My New Watchlist"}
    )

    assert response.status_code == 201
    result = response.json()
    assert result["name"] == "My New Watchlist"
    assert result["user_id"] == str(test_user.id)
    assert result["sort"] == "custom"
    assert result["securities"] == []

    # It is now listed for the caller
    list_response = await auth_client.get("/api/v1/market/watchlists")
    assert list_response.status_code == 200
    assert "My New Watchlist" in [w["name"] for w in list_response.json()]


@pytest.mark.anyio
async def test_watchlists_list_includes_securities(auth_client, test_security):
    """Test GET /watchlists returns each watchlist's securities inline."""
    await auth_client.post(f"/api/v1/market/watchlists/securities/{test_security.id}")

    response = await auth_client.get("/api/v1/market/watchlists")

    assert response.status_code == 200
    result = response.json()
    assert len(result) == 1
    assert "securities" in result[0]
    assert result[0]["sort"] == "custom"
    assert len(result[0]["securities"]) == 1
    assert result[0]["securities"][0]["id"] == str(test_security.id)
    assert result[0]["securities"][0]["position"] == 1
    assert "added_at" in result[0]["securities"][0]


@pytest.mark.anyio
async def test_watchlist_rename(auth_client):
    """Test PATCH /watchlists/{id} renames and returns the updated watchlist."""
    create_response = await auth_client.post(
        "/api/v1/market/watchlists", json={"name": "Before"}
    )
    watchlist_id = create_response.json()["id"]

    response = await auth_client.patch(
        f"/api/v1/market/watchlists/{watchlist_id}", json={"name": "After"}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == watchlist_id
    assert result["name"] == "After"

    list_response = await auth_client.get("/api/v1/market/watchlists")
    assert "After" in [w["name"] for w in list_response.json()]
    assert "Before" not in [w["name"] for w in list_response.json()]


@pytest.mark.anyio
async def test_watchlist_rename_duplicate_name(auth_client):
    """Test PATCH /watchlists/{id} returns 409 for a duplicate name."""
    await auth_client.post("/api/v1/market/watchlists", json={"name": "Taken"})
    create_response = await auth_client.post(
        "/api/v1/market/watchlists", json={"name": "Other"}
    )
    watchlist_id = create_response.json()["id"]

    response = await auth_client.patch(
        f"/api/v1/market/watchlists/{watchlist_id}", json={"name": "Taken"}
    )

    assert response.status_code == 409

    # The original name is unchanged
    list_response = await auth_client.get("/api/v1/market/watchlists")
    names = [w["name"] for w in list_response.json()]
    assert "Other" in names


@pytest.mark.anyio
async def test_watchlist_rename_not_owned(auth_client, other_user, db_session):
    """Test PATCH /watchlists/{id} returns 404 for another user's watchlist."""
    from uuid import uuid4
    from src.market.model import WatchlistModel

    watchlist_model = WatchlistModel(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Watchlist",
    )
    db_session.add(watchlist_model)
    await db_session.commit()

    response = await auth_client.patch(
        f"/api/v1/market/watchlists/{watchlist_model.id}", json={"name": "Stolen"}
    )

    assert response.status_code == 404


async def _seed_memberships(
    db_session, watchlist_id, symbols: list[str]
):
    """Create securities and membership rows at positions ``0..n-1``."""
    from uuid import uuid4

    from src.market.model import SecurityModel, WatchlistsSecuritiesModel

    securities = [
        SecurityModel(
            id=uuid4(),
            symbol=symbol,
            exchange="US",
            currency="USD",
            name=f"Order test {symbol}",
            isin=None,
            is_active=True,
            updated_at=datetime.now(timezone.utc),
        )
        for symbol in symbols
    ]
    db_session.add_all(securities)
    await db_session.flush()
    for position, security in enumerate(securities):
        db_session.add(
            WatchlistsSecuritiesModel(
                watchlist_id=watchlist_id,
                security_id=security.id,
                position=position,
            )
        )
    await db_session.commit()
    return securities


async def _membership_positions(db_session, watchlist_id) -> list[tuple[object, int]]:
    from sqlalchemy import select

    from src.market.model import WatchlistsSecuritiesModel

    result = await db_session.execute(
        select(
            WatchlistsSecuritiesModel.security_id,
            WatchlistsSecuritiesModel.position,
        )
        .where(WatchlistsSecuritiesModel.watchlist_id == watchlist_id)
        .order_by(WatchlistsSecuritiesModel.position)
    )
    return [(security_id, position) for security_id, position in result.all()]


@pytest.mark.anyio
async def test_watchlist_patch_sort(auth_client):
    """PATCH {"sort": ...} persists the mode and the next GET reflects it."""
    create_response = await auth_client.post(
        "/api/v1/market/watchlists", json={"name": "Sorted"}
    )
    watchlist_id = create_response.json()["id"]

    response = await auth_client.patch(
        f"/api/v1/market/watchlists/{watchlist_id}", json={"sort": "date_added"}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == watchlist_id
    assert result["name"] == "Sorted"
    assert result["sort"] == "date_added"

    list_response = await auth_client.get("/api/v1/market/watchlists")
    persisted = {w["id"]: w["sort"] for w in list_response.json()}
    assert persisted[watchlist_id] == "date_added"


@pytest.mark.anyio
async def test_watchlist_patch_invalid_sort(auth_client, db_session):
    """PATCH with an unsupported sort value is a 422 and stores nothing."""
    from uuid import UUID

    from src.market.model import WatchlistModel

    create_response = await auth_client.post(
        "/api/v1/market/watchlists", json={"name": "Sort Guard"}
    )
    watchlist_id = create_response.json()["id"]

    response = await auth_client.patch(
        f"/api/v1/market/watchlists/{watchlist_id}", json={"sort": "bogus"}
    )

    assert response.status_code == 422

    watchlist_model = await db_session.get(WatchlistModel, UUID(watchlist_id))
    assert watchlist_model is not None
    assert watchlist_model.sort == "custom"


@pytest.mark.anyio
async def test_watchlist_patch_name_and_sort(auth_client):
    """A combined PATCH applies the rename and the sort mode together."""
    create_response = await auth_client.post(
        "/api/v1/market/watchlists", json={"name": "Before"}
    )
    watchlist_id = create_response.json()["id"]

    response = await auth_client.patch(
        f"/api/v1/market/watchlists/{watchlist_id}",
        json={"name": "After", "sort": "name_asc"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["name"] == "After"
    assert result["sort"] == "name_asc"

    list_response = await auth_client.get("/api/v1/market/watchlists")
    updated = next(w for w in list_response.json() if w["id"] == watchlist_id)
    assert updated["name"] == "After"
    assert updated["sort"] == "name_asc"


@pytest.mark.anyio
async def test_watchlist_patch_empty_payload(auth_client):
    """A bare PATCH returns the current watchlist without changing anything."""
    create_response = await auth_client.post(
        "/api/v1/market/watchlists", json={"name": "Untouched"}
    )
    watchlist_id = create_response.json()["id"]

    response = await auth_client.patch(
        f"/api/v1/market/watchlists/{watchlist_id}", json={}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == watchlist_id
    assert result["name"] == "Untouched"
    assert result["sort"] == "custom"


@pytest.mark.anyio
async def test_watchlist_reorder_securities(auth_client, test_watchlists, db_session):
    """PUT /watchlists/{id}/securities/order rewrites positions 0..n-1."""
    watchlist = test_watchlists[0]
    securities = await _seed_memberships(db_session, watchlist.id, ["AAA", "BBB", "CCC"])

    new_order = [securities[2].id, securities[0].id, securities[1].id]
    response = await auth_client.put(
        f"/api/v1/market/watchlists/{watchlist.id}/securities/order",
        json={"security_ids": [str(security_id) for security_id in new_order]},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["id"] == str(watchlist.id)
    assert [s["id"] for s in result["securities"]] == [
        str(security_id) for security_id in new_order
    ]
    assert [s["position"] for s in result["securities"]] == [0, 1, 2]

    # The new order is persisted, not just reflected in the response.
    assert await _membership_positions(db_session, watchlist.id) == [
        (security_id, position) for position, security_id in enumerate(new_order)
    ]
    list_response = await auth_client.get("/api/v1/market/watchlists")
    persisted = next(w for w in list_response.json() if w["id"] == str(watchlist.id))
    assert [s["id"] for s in persisted["securities"]] == [
        str(security_id) for security_id in new_order
    ]


@pytest.mark.anyio
async def test_watchlist_reorder_rejects_bad_payload(
    auth_client, test_watchlists, db_session
):
    """A payload that is not a permutation is a 422 that changes no position."""
    from uuid import uuid4

    from src.market.model import SecurityModel

    watchlist = test_watchlists[0]
    securities = await _seed_memberships(db_session, watchlist.id, ["AAA", "BBB", "CCC"])
    first, second, third = securities
    seeded = [(security.id, position) for position, security in enumerate(securities)]

    foreign = SecurityModel(
        id=uuid4(),
        symbol="ZZZ",
        exchange="US",
        currency="USD",
        name="Not a member",
        isin=None,
        is_active=True,
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(foreign)
    await db_session.commit()

    url = f"/api/v1/market/watchlists/{watchlist.id}/securities/order"
    bad_payloads = [
        # duplicated id
        [first.id, first.id, third.id],
        # missing id
        [first.id, second.id],
        # foreign id
        [first.id, second.id, foreign.id],
        # a superset of the membership
        [first.id, second.id, third.id, foreign.id],
    ]

    for payload in bad_payloads:
        response = await auth_client.put(
            url, json={"security_ids": [str(sid) for sid in payload]}
        )
        assert response.status_code == 422
        assert await _membership_positions(db_session, watchlist.id) == seeded


@pytest.mark.anyio
async def test_watchlist_write_endpoints_not_owned(
    auth_client, other_user, db_session
):
    """PATCH sort and PUT order return 404 for another user's watchlist."""
    from uuid import uuid4

    from src.market.model import WatchlistModel

    other_watchlist = WatchlistModel(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Watchlist",
    )
    db_session.add(other_watchlist)
    await db_session.commit()

    patch_response = await auth_client.patch(
        f"/api/v1/market/watchlists/{other_watchlist.id}",
        json={"sort": "date_added"},
    )
    put_response = await auth_client.put(
        f"/api/v1/market/watchlists/{other_watchlist.id}/securities/order",
        json={"security_ids": []},
    )

    assert patch_response.status_code == 404
    assert put_response.status_code == 404

    # Cross-user isolation: the other user's watchlist is untouched.
    refreshed = await db_session.get(WatchlistModel, other_watchlist.id)
    assert refreshed is not None
    assert refreshed.sort == "custom"
    assert await _membership_positions(db_session, other_watchlist.id) == []


@pytest.mark.anyio
async def test_watchlist_delete(auth_client):
    """Test DELETE /watchlists/{id} removes the watchlist."""
    create_response = await auth_client.post(
        "/api/v1/market/watchlists", json={"name": "To Delete"}
    )
    watchlist_id = create_response.json()["id"]

    response = await auth_client.delete(f"/api/v1/market/watchlists/{watchlist_id}")

    assert response.status_code == 204

    list_response = await auth_client.get("/api/v1/market/watchlists")
    assert watchlist_id not in [w["id"] for w in list_response.json()]


@pytest.mark.anyio
async def test_watchlist_delete_not_owned(auth_client, other_user, db_session):
    """Test DELETE /watchlists/{id} returns 404 for another user's watchlist."""
    from uuid import uuid4
    from src.market.model import WatchlistModel

    watchlist_model = WatchlistModel(
        id=uuid4(),
        user_id=other_user.id,
        name="Other User Watchlist",
    )
    db_session.add(watchlist_model)
    await db_session.commit()

    response = await auth_client.delete(
        f"/api/v1/market/watchlists/{watchlist_model.id}"
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_watchlist_crud_unauth():
    """Test watchlist create/rename/delete return 401 without auth."""
    from uuid import uuid4

    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        create_response = await ac.post(
            "/api/v1/market/watchlists", json={"name": "Nope"}
        )
        rename_response = await ac.patch(
            f"/api/v1/market/watchlists/{uuid4()}", json={"name": "Nope"}
        )
        delete_response = await ac.delete(f"/api/v1/market/watchlists/{uuid4()}")

    assert create_response.status_code == 401
    assert rename_response.status_code == 401
    assert delete_response.status_code == 401



@pytest.mark.anyio
async def test_get_prices_1d_default(auth_client, test_security, db_session):
    """Test GET /market/prices/{security_id} with default interval=1d."""
    price = PriceModel(
        security_id=test_security.id,
        date=date(2026, 1, 15),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("153.00"),
        adjusted_close=Decimal("153.00"),
        volume=1000000,
    )
    db_session.add(price)
    await db_session.commit()

    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?from_date=2026-01-01&to_date=2026-01-31"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] > 0
    assert len(result["items"]) > 0


@pytest.mark.anyio
async def test_get_prices_1h_intraday(auth_client, test_security, db_session):
    """Test GET /market/prices/{security_id} with interval=1h."""
    candle = IntradayPriceModel(
        security_id=test_security.id,
        timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.50"),
        close=Decimal("151.00"),
        volume=10000,
    )
    db_session.add(candle)
    await db_session.commit()

    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1h&from_date=2026-01-15T00:00:00Z&to_date=2026-01-15T23:59:59Z"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert Decimal(result["items"][0]["close"]) == Decimal("151.00")


@pytest.mark.anyio
async def test_get_prices_4h_intraday_aggregation(auth_client, test_security, db_session):
    """Test GET /market/prices/{security_id} with interval=4haggregates 1h candles."""
    candles = [
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("98.00"),
            close=Decimal("102.00"),
            volume=1000,
        ),
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            open=Decimal("102.00"),
            high=Decimal("110.00"),
            low=Decimal("101.00"),
            close=Decimal("108.00"),
            volume=1500,
        ),
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            open=Decimal("108.00"),
            high=Decimal("109.00"),
            low=Decimal("104.00"),
            close=Decimal("105.00"),
            volume=1200,
        ),
        IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
            open=Decimal("105.00"),
            high=Decimal("107.00"),
            low=Decimal("95.00"),
            close=Decimal("99.00"),
            volume=2000,
        ),
    ]
    for c in candles:
        db_session.add(c)
    await db_session.commit()

    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=4h"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 1
    assert len(result["items"]) == 1

    agg = result["items"][0]
    assert Decimal(agg["open"]) == Decimal("100.00")
    assert Decimal(agg["high"]) == Decimal("110.00")
    assert Decimal(agg["low"]) == Decimal("95.00")
    assert Decimal(agg["close"]) == Decimal("99.00")
    assert agg["volume"] == 5700


@pytest.mark.anyio
async def test_get_prices_1h_intraday_no_date_range(auth_client, test_security, db_session):
    """Test 1h intraday endpoint with no from_date/to_date (the actual repro from #140).

    When the table is populated, a request without date bounds should return data
    instead of an empty list.
    """
    candle = IntradayPriceModel(
        security_id=test_security.id,
        timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
        open=Decimal("150.00"),
        high=Decimal("152.00"),
        low=Decimal("149.50"),
        close=Decimal("151.00"),
        volume=10000,
    )
    db_session.add(candle)
    await db_session.commit()

    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1h"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] >= 1
    assert len(result["items"]) >= 1
    assert Decimal(result["items"][0]["close"]) == Decimal("151.00")


@pytest.mark.anyio
async def test_get_prices_1h_on_the_fly_fetch(auth_client, test_security, db_session):
    """Test GET /market/prices/{security_id} with interval=1h fetches prices on the fly when none exist."""
    async def mock_fetch(security, days=30, from_datetime=None, to_datetime=None):
        candle = IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.50"),
            close=Decimal("151.00"),
            volume=10000,
        )
        db_session.add(candle)
        await db_session.commit()
        return True

    with patch.object(MarketService, "fetch_and_save_intraday_prices", side_effect=mock_fetch) as mock_fetch_svc:
        response = await auth_client.get(
            f"/api/v1/market/prices/{test_security.id}?interval=1h&from_date=2026-01-15T00:00:00Z&to_date=2026-01-15T23:59:59Z"
        )

    assert response.status_code == 200
    mock_fetch_svc.assert_called_once()
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert Decimal(result["items"][0]["close"]) == Decimal("151.00")


@pytest.mark.anyio
async def test_get_prices_4h_on_the_fly_fetch(auth_client, test_security, db_session):
    """Test GET /market/prices/{security_id} with interval=4h fetches prices on the fly and aggregates them."""
    async def mock_fetch(security, days=30, from_datetime=None, to_datetime=None):
        candles = [
            IntradayPriceModel(
                security_id=test_security.id,
                timestamp=datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
                open=Decimal("100.00"),
                high=Decimal("105.00"),
                low=Decimal("98.00"),
                close=Decimal("102.00"),
                volume=1000,
            ),
            IntradayPriceModel(
                security_id=test_security.id,
                timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
                open=Decimal("102.00"),
                high=Decimal("108.00"),
                low=Decimal("101.00"),
                close=Decimal("107.00"),
                volume=1500,
            ),
        ]
        db_session.add_all(candles)
        await db_session.commit()
        return True

    with patch.object(MarketService, "fetch_and_save_intraday_prices", side_effect=mock_fetch) as mock_fetch_svc:
        response = await auth_client.get(
            f"/api/v1/market/prices/{test_security.id}?interval=4h&from_date=2026-01-15T00:00:00Z&to_date=2026-01-15T23:59:59Z"
        )

    assert response.status_code == 200
    mock_fetch_svc.assert_called_once()
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert Decimal(result["items"][0]["open"]) == Decimal("100.00")
    assert Decimal(result["items"][0]["close"]) == Decimal("107.00")


@pytest.mark.anyio
async def test_get_prices_intraday_on_the_fly_no_data(auth_client, test_security):
    """Test GET /market/prices/{security_id} cleanly returns empty list when on-demand fetch finds no data."""
    with patch.object(MarketService, "fetch_and_save_intraday_prices", AsyncMock(return_value=False)) as mock_fetch_svc:
        response = await auth_client.get(
            f"/api/v1/market/prices/{test_security.id}?interval=1h"
        )

    assert response.status_code == 200
    mock_fetch_svc.assert_called_once()
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 0
    assert result["items"] == []


@pytest.mark.anyio
async def test_get_prices_intraday_on_the_fly_when_prior_data_missing(
    auth_client, test_security, db_session
):
    """Test on-the-fly fetch is triggered when DB has recent intraday candles but earlier requested data is missing."""
    existing_candle = IntradayPriceModel(
        security_id=test_security.id,
        timestamp=datetime(2026, 2, 15, 9, 0, tzinfo=timezone.utc),
        open=Decimal("160.00"),
        high=Decimal("162.00"),
        low=Decimal("159.00"),
        close=Decimal("161.00"),
        volume=12000,
    )
    db_session.add(existing_candle)
    await db_session.commit()

    async def mock_fetch(security, days=30, from_datetime=None, to_datetime=None):
        earlier_candle = IntradayPriceModel(
            security_id=test_security.id,
            timestamp=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc),
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.50"),
            close=Decimal("151.00"),
            volume=10000,
        )
        db_session.add(earlier_candle)
        await db_session.commit()
        return True

    with patch.object(MarketService, "fetch_and_save_intraday_prices", side_effect=mock_fetch) as mock_fetch_svc:
        response = await auth_client.get(
            f"/api/v1/market/prices/{test_security.id}?interval=1h&from_date=2026-01-01T00:00:00Z&to_date=2026-02-15T23:59:59Z"
        )

    assert response.status_code == 200
    mock_fetch_svc.assert_called_once()
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 2
    assert len(result["items"]) == 2
    assert Decimal(result["items"][0]["close"]) == Decimal("151.00")
    assert Decimal(result["items"][1]["close"]) == Decimal("161.00")


@pytest.mark.anyio
async def test_get_prices_invalid_interval_returns_422(auth_client, test_security):
    """Test GET /market/prices/{security_id} with invalid interval returns 422."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=invalid"
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_prices_1d_missing_dates_returns_422(auth_client, test_security):
    """Test GET /market/prices/{security_id} with interval=1d missing dates returns 422."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1d"
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_prices_from_date_after_to_date_returns_422(auth_client, test_security):
    """Test GET /market/prices/{security_id} with from_date > to_date returns 422."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1d&from_date=2026-02-01&to_date=2026-01-01"
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_prices_security_not_found_returns_404(auth_client):
    """Test GET /market/prices/{security_id} returns 404 if security not found."""
    from uuid import uuid4
    fake_id = uuid4()
    response = await auth_client.get(
        f"/api/v1/market/prices/{fake_id}?from_date=2026-01-01&to_date=2026-01-31"
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_indicator_preferences_endpoints_return_404(auth_client, test_security):
    """Test GET and PUT /securities/{id}/indicator-preferences return 404 after removal.

    Regression test: the per-security indicator-preferences endpoints were deleted
    (F-user-chart-preferences-T04). FastAPI returns 404 for unregistered routes.
    """
    get_resp = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/indicator-preferences"
    )
    assert get_resp.status_code == 404

    put_resp = await auth_client.put(
        f"/api/v1/market/securities/{test_security.id}/indicator-preferences",
        json={"indicators_json": {}},
    )
    assert put_resp.status_code == 404


@pytest.mark.anyio
async def test_get_prices_1w_weekly_aggregation(auth_client, test_security):
    """Test GET /market/prices/{security_id} with interval=1w aggregates daily prices into weekly candles."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1w&from_date=2026-01-01&to_date=2026-01-31"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 5
    assert len(result["items"]) == 5
    assert result["items"][0]["date"] < result["items"][1]["date"]


@pytest.mark.anyio
async def test_get_prices_1m_monthly_aggregation(auth_client, test_security):
    """Test GET /market/prices/{security_id} with interval=1m aggregates daily prices into monthly candles."""
    response = await auth_client.get(
        f"/api/v1/market/prices/{test_security.id}?interval=1m&from_date=2026-01-01&to_date=2026-02-28"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["security_id"] == str(test_security.id)
    assert result["total"] == 2
    assert len(result["items"]) == 2
    assert result["items"][0]["date"] == "2026-01-01"
    assert result["items"][1]["date"].startswith("2026-02-")


@pytest.mark.anyio
async def test_create_alert_with_wave_source(auth_client, test_security):
    """POST alert with source='wave' persists and GET lists it as 'wave'."""
    create_response = await auth_client.post(
        f"/api/v1/market/securities/{test_security.id}/alerts",
        json={"target_price": "100.00", "condition": "above", "source": "wave"},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["source"] == "wave"

    get_response = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/alerts"
    )
    assert get_response.status_code == 200
    items = get_response.json()["items"]
    assert any(a["id"] == created["id"] and a["source"] == "wave" for a in items)


@pytest.mark.anyio
async def test_create_alert_defaults_to_manual_source(auth_client, test_security):
    """POST alert without source defaults to 'manual'."""
    create_response = await auth_client.post(
        f"/api/v1/market/securities/{test_security.id}/alerts",
        json={"target_price": "100.00", "condition": "above"},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["source"] == "manual"


@pytest.mark.anyio
async def test_create_alert_invalid_source_returns_422(auth_client, test_security):
    """POST alert with invalid source returns 422."""
    response = await auth_client.post(
        f"/api/v1/market/securities/{test_security.id}/alerts",
        json={"target_price": "100.00", "condition": "above", "source": "bogus"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_valuation_not_found(auth_client, test_security):
    """GET valuation returns 404 when not set."""
    response = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/valuation"
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_put_and_get_valuation(auth_client, test_security):
    """PUT valuation creates/updates and GET returns it."""
    put_response = await auth_client.put(
        f"/api/v1/market/securities/{test_security.id}/valuation",
        json={"lower_bound": "25.50", "upper_bound": "60.00"},
    )
    assert put_response.status_code == 200
    data = put_response.json()
    assert data["security_id"] == str(test_security.id)
    assert float(data["lower_bound"]) == 25.50
    assert float(data["upper_bound"]) == 60.00

    # Retrieve
    get_response = await auth_client.get(
        f"/api/v1/market/securities/{test_security.id}/valuation"
    )
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["id"] == data["id"]
    assert float(get_data["lower_bound"]) == 25.50
    assert float(get_data["upper_bound"]) == 60.00


@pytest.mark.anyio
async def test_batch_valuations_endpoint(auth_client, test_security):
    """GET and POST batch endpoints return valuations for requested security IDs."""
    await auth_client.put(
        f"/api/v1/market/securities/{test_security.id}/valuation",
        json={"lower_bound": "15.00", "upper_bound": "35.00"},
    )

    # GET batch with query parameter
    get_res = await auth_client.get(
        f"/api/v1/market/securities/valuation/batch?security_ids={test_security.id}"
    )
    assert get_res.status_code == 200
    items = get_res.json()
    assert len(items) == 1
    assert items[0]["security_id"] == str(test_security.id)

    # POST batch with body
    post_res = await auth_client.post(
        "/api/v1/market/securities/valuation/batch",
        json={"security_ids": [str(test_security.id)]},
    )
    assert post_res.status_code == 200
    post_items = post_res.json()
    assert len(post_items) == 1
    assert post_items[0]["security_id"] == str(test_security.id)

