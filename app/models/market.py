from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class MarketBar(SQLModel, table=True):
    __tablename__ = "market_bars"
    __table_args__ = (
        UniqueConstraint("instrument_id", "timeframe", "ts", name="uq_marketbar_instrument_timeframe_ts"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    timeframe: str = Field(index=True, max_length=16, default="1d")
    ts: datetime = Field(index=True)

    open: float
    high: float
    low: float
    close: float
    volume: float

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TechnicalFeature(SQLModel, table=True):
    __tablename__ = "technical_features"
    __table_args__ = (
        UniqueConstraint("instrument_id", "timeframe", "ts", name="uq_tech_instrument_timeframe_ts"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    timeframe: str = Field(index=True, max_length=16, default="1d")
    ts: datetime = Field(index=True)

    ma20: Optional[float] = None
    ma200: Optional[float] = None
    rsi14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    atr14: Optional[float] = None
    vol20_mean: Optional[float] = None
    vol20_ratio: Optional[float] = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StockQuote(SQLModel, table=True):
    """
    Latest quote snapshot per instrument (used by homepage, etc.).
    """

    __tablename__ = "stock_quotes"
    __table_args__ = (
        UniqueConstraint("instrument_id", name="uq_stockquote_instrument"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: int = Field(index=True, foreign_key="instruments.id")

    last: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    market_cap: Optional[float] = None
    currency: Optional[str] = Field(default=None, max_length=8)
    source: Optional[str] = Field(default=None, max_length=32)

    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

