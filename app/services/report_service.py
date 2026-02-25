from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.models.market import MarketBar, TechnicalFeature
from app.models.news import NewsItem
from app.schemas.analysis import Bias
from app.services.llm_service import LlmUnavailable, openai_compatible_chat_json


def _sha256(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_latest_snapshot(
    session: Session,
    *,
    instrument_id: int,
    timeframe: str,
    start: datetime,
    end: datetime,
    news_limit: int = 12,
) -> dict[str, Any]:
    bars = session.exec(
        select(MarketBar)
        .where(
            MarketBar.instrument_id == instrument_id,
            MarketBar.timeframe == timeframe,
            MarketBar.ts >= start,
            MarketBar.ts <= end,
        )
        .order_by(MarketBar.ts.asc())
    ).all()
    feats = session.exec(
        select(TechnicalFeature)
        .where(
            TechnicalFeature.instrument_id == instrument_id,
            TechnicalFeature.timeframe == timeframe,
            TechnicalFeature.ts >= start,
            TechnicalFeature.ts <= end,
        )
        .order_by(TechnicalFeature.ts.asc())
    ).all()
    news = session.exec(
        select(NewsItem)
        .where(
            NewsItem.instrument_id == instrument_id,
            NewsItem.published_at.is_not(None),
            NewsItem.published_at >= start,
            NewsItem.published_at <= end,
        )
        .order_by(NewsItem.published_at.desc())
        .limit(news_limit)
    ).all()

    latest_bar = bars[-1] if bars else None
    latest_feat = feats[-1] if feats else None
    return {
        "latest_bar": latest_bar.model_dump() if latest_bar else None,
        "latest_feat": latest_feat.model_dump() if latest_feat else None,
        "bars_count": len(bars),
        "news": [
            {
                "published_at": n.published_at.isoformat() if n.published_at else None,
                "source": n.source,
                "title": n.title,
                "url": n.url,
                "sentiment_label": n.sentiment_label,
                "sentiment_score": n.sentiment_score,
            }
            for n in news
        ],
    }


def price_features_text(snapshot: dict[str, Any]) -> str:
    b = snapshot.get("latest_bar") or {}
    f = snapshot.get("latest_feat") or {}
    if not b:
        return "No price data available."
    close = b.get("close")
    ma20 = f.get("ma20")
    ma200 = f.get("ma200")
    rsi = f.get("rsi14")
    macd = f.get("macd")
    macd_sig = f.get("macd_signal")
    vol_ratio = f.get("vol20_ratio")

    parts: list[str] = []
    parts.append(f"Close {close:.2f}")
    if ma20:
        parts.append(f"{'above' if close > ma20 else 'below'} 20MA ({ma20:.2f})")
    if ma200:
        parts.append(f"{'above' if close > ma200 else 'below'} 200MA ({ma200:.2f})")
    if rsi is not None:
        parts.append(f"RSI14 {rsi:.1f}")
    if macd is not None and macd_sig is not None:
        parts.append(f"MACD {macd:.3f} vs signal {macd_sig:.3f}")
    if vol_ratio is not None:
        parts.append(f"Volume {vol_ratio:.2f}x vs 20-day avg")
    return "; ".join(parts)


def rule_bias(snapshot: dict[str, Any]) -> tuple[Bias, float, dict[str, Any]]:
    b = snapshot.get("latest_bar") or {}
    f = snapshot.get("latest_feat") or {}
    if not b or not f:
        return "NEUTRAL", 0.3, {"score": 0.0, "signals": []}

    close = float(b["close"])
    score = 0.0
    signals: list[str] = []

    ma20 = f.get("ma20")
    ma200 = f.get("ma200")
    if ma200:
        if close > ma200:
            score += 1.0
            signals.append("above_ma200")
        else:
            score -= 1.0
            signals.append("below_ma200")
    if ma20:
        if close > ma20:
            score += 0.5
            signals.append("above_ma20")
        else:
            score -= 0.5
            signals.append("below_ma20")

    rsi = f.get("rsi14")
    if rsi is not None:
        rsi = float(rsi)
        if rsi >= 60:
            score += 0.4
            signals.append("rsi_strong")
        elif rsi <= 40:
            score -= 0.4
            signals.append("rsi_weak")

    macd = f.get("macd")
    macd_sig = f.get("macd_signal")
    if macd is not None and macd_sig is not None:
        if float(macd) > float(macd_sig):
            score += 0.3
            signals.append("macd_bullish")
        else:
            score -= 0.3
            signals.append("macd_bearish")

    vol_ratio = f.get("vol20_ratio")
    if vol_ratio is not None and float(vol_ratio) >= 1.5:
        score += 0.1
        signals.append("volume_expanded")

    # News sentiment: average of recent
    news = snapshot.get("news") or []
    if news:
        scores = [float(n.get("sentiment_score") or 0.0) for n in news[:8]]
        news_score = sum(scores) / max(1, len(scores))
        score += 0.6 * news_score
        if news_score >= 0.15:
            signals.append("news_positive")
        elif news_score <= -0.15:
            signals.append("news_negative")

    if score >= 0.8:
        bias: Bias = "UP"
    elif score <= -0.8:
        bias = "DOWN"
    else:
        bias = "NEUTRAL"
    confidence = min(1.0, 0.35 + abs(score) / 2.0)
    return bias, float(confidence), {"score": float(score), "signals": signals}


def rule_report(snapshot: dict[str, Any]) -> dict[str, Any]:
    price_text = price_features_text(snapshot)
    bias, conf, meta = rule_bias(snapshot)
    news = snapshot.get("news") or []

    top_news = []
    for n in news[:6]:
        src = f" ({n['source']})" if n.get("source") else ""
        top_news.append(f"- {n['title']}{src}")
    news_text = "\n".join(top_news) if top_news else "- No relevant headlines found."

    summary = f"Price/Technicals: {price_text}\nNews (recent):\n{news_text}"
    reasoning = (
        f"Bias is {bias} based on combined signals: {', '.join(meta['signals'][:6]) or 'insufficient data'}. "
        "This is a short-term heuristic combining trend/momentum/volume and headline sentiment."
    )

    tags = {
        "signals": meta["signals"],
    }
    evidence = {
        "price_features_text": price_text,
        "news": news[:10],
        "scoring": meta,
    }
    return {
        "summary": summary,
        "reasoning": reasoning,
        "bias": bias,
        "confidence": conf,
        "tags": tags,
        "evidence": evidence,
    }


def generate_report(snapshot: dict[str, Any]) -> tuple[dict[str, Any], str, str | None]:
    """
    Returns (report_json, input_hash, model_used)
    """
    input_obj = {
        "price_features_text": price_features_text(snapshot),
        "news": snapshot.get("news") or [],
        "bars_count": snapshot.get("bars_count"),
    }
    input_hash = _sha256(input_obj)

    schema_hint = {
        "summary": "string",
        "reasoning": "string (2-3 sentences, cite evidence indices)",
        "bias": "UP|DOWN|NEUTRAL",
        "confidence": "number 0..1",
        "tags": {"events": ["..."], "signals": ["..."]},
        "evidence": {"price_features_text": "string", "news": ["..."]},
    }

    system = (
        "You are a stock analyst. You must be concise, evidence-based, and avoid making up facts. "
        "Use the provided price feature text and headlines only."
    )
    user = (
        f"Price summary:\n{input_obj['price_features_text']}\n\n"
        "Recent headlines (most recent first):\n"
        + "\n".join([f"[{i}] {n.get('title')}" for i, n in enumerate(input_obj["news"][:10])])
        + "\n\nTask:\n"
        "1) Summarize key events impacting the stock (3-6 bullets)\n"
        "2) Predict short-term market bias (UP/DOWN/NEUTRAL)\n"
        "3) Provide reasoning in 2-3 sentences citing evidence indices like [0], [1]\n"
        "Return JSON only."
    )

    try:
        out = openai_compatible_chat_json(system, user, schema_hint=schema_hint)
        out.setdefault("evidence", {})
        out["evidence"].setdefault("price_features_text", input_obj["price_features_text"])
        out["evidence"].setdefault("news", input_obj["news"][:10])
        return out, input_hash, "openai_compatible_chat"
    except (LlmUnavailable, Exception):
        return rule_report(snapshot), input_hash, None

