"""SQLAlchemy 2.x models (SPEC §4).

Non-negotiable data rule (SPEC §0): transactions are stored in **native currency**. The
TRY value of a transaction is always derived at read time from
`price_native x quantity x fx_rate_to_try`. No TRY-denominated cost basis is ever stored
as a source of truth — `fx_rate_to_try` is a separately stored, separately sourced field
carrying its own `fx_rate_date` and `fx_provider`.

All monetary columns are NUMERIC and round-trip as `Decimal`. Never float.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

#: Wide enough for TWD prices in the hundreds and FX rates to six decimals.
MONEY = Numeric(24, 8)
QTY = Numeric(24, 8)
RATE = Numeric(24, 10)

#: Transaction prices get extra scale because split adjustment divides them. A 3-for-1
#: split turns 100.00 into a non-terminating decimal, so *some* rounding is unavoidable
#: (SPEC §5's cost-basis invariance is a money-level property, not a bit-level one).
#: Twelve places keep the residual on a realistic basis far below a cent — see
#: `PriceService.apply_pending_splits`, which quantizes to this scale and then asserts
#: the invariant against the stored value rather than an in-memory one.
PRICE = Numeric(28, 12)
PRICE_SCALE = Decimal("1e-12")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Side(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class ActionKind(str, enum.Enum):
    SPLIT = "SPLIT"
    DIVIDEND = "DIVIDEND"


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    workspace: Mapped["Workspace | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Workspace(Base):
    __tablename__ = "workspace"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    user: Mapped[User | None] = relationship(back_populates="workspace")
    portfolios: Mapped[list["Portfolio"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    guest_access: Mapped["GuestAccess | None"] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", uselist=False
    )


class GuestAccess(Base):
    __tablename__ = "guest_access"
    __table_args__ = (
        UniqueConstraint("secret_digest", name="uq_guest_access_secret_digest"),
        CheckConstraint("length(secret_digest) = 32", name="ck_guest_access_digest_length"),
    )

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), primary_key=True
    )
    secret_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_access_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="guest_access")


class UserSession(Base):
    __tablename__ = "user_session"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_user_session_public_id"),
        UniqueConstraint("secret_digest", name="uq_user_session_secret_digest"),
        CheckConstraint(
            "length(public_id) = 22", name="ck_user_session_public_id_length"
        ),
        CheckConstraint(
            "length(secret_digest) = 32", name="ck_user_session_digest_length"
        ),
        Index("ix_user_session_user_active", "user_id", "revoked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, active_history=True
    )
    public_id: Mapped[str] = mapped_column(
        String(22), nullable=False, active_history=True
    )
    secret_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_access_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class Portfolio(Base):
    __tablename__ = "portfolio"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "name", name="uq_portfolio_workspace_name"
        ),
        CheckConstraint(
            "length(base_currency) = 3",
            name="ck_portfolio_base_currency_length",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="TRY"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    workspace: Mapped[Workspace] = relationship(back_populates="portfolios")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="portfolio", passive_deletes="all"
    )
    snapshots: Mapped[list["Snapshot"]] = relationship(
        back_populates="portfolio", passive_deletes="all"
    )


class Instrument(Base):
    __tablename__ = "instrument"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    exchange: Mapped[str] = mapped_column(String(16), nullable=False)
    yf_symbol: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    corporate_actions: Mapped[list["CorporateAction"]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Instrument {self.ticker} ({self.yf_symbol}) {self.currency}>"


class Transaction(Base):
    __tablename__ = "transaction"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_transaction_qty_positive"),
        CheckConstraint("price_native >= 0", name="ck_transaction_price_nonneg"),
        CheckConstraint("fx_rate_to_try > 0", name="ck_transaction_fx_positive"),
        Index("ix_transaction_instrument_date", "instrument_id", "trade_date"),
        Index(
            "ix_transaction_portfolio_instrument_date",
            "portfolio_id",
            "instrument_id",
            "trade_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "portfolio.id",
            name="fk_transaction_portfolio_id_portfolio",
            ondelete="CASCADE",
        ),
        nullable=True,
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instrument.id", ondelete="CASCADE"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[Side] = mapped_column(Enum(Side, native_enum=False), nullable=False)

    #: Always positive. Sign is derived from `side` (SPEC §4).
    quantity: Mapped[Decimal] = mapped_column(QTY, nullable=False)
    price_native: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    fees_native: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))

    #: Units of TRY per one unit of the instrument's native currency, on `fx_rate_date`.
    fx_rate_to_try: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    #: The date the rate was actually published — may precede `trade_date` when the trade
    #: fell on a weekend or holiday and the rate was carried forward (SPEC §3).
    fx_rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: Provenance. 'yfinance', 'tcmb', 'manual', or an explicit triangulation label such
    #: as 'yfinance:SEKUSD=X*USDTRY=X' (docs/FINDINGS.md F-2).
    fx_provider: Mapped[str] = mapped_column(String(64), nullable=False)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    instrument: Mapped[Instrument] = relationship(back_populates="transactions")
    portfolio: Mapped[Portfolio | None] = relationship(back_populates="transactions")

    @property
    def fx_carried_forward(self) -> bool:
        """True when no rate was published on the trade date itself."""
        return self.fx_rate_date != self.trade_date

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"<Transaction {self.side.value} {self.quantity} "
            f"@{self.price_native} on {self.trade_date}>"
        )


class PriceCache(Base):
    """Daily closes in native currency.

    Settled historical closes are immutable and cached permanently (SPEC §8). Stored
    unadjusted (`auto_adjust=False`) — split handling rewrites transactions, never
    market prices (SPEC §5).
    """

    __tablename__ = "price_cache"
    __table_args__ = (
        UniqueConstraint("instrument_id", "price_date", name="uq_price_cache_instrument_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instrument.id", ondelete="CASCADE"), nullable=False
    )
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_native: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    is_adjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class FxCache(Base):
    """Published FX rates. Historical rates are immutable and cached permanently."""

    __tablename__ = "fx_cache"
    __table_args__ = (
        UniqueConstraint("base", "quote", "rate_date", "provider", name="uq_fx_cache_key"),
        Index("ix_fx_cache_lookup", "base", "quote", "rate_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base: Mapped[str] = mapped_column(String(3), nullable=False)
    quote: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    #: Provenance label, including any explicit triangulation route (docs/FINDINGS.md F-2).
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class CorporateAction(Base):
    """Splits and dividends (SPEC §5).

    The uniqueness constraint on `(instrument_id, action_date, kind)` plus
    `applied_to_transactions` is what makes split adjustment idempotent — applying the
    same split twice is a bug, and these two guards together prevent it.
    """

    __tablename__ = "corporate_action"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "action_date", "kind", name="uq_corporate_action_identity"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instrument.id", ondelete="CASCADE"), nullable=False
    )
    action_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[ActionKind] = mapped_column(Enum(ActionKind, native_enum=False), nullable=False)
    #: For SPLIT, shares received per share held (a 5-for-1 split is 5).
    ratio: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    applied_to_transactions: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    instrument: Mapped[Instrument] = relationship(back_populates="corporate_actions")


class Snapshot(Base):
    """Optional daily materialisation of the portfolio payload (SPEC §4)."""

    __tablename__ = "snapshot"
    __table_args__ = (
        Index("ix_snapshot_portfolio_date", "portfolio_id", "snapshot_date"),
    )

    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    portfolio_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "portfolio.id",
            name="fk_snapshot_portfolio_id_portfolio",
            ondelete="CASCADE",
        ),
        nullable=True,
    )
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    portfolio: Mapped[Portfolio | None] = relationship(back_populates="snapshots")
