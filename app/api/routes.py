from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.analysis import AnalysisRunRequest, AnalysisRunResponse
from app.schemas.markets import MarketsOverview
from app.schemas.stock import ChartResponse, HistoryResponse, NewsListResponse, StockOverview
from app.services.analysis_service import get_latest_report, get_run_response, run_analysis_sync
from app.services.instrument_service import get_or_create_instrument
from app.services.markets_service import get_markets_overview
from app.services.stock_service import get_chart_data, get_history, get_news_list, get_stock_overview


router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}


@router.post("/v1/analysis/run", response_model=AnalysisRunResponse)
def analysis_run(req: AnalysisRunRequest, session: Session = Depends(get_session)):
    return run_analysis_sync(session, req)


@router.get("/v1/analysis/run/{run_id}", response_model=AnalysisRunResponse)
def analysis_run_get(run_id: str, session: Session = Depends(get_session)):
    return get_run_response(session, run_id)


@router.get("/v1/report/latest", response_model=AnalysisRunResponse)
def report_latest(ticker: str, session: Session = Depends(get_session)):
    return get_latest_report(session, ticker)


@router.get("/v1/report/long-term", response_model=AnalysisRunResponse)
def report_long_term(
    ticker: str,
    years: int = Query(5, ge=1, le=15),
    session: Session = Depends(get_session),
):
    # Long-term bias: longer lookback, typically price/technicals weighted more than headlines.
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * years)
    req = AnalysisRunRequest(
        ticker=ticker,
        start=start,
        end=end,
        timeframe="1d",
        include_news=False,
        include_macro=False,
    )
    return run_analysis_sync(session, req)


@router.get("/v1/stock/overview", response_model=StockOverview)
def stock_overview(ticker: str = Query(..., min_length=1, max_length=16)):
    return get_stock_overview(ticker)


@router.get("/v1/stock/history", response_model=HistoryResponse)
def stock_history(
    ticker: str = Query(..., min_length=1, max_length=16),
    days: int = Query(60, ge=1, le=365),
    timeframe: str = Query("1d"),
    session: Session = Depends(get_session),
):
    inst = get_or_create_instrument(session, ticker)
    return get_history(session, instrument=inst, days=days, timeframe=timeframe)


@router.get("/v1/stock/news", response_model=NewsListResponse)
def stock_news(
    ticker: str = Query(..., min_length=1, max_length=16),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    inst = get_or_create_instrument(session, ticker)
    return get_news_list(session, instrument=inst, limit=limit)


@router.get("/v1/stock/chart", response_model=ChartResponse)
def stock_chart(
    ticker: str = Query(..., min_length=1, max_length=16),
    days: int = Query(120, ge=1, le=730),
    timeframe: str = Query("1d"),
    session: Session = Depends(get_session),
):
    inst = get_or_create_instrument(session, ticker)
    return get_chart_data(session, instrument=inst, days=days, timeframe=timeframe)


@router.get("/v1/markets/overview", response_model=MarketsOverview)
def markets_overview():
    return get_markets_overview()

