# SQLAlchemy ORM models for the retail portfolio application

from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ActionEnum(Enum):
    hold = "hold"
    observe = "observe"
    buy = "buy"
    sell = "sell"


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now)  # pylint: disable=not-callable

    # Relationships
    accounts: Mapped[list["Account"]] = relationship(back_populates="user")
    watchlists: Mapped[list["Watchlist"]] = relationship(back_populates="user")
    notes: Mapped[list["Note"]] = relationship(back_populates="user")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="user")
    action_items: Mapped[list["ActionItem"]] = relationship(back_populates="user")


class AccountType(Base):
    """Account type model."""

    __tablename__ = "account_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    country: Mapped[str] = mapped_column(String, default="CA")
    tax_advantaged: Mapped[bool] = mapped_column(Boolean)

    # Relationships
    accounts: Mapped[list["Account"]] = relationship(back_populates="account_type")


class Institution(Base):
    """Institution model."""

    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    website: Mapped[str] = mapped_column(String, nullable=True)
    country: Mapped[str] = mapped_column(String, default="CA")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    accounts: Mapped[list["Account"]] = relationship(back_populates="institution")


class Account(Base):
    """Account model."""

    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    account_type_id: Mapped[int] = mapped_column(ForeignKey("account_types.id"))
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Index on (user_id, institution_id, account_type_id)
    __table_args__ = (
        Index(
            "ix_account_user_institution_type",
            "user_id",
            "institution_id",
            "account_type_id",
        ),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="accounts")
    account_type: Mapped["AccountType"] = relationship(back_populates="accounts")
    institution: Mapped["Institution"] = relationship(back_populates="accounts")
    notes: Mapped[list["Note"]] = relationship(back_populates="account")


class Ticker(Base):  # pylint: disable=too-few-public-methods
    """Ticker model."""

    __tablename__ = "tickers"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    sector: Mapped[str] = mapped_column(String, nullable=True)
    industry: Mapped[str] = mapped_column(String, nullable=True)
    market_cap: Mapped[float] = mapped_column(Float)
    pe_ratio: Mapped[float] = mapped_column(Float, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="ticker"
    )
    notes: Mapped[list["Note"]] = relationship(back_populates="ticker")
    action_items: Mapped[list["ActionItem"]] = relationship(back_populates="ticker")


class Watchlist(Base):
    """Watchlist model."""

    __tablename__ = "watchlists"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String, default="Main Watchlist")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now)  # pylint: disable=not-callable

    # Relationships
    user: Mapped["User"] = relationship(back_populates="watchlists")
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist"
    )


class WatchlistItem(Base):
    """Watchlist item model."""

    __tablename__ = "watchlist_items"

    watchlist_id: Mapped[UUID] = mapped_column(
        ForeignKey("watchlists.id"), primary_key=True
    )
    ticker_symbol: Mapped[str] = mapped_column(
        ForeignKey("tickers.symbol"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=func.now)  # pylint: disable=not-callable

    # Relationships
    watchlist: Mapped["Watchlist"] = relationship(back_populates="watchlist_items")
    ticker: Mapped["Ticker"] = relationship(back_populates="watchlist_items")


class Note(Base):  # pylint: disable=too-few-public-methods
    """Note model."""

    __tablename__ = "notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    ticker_symbol: Mapped[str] = mapped_column(
        ForeignKey("tickers.symbol"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now)  # pylint: disable=not-callable
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now,
        onupdate=func.now,  # pylint: disable=not-callable
    )

    # Unique constraint on (user_id, date)
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="notes")
    account: Mapped["Account"] = relationship(back_populates="notes")
    ticker: Mapped["Ticker"] = relationship(back_populates="notes")


class Reminder(Base):
    """Reminder model."""

    __tablename__ = "reminders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    trigger_date: Mapped[datetime] = mapped_column(DateTime)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring_type: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="reminders")


class ActionItem(Base):
    """Action item model."""

    __tablename__ = "action_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticker_symbol: Mapped[str] = mapped_column(ForeignKey("tickers.symbol"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[ActionEnum] = mapped_column(SAEnum(ActionEnum))
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=func.now)  # pylint: disable=not-callable

    # Unique constraint on (user_id, ticker_symbol)
    __table_args__ = (UniqueConstraint("user_id", "ticker_symbol"),)

    # Relationships
    ticker: Mapped["Ticker"] = relationship(back_populates="action_items")
    user: Mapped["User"] = relationship(back_populates="action_items")
