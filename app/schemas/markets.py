from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class MarketMiniPoint(BaseModel):
  ts: datetime
  value: float


class MarketItem(BaseModel):
  symbol: str
  name: str
  last: Optional[float] = None
  change: Optional[float] = None
  change_percent: Optional[float] = None
  mini: List[MarketMiniPoint] = []


class MarketsOverview(BaseModel):
  items: list[MarketItem]

