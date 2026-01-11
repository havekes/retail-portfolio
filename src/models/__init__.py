# pyright: reportImportCycles=false
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models to ensure they are registered with SQLAlchemy
from . import (  # noqa: E402
    account,  # pyright: ignore[reportUnusedImport]
    account_type,  # pyright: ignore[reportUnusedImport]
    action_item,  # pyright: ignore[reportUnusedImport]
    external_user,  # pyright: ignore[reportUnusedImport]
    institution,  # pyright: ignore[reportUnusedImport]
    note,  # pyright: ignore[reportUnusedImport]
    position,  # pyright: ignore[reportUnusedImport]
    reminder,  # pyright: ignore[reportUnusedImport]
    security,  # pyright: ignore[reportUnusedImport]
    user,  # pyright: ignore[reportUnusedImport]
    watchlist,  # pyright: ignore[reportUnusedImport]
    watchlist_item,  # pyright: ignore[reportUnusedImport]
)
