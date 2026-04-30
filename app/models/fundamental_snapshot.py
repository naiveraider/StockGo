from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


class FundamentalSnapshot(SQLModel, table=True):
    __tablename__ = "fundamental_snapshots"
    __table_args__ = (UniqueConstraint("instrument_id", name="uq_fundamental_snapshot_instrument"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: int = Field(index=True, foreign_key="instruments.id")

    source: Optional[str] = Field(default="yfinance", max_length=32)

    sector: Optional[str] = Field(default=None, max_length=128)
    industry: Optional[str] = Field(default=None, max_length=128)
    long_business_summary: Optional[str] = Field(default=None, max_length=12000)

    market_cap: Optional[float] = Field(default=None, index=True)
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    price_to_sales: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    profit_margin: Optional[float] = None
    return_on_equity: Optional[float] = None
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cashflow: Optional[float] = None
    operating_cashflow: Optional[float] = None
    total_cash: Optional[float] = None
    total_debt: Optional[float] = None
    beta: Optional[float] = None

    raw_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
