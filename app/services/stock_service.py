from __future__ import annotations

from datetime import datetime, timedelta, timezone

import yfinance as yf
from sqlmodel import Session, select
from app.models.instrument import Instrument
from app.models.market import MarketBar, TechnicalFeature
from app.models.news import NewsItem
from app.schemas.stock import ChartPoint, ChartResponse, HistoryResponse, NewsItemOut, NewsListResponse, OhlcPoint, StockOverview


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_stock_overview(ticker: str) -> StockOverview:
    t = ticker.strip().upper()
    yf_t = yf.Ticker(t)

    fast = getattr(yf_t, "fast_info", None) or {}
    info = {}
    try:
        info = yf_t.info or {}
    except Exception:
        info = {}

    last_price = fast.get("last_price") or fast.get("lastPrice")
    prev_close = fast.get("previous_close") or fast.get("previousClose")
    change = None
    change_pct = None
    if last_price is not None and prev_close:
        change = float(last_price) - float(prev_close)
        if prev_close:
            change_pct = 100.0 * change / float(prev_close)

    return StockOverview(
        ticker=t,
        exchange=fast.get("exchange") or info.get("exchange"),
        currency=fast.get("currency") or info.get("currency"),
        last_price=last_price,
        prev_close=prev_close,
        change=change,
        change_percent=change_pct,
        market_cap=float(info["marketCap"]) if "marketCap" in info and info["marketCap"] is not None else None,
        pe_ratio=float(info["trailingPE"]) if "trailingPE" in info and info["trailingPE"] is not None else None,
        forward_pe=float(info["forwardPE"]) if "forwardPE" in info and info["forwardPE"] is not None else None,
        fifty_two_week_high=float(info["fiftyTwoWeekHigh"])
        if "fiftyTwoWeekHigh" in info and info["fiftyTwoWeekHigh"] is not None
        else None,
        fifty_two_week_low=float(info["fiftyTwoWeekLow"])
        if "fiftyTwoWeekLow" in info and info["fiftyTwoWeekLow"] is not None
        else None,
        updated_at=_now_utc(),
    )


def get_stock_overviews_batch(tickers: list[str], max_workers: int = 8) -> list[StockOverview | None]:
    """
    Fetch overviews for multiple tickers **sequentially** using yfinance only.
    Returns one entry per ticker in same order; None where fetch failed.
    """
    if not tickers:
        return []
    tickers = [t.strip().upper() for t in tickers if t and t.strip()]
    if not tickers:
        return []

    results: list[StockOverview | None] = []
    for t in tickers:
        try:
            results.append(get_stock_overview(t))
        except Exception:
            results.append(None)
    return results


def get_history(session: Session, *, instrument: Instrument, days: int = 60, timeframe: str = "1d") -> HistoryResponse:
    end = _now_utc()
    start = end - timedelta(days=max(1, days))
    bars = session.exec(
        select(MarketBar)
        .where(
            MarketBar.instrument_id == instrument.id,
            MarketBar.timeframe == timeframe,
            MarketBar.ts >= start,
            MarketBar.ts <= end,
        )
        .order_by(MarketBar.ts.asc())
    ).all()
    points = [
        OhlcPoint(
            ts=b.ts,
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume,
        )
        for b in bars
    ]
    return HistoryResponse(ticker=instrument.ticker, timeframe=timeframe, points=points)


def get_news_list(session: Session, *, instrument: Instrument, limit: int = 20) -> NewsListResponse:
    items = session.exec(
        select(NewsItem)
        .where(NewsItem.instrument_id == instrument.id)
        .order_by(NewsItem.published_at.desc())
        .limit(limit)
    ).all()
    return NewsListResponse(
        ticker=instrument.ticker,
        items=[
            NewsItemOut(
                published_at=n.published_at,
                source=n.source,
                title=n.title,
                url=n.url,
                sentiment_label=n.sentiment_label,
                sentiment_score=n.sentiment_score,
            )
            for n in items
        ],
    )


def get_chart_data(
    session: Session,
    *,
    instrument: Instrument,
    days: int = 120,
    timeframe: str = "1d",
) -> ChartResponse:
    end = _now_utc()
    start = end - timedelta(days=max(1, days))

    bars = session.exec(
        select(MarketBar)
        .where(
            MarketBar.instrument_id == instrument.id,
            MarketBar.timeframe == timeframe,
            MarketBar.ts >= start,
            MarketBar.ts <= end,
        )
        .order_by(MarketBar.ts.asc())
    ).all()
    feats = session.exec(
        select(TechnicalFeature)
        .where(
            TechnicalFeature.instrument_id == instrument.id,
            TechnicalFeature.timeframe == timeframe,
            TechnicalFeature.ts >= start,
            TechnicalFeature.ts <= end,
        )
        .order_by(TechnicalFeature.ts.asc())
    ).all()
    feat_by_ts = {f.ts: f for f in feats}

    points: list[ChartPoint] = []
    for b in bars:
        f = feat_by_ts.get(b.ts)
        points.append(
            ChartPoint(
                ts=b.ts,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                ma20=f.ma20 if f else None,
                ma200=f.ma200 if f else None,
                rsi14=f.rsi14 if f else None,
                macd=f.macd if f else None,
                macd_signal=f.macd_signal if f else None,
            )
        )

    return ChartResponse(ticker=instrument.ticker, timeframe=timeframe, points=points)

