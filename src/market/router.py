from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.auth import current_user
from src.market.api_types import Price, SecurityId
from src.market.repository import PriceRepository, SecurityRepository
from src.market.repository_eodhd import eodhd_price_repository_factory
from src.market.repository_sqlalchemy import sqlalchemy_security_repository_factory
from src.schemas import User

router = APIRouter(prefix="/api/market")


@router.get("/prices/{security_id}/last-close")
async def get_last_close_prices(
    _: Annotated[User, Depends(current_user)],
    price_repository: Annotated[
        PriceRepository, Depends(eodhd_price_repository_factory)
    ],
    security_repository: Annotated[
        SecurityRepository, Depends(sqlalchemy_security_repository_factory)
    ],
    security_id: SecurityId,
) -> Price:
    """
    Get last close OHLC price for a security
    """
    security = await security_repository.get_by_id(security_id)
    price = await price_repository.get_latest_price(security)

    return Price.model_validate(price)
