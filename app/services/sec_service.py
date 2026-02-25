"""
SEC EDGAR integration: companyfacts API for shareholders' equity and optional notes.

- company_tickers.json: ticker -> CIK (10-digit zero-padded).
- companyfacts: us-gaap StockholdersEquity (and related) -> shareholders_equity_statements.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Any, Optional

import requests
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.financials import ShareholdersEquity
from app.models.instrument import Instrument
from app.services.instrument_service import get_or_create_instrument

logger = logging.getLogger(__name__)

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# In-memory cache: ticker -> CIK (str, 10-digit). Refreshed when None or on first use.
_ticker_to_cik_cache: Optional[dict[str, str]] = None


def _cik_to_10(cik: int | str) -> str:
    """Format CIK as 10-digit zero-padded string."""
    return str(int(cik)).zfill(10)


def _headers() -> dict[str, str]:
    return {"User-Agent": get_settings().sec_user_agent}


def fetch_companyfacts(cik: str) -> dict[str, Any]:
    """
    Fetch companyfacts JSON for a given CIK (10-digit zero-padded string).
    Raises on HTTP errors; returns raw JSON.
    """
    url = SEC_COMPANYFACTS_URL.format(cik=_cik_to_10(cik) if cik.isdigit() else cik)
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def ticker_to_cik(refresh: bool = False) -> dict[str, str]:
    """
    Return mapping ticker -> CIK (10-digit str). Uses SEC company_tickers.json.
    Cached in memory; pass refresh=True to force refetch.
    """
    global _ticker_to_cik_cache
    if _ticker_to_cik_cache is not None and not refresh:
        return _ticker_to_cik_cache
    r = requests.get(SEC_TICKERS_URL, headers=_headers(), timeout=30)
    r.raise_for_status()
    data = r.json()
    # Format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "..."}, ...}
    out: dict[str, str] = {}
    for v in data.values():
        if isinstance(v, dict):
            ticker = (v.get("ticker") or "").strip().upper()
            cik = v.get("cik_str") or v.get("cik")
            if ticker and cik is not None:
                out[ticker] = _cik_to_10(cik)
    _ticker_to_cik_cache = out
    return out


def _fp_to_quarter(fp: Optional[str]) -> Optional[int]:
    """Map SEC 'fp' (e.g. 'Q1','FY') to fiscal_quarter 1-4 or None for annual."""
    if not fp:
        return None
    fp = fp.strip().upper()
    if fp == "FY":
        return None
    m = re.match(r"Q([1-4])", fp)
    return int(m.group(1)) if m else None


# us-gaap concepts we persist as shareholders' equity (primary: StockholdersEquity)
EQUITY_CONCEPTS = (
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    "StockholdersEquityExcludingPortionAttributableToNoncontrollingInterest",
    "StockholdersEquityOther",
)


def _extract_equity_facts(companyfacts: dict[str, Any]) -> list[dict[str, Any]]:
    """
    From companyfacts JSON, extract us-gaap equity facts into a list of records
    with keys: end (date str), fy, fp, val, form, concept.
    """
    facts = companyfacts.get("facts", {}) or {}
    us_gaap = facts.get("us-gaap") or {}
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, Optional[int], Optional[int]]] = set()

    for concept in EQUITY_CONCEPTS:
        if concept not in us_gaap:
            continue
        concept_data = us_gaap[concept]
        units = concept_data.get("units") or {}
        # Prefer USD; fallback to "USD/shares" or first key
        for unit_key in ("USD", "USD/shares", "shares"):
            if unit_key not in units:
                continue
            for item in units[unit_key]:
                if not isinstance(item, dict):
                    continue
                end_str = item.get("end")
                val = item.get("val")
                fy = item.get("fy")
                fp = item.get("fp")
                if not end_str or val is None:
                    continue
                try:
                    period_end = date.fromisoformat(end_str)
                except Exception:
                    continue
                fq = _fp_to_quarter(fp)
                key = (end_str, fy, fq)
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "period_end": period_end,
                    "fiscal_year": fy,
                    "fiscal_quarter": fq,
                    "val": val,
                    "form": item.get("form"),
                    "concept": concept,
                    "unit": unit_key,
                })
            break
    return out


def sync_sec_equity_for_ticker(session: Session, ticker: str) -> int:
    """
    For a given ticker: resolve CIK, fetch companyfacts, parse us-gaap equity concepts,
    upsert into shareholders_equity_statements. Returns number of rows upserted.
    """
    inst = get_or_create_instrument(session, ticker)
    cik_map = ticker_to_cik()
    cik = cik_map.get(inst.ticker)
    if not cik:
        logger.warning("SEC: no CIK for ticker %s", inst.ticker)
        return 0

    try:
        companyfacts = fetch_companyfacts(cik)
    except requests.RequestException as e:
        logger.warning("SEC companyfacts failed for %s (CIK %s): %s", inst.ticker, cik, e)
        return 0

    facts_list = _extract_equity_facts(companyfacts)
    if not facts_list:
        return 0

    inserted = 0
    for rec in facts_list:
        period_end = rec["period_end"]
        fy = rec.get("fiscal_year")
        fq = rec.get("fiscal_quarter")
        data = {
            "value": rec.get("val"),
            "concept": rec.get("concept"),
            "unit": rec.get("unit"),
            "form": rec.get("form"),
        }
        existing = session.exec(
            select(ShareholdersEquity).where(
                ShareholdersEquity.instrument_id == inst.id,
                ShareholdersEquity.period_end == period_end,
                ShareholdersEquity.fiscal_year == fy,
                ShareholdersEquity.fiscal_quarter == fq,
            )
        ).first()
        if existing:
            existing.data = data
            session.add(existing)
        else:
            row = ShareholdersEquity(
                instrument_id=inst.id,
                period_start=None,
                period_end=period_end,
                fiscal_year=fy,
                fiscal_quarter=fq,
                currency="USD",
                filed_at=None,
                data=data,
            )
            session.add(row)
            inserted += 1
    session.commit()
    return inserted


def sync_sec_notes_for_ticker(session: Session, ticker: str) -> int:
    """
    Placeholder: SEC companyfacts does not contain full financial notes.
    Future: use 10-K/10-Q filings or other endpoints to store note references/structured data.
    """
    # No-op for now
    return 0
