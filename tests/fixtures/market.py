"""Market data and EODHD API mocking fixtures."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.schema import UserSchema
from src.market.api_types import EodhdSearchResult, HistoricalPrice
from src.market.model import WatchlistModel
from src.market.schema import SecuritySchema, WatchlistSchema

@pytest.fixture
async def test_watchlist(
    db_session: AsyncSession, test_user: UserSchema
) -> WatchlistSchema:
    """Create and persist a test watchlist."""
    watchlist_model = WatchlistModel(
        id=uuid4(),
        user_id=test_user.id,
        name="Test Watchlist",
    )
    db_session.add(watchlist_model)
    await db_session.commit()
    await db_session.refresh(watchlist_model)

    return WatchlistSchema.model_validate(watchlist_model)

@pytest.fixture
async def test_watchlists(
    db_session: AsyncSession, test_user: UserSchema
) -> list[WatchlistSchema]:
    """Create and persist multiple test watchlists."""
    watchlists = []
    for i in range(2):
        watchlist_model = WatchlistModel(
            id=uuid4(),
            user_id=test_user.id,
            name=f"Test Watchlist {i}",
        )
        db_session.add(watchlist_model)
        await db_session.flush()
        await db_session.refresh(watchlist_model)
        watchlists.append(WatchlistSchema.model_validate(watchlist_model))

    await db_session.commit()
    return watchlists