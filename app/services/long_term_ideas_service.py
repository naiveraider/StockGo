from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, func, select

from app.models.analysis import AnalysisOutput, AnalysisRun
from app.models.fundamental_snapshot import FundamentalSnapshot
from app.models.instrument import Instrument
from app.models.market import StockQuote
from app.services.fundamental_snapshot_service import warm_fundamental_snapshots
from app.services.llm_service import LlmUnavailable, openai_compatible_chat_json
from app.services.policy_service import get_policy_prompts, render_policy_template


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _money_text(value: float | None) -> str:
    if value is None:
        return "Not available"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.1f}T"
    if abs_value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:.0f}"


def _pct_text(value: float | None) -> str:
    if value is None:
        return "Not available"
    return f"{value * 100:.1f}%"


def _sentence(value: str | None) -> str | None:
    if not value:
        return None
    parts = [part.strip() for part in value.replace("\n", " ").split(". ") if part.strip()]
    if not parts:
        return None
    sentence = parts[0]
    if not sentence.endswith("."):
        sentence += "."
    return sentence


def _valuation_label(snapshot: FundamentalSnapshot) -> str:
    trailing_pe = _safe_float(snapshot.trailing_pe)
    forward_pe = _safe_float(snapshot.forward_pe)
    revenue_growth = _safe_float(snapshot.revenue_growth)
    earnings_growth = _safe_float(snapshot.earnings_growth)
    price_to_sales = _safe_float(snapshot.price_to_sales)

    anchor = forward_pe if forward_pe is not None else trailing_pe
    if anchor is None and price_to_sales is None:
        return "fair: valuation multiples are limited, so there is not enough evidence to call it obviously cheap or expensive."
    if anchor is not None and anchor <= 18:
        return f"cheap: earnings multiple around {anchor:.1f}x looks modest for the current growth profile."
    if anchor is not None and anchor >= 32:
        growth_text = []
        if revenue_growth is not None:
            growth_text.append(f"revenue growth {_pct_text(revenue_growth)}")
        if earnings_growth is not None:
            growth_text.append(f"earnings growth {_pct_text(earnings_growth)}")
        suffix = f" Even with {', '.join(growth_text)}, expectations are demanding." if growth_text else " Expectations are demanding at this level."
        return f"expensive: earnings multiple around {anchor:.1f}x is rich for a 3-year entry point.{suffix}"
    if price_to_sales is not None and price_to_sales >= 10:
        return f"expensive: price-to-sales around {price_to_sales:.1f}x leaves little room for execution misses."
    return f"fair: valuation around {anchor:.1f}x earnings is reasonable relative to its current quality and growth outlook." if anchor is not None else "fair: valuation looks balanced relative to its current fundamentals."


def _risk_text(snapshot: FundamentalSnapshot) -> str:
    debt_to_equity = _safe_float(snapshot.debt_to_equity)
    revenue_growth = _safe_float(snapshot.revenue_growth)
    earnings_growth = _safe_float(snapshot.earnings_growth)
    beta = _safe_float(snapshot.beta)
    trailing_pe = _safe_float(snapshot.trailing_pe)
    risks: list[str] = []
    if trailing_pe is not None and trailing_pe >= 30:
        risks.append("premium valuation could compress if growth slows")
    if debt_to_equity is not None and debt_to_equity >= 120:
        risks.append("balance sheet leverage is higher than ideal")
    if revenue_growth is not None and revenue_growth <= 0.05:
        risks.append("top-line growth is not especially strong")
    if earnings_growth is not None and earnings_growth <= 0.05:
        risks.append("earnings growth may not keep up with expectations")
    if beta is not None and beta >= 1.5:
        risks.append("the stock can be volatile during drawdowns")
    if not risks:
        risks.append("execution risk, competition, and macro slowdowns remain the main threats")
    return "; ".join(risks) + "."


def _build_candidate_payload(
    instrument: Instrument,
    snapshot: FundamentalSnapshot,
    quote: StockQuote,
    analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    revenue_growth = _safe_float(snapshot.revenue_growth)
    earnings_growth = _safe_float(snapshot.earnings_growth)
    gross_margin = _safe_float(snapshot.gross_margin)
    operating_margin = _safe_float(snapshot.operating_margin)
    profit_margin = _safe_float(snapshot.profit_margin)
    return_on_equity = _safe_float(snapshot.return_on_equity)
    debt_to_equity = _safe_float(snapshot.debt_to_equity)
    current_ratio = _safe_float(snapshot.current_ratio)
    market_cap = _safe_float(snapshot.market_cap or quote.market_cap)
    free_cashflow = _safe_float(snapshot.free_cashflow)
    operating_cashflow = _safe_float(snapshot.operating_cashflow)

    fundamental_score = 0.0
    if revenue_growth is not None:
        fundamental_score += 2.0 if revenue_growth >= 0.12 else 1.0 if revenue_growth >= 0.06 else -0.5
    if earnings_growth is not None:
        fundamental_score += 2.0 if earnings_growth >= 0.12 else 1.0 if earnings_growth >= 0.06 else -0.5
    if gross_margin is not None:
        fundamental_score += 1.0 if gross_margin >= 0.45 else 0.5 if gross_margin >= 0.3 else 0.0
    if operating_margin is not None:
        fundamental_score += 1.0 if operating_margin >= 0.18 else 0.5 if operating_margin >= 0.1 else 0.0
    if profit_margin is not None:
        fundamental_score += 0.5 if profit_margin >= 0.15 else 0.0
    if return_on_equity is not None:
        fundamental_score += 1.0 if return_on_equity >= 0.18 else 0.5 if return_on_equity >= 0.1 else 0.0
    if debt_to_equity is not None:
        fundamental_score += 1.0 if debt_to_equity <= 80 else 0.5 if debt_to_equity <= 140 else -0.5
    if current_ratio is not None:
        fundamental_score += 0.5 if current_ratio >= 1.2 else -0.25
    if free_cashflow is not None:
        fundamental_score += 1.0 if free_cashflow > 0 else -1.0
    if operating_cashflow is not None and operating_cashflow > 0:
        fundamental_score += 0.5
    if market_cap is not None and market_cap >= 20_000_000_000:
        fundamental_score += 0.5
    if analysis and analysis.get("bias") == "UP":
        fundamental_score += 0.5
    if analysis:
        fundamental_score += float(analysis.get("confidence") or 0.0)

    business_model = _sentence(snapshot.long_business_summary) or (
        f"{instrument.name or instrument.ticker} operates in {snapshot.sector or 'its sector'} and serves {snapshot.industry or 'its end market'}."
    )
    growth_drivers = []
    if revenue_growth is not None:
        growth_drivers.append(f"revenue growth is running around {_pct_text(revenue_growth)}")
    if earnings_growth is not None:
        growth_drivers.append(f"earnings growth is running around {_pct_text(earnings_growth)}")
    if market_cap is not None:
        growth_drivers.append(f"it already operates at scale with market cap near {_money_text(market_cap)}")
    growth_driver_text = "; ".join(growth_drivers) + "." if growth_drivers else "Growth visibility is supported by the current business mix and market position."
    moat_parts = []
    if gross_margin is not None:
        moat_parts.append(f"gross margin {_pct_text(gross_margin)}")
    if operating_margin is not None:
        moat_parts.append(f"operating margin {_pct_text(operating_margin)}")
    if return_on_equity is not None:
        moat_parts.append(f"ROE {_pct_text(return_on_equity)}")
    moat_text = (
        f"Competitive position is supported by {', '.join(moat_parts)} and scale in {snapshot.industry or 'its category'}."
        if moat_parts
        else "Competitive position appears supported by scale, brand, and execution, but moat evidence is limited in the dataset."
    )
    balance_sheet_text = (
        f"Cash {_money_text(_safe_float(snapshot.total_cash))} versus debt {_money_text(_safe_float(snapshot.total_debt))}, current ratio {f'{current_ratio:.2f}' if current_ratio is not None else 'Not available'}."
        if current_ratio is not None or snapshot.total_cash is not None or snapshot.total_debt is not None
        else "Balance sheet detail is limited from the current snapshot."
    )

    return {
        "ticker": instrument.ticker,
        "name": instrument.name,
        "updated_at": snapshot.updated_at.isoformat(),
        "candidate_score": round(fundamental_score, 2),
        "analysis": analysis or {"bias": "NEUTRAL", "confidence": 0.0, "summary": "", "reasoning": ""},
        "fundamentals": {
            "sector": snapshot.sector,
            "industry": snapshot.industry,
            "market_cap": market_cap,
            "revenue_growth": revenue_growth,
            "earnings_growth": earnings_growth,
            "gross_margin": gross_margin,
            "operating_margin": operating_margin,
            "profit_margin": profit_margin,
            "return_on_equity": return_on_equity,
            "debt_to_equity": debt_to_equity,
            "current_ratio": current_ratio,
            "free_cashflow": free_cashflow,
            "operating_cashflow": operating_cashflow,
            "valuation": _valuation_label(snapshot),
            "business_model": business_model,
            "growth_drivers": growth_driver_text,
            "moat": moat_text,
            "balance_sheet": balance_sheet_text,
            "risks": _risk_text(snapshot),
        },
    }


def _fallback_ideas(candidates: list[dict[str, Any]], idea_count: int) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    for candidate in candidates[:idea_count]:
        fundamentals = candidate.get("fundamentals") or {}
        ideas.append(
            {
                "ticker": candidate["ticker"],
                "name": candidate.get("name"),
                "business_model": fundamentals.get("business_model") or "Not available",
                "growth_drivers": fundamentals.get("growth_drivers") or "Not available",
                "competitive_advantage": (
                    (fundamentals.get("moat") or "Not available")
                    + " "
                    + (fundamentals.get("balance_sheet") or "")
                ).strip(),
                "risks_and_threats": fundamentals.get("risks") or "Not available",
                "valuation": fundamentals.get("valuation") or "Not available",
                "why_outperform": (
                    f"{candidate.get('name') or candidate['ticker']} combines a quality score of {candidate['candidate_score']:.1f} with "
                    f"analysis confidence of {round(candidate['analysis']['confidence'] * 100)}%, which supports the case for multi-year outperformance if execution stays on track."
                ),
                "confidence": max(0.0, min(1.0, 0.45 + (candidate["candidate_score"] / 10.0))),
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
                "business_model": str(item.get("business_model") or source["fundamentals"].get("business_model") or "Not available"),
                "growth_drivers": str(item.get("growth_drivers") or source["fundamentals"].get("growth_drivers") or "Not available"),
                "competitive_advantage": str(item.get("competitive_advantage") or source["fundamentals"].get("moat") or "Not available"),
                "risks_and_threats": str(item.get("risks_and_threats") or source["fundamentals"].get("risks") or "Not available"),
                "valuation": str(item.get("valuation") or source["fundamentals"].get("valuation") or "Not available"),
                "why_outperform": str(item.get("why_outperform") or source["analysis"].get("reasoning") or "Not available"),
                "confidence": max(0.0, min(1.0, confidence if confidence is not None else source["analysis"]["confidence"])),
            }
        )
        if len(cleaned) >= idea_count:
            break
    return cleaned


def generate_long_term_ideas(
    session: Session,
    *,
    idea_count: int = 3,
    candidate_pool_size: int = 15,
) -> tuple[dict[str, Any], str | None, bool]:
    warm_fundamental_snapshots(session, warm_limit=max(40, candidate_pool_size * 6))

    sub = (
        select(
            AnalysisRun.instrument_id,
            func.max(AnalysisRun.created_at).label("max_created"),
        )
        .where(AnalysisRun.status == "completed")
        .group_by(AnalysisRun.instrument_id)
        .subquery()
    )

    analysis_rows = session.exec(
        select(AnalysisRun.instrument_id, AnalysisOutput, AnalysisRun)
        .select_from(sub)
        .join(
            AnalysisRun,
            (AnalysisRun.instrument_id == sub.c.instrument_id)
            & (AnalysisRun.created_at == sub.c.max_created),
        )
        .join(AnalysisOutput, AnalysisOutput.run_id == AnalysisRun.id)
    ).all()
    analysis_map = {
        instrument_id: {
            "bias": output.bias,
            "confidence": float(output.confidence),
            "summary": output.summary_text,
            "reasoning": output.reasoning_text,
            "updated_at": run.created_at.isoformat(),
        }
        for instrument_id, output, run in analysis_rows
    }

    rows = session.exec(
        select(Instrument, FundamentalSnapshot, StockQuote)
        .join(StockQuote, StockQuote.instrument_id == Instrument.id)
        .join(FundamentalSnapshot, FundamentalSnapshot.instrument_id == Instrument.id)
        .where(Instrument.is_etf == False)  # noqa: E712
        .order_by(StockQuote.market_cap.desc())
    ).all()

    candidates: list[dict[str, Any]] = []
    for instrument, snapshot, quote in rows:
        if (snapshot.market_cap or quote.market_cap or 0.0) < 5_000_000_000:
            continue
        if not snapshot.long_business_summary and snapshot.revenue_growth is None and snapshot.earnings_growth is None:
            continue
        candidates.append(_build_candidate_payload(instrument, snapshot, quote, analysis_map.get(instrument.id)))

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
                "business_model": "string",
                "growth_drivers": "string",
                "competitive_advantage": "string",
                "risks_and_threats": "string",
                "valuation": "string",
                "why_outperform": "string",
                "confidence": "number 0..1",
            }
        ]
    }
    system_template, user_template = get_policy_prompts(session, "long_term_pick")
    candidate_set = "\n".join(
        [
            f"- {candidate['ticker']} | {candidate.get('name') or 'Unknown company'} | analysis_bias={candidate['analysis']['bias']} | "
            f"analysis_confidence={candidate['analysis']['confidence']:.2f} | sector={candidate['fundamentals'].get('sector')} | "
            f"industry={candidate['fundamentals'].get('industry')} | market_cap={_money_text(candidate['fundamentals'].get('market_cap'))} | "
            f"revenue_growth={_pct_text(candidate['fundamentals'].get('revenue_growth'))} | earnings_growth={_pct_text(candidate['fundamentals'].get('earnings_growth'))} | "
            f"gross_margin={_pct_text(candidate['fundamentals'].get('gross_margin'))} | operating_margin={_pct_text(candidate['fundamentals'].get('operating_margin'))} | "
            f"roe={_pct_text(candidate['fundamentals'].get('return_on_equity'))} | debt_to_equity={candidate['fundamentals'].get('debt_to_equity')} | "
            f"valuation={candidate['fundamentals'].get('valuation')} | business_model={candidate['fundamentals'].get('business_model')} | "
            f"growth_drivers={candidate['fundamentals'].get('growth_drivers')} | moat={candidate['fundamentals'].get('moat')} | risks={candidate['fundamentals'].get('risks')} | "
            f"analysis_summary={candidate['analysis'].get('summary')} | analysis_reasoning={candidate['analysis'].get('reasoning')}"
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