from enum import Enum
from typing import Any, TypeVar, override

from sqlalchemy import Dialect, Integer
from sqlalchemy.types import TypeDecorator

T = TypeVar("T", bound=Enum)


class EnumAsInteger(TypeDecorator[T]):
    impl = Integer
    cache_ok = True

    def __init__(self, enum_class: type[T], *args: Any, **kwargs: Any) -> None:  # pyright: ignore[reportExplicitAny]
        super().__init__(*args, **kwargs)
        self.enum_class = enum_class

    @override
    def process_bind_param(self, value: Any | None, dialect: Dialect) -> int | None:  # pyright: ignore[reportExplicitAny]
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        # Allow passing the raw integer value directly
        return int(value)

    @override
    def process_result_value(self, value: int | None, dialect: Dialect) -> T | None:
        if value is None:
            return None
        return self.enum_class(value)
