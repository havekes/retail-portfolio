import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException
from svcs.fastapi import DepContainer

from src.auth.api import current_user
from src.auth.api_types import User
from src.market.api_types import Price, SecurityId, SecuritySearchResult

from src.market.gateway import MarketGateway
from src.market.repository import (
    PriceRepository,
    SecurityRepository,
    WatchlistRepository,
)
from src.market.schema import PriceHistoryRead, WatchlistRead

logger = logging.getLogger(__name__)

market_router = APIRouter(prefix="/api/market")


@market_router.get("/prices/{security_id}/last-close")
async def market_last_close_price(
    _: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> Price:
    """
    Get last close OHLC price for a security
    """
    price_repository = await services.aget(PriceRepository)
    security_repository = await services.aget(SecurityRepository)
    security = await security_repository.get_by_id_or_fail(security_id)
    price = await price_repository.get_latest_price(security)

    logger.info("Retrieved last close price for security %s", security_id)

    return Price.model_validate(price)


@market_router.get("/search")
async def market_search(
    _: Annotated[User, Depends(current_user)],
    q: Annotated[str, Query(description="Search query", min_length=1, max_length=100)],
    services: DepContainer,
) -> list[SecuritySearchResult]:
    """
    Search for securities by query string
    """
    gateway = services.get(MarketGateway)
    results = gateway.search(q)
    logger.info(
        "Searched for securities with query: %s, found %d results", q, len(results)
    )
    return results


@market_router.get("/prices/{security_id}")
async def market_get_prices(
    _: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    from_date: Annotated[date, Query(description="Start date (ISO 8601)")],
    to_date: Annotated[date, Query(description="End date (ISO 8601)")],
    services: DepContainer,
) -> PriceHistoryRead:
    """
    Get historical prices for a security within a date range
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="from_date must be less than or equal to to_date",
        )

    price_repository = await services.aget(PriceRepository)
    security_repository = await services.aget(SecurityRepository)
    security = await security_repository.get_by_id_or_fail(security_id)
    prices = await price_repository.get_prices(security, from_date, to_date)

    logger.info(
        "Retrieved %d prices for security %s from %s to %s",
        len(prices),
        security_id,
        from_date,
        to_date,
    )

    return PriceHistoryRead(
        security_id=security_id,
        from_date=from_date,
        to_date=to_date,
        prices=[Price.model_validate(price) for price in prices],
    )


@market_router.get("/watchlists")
async def market_watchlists(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> list[WatchlistRead]:
    """
    Get all watchlists for the logged in user
    """
    watchlist_repository = await services.aget(WatchlistRepository)
    return await watchlist_repository.get_all_for_user(user.id)
