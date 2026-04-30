from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class PickCache(SQLModel, table=True):
    __tablename__ = "pick_caches"

    key: str = Field(primary_key=True, max_length=64)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    source_model: str | None = Field(default=None, max_length=64)
    fallback_used: bool = Field(default=False)
    candidates_considered: int = Field(default=0)
    ideas: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))