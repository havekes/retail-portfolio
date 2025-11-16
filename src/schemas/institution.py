from typing import Optional

from pydantic import BaseModel


class Institution(BaseModel):
    id: int
    name: str
    website: Optional[str] = None
    country: str = "CA"
    is_active: bool = True
