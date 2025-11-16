from pydantic import BaseModel, ConfigDict


class AccountType(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str = "CA"
    tax_advantaged: bool
