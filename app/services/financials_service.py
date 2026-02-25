from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from sqlmodel import Session, select

from app.models.financials import BalanceSheet, CashFlowStatement, IncomeStatement
from app.models.instrument import Instrument
from app.services.instrument_service import get_or_create_instrument


def _df_to_records(
    df: Optional[pd.DataFrame],
    *,
    is_quarterly: bool,
) -> list[tuple[date, dict]]:
    if df is None or df.empty:
        return []
    out: list[tuple[date, dict]] = []
    for col in df.columns:
        try:
            period_end = pd.to_datetime(col).date()
        except Exception:
            continue
        series = df[col]
        # Replace NaN/inf with None for JSON compatibility
        cleaned = series.replace([np.nan, np.inf, -np.inf], np.nan).dropna()
        data = {str(k): float(v) if isinstance(v, (int, float, np.floating)) else v for k, v in cleaned.to_dict().items()}
        out.append((period_end, data))
    return out


def _upsert_balance_sheets(session: Session, inst: Instrument, df: Optional[pd.DataFrame], *, is_quarterly: bool) -> int:
    records = _df_to_records(df, is_quarterly=is_quarterly)
    if not records:
        return 0
    inserted = 0
    for period_end, data in records:
        fy = period_end.year
        fq = None if not is_quarterly else (period_end.month - 1) // 3 + 1
        existing = session.exec(
            select(BalanceSheet).where(
                BalanceSheet.instrument_id == inst.id,
                BalanceSheet.period_end == period_end,
                BalanceSheet.fiscal_year == fy,
                BalanceSheet.fiscal_quarter == fq,
            )
        ).first()
        if existing:
            existing.data = data
            session.add(existing)
        else:
            bs = BalanceSheet(
                instrument_id=inst.id,
                period_start=None,
                period_end=period_end,
                fiscal_year=fy,
                fiscal_quarter=fq,
                currency=None,
                filed_at=None,
                data=data,
            )
            session.add(bs)
            inserted += 1
    session.commit()
    return inserted


def _upsert_income_statements(
    session: Session, inst: Instrument, df: Optional[pd.DataFrame], *, is_quarterly: bool
) -> int:
    records = _df_to_records(df, is_quarterly=is_quarterly)
    if not records:
        return 0
    inserted = 0
    for period_end, data in records:
        fy = period_end.year
        fq = None if not is_quarterly else (period_end.month - 1) // 3 + 1
        existing = session.exec(
            select(IncomeStatement).where(
                IncomeStatement.instrument_id == inst.id,
                IncomeStatement.period_end == period_end,
                IncomeStatement.fiscal_year == fy,
                IncomeStatement.fiscal_quarter == fq,
            )
        ).first()
        if existing:
            existing.data = data
            session.add(existing)
        else:
            row = IncomeStatement(
                instrument_id=inst.id,
                period_start=None,
                period_end=period_end,
                fiscal_year=fy,
                fiscal_quarter=fq,
                currency=None,
                filed_at=None,
                data=data,
            )
            session.add(row)
            inserted += 1
    session.commit()
    return inserted


def _upsert_cash_flows(
    session: Session, inst: Instrument, df: Optional[pd.DataFrame], *, is_quarterly: bool
) -> int:
    records = _df_to_records(df, is_quarterly=is_quarterly)
    if not records:
        return 0
    inserted = 0
    for period_end, data in records:
        fy = period_end.year
        fq = None if not is_quarterly else (period_end.month - 1) // 3 + 1
        existing = session.exec(
            select(CashFlowStatement).where(
                CashFlowStatement.instrument_id == inst.id,
                CashFlowStatement.period_end == period_end,
                CashFlowStatement.fiscal_year == fy,
                CashFlowStatement.fiscal_quarter == fq,
            )
        ).first()
        if existing:
            existing.data = data
            session.add(existing)
        else:
            row = CashFlowStatement(
                instrument_id=inst.id,
                period_start=None,
                period_end=period_end,
                fiscal_year=fy,
                fiscal_quarter=fq,
                currency=None,
                filed_at=None,
                data=data,
            )
            session.add(row)
            inserted += 1
    session.commit()
    return inserted


def sync_financials_for_ticker(session: Session, ticker: str) -> None:
    """
    Fetches financial statements from yfinance and upserts into dedicated tables
    for a single ticker. Intended to be called from scheduler or manually.
    """
    inst = get_or_create_instrument(session, ticker)
    t = yf.Ticker(inst.ticker)

    # Annual
    _upsert_balance_sheets(session, inst, t.balance_sheet, is_quarterly=False)
    _upsert_income_statements(session, inst, t.financials, is_quarterly=False)
    _upsert_cash_flows(session, inst, t.cashflow, is_quarterly=False)

    # Quarterly
    _upsert_balance_sheets(session, inst, t.quarterly_balance_sheet, is_quarterly=True)
    _upsert_income_statements(session, inst, t.quarterly_financials, is_quarterly=True)
    _upsert_cash_flows(session, inst, t.quarterly_cashflow, is_quarterly=True)

