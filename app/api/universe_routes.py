from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, func, select

from app.db.session import get_session
from app.models.instrument import Instrument
from app.models.market import StockQuote
from app.schemas.universe import InstrumentOut, InstrumentsPage, StockSummary, StockSummaryPage, UniverseSyncResponse
from app.services.universe_service import sync_universe


router = APIRouter(prefix="/v1", tags=["universe"])


@router.post("/universe/sync", response_model=UniverseSyncResponse)
def universe_sync(session: Session = Depends(get_session)):
    inserted, updated, total = sync_universe(session)
    return UniverseSyncResponse(inserted=inserted, updated=updated, total=total)


@router.get("/stocks", response_model=InstrumentsPage)
def stocks_list(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    exchange: str | None = Query(None, description="Optional exchange filter, e.g. NASDAQ, N, A, P"),
    session: Session = Depends(get_session),
):
    q = select(Instrument).where(Instrument.is_etf == False)  # noqa: E712
    if exchange:
        q = q.where(Instrument.exchange == exchange)
    total = session.exec(select(func.count()).select_from(q.subquery())).one()
    items = session.exec(q.order_by(Instrument.ticker.asc()).offset(offset).limit(limit)).all()
    return InstrumentsPage(
        items=[InstrumentOut(ticker=i.ticker, exchange=i.exchange, name=i.name, created_at=i.created_at) for i in items],
        limit=limit,
        offset=offset,
        total=int(total),
    )


@router.get("/stocks/search", response_model=list[InstrumentOut])
def stocks_search(
    q: str = Query(..., min_length=1, max_length=32),
    limit: int = Query(10, ge=1, le=20),
    session: Session = Depends(get_session),
):
    query = q.strip().upper()
    items = session.exec(
        select(Instrument)
        .where(Instrument.is_etf == False)  # noqa: E712
        .where((Instrument.ticker.like(f"{query}%")) | (Instrument.name.like(f"%{q.strip()}%")))
        .order_by(Instrument.ticker.asc())
        .limit(limit)
    ).all()
    return [InstrumentOut(ticker=i.ticker, exchange=i.exchange, name=i.name, created_at=i.created_at) for i in items]


@router.get("/stocks/summary", response_model=StockSummaryPage)
def stocks_summary(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="Optional search by symbol prefix or name"),
    session: Session = Depends(get_session),
):
    base = select(Instrument).where(Instrument.is_etf == False)  # noqa: E712
    if q:
        query = q.strip()
        if query:
            up = query.upper()
            base = base.where(
                (Instrument.ticker.like(f"{up}%")) | (Instrument.name.like(f"%{query}%"))
            )
    total = session.exec(select(func.count()).select_from(base.subquery())).one()

    rows = session.exec(
        select(Instrument, StockQuote)
        .select_from(Instrument)
        .outerjoin(StockQuote, StockQuote.instrument_id == Instrument.id)
        .where(Instrument.is_etf == False)  # noqa: E712
        .order_by(Instrument.ticker.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    summaries: list[StockSummary] = []
    for inst, quote in rows:
        if quote:
            summaries.append(
                StockSummary(
                    ticker=inst.ticker,
                    exchange=inst.exchange,
                    name=inst.name,
                    last=quote.last,
                    change=quote.change,
                    change_percent=quote.change_percent,
                    market_cap=quote.market_cap,
                )
            )
        else:
            summaries.append(
                StockSummary(
                    ticker=inst.ticker,
                    exchange=inst.exchange,
                    name=inst.name,
                )
            )

    return StockSummaryPage(items=summaries, limit=limit, offset=offset, total=int(total))

