from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StockOverview(BaseModel):
    ticker: str
    exchange: Optional[str] = None
    currency: Optional[str] = None

    last_price: Optional[float] = None
    prev_close: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None

    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = Field(default=None, description="Trailing PE if available")
    forward_pe: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None

    updated_at: Optional[datetime] = None


class OhlcPoint(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class HistoryResponse(BaseModel):
    ticker: str
    timeframe: str
    points: list[OhlcPoint]


class NewsItemOut(BaseModel):
    published_at: Optional[datetime] = None
    source: Optional[str] = None
    title: str
    url: str
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None


class NewsListResponse(BaseModel):
    ticker: str
    items: list[NewsItemOut]


class ChartPoint(BaseModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    ma20: Optional[float] = None
    ma200: Optional[float] = None
    rsi14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None


class ChartResponse(BaseModel):
    ticker: str
    timeframe: str
    points: list[ChartPoint]

