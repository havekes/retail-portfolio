from pydantic import BaseModel


class Institution(BaseModel):
    id: int
    name: str
    website: str | None = None
    country: str = "CA"
    is_active: bool = True
