from __future__ import annotations

from datetime import date
import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from sqlmodel import Session

from app.models.instrument import Instrument
from app.services.financial_statement_service import (
    upsert_balance_sheet,
    upsert_cash_flow_statement,
    upsert_financial_statement,
    upsert_income_statement,
)
from app.services.instrument_service import get_or_create_instrument


logger = logging.getLogger(__name__)


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


def _step_result(*, step: str, generated: bool, source_rows: int, inserted: int, updated: int) -> dict[str, Any]:
    return {
        "step": step,
        "generated": generated,
        "source_rows": source_rows,
        "inserted": inserted,
        "updated": updated,
    }


def _upsert_balance_sheets(
    session: Session,
    inst: Instrument,
    df: Optional[pd.DataFrame],
    *,
    is_quarterly: bool,
) -> dict[str, Any]:
    records = _df_to_records(df, is_quarterly=is_quarterly)
    step_name = "balance_sheet_quarterly" if is_quarterly else "balance_sheet_annual"
    if not records:
        return _step_result(step=step_name, generated=False, source_rows=0, inserted=0, updated=0)
    inserted = 0
    updated = 0
    for period_end, data in records:
        fy = period_end.year
        fq = None if not is_quarterly else (period_end.month - 1) // 3 + 1
        upsert_financial_statement(
            session,
            instrument_id=inst.id,
            statement_type="balance_sheet",
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            is_annual=not is_quarterly,
            currency=None,
            source="yahoo",
            filed_at=None,
        )
        created = upsert_balance_sheet(
            session,
            instrument_id=inst.id,
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            period_start=None,
            currency=None,
            filed_at=None,
        )
        if created:
            inserted += 1
        else:
            updated += 1
    session.commit()
    return _step_result(step=step_name, generated=True, source_rows=len(records), inserted=inserted, updated=updated)


def _upsert_income_statements(
    session: Session, inst: Instrument, df: Optional[pd.DataFrame], *, is_quarterly: bool
) -> dict[str, Any]:
    records = _df_to_records(df, is_quarterly=is_quarterly)
    step_name = "income_statement_quarterly" if is_quarterly else "income_statement_annual"
    if not records:
        return _step_result(step=step_name, generated=False, source_rows=0, inserted=0, updated=0)
    inserted = 0
    updated = 0
    for period_end, data in records:
        fy = period_end.year
        fq = None if not is_quarterly else (period_end.month - 1) // 3 + 1
        upsert_financial_statement(
            session,
            instrument_id=inst.id,
            statement_type="income_statement",
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            is_annual=not is_quarterly,
            currency=None,
            source="yahoo",
            filed_at=None,
        )
        created = upsert_income_statement(
            session,
            instrument_id=inst.id,
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            period_start=None,
            currency=None,
            filed_at=None,
        )
        if created:
            inserted += 1
        else:
            updated += 1
    session.commit()
    return _step_result(step=step_name, generated=True, source_rows=len(records), inserted=inserted, updated=updated)


def _upsert_cash_flows(
    session: Session, inst: Instrument, df: Optional[pd.DataFrame], *, is_quarterly: bool
) -> dict[str, Any]:
    records = _df_to_records(df, is_quarterly=is_quarterly)
    step_name = "cash_flow_quarterly" if is_quarterly else "cash_flow_annual"
    if not records:
        return _step_result(step=step_name, generated=False, source_rows=0, inserted=0, updated=0)
    inserted = 0
    updated = 0
    for period_end, data in records:
        fy = period_end.year
        fq = None if not is_quarterly else (period_end.month - 1) // 3 + 1
        upsert_financial_statement(
            session,
            instrument_id=inst.id,
            statement_type="cash_flow_statement",
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            is_annual=not is_quarterly,
            currency=None,
            source="yahoo",
            filed_at=None,
        )
        created = upsert_cash_flow_statement(
            session,
            instrument_id=inst.id,
            period_end=period_end,
            fiscal_year=fy,
            fiscal_quarter=fq,
            data=data,
            period_start=None,
            currency=None,
            filed_at=None,
        )
        if created:
            inserted += 1
        else:
            updated += 1
    session.commit()
    return _step_result(step=step_name, generated=True, source_rows=len(records), inserted=inserted, updated=updated)


def sync_financials_for_ticker(session: Session, ticker: str) -> dict[str, Any]:
    """
    Fetches financial statements from yfinance and upserts into dedicated tables
    for a single ticker. Intended to be called from scheduler or manually.
    """
    inst = get_or_create_instrument(session, ticker)
    t = yf.Ticker(inst.ticker)
    step_logs: list[dict[str, Any]] = []

    # Annual
    step_logs.append(_upsert_balance_sheets(session, inst, t.balance_sheet, is_quarterly=False))
    step_logs.append(_upsert_income_statements(session, inst, t.financials, is_quarterly=False))
    step_logs.append(_upsert_cash_flows(session, inst, t.cashflow, is_quarterly=False))

    # Quarterly
    step_logs.append(_upsert_balance_sheets(session, inst, t.quarterly_balance_sheet, is_quarterly=True))
    step_logs.append(_upsert_income_statements(session, inst, t.quarterly_financials, is_quarterly=True))
    step_logs.append(_upsert_cash_flows(session, inst, t.quarterly_cashflow, is_quarterly=True))

    for step in step_logs:
        logger.info(
            "financials_sync ticker=%s step=%s generated=%s source_rows=%s inserted=%s updated=%s",
            inst.ticker,
            step["step"],
            step["generated"],
            step["source_rows"],
            step["inserted"],
            step["updated"],
        )

    return {
        "ticker": inst.ticker,
        "steps": step_logs,
        "generated_steps": sum(1 for step in step_logs if step["generated"]),
        "inserted": sum(int(step["inserted"]) for step in step_logs),
        "updated": sum(int(step["updated"]) for step in step_logs),
    }

