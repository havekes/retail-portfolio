from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models to ensure they are registered with SQLAlchemy
from . import (
    account,
    account_type,
    action_item,
    institution,
    note,
    position,
    reminder,
    security,
    user,
    watchlist,
    watchlist_item,
)
