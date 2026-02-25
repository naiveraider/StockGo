from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlmodel import Session, select

from app.models.instrument import Instrument
from app.models.market import StockQuote
from app.services.stock_service import get_stock_overviews_batch


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def refresh_quotes_for_tickers(session: Session, tickers: Iterable[str]) -> int:
    """
    Fetch quotes for given tickers (Alpha Vantage preferred via get_stock_overview)
    and upsert into stock_quotes. Returns number of updated rows.
    """
    norm = [t.strip().upper() for t in tickers if t and t.strip()]
    if not norm:
        return 0

    instruments = session.exec(
        select(Instrument).where(Instrument.ticker.in_(norm))
    ).all()
    if not instruments:
        return 0

    ordered = sorted(instruments, key=lambda i: i.ticker)
    ov_list = get_stock_overviews_batch([i.ticker for i in ordered])

    updated = 0
    for inst, ov in zip(ordered, ov_list):
        if ov is None:
            continue
        quote = session.exec(
            select(StockQuote).where(StockQuote.instrument_id == inst.id)
        ).first()
        if quote is None:
            quote = StockQuote(instrument_id=inst.id)
        quote.last = ov.last_price
        quote.change = ov.change
        quote.change_percent = ov.change_percent
        quote.market_cap = ov.market_cap
        quote.currency = ov.currency
        quote.source = "alpha_vantage"  # or 'yfinance' inside get_stock_overview, but we prefer AV
        quote.updated_at = _now_utc()
        session.add(quote)
        updated += 1

    session.commit()
    return updated

