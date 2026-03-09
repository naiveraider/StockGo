from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class UserSelection(SQLModel, table=True):
    __tablename__ = "user_selections"
    __table_args__ = (
        UniqueConstraint("user_id", "instrument_id", name="uq_user_selection_user_instrument"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
