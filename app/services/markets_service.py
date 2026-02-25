from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from app.schemas.markets import MarketItem, MarketMiniPoint, MarketsOverview


INDEXES: list[tuple[str, str]] = [
    ("^GSPC", "S&P 500"),
    ("^DJI", "Dow 30"),
    ("^IXIC", "Nasdaq"),
    ("^RUT", "Russell 2000"),
    ("^VIX", "VIX"),
    ("GC=F", "Gold"),
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_markets_overview() -> MarketsOverview:
    items: list[MarketItem] = []

    for symbol, name in INDEXES:
        last = None
        change = None
        change_pct = None
        mini: list[MarketMiniPoint] = []

        try:
            t = yf.Ticker(symbol)
            fast: dict[str, Any] = getattr(t, "fast_info", None) or {}

            last = fast.get("last_price") or fast.get("lastPrice")
            prev = fast.get("previous_close") or fast.get("previousClose")
            if last is not None and prev:
                change = float(last) - float(prev)
                change_pct = 100.0 * change / float(prev)

            hist = t.history(period="5d", interval="1h")
            if hist is not None and not hist.empty:
                hist = hist.tail(24)
                for ts, row in hist.iterrows():
                    v = float(row.get("Close") or row.get("close") or row.get("Adj Close") or 0.0)
                    if v:
                        if ts.tzinfo is None:
                            ts = ts.tz_localize(timezone.utc)
                        else:
                            ts = ts.tz_convert(timezone.utc)
                        mini.append(MarketMiniPoint(ts=ts, value=v))
        except Exception:
            # Keep empty/partial item on error
            pass

        items.append(
            MarketItem(
                symbol=symbol,
                name=name,
                last=float(last) if last is not None else None,
                change=change,
                change_percent=change_pct,
                mini=mini,
            )
        )

    return MarketsOverview(items=items)

