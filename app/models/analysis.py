from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import Column
from sqlalchemy import JSON
from sqlmodel import Field, SQLModel


class AnalysisRun(SQLModel, table=True):
    __tablename__ = "analysis_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(default_factory=lambda: str(uuid4()), index=True, unique=True, max_length=36)

    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    start: datetime = Field(index=True)
    end: datetime = Field(index=True)
    timeframe: str = Field(max_length=16, default="1d")

    status: str = Field(max_length=16, default="completed")  # queued/running/completed/failed
    error: Optional[str] = Field(default=None, max_length=1024)

    prompt_version: Optional[str] = Field(default="v1", max_length=32)
    model: Optional[str] = Field(default=None, max_length=64)
    input_hash: Optional[str] = Field(default=None, max_length=64)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalysisOutput(SQLModel, table=True):
    __tablename__ = "analysis_outputs"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True, foreign_key="analysis_runs.id")

    bias: str = Field(max_length=16)  # UP/DOWN/NEUTRAL
    confidence: float = 0.5

    summary_text: str = Field(max_length=8000)
    reasoning_text: str = Field(max_length=4000)

    tags: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    evidence: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

