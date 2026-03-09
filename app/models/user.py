from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.core.roles import ROLE_MEMBER


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: str = Field(default=ROLE_MEMBER, max_length=32, index=True)  # member | intermediate | advanced | admin

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

