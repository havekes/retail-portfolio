from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Position(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    security_symbol: str
    quantity: float
    average_cost: float | None = None
