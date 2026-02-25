from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf
from sqlmodel import Session, select

from app.models.market import MarketBar


def get_last_bar_ts(session: Session, *, instrument_id: int, timeframe: str) -> datetime | None:
    bar = session.exec(
        select(MarketBar)
        .where(MarketBar.instrument_id == instrument_id, MarketBar.timeframe == timeframe)
        .order_by(MarketBar.ts.desc())
        .limit(1)
    ).first()
    if not bar:
        return None
    ts = bar.ts
    return ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def fetch_history_df(ticker: str, start: datetime, end: datetime, timeframe: str) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(
        start=start,
        end=end,
        interval=timeframe,
        auto_adjust=False,
        actions=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df.reset_index(inplace=True)
    # yfinance uses "Date" for daily and "Datetime" for intraday
    ts_col = "Datetime" if "Datetime" in df.columns else "Date"
    df.rename(columns={ts_col: "ts"}, inplace=True)
    df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        },
        inplace=True,
    )

    df = df[["ts", "open", "high", "low", "close", "volume"]]

    # Normalize timezone to UTC
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.dropna(subset=["ts"])
    return df


def upsert_market_bars(
    session: Session,
    *,
    instrument_id: int,
    timeframe: str,
    df: pd.DataFrame,
) -> int:
    if df.empty:
        return 0

    min_ts = df["ts"].min().to_pydatetime()
    max_ts = df["ts"].max().to_pydatetime()
    existing = session.exec(
        select(MarketBar.ts).where(
            MarketBar.instrument_id == instrument_id,
            MarketBar.timeframe == timeframe,
            MarketBar.ts >= min_ts,
            MarketBar.ts <= max_ts,
        )
    ).all()
    existing_ts = {x.replace(tzinfo=timezone.utc) if x.tzinfo is None else x.astimezone(timezone.utc) for x in existing}

    to_add: list[MarketBar] = []
    for row in df.itertuples(index=False):
        ts: datetime = row.ts.to_pydatetime() if hasattr(row.ts, "to_pydatetime") else row.ts
        ts = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if ts in existing_ts:
            continue
        to_add.append(
            MarketBar(
                instrument_id=instrument_id,
                timeframe=timeframe,
                ts=ts,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume) if row.volume is not None else 0.0,
            )
        )

    if not to_add:
        return 0
    session.add_all(to_add)
    session.commit()
    return len(to_add)

