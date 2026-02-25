from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class NewsItem(SQLModel, table=True):
    __tablename__ = "news_items"
    __table_args__ = (UniqueConstraint("url", name="uq_news_url"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: Optional[int] = Field(default=None, index=True, foreign_key="instruments.id")

    published_at: Optional[datetime] = Field(default=None, index=True)
    source: Optional[str] = Field(default=None, max_length=128)
    title: str = Field(max_length=512)
    summary: Optional[str] = Field(default=None)
    # MySQL utf8mb4 index key length limit requires a shorter unique column.
    url: str = Field(max_length=512)
    lang: Optional[str] = Field(default="en", max_length=8)

    sentiment_label: Optional[str] = Field(default=None, max_length=16)  # POS/NEG/NEU
    sentiment_score: Optional[float] = None  # -1..1
    sentiment_model: Optional[str] = Field(default=None, max_length=64)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

