from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.engine import get_engine
from app.models.instrument import Instrument
from app.schemas.analysis import AnalysisRunRequest
from app.services.analysis_service import run_analysis_sync
from app.services.financials_service import sync_financials_for_ticker
from app.services.fundamental_snapshot_service import run_fundamental_snapshots_once
from app.services.pick_cache_service import list_pick_cache_keys, refresh_pick_cache
from app.services.quote_service import refresh_quotes_for_tickers
from app.services.sec_service import sync_sec_equity_for_ticker, sync_sec_notes_for_ticker


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


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

        if settings.scheduler_financials_only:
            self._scheduler.add_job(
                self._update_financials_job,
                trigger=IntervalTrigger(days=7),
                id="update_financials",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300,
            )
            self._scheduler.start()
            return

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

        # Weekly cached fundamentals refresh for the full stock universe.
        self._scheduler.add_job(
            self._update_fundamentals_job,
            trigger=IntervalTrigger(days=7),
            id="update_fundamentals",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

        # Cached pick pages: populate once on startup, then refresh daily.
        self._scheduler.add_job(
            self._update_pick_caches_job,
            trigger=IntervalTrigger(days=1),
            id="update_pick_caches",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
            next_run_time=_now_utc(),
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
            next_run_time=_now_utc(),
        )

        self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def _resolve_tickers(self, tickers: list[str] | None = None) -> list[str]:
        if tickers is not None:
            return _normalize_tickers(tickers)
        return get_settings().watchlist_tickers()

    def run_reports_once(self, tickers: list[str] | None = None) -> dict[str, int | list[str]]:
        settings = get_settings()
        engine = get_engine()
        end = _now_utc()
        start = end - timedelta(days=max(30, settings.report_lookback_days))
        resolved = self._resolve_tickers(tickers)
        if not resolved:
            return {"tickers": [], "requested": 0, "succeeded": 0, "failed": 0}

        succeeded = 0
        failed = 0
        with Session(engine) as session:
            for ticker in resolved:
                req = AnalysisRunRequest(
                    ticker=ticker,
                    start=start,
                    end=end,
                    timeframe="1d",
                    include_news=True,
                    include_macro=False,
                )
                resp = run_analysis_sync(session, req)
                if resp.status == "completed":
                    succeeded += 1
                else:
                    failed += 1
        return {"tickers": resolved, "requested": len(resolved), "succeeded": succeeded, "failed": failed}

    def run_news_once(self, tickers: list[str] | None = None) -> dict[str, int | list[str]]:
        engine = get_engine()
        end = _now_utc()
        start = end - timedelta(days=7)
        resolved = self._resolve_tickers(tickers)
        if not resolved:
            return {"tickers": [], "requested": 0, "succeeded": 0, "failed": 0}

        succeeded = 0
        failed = 0
        with Session(engine) as session:
            for ticker in resolved:
                req = AnalysisRunRequest(
                    ticker=ticker,
                    start=start,
                    end=end,
                    timeframe="1d",
                    include_news=True,
                    include_macro=False,
                )
                resp = run_analysis_sync(session, req)
                if resp.status == "completed":
                    succeeded += 1
                else:
                    failed += 1
        return {"tickers": resolved, "requested": len(resolved), "succeeded": succeeded, "failed": failed}

    def run_financials_once(self, tickers: list[str] | None = None) -> dict[str, object]:
        engine = get_engine()
        resolved = self._resolve_tickers(tickers)
        if not resolved:
            return {"tickers": [], "requested": 0, "succeeded": 0, "failed": 0, "details": []}

        succeeded = 0
        failed = 0
        details: list[dict[str, object]] = []
        with Session(engine) as session:
            for ticker in resolved:
                try:
                    detail = sync_financials_for_ticker(session, ticker)
                    sync_sec_equity_for_ticker(session, ticker)
                    sync_sec_notes_for_ticker(session, ticker)
                    details.append({"ticker": ticker, "status": "completed", **detail})
                    succeeded += 1
                except Exception as exc:
                    details.append({"ticker": ticker, "status": "failed", "error": str(exc), "steps": []})
                    failed += 1
                    continue
        return {
            "tickers": resolved,
            "requested": len(resolved),
            "succeeded": succeeded,
            "failed": failed,
            "details": details,
        }

    def run_sec_once(self, tickers: list[str] | None = None) -> dict[str, int | list[str]]:
        engine = get_engine()
        resolved = self._resolve_tickers(tickers)
        if not resolved:
            return {"tickers": [], "requested": 0, "succeeded": 0, "failed": 0}

        succeeded = 0
        failed = 0
        with Session(engine) as session:
            for ticker in resolved:
                try:
                    sync_sec_equity_for_ticker(session, ticker)
                    sync_sec_notes_for_ticker(session, ticker)
                    succeeded += 1
                except Exception:
                    failed += 1
                    continue
        return {"tickers": resolved, "requested": len(resolved), "succeeded": succeeded, "failed": failed}

    def run_quotes_once(self, tickers: list[str] | None = None) -> dict[str, int | list[str]]:
        engine = get_engine()
        with Session(engine) as session:
            if tickers is None:
                resolved = session.exec(
                    select(Instrument.ticker).where(Instrument.is_etf == False)  # noqa: E712
                ).all()
                resolved = _normalize_tickers(resolved)
            else:
                resolved = self._resolve_tickers(tickers)
            if not resolved:
                return {"tickers": [], "requested": 0, "succeeded": 0, "failed": 0}

            updated = refresh_quotes_for_tickers(session, resolved)
        failed = max(0, len(resolved) - updated)
        return {"tickers": resolved, "requested": len(resolved), "succeeded": updated, "failed": failed}

    def run_fundamentals_once(self, tickers: list[str] | None = None) -> dict[str, object]:
        return run_fundamental_snapshots_once(tickers)

    def run_pick_cache_once(self, key: str) -> dict[str, object]:
        engine = get_engine()
        with Session(engine) as session:
            cache = refresh_pick_cache(session, key)
        return {
            "key": key,
            "generated_at": cache.generated_at.isoformat(),
            "source_model": cache.source_model,
            "fallback_used": cache.fallback_used,
            "candidates_considered": cache.candidates_considered,
            "idea_count": len((cache.ideas or {}).get("ideas") or []),
        }

    def run_all_pick_caches_once(self) -> dict[str, object]:
        refreshed: list[dict[str, object]] = []
        for key in list_pick_cache_keys():
            refreshed.append(self.run_pick_cache_once(key))
        return {"items": refreshed, "count": len(refreshed)}

    def _update_reports_job(self) -> None:
        self.run_reports_once()

    def _update_news_job(self) -> None:
        # News is already pulled during report updates; this job is a lightweight "keep fresh" option.
        self.run_news_once()

    def _update_financials_job(self) -> None:
        self.run_financials_once()

    def _update_sec_job(self) -> None:
        """Weekly SEC companyfacts sync: shareholders' equity for watchlist."""
        self.run_sec_once()

    def _update_quotes_job(self) -> None:
        """Intraday quotes refresh for all non-ETF instruments (used by homepage preview)."""
        self.run_quotes_once()

    def _update_fundamentals_job(self) -> None:
        """Weekly cached fundamentals refresh for all non-ETF instruments."""
        self.run_fundamentals_once()

    def _update_pick_caches_job(self) -> None:
        """Refresh cached short-term and long-term pick pages."""
        self.run_all_pick_caches_once()


scheduler_service = SchedulerService()

