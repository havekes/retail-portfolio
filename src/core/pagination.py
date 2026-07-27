from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=100)


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    offset: int
    limit: int
