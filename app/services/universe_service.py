from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlmodel import Session, select

from app.models.instrument import Instrument


NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


@dataclass(frozen=True)
class UniverseRow:
    ticker: str
    exchange: str | None
    name: str | None
    is_etf: bool = False


def _parse_pipe_file(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return [], []
    # last line is "File Creation Time: ..."
    if lines[-1].lower().startswith("file creation time"):
        lines = lines[:-1]
    header = lines[0].split("|")
    rows = [ln.split("|") for ln in lines[1:] if "|" in ln]
    return header, rows


def _fetch_text(url: str) -> str:
    with httpx.Client(timeout=20.0, headers={"User-Agent": "StockGo/0.1"}) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def load_us_universe() -> list[UniverseRow]:
    """
    Loads US listed symbols from NasdaqTrader (Nasdaq + NYSE/AMEX/etc).
    Source: nasdaqlisted.txt and otherlisted.txt.
    """
    out: list[UniverseRow] = []

    # Nasdaq listed
    header, rows = _parse_pipe_file(_fetch_text(NASDAQ_LISTED_URL))
    idx_symbol = header.index("Symbol") if "Symbol" in header else 0
    idx_name = header.index("Security Name") if "Security Name" in header else None
    idx_test = header.index("Test Issue") if "Test Issue" in header else None
    idx_etf = header.index("ETF") if "ETF" in header else None
    for r in rows:
        if idx_test is not None and len(r) > idx_test and r[idx_test] == "Y":
            continue
        sym = r[idx_symbol].strip().upper()
        if not sym or sym == "Symbol":
            continue
        name = r[idx_name].strip() if idx_name is not None and len(r) > idx_name else None
        is_etf = bool(idx_etf is not None and len(r) > idx_etf and r[idx_etf].strip().upper() == "Y")
        out.append(UniverseRow(ticker=sym, exchange="NASDAQ", name=name, is_etf=is_etf))

    # Other listed (NYSE/AMEX + others)
    header, rows = _parse_pipe_file(_fetch_text(OTHER_LISTED_URL))
    # Columns: ACT Symbol | Security Name | Exchange | CQS Symbol | ETF | Round Lot Size | Test Issue | NASDAQ Symbol
    idx_symbol = header.index("ACT Symbol") if "ACT Symbol" in header else 0
    idx_name = header.index("Security Name") if "Security Name" in header else None
    idx_exch = header.index("Exchange") if "Exchange" in header else None
    idx_etf = header.index("ETF") if "ETF" in header else None
    idx_test = header.index("Test Issue") if "Test Issue" in header else None
    for r in rows:
        if idx_test is not None and len(r) > idx_test and r[idx_test] == "Y":
            continue
        sym = r[idx_symbol].strip().upper()
        if not sym or sym == "ACT Symbol":
            continue
        name = r[idx_name].strip() if idx_name is not None and len(r) > idx_name else None
        exch = r[idx_exch].strip() if idx_exch is not None and len(r) > idx_exch else None
        # Exchange codes: N=NYSE, A=NYSE American, P=NYSE Arca, Z=BATS, V=IEXG, etc.
        is_etf = bool(idx_etf is not None and len(r) > idx_etf and r[idx_etf].strip().upper() == "Y")
        out.append(UniverseRow(ticker=sym, exchange=exch or "OTHER", name=name, is_etf=is_etf))

    # De-dup by ticker (prefer Nasdaq row with full name)
    best: dict[str, UniverseRow] = {}
    for r in out:
        prev = best.get(r.ticker)
        if not prev:
            best[r.ticker] = r
            continue
        if (not prev.name) and r.name:
            best[r.ticker] = r
    return list(best.values())


def sync_universe(session: Session) -> tuple[int, int, int]:
    """
    Upserts the US universe into instruments table.
    Returns (inserted, updated, total)
    """
    rows = load_us_universe()
    tickers = [r.ticker for r in rows]
    existing = session.exec(select(Instrument).where(Instrument.ticker.in_(tickers))).all()
    existing_by_ticker = {i.ticker: i for i in existing}

    inserted = 0
    updated = 0
    for r in rows:
        inst = existing_by_ticker.get(r.ticker)
        if not inst:
            inst = Instrument(
                ticker=r.ticker,
                exchange=r.exchange or "US",
                name=(r.name[:128] if r.name else None),
                is_etf=bool(r.is_etf),
            )
            session.add(inst)
            inserted += 1
            continue
        changed = False
        if r.exchange and inst.exchange != r.exchange:
            inst.exchange = r.exchange
            changed = True
        if r.name and (not inst.name or inst.name != r.name[:128]):
            inst.name = r.name[:128]
            changed = True
        if bool(inst.is_etf) != bool(r.is_etf):
            inst.is_etf = bool(r.is_etf)
            changed = True
        if changed:
            session.add(inst)
            updated += 1

    session.commit()
    return inserted, updated, len(rows)

