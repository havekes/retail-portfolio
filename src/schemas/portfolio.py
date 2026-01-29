from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PortfolioBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None
    user_id: UUID
    is_active: bool = True
    created_at: datetime | None = None


class PortfolioRead(PortfolioBase):
    id: UUID


class PortfolioWrite(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None
    is_active: bool = True


class PortfolioAccountBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: UUID
    account_id: UUID
    added_at: datetime | None = None


class PortfolioAccountRead(PortfolioAccountBase):
    pass


class PortfolioAccountWrite(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: UUID
    account_id: UUID
