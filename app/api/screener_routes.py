from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, distinct, func, select

from app.db.session import get_session
from app.models.analysis import AnalysisOutput, AnalysisRun
from app.models.instrument import Instrument
from app.schemas.analysis import AnalysisRunRequest, AnalysisRunResponse
from app.schemas.universe import InstrumentOut, InstrumentsPage, ShortTermRow, ShortTermPage
from app.services.analysis_service import run_analysis_sync
from app.services.instrument_service import get_or_create_instrument


router = APIRouter(prefix="/v1/screener", tags=["screener"])


@router.get("/stocks", response_model=InstrumentsPage)
def screener_stocks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="Optional search by symbol prefix or name"),
    session: Session = Depends(get_session),
):
    # Only instruments that appear in completed analysis_runs AND have an AnalysisOutput
    base = (
        select(Instrument)
        .join(AnalysisRun, AnalysisRun.instrument_id == Instrument.id)
        .join(AnalysisOutput, AnalysisOutput.run_id == AnalysisRun.id)
        .where(Instrument.is_etf == False)  # noqa: E712
        .where(AnalysisRun.status == "completed")
    )
    if q:
        query = q.strip()
        if query:
            up = query.upper()
            base = base.where(
                (Instrument.ticker.like(f"{up}%")) | (Instrument.name.like(f"%{query}%"))
            )

    # Remove duplicates by ticker
    sub = select(distinct(Instrument.ticker).label("ticker")).select_from(base.subquery())
    total = session.exec(select(func.count()).select_from(sub.subquery())).one()

    items = (
        session.exec(
            base.order_by(Instrument.ticker.asc()).offset(offset).limit(limit)
        ).all()
    )
    return InstrumentsPage(
        items=[InstrumentOut(ticker=i.ticker, exchange=i.exchange, name=i.name, created_at=i.created_at) for i in items],
        limit=limit,
        offset=offset,
        total=int(total),
    )


@router.post("/add", response_model=AnalysisRunResponse)
def screener_add(
    ticker: str,
    days: int = Query(90, ge=7, le=365),
    session: Session = Depends(get_session),
):
    """
    Add a ticker into screener by triggering an analysis run.
    This guarantees there is at least one analysis_runs row for the instrument.
    """
    inst = get_or_create_instrument(session, ticker)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    req = AnalysisRunRequest(
        ticker=inst.ticker,
        start=start,
        end=end,
        timeframe="1d",
        include_news=True,
        include_macro=False,
    )
    return run_analysis_sync(session, req)


@router.get("/short-term", response_model=ShortTermPage)
def screener_short_term(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="Search by symbol prefix or name"),
    session: Session = Depends(get_session),
):
    """
    List short-term bias rows based on analysis_outputs joined with instruments.
    One row per (instrument, latest completed run). Optional search by symbol or name.
    """
    # Latest completed run per instrument
    sub = (
        select(
            AnalysisRun.instrument_id,
            func.max(AnalysisRun.created_at).label("max_created"),
        )
        .where(AnalysisRun.status == "completed")
        .group_by(AnalysisRun.instrument_id)
        .subquery()
    )

    base = (
        select(Instrument, AnalysisOutput, AnalysisRun)
        .join(sub, sub.c.instrument_id == Instrument.id)
        .join(
            AnalysisRun,
            (AnalysisRun.instrument_id == sub.c.instrument_id)
            & (AnalysisRun.created_at == sub.c.max_created),
        )
        .join(AnalysisOutput, AnalysisOutput.run_id == AnalysisRun.id)
        .where(Instrument.is_etf == False)  # noqa: E712
    )
    if q:
        query = q.strip()
        if query:
            up = query.upper()
            base = base.where(
                (Instrument.ticker.like(f"{up}%")) | (Instrument.name.like(f"%{query}%"))
            )
    base = base.order_by(AnalysisRun.created_at.desc())

    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    rows = session.exec(base.offset(offset).limit(limit)).all()

    out: list[ShortTermRow] = []
    for inst, out_row, run in rows:
        out.append(
            ShortTermRow(
                ticker=inst.ticker,
                name=inst.name,
                bias=out_row.bias,
                confidence=float(out_row.confidence),
                updated_at=run.created_at,
            )
        )
    return ShortTermPage(items=out, total=int(total))

