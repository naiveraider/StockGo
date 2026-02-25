from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class InstrumentOut(BaseModel):
    ticker: str
    exchange: Optional[str] = None
    name: Optional[str] = None
    created_at: Optional[datetime] = None


class InstrumentsPage(BaseModel):
    items: list[InstrumentOut]
    limit: int
    offset: int
    total: int


class StockSummary(BaseModel):
    ticker: str
    exchange: Optional[str] = None
    name: Optional[str] = None
    last: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    market_cap: Optional[float] = None


class StockSummaryPage(BaseModel):
    items: list[StockSummary]
    limit: int
    offset: int
    total: int


class ShortTermRow(BaseModel):
    ticker: str
    name: Optional[str] = None
    bias: Literal["UP", "DOWN", "NEUTRAL"]
    confidence: float
    updated_at: datetime


class ShortTermPage(BaseModel):
    items: list[ShortTermRow]
    total: int


class UniverseSyncResponse(BaseModel):
    inserted: int
    updated: int
    total: int

