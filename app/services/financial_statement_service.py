from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.financials import (
    BalanceSheet,
    CashFlowStatement,
    FinancialNote,
    FinancialStatement,
    IncomeStatement,
    ShareholdersEquity,
)


def _upsert_specialized_statement(
    session: Session,
    *,
    model_cls: type[BalanceSheet] | type[IncomeStatement] | type[CashFlowStatement] | type[ShareholdersEquity] | type[FinancialNote],
    instrument_id: int,
    period_end: date,
    fiscal_year: Optional[int],
    fiscal_quarter: Optional[int],
    data: dict[str, Any],
    period_start: Optional[date] = None,
    currency: Optional[str] = None,
    filed_at: Optional[datetime] = None,
) -> bool:
    existing = session.exec(
        select(model_cls).where(
            model_cls.instrument_id == instrument_id,
            model_cls.period_end == period_end,
            model_cls.fiscal_year == fiscal_year,
            model_cls.fiscal_quarter == fiscal_quarter,
        )
    ).first()
    if existing:
        existing.period_start = period_start
        existing.currency = currency
        existing.filed_at = filed_at
        existing.data = data
        session.add(existing)
        return False

    row = model_cls(
        instrument_id=instrument_id,
        period_start=period_start,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        currency=currency,
        filed_at=filed_at,
        data=data,
    )
    session.add(row)
    return True


def upsert_financial_statement(
    session: Session,
    *,
    instrument_id: int,
    statement_type: str,
    period_end: date,
    fiscal_year: Optional[int],
    fiscal_quarter: Optional[int],
    data: dict[str, Any],
    period_start: Optional[date] = None,
    is_annual: bool = False,
    is_ttm: bool = False,
    currency: Optional[str] = None,
    source: Optional[str] = None,
    filed_at: Optional[datetime] = None,
) -> None:
    existing = session.exec(
        select(FinancialStatement).where(
            FinancialStatement.instrument_id == instrument_id,
            FinancialStatement.statement_type == statement_type,
            FinancialStatement.period_end == period_end,
            FinancialStatement.fiscal_year == fiscal_year,
            FinancialStatement.fiscal_quarter == fiscal_quarter,
        )
    ).first()
    if existing:
        existing.period_start = period_start
        existing.is_annual = is_annual
        existing.is_ttm = is_ttm
        existing.currency = currency
        existing.source = source
        existing.filed_at = filed_at
        existing.data = data
        session.add(existing)
        return

    row = FinancialStatement(
        instrument_id=instrument_id,
        statement_type=statement_type,
        period_start=period_start,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        is_annual=is_annual,
        is_ttm=is_ttm,
        currency=currency,
        source=source,
        filed_at=filed_at,
        data=data,
    )
    session.add(row)


def upsert_balance_sheet(
    session: Session,
    *,
    instrument_id: int,
    period_end: date,
    fiscal_year: Optional[int],
    fiscal_quarter: Optional[int],
    data: dict[str, Any],
    period_start: Optional[date] = None,
    currency: Optional[str] = None,
    filed_at: Optional[datetime] = None,
) -> bool:
    return _upsert_specialized_statement(
        session,
        model_cls=BalanceSheet,
        instrument_id=instrument_id,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        data=data,
        period_start=period_start,
        currency=currency,
        filed_at=filed_at,
    )


def upsert_income_statement(
    session: Session,
    *,
    instrument_id: int,
    period_end: date,
    fiscal_year: Optional[int],
    fiscal_quarter: Optional[int],
    data: dict[str, Any],
    period_start: Optional[date] = None,
    currency: Optional[str] = None,
    filed_at: Optional[datetime] = None,
) -> bool:
    return _upsert_specialized_statement(
        session,
        model_cls=IncomeStatement,
        instrument_id=instrument_id,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        data=data,
        period_start=period_start,
        currency=currency,
        filed_at=filed_at,
    )


def upsert_cash_flow_statement(
    session: Session,
    *,
    instrument_id: int,
    period_end: date,
    fiscal_year: Optional[int],
    fiscal_quarter: Optional[int],
    data: dict[str, Any],
    period_start: Optional[date] = None,
    currency: Optional[str] = None,
    filed_at: Optional[datetime] = None,
) -> bool:
    return _upsert_specialized_statement(
        session,
        model_cls=CashFlowStatement,
        instrument_id=instrument_id,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        data=data,
        period_start=period_start,
        currency=currency,
        filed_at=filed_at,
    )


def upsert_shareholders_equity(
    session: Session,
    *,
    instrument_id: int,
    period_end: date,
    fiscal_year: Optional[int],
    fiscal_quarter: Optional[int],
    data: dict[str, Any],
    period_start: Optional[date] = None,
    currency: Optional[str] = None,
    filed_at: Optional[datetime] = None,
) -> bool:
    return _upsert_specialized_statement(
        session,
        model_cls=ShareholdersEquity,
        instrument_id=instrument_id,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        data=data,
        period_start=period_start,
        currency=currency,
        filed_at=filed_at,
    )


def upsert_financial_note(
    session: Session,
    *,
    instrument_id: int,
    period_end: date,
    fiscal_year: Optional[int],
    fiscal_quarter: Optional[int],
    data: dict[str, Any],
    period_start: Optional[date] = None,
    currency: Optional[str] = None,
    filed_at: Optional[datetime] = None,
) -> bool:
    return _upsert_specialized_statement(
        session,
        model_cls=FinancialNote,
        instrument_id=instrument_id,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        data=data,
        period_start=period_start,
        currency=currency,
        filed_at=filed_at,
    )