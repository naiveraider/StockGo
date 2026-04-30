from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, func, select

from app.models.analysis import AnalysisOutput, AnalysisRun
from app.models.instrument import Instrument
from app.models.market import MarketBar, TechnicalFeature
from app.models.news import NewsItem
from app.services.llm_service import LlmUnavailable, openai_compatible_chat_json
from app.services.policy_service import get_policy_prompts, render_policy_template


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_price(value: float | None) -> str:
    return f"${value:.2f}" if value is not None else "Not available"


def _compute_trend(close: float | None, ma20: float | None, ma200: float | None, change_20d_pct: float | None) -> str:
    if close is None:
        return "Trend unavailable"
    if ma20 is not None and ma200 is not None and close > ma20 > ma200:
        if change_20d_pct is not None and change_20d_pct >= 8:
            return "Strong breakout / trend continuation"
        return "Uptrend above 20DMA and 200DMA"
    if ma20 is not None and close > ma20:
        return "Constructive trend above 20DMA"
    return "Mixed trend"


def _risk_level(confidence: float, vol_ratio: float | None, atr_pct: float | None) -> str:
    risk_score = 0
    if confidence < 0.72:
        risk_score += 1
    if vol_ratio is not None and vol_ratio >= 2.0:
        risk_score += 1
    if atr_pct is not None and atr_pct >= 0.05:
        risk_score += 1
    if risk_score >= 2:
        return "high"
    if risk_score == 1:
        return "medium"
    return "low"


def _pick_level(close: float | None, support: float | None, resistance: float | None, default: float | None) -> float | None:
    for value in (support, resistance, default, close):
        if value is not None:
            return value
    return None


def _build_candidate_payload(
    session: Session,
    instrument: Instrument,
    output: AnalysisOutput,
    run: AnalysisRun,
) -> dict[str, Any]:
    latest_bar = session.exec(
        select(MarketBar)
        .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == "1d")
        .order_by(MarketBar.ts.desc())
        .limit(1)
    ).first()
    latest_feat = session.exec(
        select(TechnicalFeature)
        .where(TechnicalFeature.instrument_id == instrument.id, TechnicalFeature.timeframe == "1d")
        .order_by(TechnicalFeature.ts.desc())
        .limit(1)
    ).first()
    recent_bars = session.exec(
        select(MarketBar)
        .where(MarketBar.instrument_id == instrument.id, MarketBar.timeframe == "1d")
        .order_by(MarketBar.ts.desc())
        .limit(20)
    ).all()
    recent_news = session.exec(
        select(NewsItem)
        .where(NewsItem.instrument_id == instrument.id)
        .where(NewsItem.published_at.is_not(None))
        .order_by(NewsItem.published_at.desc())
        .limit(5)
    ).all()

    bars = list(reversed(recent_bars))
    close = _safe_float(latest_bar.close) if latest_bar else None
    ma20 = _safe_float(latest_feat.ma20) if latest_feat else None
    ma200 = _safe_float(latest_feat.ma200) if latest_feat else None
    atr14 = _safe_float(latest_feat.atr14) if latest_feat else None
    rsi14 = _safe_float(latest_feat.rsi14) if latest_feat else None
    macd = _safe_float(latest_feat.macd) if latest_feat else None
    macd_signal = _safe_float(latest_feat.macd_signal) if latest_feat else None
    vol_ratio = _safe_float(latest_feat.vol20_ratio) if latest_feat else None
    recent_high = max((_safe_float(bar.high) or 0.0) for bar in bars) if bars else None
    recent_low = min((_safe_float(bar.low) or 0.0) for bar in bars) if bars else None
    change_20d_pct = None
    if len(bars) >= 2:
        start_close = _safe_float(bars[0].close)
        end_close = _safe_float(bars[-1].close)
        if start_close and end_close:
            change_20d_pct = ((end_close / start_close) - 1.0) * 100.0

    support_candidates = [value for value in [ma20, ma200, recent_low] if value is not None and (close is None or value <= close)]
    resistance_candidates = [value for value in [recent_high, ma20, ma200] if value is not None and (close is None or value >= close)]
    support = max(support_candidates) if support_candidates else _pick_level(close, recent_low, ma20, ma200)
    resistance = min(resistance_candidates) if resistance_candidates else _pick_level(close, recent_high, ma20, ma200)
    atr_pct = (atr14 / close) if atr14 is not None and close not in (None, 0.0) else None

    sentiment_scores = [_safe_float(item.sentiment_score) or 0.0 for item in recent_news]
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
    news_sentiment = (
        "bullish" if avg_sentiment >= 0.15 else "negative" if avg_sentiment <= -0.15 else "neutral"
    )

    candidate_score = float(output.confidence) * 100.0
    if vol_ratio is not None:
        candidate_score += max(0.0, vol_ratio - 1.0) * 8.0
    if change_20d_pct is not None:
        candidate_score += max(0.0, change_20d_pct) * 0.5
    candidate_score += avg_sentiment * 10.0

    return {
        "ticker": instrument.ticker,
        "name": instrument.name,
        "exchange": instrument.exchange,
        "updated_at": run.created_at.isoformat(),
        "candidate_score": round(candidate_score, 2),
        "analysis": {
            "bias": output.bias,
            "confidence": float(output.confidence),
            "summary": output.summary_text,
            "reasoning": output.reasoning_text,
            "tags": output.tags or {},
        },
        "technicals": {
            "last_close": close,
            "recent_20d_high": recent_high,
            "recent_20d_low": recent_low,
            "support": support,
            "resistance": resistance,
            "change_20d_pct": change_20d_pct,
            "trend": _compute_trend(close, ma20, ma200, change_20d_pct),
            "ma20": ma20,
            "ma200": ma200,
            "rsi14": rsi14,
            "macd": macd,
            "macd_signal": macd_signal,
            "atr14": atr14,
            "vol20_ratio": vol_ratio,
        },
        "news_sentiment": {
            "average_score": round(avg_sentiment, 3),
            "label": news_sentiment,
        },
        "news": [
            {
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "title": item.title,
                "source": item.source,
                "sentiment_label": item.sentiment_label,
                "sentiment_score": _safe_float(item.sentiment_score),
            }
            for item in recent_news
        ],
        "derived_plan": {
            "entry_anchor": _format_price(close),
            "support": _format_price(support),
            "resistance": _format_price(resistance),
            "risk_level": _risk_level(float(output.confidence), vol_ratio, atr_pct),
        },
    }


def _fallback_ideas(candidates: list[dict[str, Any]], idea_count: int) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    for candidate in candidates[:idea_count]:
        technicals = candidate.get("technicals") or {}
        analysis = candidate.get("analysis") or {}
        news = candidate.get("news") or []
        support = _safe_float(technicals.get("support"))
        resistance = _safe_float(technicals.get("resistance"))
        last_close = _safe_float(technicals.get("last_close"))
        change_20d_pct = _safe_float(technicals.get("change_20d_pct"))
        vol_ratio = _safe_float(technicals.get("vol20_ratio"))
        catalyst_item = news[0] if news else None
        catalyst = catalyst_item.get("title") if catalyst_item else "Follow-through on recent news and momentum"
        catalyst_date = (catalyst_item.get("published_at") or "")[:10] or None
        entry_low = support if support is not None else last_close
        entry_high = last_close if last_close is not None else resistance
        if entry_low is not None and entry_high is not None and entry_low > entry_high:
            entry_low, entry_high = entry_high, entry_low
        entry_range = (
            f"{_format_price(entry_low)} to {_format_price(entry_high)}"
            if entry_low is not None and entry_high is not None
            else "Not available"
        )
        exit_strategy = (
            f"Take partial profits into {_format_price(resistance)} and cut the trade on a daily close below {_format_price(support)}."
            if support is not None or resistance is not None
            else "Take profits into strength and exit if momentum breaks down."
        )
        move_reason = []
        if change_20d_pct is not None:
            move_reason.append(f"{change_20d_pct:.1f}% 20-day price momentum")
        if vol_ratio is not None:
            move_reason.append(f"{vol_ratio:.2f}x relative volume")
        move_reason.append(f"{candidate.get('news_sentiment', {}).get('label', 'neutral')} news tone")
        ideas.append(
            {
                "ticker": candidate["ticker"],
                "name": candidate.get("name"),
                "why_now": (
                    f"Latest analysis stays bullish with {round(float(analysis.get('confidence', 0.5)) * 100)}% confidence, backed by "
                    + ", ".join(move_reason)
                    + "."
                ),
                "catalyst": catalyst,
                "catalyst_date": catalyst_date,
                "technical_setup": (
                    f"{technicals.get('trend', 'Trend unavailable')}; support near {_format_price(support)} and resistance near {_format_price(resistance)}."
                ),
                "bull_case": f"Momentum continues and the stock breaks through {_format_price(resistance)} on follow-through volume.",
                "bear_case": f"Momentum fades and the stock loses {_format_price(support)}, which would invalidate the setup.",
                "entry_range": entry_range,
                "exit_strategy": exit_strategy,
                "risk_level": candidate.get("derived_plan", {}).get("risk_level", "medium"),
                "confidence": float(analysis.get("confidence", 0.5)),
            }
        )
    return ideas


def _sanitize_ideas(raw: dict[str, Any], candidates: list[dict[str, Any]], idea_count: int) -> list[dict[str, Any]]:
    ideas = raw.get("ideas") if isinstance(raw, dict) else None
    if not isinstance(ideas, list):
        return []

    candidate_map = {item["ticker"]: item for item in candidates}
    cleaned: list[dict[str, Any]] = []
    for item in ideas:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper()
        if ticker not in candidate_map or any(existing["ticker"] == ticker for existing in cleaned):
            continue
        source = candidate_map[ticker]
        confidence = _safe_float(item.get("confidence"))
        cleaned.append(
            {
                "ticker": ticker,
                "name": source.get("name"),
                "why_now": str(item.get("why_now") or source.get("analysis", {}).get("reasoning") or "Not available"),
                "catalyst": str(item.get("catalyst") or "Not available"),
                "catalyst_date": str(item.get("catalyst_date")) if item.get("catalyst_date") else None,
                "technical_setup": str(item.get("technical_setup") or "Not available"),
                "bull_case": str(item.get("bull_case") or "Not available"),
                "bear_case": str(item.get("bear_case") or "Not available"),
                "entry_range": str(item.get("entry_range") or "Not available"),
                "exit_strategy": str(item.get("exit_strategy") or "Not available"),
                "risk_level": str(item.get("risk_level") or source.get("derived_plan", {}).get("risk_level") or "medium").lower(),
                "confidence": max(0.0, min(1.0, confidence if confidence is not None else float(source.get("analysis", {}).get("confidence", 0.5)))),
            }
        )
        if len(cleaned) >= idea_count:
            break
    return cleaned


def generate_short_term_ideas(
    session: Session,
    *,
    idea_count: int = 3,
    candidate_pool_size: int = 12,
    min_confidence: float = 0.65,
) -> tuple[dict[str, Any], str | None, bool]:
    sub = (
        select(
            AnalysisRun.instrument_id,
            func.max(AnalysisRun.created_at).label("max_created"),
        )
        .where(AnalysisRun.status == "completed")
        .group_by(AnalysisRun.instrument_id)
        .subquery()
    )

    rows = session.exec(
        select(Instrument, AnalysisOutput, AnalysisRun)
        .join(sub, sub.c.instrument_id == Instrument.id)
        .join(
            AnalysisRun,
            (AnalysisRun.instrument_id == sub.c.instrument_id)
            & (AnalysisRun.created_at == sub.c.max_created),
        )
        .join(AnalysisOutput, AnalysisOutput.run_id == AnalysisRun.id)
        .where(Instrument.is_etf == False)  # noqa: E712
        .where(AnalysisOutput.bias == "UP")
        .where(AnalysisOutput.confidence >= min_confidence)
    ).all()

    candidates = [
        _build_candidate_payload(session, instrument, output, run)
        for instrument, output, run in rows
    ]
    candidates.sort(key=lambda item: (item["candidate_score"], item["analysis"]["confidence"], item["updated_at"]), reverse=True)
    shortlisted = candidates[:candidate_pool_size]

    if not shortlisted:
        return {
            "generated_at": datetime.now(timezone.utc),
            "source_model": None,
            "fallback_used": True,
            "candidates_considered": 0,
            "ideas": [],
        }, None, True

    schema_hint = {
        "ideas": [
            {
                "ticker": "string, must be one of the candidate tickers",
                "why_now": "string",
                "catalyst": "string",
                "catalyst_date": "string or null",
                "technical_setup": "string",
                "bull_case": "string",
                "bear_case": "string",
                "entry_range": "string",
                "exit_strategy": "string",
                "risk_level": "low|medium|high",
                "confidence": "number 0..1",
            }
        ]
    }
    system_template, user_template = get_policy_prompts(session, "short_term_pick")
    candidate_set = "\n".join(
        [
            f"- {candidate['ticker']} | {candidate.get('name') or 'Unknown company'} | analysis_confidence={candidate['analysis']['confidence']:.2f} | "
            f"trend={candidate['technicals']['trend']} | rel_volume={candidate['technicals'].get('vol20_ratio')} | "
            f"news_sentiment={candidate['news_sentiment']['label']} | support={candidate['derived_plan']['support']} | "
            f"resistance={candidate['derived_plan']['resistance']} | summary={candidate['analysis']['summary']} | reasoning={candidate['analysis']['reasoning']} | "
            f"recent_news={[news['title'] for news in candidate['news'][:3]]}"
            for candidate in shortlisted
        ]
    )
    system = system_template
    user = render_policy_template(
        user_template,
        {
            "idea_count": str(idea_count),
            "candidate_set": candidate_set,
        },
    )

    try:
        raw = openai_compatible_chat_json(system, user, schema_hint=schema_hint)
        ideas = _sanitize_ideas(raw, shortlisted, idea_count)
        if len(ideas) < idea_count:
            raise ValueError("LLM returned too few valid ideas")
        return {
            "generated_at": datetime.now(timezone.utc),
            "source_model": "openai_compatible_chat",
            "fallback_used": False,
            "candidates_considered": len(shortlisted),
            "ideas": ideas,
        }, "openai_compatible_chat", False
    except (LlmUnavailable, Exception):
        return {
            "generated_at": datetime.now(timezone.utc),
            "source_model": None,
            "fallback_used": True,
            "candidates_considered": len(shortlisted),
            "ideas": _fallback_ideas(shortlisted, idea_count),
        }, None, True