from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.engine import get_engine
from app.models.instrument import Instrument
from app.schemas.analysis import AnalysisRunRequest
from app.services.analysis_service import run_analysis_sync
from app.services.financials_service import sync_financials_for_ticker
from app.services.quote_service import refresh_quotes_for_tickers
from app.services.sec_service import sync_sec_equity_for_ticker


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class SchedulerService:
    def __init__(self) -> None:
        self._scheduler: BackgroundScheduler | None = None

    def start(self) -> None:
        settings = get_settings()
        if not settings.scheduler_enabled:
            return
        if self._scheduler and self._scheduler.running:
            return

        self._scheduler = BackgroundScheduler(timezone="UTC")

        # Market + indicators + report
        self._scheduler.add_job(
            self._update_reports_job,
            trigger=IntervalTrigger(minutes=max(1, settings.market_update_minutes)),
            id="update_reports",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )

        # News-only refresh (kept separate so you can tune frequency)
        self._scheduler.add_job(
            self._update_news_job,
            trigger=IntervalTrigger(minutes=max(1, settings.news_update_minutes)),
            id="update_news",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )

        # Weekly financials refresh for watchlist
        self._scheduler.add_job(
            self._update_financials_job,
            trigger=IntervalTrigger(days=7),
            id="update_financials",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

        # Weekly SEC equity (companyfacts) for watchlist
        self._scheduler.add_job(
            self._update_sec_job,
            trigger=IntervalTrigger(days=7),
            id="update_sec",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

        # Intraday quotes refresh for watchlist (every 5 minutes)
        self._scheduler.add_job(
            self._update_quotes_job,
            trigger=IntervalTrigger(minutes=5),
            id="update_quotes",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )

        # Run an initial quotes refresh once at startup
        try:
            self._update_quotes_job()
        except Exception:
            # Don't block startup if initial quotes refresh fails
            pass

        self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def _update_reports_job(self) -> None:
        settings = get_settings()
        engine = get_engine()
        end = _now_utc()
        start = end - timedelta(days=max(30, settings.report_lookback_days))
        tickers = settings.watchlist_tickers()
        if not tickers:
            return

        with Session(engine) as session:
            for ticker in tickers:
                req = AnalysisRunRequest(
                    ticker=ticker,
                    start=start,
                    end=end,
                    timeframe="1d",
                    include_news=True,
                    include_macro=False,
                )
                run_analysis_sync(session, req)

    def _update_news_job(self) -> None:
        # News is already pulled during report updates; this job is a lightweight "keep fresh" option.
        settings = get_settings()
        engine = get_engine()
        end = _now_utc()
        start = end - timedelta(days=7)
        tickers = settings.watchlist_tickers()
        if not tickers:
            return

        with Session(engine) as session:
            for ticker in tickers:
                req = AnalysisRunRequest(
                    ticker=ticker,
                    start=start,
                    end=end,
                    timeframe="1d",
                    include_news=True,
                    include_macro=False,
                )
                # Will incrementally upsert news; also computes report, but with short lookback.
                run_analysis_sync(session, req)

    def _update_financials_job(self) -> None:
        settings = get_settings()
        engine = get_engine()
        tickers = settings.watchlist_tickers()
        if not tickers:
            return

        with Session(engine) as session:
            # Ensure instruments exist
            existing = session.exec(
                select(Instrument).where(Instrument.ticker.in_(tickers))
            ).all()
            existing_map = {i.ticker: i for i in existing}

            for ticker in tickers:
                try:
                    sync_financials_for_ticker(session, ticker)
                except Exception:
                    # Don't break the whole job if one ticker fails
                    continue

    def _update_sec_job(self) -> None:
        """Weekly SEC companyfacts sync: shareholders' equity for watchlist."""
        settings = get_settings()
        engine = get_engine()
        tickers = settings.watchlist_tickers()
        if not tickers:
            return

        with Session(engine) as session:
            for ticker in tickers:
                try:
                    sync_sec_equity_for_ticker(session, ticker)
                except Exception:
                    continue

    def _update_quotes_job(self) -> None:
        """Intraday quotes refresh for all non-ETF instruments (used by homepage preview)."""
        engine = get_engine()
        with Session(engine) as session:
            tickers = session.exec(
                select(Instrument.ticker).where(Instrument.is_etf == False)  # noqa: E712
            ).all()
            if not tickers:
                return

            # Batch to avoid hammering external quote API in a single call
            batch_size = 100
            for i in range(0, len(tickers), batch_size):
                refresh_quotes_for_tickers(session, tickers[i : i + batch_size])


scheduler_service = SchedulerService()

