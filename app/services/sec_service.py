"""
SEC EDGAR integration: companyfacts API for shareholders' equity and optional notes.

- company_tickers.json: ticker -> CIK (10-digit zero-padded).
- companyfacts: us-gaap StockholdersEquity (and related) -> shareholders_equity_statements.
"""

from __future__ import annotations

from html import unescape
import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Any, Optional

import requests
from sqlmodel import Session

from app.core.config import get_settings
from app.models.instrument import Instrument
from app.services.financial_statement_service import (
    upsert_financial_note,
    upsert_financial_statement,
    upsert_shareholders_equity,
)
from app.services.instrument_service import get_or_create_instrument

logger = logging.getLogger(__name__)

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

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


def fetch_submissions(cik: str) -> dict[str, Any]:
    """
    Fetch SEC submissions JSON for a given CIK (10-digit zero-padded string).
    Raises on HTTP errors; returns raw JSON.
    """
    url = SEC_SUBMISSIONS_URL.format(cik=_cik_to_10(cik) if cik.isdigit() else cik)
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


def _parse_iso_date(value: Any) -> Optional[date]:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _date_to_datetime_utc(value: Optional[date]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _is_annual_form(form: str) -> bool:
    normalized = (form or "").upper()
    return normalized.startswith("10-K") or normalized.startswith("20-F") or normalized.startswith("40-F")


def _filing_period_quarter(period_end: date, form: str) -> Optional[int]:
    if _is_annual_form(form):
        return None
    return (period_end.month - 1) // 3 + 1


def _filing_document_url(*, cik: str, accession_number: str, primary_document: str) -> Optional[str]:
    if not accession_number or not primary_document:
        return None
    accession_compact = accession_number.replace("-", "")
    return SEC_ARCHIVES_FILING_URL.format(
        cik=str(int(cik)),
        accession=accession_compact,
        document=primary_document,
    )


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" :-\u00a0")


def _extract_note_headings_from_html(html_text: str) -> list[str]:
    if not html_text:
        return []

    patterns = (
        r"<(?:h1|h2|h3|h4|h5|h6|div|p|td|font|a|span|b|strong)[^>]*>\s*(?:notes?\s+to\s+[^<]{0,220}|note\s+\d+[a-zA-Z]?(?:\.|:|\s|-)[^<]{0,220})\s*</(?:h1|h2|h3|h4|h5|h6|div|p|td|font|a|span|b|strong)>",
        r">\s*(?:notes?\s+to\s+[^<]{0,220}|note\s+\d+[a-zA-Z]?(?:\.|:|\s|-)[^<]{0,220})\s*<",
    )

    out: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, html_text, flags=re.IGNORECASE):
            heading = _clean_html_text(match.group(0))
            heading = heading.rstrip("<>")
            if not heading:
                continue
            lowered = heading.lower()
            if "note" not in lowered:
                continue
            if heading in seen:
                continue
            seen.add(heading)
            out.append(heading)
            if len(out) >= 40:
                return out
    return out


def _extract_note_filings(submissions: dict[str, Any], cik: str) -> list[dict[str, Any]]:
    recent = ((submissions.get("filings") or {}).get("recent") or {})
    forms = recent.get("form") or []
    accession_numbers = recent.get("accessionNumber") or []
    filing_dates = recent.get("filingDate") or []
    report_dates = recent.get("reportDate") or []
    primary_documents = recent.get("primaryDocument") or []
    primary_descriptions = recent.get("primaryDocDescription") or []
    items_len = min(
        len(forms),
        len(accession_numbers),
        len(filing_dates),
        len(report_dates),
        len(primary_documents),
        len(primary_descriptions),
    )

    out: list[dict[str, Any]] = []
    for idx in range(items_len):
        form = forms[idx] or ""
        if not re.match(r"^(10-Q|10-Q/A|10-K|10-K/A|20-F|20-F/A|40-F|40-F/A)$", form, flags=re.IGNORECASE):
            continue
        filing_date = _parse_iso_date(filing_dates[idx])
        report_date = _parse_iso_date(report_dates[idx])
        period_end = report_date or filing_date
        if period_end is None:
            continue

        accession_number = accession_numbers[idx]
        primary_document = primary_documents[idx]
        out.append({
            "form": form,
            "filing_date": filing_date,
            "report_date": report_date,
            "period_end": period_end,
            "fiscal_year": period_end.year,
            "fiscal_quarter": _filing_period_quarter(period_end, form),
            "accession_number": accession_number,
            "primary_document": primary_document,
            "primary_doc_description": primary_descriptions[idx],
            "filing_url": _filing_document_url(
                cik=cik,
                accession_number=accession_number,
                primary_document=primary_document,
            ),
        })
    return out


def _fetch_note_headings(filing_url: Optional[str]) -> list[str]:
    if not filing_url or not filing_url.lower().endswith((".htm", ".html", ".xhtml", ".xml")):
        return []
    try:
        response = requests.get(filing_url, headers=_headers(), timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.debug("SEC note filing fetch failed for %s: %s", filing_url, exc)
        return []
    return _extract_note_headings_from_html(response.text)


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
        upsert_financial_statement(
            session,
            instrument_id=inst.id,
            statement_type="shareholders_equity",
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            is_annual=fq is None,
            currency="USD",
            source="sec_companyfacts",
            filed_at=None,
        )
        created = upsert_shareholders_equity(
            session,
            instrument_id=inst.id,
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            period_start=None,
            currency="USD",
            filed_at=None,
        )
        if created:
            inserted += 1
    session.commit()
    return inserted


def sync_sec_notes_for_ticker(session: Session, ticker: str) -> int:
    """
    For a given ticker: resolve CIK, fetch recent SEC submissions, and persist
    filing-level financial note references plus any note headings extracted from
    the primary filing document into financial_notes.
    """
    inst = get_or_create_instrument(session, ticker)
    cik_map = ticker_to_cik()
    cik = cik_map.get(inst.ticker)
    if not cik:
        logger.warning("SEC: no CIK for ticker %s", inst.ticker)
        return 0

    try:
        submissions = fetch_submissions(cik)
    except requests.RequestException as exc:
        logger.warning("SEC submissions failed for %s (CIK %s): %s", inst.ticker, cik, exc)
        return 0

    filings = _extract_note_filings(submissions, cik)
    if not filings:
        return 0

    changed = 0
    for filing in filings:
        period_end = filing["period_end"]
        fy = filing.get("fiscal_year")
        fq = filing.get("fiscal_quarter")
        note_headings = _fetch_note_headings(filing.get("filing_url"))
        filed_at = _date_to_datetime_utc(filing.get("filing_date"))
        data = {
            "source": "sec_submissions",
            "form": filing.get("form"),
            "filing_date": filing.get("filing_date").isoformat() if filing.get("filing_date") else None,
            "report_date": filing.get("report_date").isoformat() if filing.get("report_date") else None,
            "accession_number": filing.get("accession_number"),
            "primary_document": filing.get("primary_document"),
            "primary_doc_description": filing.get("primary_doc_description"),
            "filing_url": filing.get("filing_url"),
            "note_headings": note_headings,
            "notes_extracted": bool(note_headings),
        }
        upsert_financial_statement(
            session,
            instrument_id=inst.id,
            statement_type="notes",
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            is_annual=fq is None,
            currency=None,
            source="sec_submissions",
            filed_at=filed_at,
        )
        upsert_financial_note(
            session,
            instrument_id=inst.id,
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            period_start=None,
            currency=None,
            filed_at=filed_at,
        )
        changed += 1
    session.commit()
    logger.info("financial_notes_sync ticker=%s rows=%s", inst.ticker, changed)
    return changed
