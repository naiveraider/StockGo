from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Iterable

import yfinance as yf
from sqlmodel import Session, select

from app.db.engine import get_engine
from app.models.fundamental_snapshot import FundamentalSnapshot
from app.models.instrument import Instrument
from app.models.market import StockQuote

SNAPSHOT_STALE_DAYS = 14
SNAPSHOT_WARMUP_LIMIT = 80


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _normalize_tickers(tickers: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ticker in tickers:
        normalized = ticker.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _extract_snapshot_payload(info: dict[str, Any]) -> dict[str, Any] | None:
    market_cap = _safe_float(info.get("marketCap"))
    long_business_summary = info.get("longBusinessSummary")
    sector = info.get("sector")
    industry = info.get("industry")
    if market_cap is None and not long_business_summary and not sector and not industry:
        return None

    return {
        "source": "yfinance",
        "sector": sector,
        "industry": industry,
        "long_business_summary": long_business_summary,
        "market_cap": market_cap,
        "trailing_pe": _safe_float(info.get("trailingPE")),
        "forward_pe": _safe_float(info.get("forwardPE")),
        "price_to_sales": _safe_float(info.get("priceToSalesTrailing12Months")),
        "revenue_growth": _safe_float(info.get("revenueGrowth")),
        "earnings_growth": _safe_float(info.get("earningsGrowth")),
        "gross_margin": _safe_float(info.get("grossMargins")),
        "operating_margin": _safe_float(info.get("operatingMargins")),
        "profit_margin": _safe_float(info.get("profitMargins")),
        "return_on_equity": _safe_float(info.get("returnOnEquity")),
        "debt_to_equity": _safe_float(info.get("debtToEquity")),
        "current_ratio": _safe_float(info.get("currentRatio")),
        "free_cashflow": _safe_float(info.get("freeCashflow")),
        "operating_cashflow": _safe_float(info.get("operatingCashflow")),
        "total_cash": _safe_float(info.get("totalCash")),
        "total_debt": _safe_float(info.get("totalDebt")),
        "beta": _safe_float(info.get("beta")),
        "raw_data": {
            "website": info.get("website"),
            "country": info.get("country"),
            "fullTimeEmployees": info.get("fullTimeEmployees"),
            "recommendationKey": info.get("recommendationKey"),
        },
    }


def _fetch_info(ticker: str) -> dict[str, Any]:
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


def upsert_fundamental_snapshot(
    session: Session,
    *,
    instrument: Instrument,
    payload: dict[str, Any],
) -> bool:
    existing = session.exec(
        select(FundamentalSnapshot).where(FundamentalSnapshot.instrument_id == instrument.id)
    ).first()
    if existing is None:
        existing = FundamentalSnapshot(instrument_id=instrument.id)
        created = True
    else:
        created = False

    for key, value in payload.items():
        setattr(existing, key, value)
    existing.updated_at = _now_utc()
    session.add(existing)
    session.commit()
    return created


def sync_fundamental_snapshot_for_ticker(session: Session, ticker: str) -> dict[str, Any]:
    instrument = session.exec(
        select(Instrument).where(Instrument.ticker == ticker.strip().upper())
    ).first()
    if instrument is None:
        raise ValueError(f"Ticker not found: {ticker}")

    payload = _extract_snapshot_payload(_fetch_info(instrument.ticker))
    if payload is None:
        return {"ticker": instrument.ticker, "generated": False, "inserted": 0, "updated": 0}

    created = upsert_fundamental_snapshot(session, instrument=instrument, payload=payload)
    return {
        "ticker": instrument.ticker,
        "generated": True,
        "inserted": 1 if created else 0,
        "updated": 0 if created else 1,
    }


def sync_fundamental_snapshots(session: Session, tickers: list[str] | None = None) -> dict[str, Any]:
    if tickers is None:
        resolved = session.exec(
            select(Instrument.ticker)
            .join(StockQuote, StockQuote.instrument_id == Instrument.id)
            .where(Instrument.is_etf == False)  # noqa: E712
            .order_by(StockQuote.market_cap.desc())
        ).all()
    else:
        resolved = _normalize_tickers(tickers)
    if not resolved:
        return {"tickers": [], "requested": 0, "succeeded": 0, "failed": 0, "details": []}

    succeeded = 0
    failed = 0
    details: list[dict[str, Any]] = []
    for ticker in resolved:
        try:
            detail = sync_fundamental_snapshot_for_ticker(session, ticker)
            details.append({"ticker": ticker, "status": "completed", **detail})
            if detail.get("generated"):
                succeeded += 1
            else:
                failed += 1
        except Exception as exc:
            session.rollback()
            details.append({"ticker": ticker, "status": "failed", "error": str(exc)})
            failed += 1
    return {
        "tickers": resolved,
        "requested": len(resolved),
        "succeeded": succeeded,
        "failed": failed,
        "details": details,
    }


def warm_fundamental_snapshots(
    session: Session,
    *,
    warm_limit: int = SNAPSHOT_WARMUP_LIMIT,
    stale_after_days: int = SNAPSHOT_STALE_DAYS,
) -> int:
    stale_before = _as_naive_utc(_now_utc() - timedelta(days=stale_after_days))
    rows = session.exec(
        select(Instrument.ticker, FundamentalSnapshot.updated_at)
        .join(StockQuote, StockQuote.instrument_id == Instrument.id)
        .outerjoin(FundamentalSnapshot, FundamentalSnapshot.instrument_id == Instrument.id)
        .where(Instrument.is_etf == False)  # noqa: E712
        .order_by(StockQuote.market_cap.desc())
        .limit(max(1, warm_limit * 3))
    ).all()

    targets: list[str] = []
    for ticker, updated_at in rows:
        if updated_at is None or _as_naive_utc(updated_at) < stale_before:
            targets.append(ticker)
        if len(targets) >= warm_limit:
            break
    if not targets:
        return 0

    synced = 0
    for ticker in targets:
        try:
            detail = sync_fundamental_snapshot_for_ticker(session, ticker)
            if detail.get("generated"):
                synced += 1
        except Exception:
            session.rollback()
            continue
    return synced


def run_fundamental_snapshots_once(tickers: list[str] | None = None) -> dict[str, Any]:
    engine = get_engine()
    with Session(engine) as session:
        return sync_fundamental_snapshots(session, tickers)
