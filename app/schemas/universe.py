from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


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


class ShortTermIdea(BaseModel):
    ticker: str
    name: Optional[str] = None
    why_now: str
    catalyst: str
    catalyst_date: Optional[str] = None
    technical_setup: str
    bull_case: str
    bear_case: str
    entry_range: str
    exit_strategy: str
    risk_level: Literal["low", "medium", "high"]
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ShortTermIdeasResponse(BaseModel):
    generated_at: datetime
    source_model: Optional[str] = None
    fallback_used: bool = False
    candidates_considered: int = 0
    ideas: list[ShortTermIdea]


class LongTermIdea(BaseModel):
    ticker: str
    name: Optional[str] = None
    business_model: str
    growth_drivers: str
    competitive_advantage: str
    risks_and_threats: str
    valuation: str
    why_outperform: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class LongTermIdeasResponse(BaseModel):
    generated_at: datetime
    source_model: Optional[str] = None
    fallback_used: bool = False
    candidates_considered: int = 0
    ideas: list[LongTermIdea]


class UniverseSyncResponse(BaseModel):
    inserted: int
    updated: int
    total: int

