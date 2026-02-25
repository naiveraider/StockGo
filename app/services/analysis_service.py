from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.analysis import AnalysisOutput, AnalysisRun
from app.schemas.analysis import AnalysisReport, AnalysisRunRequest, AnalysisRunResponse
from app.services.instrument_service import get_or_create_instrument
from app.services.market_service import fetch_history_df, get_last_bar_ts, upsert_market_bars
from app.services.news_service import fetch_google_news_entries, get_last_news_published_at, upsert_news_items
from app.services.report_service import generate_report, load_latest_snapshot
from app.services.technical_service import upsert_technical_features
from app.services.timeutil import as_utc_dt


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_run(
    session: Session,
    *,
    instrument_id: int,
    start: datetime,
    end: datetime,
    timeframe: str,
    status: str,
) -> AnalysisRun:
    run = AnalysisRun(
        instrument_id=instrument_id,
        start=start,
        end=end,
        timeframe=timeframe,
        status=status,
        updated_at=_now_utc(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def set_run_failed(session: Session, run: AnalysisRun, err: str) -> None:
    # If the session is in a failed transaction state, clear it first.
    try:
        session.rollback()
    except Exception:
        pass
    run.status = "failed"
    run.error = (err or "unknown error")[:1024]
    run.updated_at = _now_utc()
    session.add(run)
    session.commit()


def set_run_completed(session: Session, run: AnalysisRun, *, input_hash: str, model_used: str | None) -> None:
    run.status = "completed"
    run.input_hash = input_hash
    run.model = model_used
    run.updated_at = _now_utc()
    session.add(run)
    session.commit()


def store_output(session: Session, *, run_db_id: int, report: dict) -> None:
    out = AnalysisOutput(
        run_id=run_db_id,
        bias=report["bias"],
        confidence=float(report.get("confidence", 0.5)),
        summary_text=report["summary"],
        reasoning_text=report["reasoning"],
        tags=report.get("tags") or {},
        evidence=report.get("evidence") or {},
    )
    session.add(out)
    session.commit()


def run_analysis_sync(session: Session, req: AnalysisRunRequest) -> AnalysisRunResponse:
    inst = get_or_create_instrument(session, req.ticker)
    start = as_utc_dt(req.start, end_of_day=False)
    end = as_utc_dt(req.end, end_of_day=True)

    run = create_run(session, instrument_id=inst.id, start=start, end=end, timeframe=req.timeframe, status="running")

    try:
        # 1) Market data (incremental with small backfill)
        last_bar_ts = get_last_bar_ts(session, instrument_id=inst.id, timeframe=req.timeframe)
        market_fetch_start = start
        if last_bar_ts:
            market_fetch_start = max(start, last_bar_ts - timedelta(days=5))
        df = fetch_history_df(inst.ticker, market_fetch_start, end, req.timeframe)
        upsert_market_bars(session, instrument_id=inst.id, timeframe=req.timeframe, df=df)

        # 2) Technical features (recompute with warmup window to keep rolling indicators correct)
        warmup_days = 400 if req.timeframe.endswith("d") else 60
        feature_start = max(start, market_fetch_start - timedelta(days=warmup_days))
        upsert_technical_features(session, instrument_id=inst.id, timeframe=req.timeframe, start=feature_start, end=end)

        # 3) News (free): Google News RSS query
        if req.include_news:
            last_news = get_last_news_published_at(session, instrument_id=inst.id)
            news_start = start
            if last_news:
                # RSS is usually recent-only; still filter by range, and allow small backfill.
                news_start = max(start, last_news - timedelta(days=3))
            q = f"{inst.ticker} stock"
            entries = fetch_google_news_entries(q)
            upsert_news_items(session, instrument_id=inst.id, entries=entries, start=news_start, end=end)

        # 4) Snapshot + report (rule by default; LLM if configured)
        snapshot = load_latest_snapshot(
            session,
            instrument_id=inst.id,
            timeframe=req.timeframe,
            start=start,
            end=end,
        )
        report_json, input_hash, model_used = generate_report(snapshot)

        store_output(session, run_db_id=run.id, report=report_json)
        set_run_completed(session, run, input_hash=input_hash, model_used=model_used)

        report = AnalysisReport(
            summary=report_json["summary"],
            reasoning=report_json["reasoning"],
            bias=report_json["bias"],
            confidence=float(report_json.get("confidence", 0.5)),
            tags=report_json.get("tags") or {},
            evidence=report_json.get("evidence") or {},
        )
        return AnalysisRunResponse(run_id=run.run_id, status=run.status, report=report)
    except Exception as e:
        # Ensure we can write the failure status even if a flush failed.
        try:
            session.rollback()
        except Exception:
            pass
        set_run_failed(session, run, str(e))
        return AnalysisRunResponse(run_id=run.run_id, status="failed", error=str(e))


def get_run_response(session: Session, run_id: str) -> AnalysisRunResponse:
    run = session.exec(select(AnalysisRun).where(AnalysisRun.run_id == run_id)).first()
    if not run:
        return AnalysisRunResponse(run_id=run_id, status="not_found", error="run not found")
    if run.status != "completed":
        return AnalysisRunResponse(run_id=run.run_id, status=run.status, error=run.error)

    out = session.exec(select(AnalysisOutput).where(AnalysisOutput.run_id == run.id)).first()
    if not out:
        return AnalysisRunResponse(run_id=run.run_id, status="completed", error="output missing")

    report = AnalysisReport(
        summary=out.summary_text,
        reasoning=out.reasoning_text,
        bias=out.bias,
        confidence=float(out.confidence),
        tags=out.tags or {},
        evidence=out.evidence or {},
    )
    return AnalysisRunResponse(run_id=run.run_id, status="completed", report=report)


def get_latest_report(session: Session, ticker: str) -> AnalysisRunResponse:
    inst = get_or_create_instrument(session, ticker)
    run = session.exec(
        select(AnalysisRun)
        .where(AnalysisRun.instrument_id == inst.id, AnalysisRun.status == "completed")
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    ).first()
    if not run:
        return AnalysisRunResponse(run_id="", status="not_found", error="no completed run for ticker")
    return get_run_response(session, run.run_id)

