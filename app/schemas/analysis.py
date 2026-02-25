from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AnalysisRunRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16, description="US stock ticker, e.g. TSLA")
    start: date | datetime
    end: date | datetime
    timeframe: str = Field(default="1d", description="yfinance interval, e.g. 1d/1h/5m")
    include_news: bool = True
    include_macro: bool = False


Bias = Literal["UP", "DOWN", "NEUTRAL"]


class AnalysisReport(BaseModel):
    summary: str
    reasoning: str
    bias: Bias
    confidence: float = Field(ge=0.0, le=1.0)
    tags: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class AnalysisRunResponse(BaseModel):
    run_id: str
    status: str
    report: Optional[AnalysisReport] = None
    error: Optional[str] = None

