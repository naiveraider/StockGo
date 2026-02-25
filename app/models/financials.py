from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, Index
from sqlalchemy import JSON as SA_JSON
from sqlmodel import Field, SQLModel


class FinancialStatement(SQLModel, table=True):
    """
    Generic financial statement table, keyed by instrument + statement type + period.

    statement_type 取值建议：
    - 'balance_sheet'              资产负债表
    - 'income_statement'           利润表 / P&L
    - 'cash_flow_statement'        现金流量表
    - 'shareholders_equity'        所有者权益变动表
    - 'notes'                      财报附注
    """

    __tablename__ = "financial_statements"
    __table_args__ = (
        Index(
            "ix_financials_instrument_type_period",
            "instrument_id",
            "statement_type",
            "fiscal_year",
            "fiscal_quarter",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    statement_type: str = Field(max_length=64, index=True)

    # 会计期间
    period_start: Optional[date] = Field(default=None)
    period_end: Optional[date] = Field(default=None, index=True)
    fiscal_year: Optional[int] = Field(default=None, index=True)
    fiscal_quarter: Optional[int] = Field(default=None, index=True)  # 1-4, 或 None 表示年度
    is_annual: bool = Field(default=False, index=True)
    is_ttm: bool = Field(default=False, index=True)

    # 货币与来源
    currency: Optional[str] = Field(default="USD", max_length=8)
    source: Optional[str] = Field(default=None, max_length=64)  # e.g. 'yahoo', 'sec', 'alphavantage'
    filed_at: Optional[datetime] = Field(default=None, index=True)  # 报告发布日期 / Filing 时间

    # 具体数值以 JSON 存储，结构由上游清洗标准化：
    # 例如：
    # {
    #   "assets": {...},
    #   "liabilities": {...},
    #   "equity": {...}
    # }
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SA_JSON))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BalanceSheet(SQLModel, table=True):
    __tablename__ = "balance_sheets"
    __table_args__ = (
        Index(
            "ix_balance_instrument_period",
            "instrument_id",
            "fiscal_year",
            "fiscal_quarter",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    period_start: Optional[date] = Field(default=None)
    period_end: Optional[date] = Field(default=None, index=True)
    fiscal_year: Optional[int] = Field(default=None, index=True)
    fiscal_quarter: Optional[int] = Field(default=None, index=True)
    currency: Optional[str] = Field(default="USD", max_length=8)
    filed_at: Optional[datetime] = Field(default=None, index=True)
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SA_JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncomeStatement(SQLModel, table=True):
    __tablename__ = "income_statements"
    __table_args__ = (
        Index(
            "ix_income_instrument_period",
            "instrument_id",
            "fiscal_year",
            "fiscal_quarter",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    period_start: Optional[date] = Field(default=None)
    period_end: Optional[date] = Field(default=None, index=True)
    fiscal_year: Optional[int] = Field(default=None, index=True)
    fiscal_quarter: Optional[int] = Field(default=None, index=True)
    currency: Optional[str] = Field(default="USD", max_length=8)
    filed_at: Optional[datetime] = Field(default=None, index=True)
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SA_JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CashFlowStatement(SQLModel, table=True):
    __tablename__ = "cash_flow_statements"
    __table_args__ = (
        Index(
            "ix_cashflow_instrument_period",
            "instrument_id",
            "fiscal_year",
            "fiscal_quarter",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    period_start: Optional[date] = Field(default=None)
    period_end: Optional[date] = Field(default=None, index=True)
    fiscal_year: Optional[int] = Field(default=None, index=True)
    fiscal_quarter: Optional[int] = Field(default=None, index=True)
    currency: Optional[str] = Field(default="USD", max_length=8)
    filed_at: Optional[datetime] = Field(default=None, index=True)
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SA_JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShareholdersEquity(SQLModel, table=True):
    __tablename__ = "shareholders_equity_statements"
    __table_args__ = (
        Index(
            "ix_equity_instrument_period",
            "instrument_id",
            "fiscal_year",
            "fiscal_quarter",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    period_start: Optional[date] = Field(default=None)
    period_end: Optional[date] = Field(default=None, index=True)
    fiscal_year: Optional[int] = Field(default=None, index=True)
    fiscal_quarter: Optional[int] = Field(default=None, index=True)
    currency: Optional[str] = Field(default="USD", max_length=8)
    filed_at: Optional[datetime] = Field(default=None, index=True)
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SA_JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FinancialNote(SQLModel, table=True):
    __tablename__ = "financial_notes"
    __table_args__ = (
        Index(
            "ix_notes_instrument_period",
            "instrument_id",
            "fiscal_year",
            "fiscal_quarter",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    instrument_id: int = Field(index=True, foreign_key="instruments.id")
    period_start: Optional[date] = Field(default=None)
    period_end: Optional[date] = Field(default=None, index=True)
    fiscal_year: Optional[int] = Field(default=None, index=True)
    fiscal_quarter: Optional[int] = Field(default=None, index=True)
    currency: Optional[str] = Field(default="USD", max_length=8)
    filed_at: Optional[datetime] = Field(default=None, index=True)
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(SA_JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

