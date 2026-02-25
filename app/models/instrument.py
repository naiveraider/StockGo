from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Instrument(SQLModel, table=True):
    __tablename__ = "instruments"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True, unique=True, max_length=32)
    exchange: Optional[str] = Field(default="US", max_length=16)
    name: Optional[str] = Field(default=None, max_length=128)
    is_etf: bool = Field(default=False, index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

