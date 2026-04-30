from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class LlmPolicy(SQLModel, table=True):
    __tablename__ = "llm_policies"

    key: str = Field(primary_key=True, max_length=64)
    title: str = Field(max_length=128)
    description: str = Field(default="", max_length=512)
    system_prompt: str = Field(sa_column=Column(Text, nullable=False))
    user_prompt: str = Field(sa_column=Column(Text, nullable=False))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")