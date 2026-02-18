from typing import Annotated

from fastapi import APIRouter, Depends
from svcs.fastapi import DepContainer

from src.auth.api import current_user
from src.auth.api_types import User
from src.market.api_types import Price, SecurityId
from src.market.repository import PriceRepository, SecurityRepository

market_router = APIRouter(prefix="/api/market")


@market_router.get("/prices/{security_id}/last-close")
async def get_last_close_prices(
    _: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> Price:
    """
    Get last close OHLC price for a security
    """
    price_repository = await services.aget(PriceRepository)
    security_repository = await services.aget(SecurityRepository)
    security = await security_repository.get_by_id(security_id)
    price = await price_repository.get_latest_price(security)

    return Price.model_validate(price)
