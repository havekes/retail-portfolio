from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Position(BaseModel):
    id: UUID
    account_id: UUID
    security_symbol: str
    quantity: float
    average_cost: float
    current_price: float
    updated_at: datetime
