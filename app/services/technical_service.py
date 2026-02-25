from __future__ import annotations

from datetime import datetime, timezone
import math

import pandas as pd
import pandas_ta as ta
from sqlmodel import Session, select

from app.models.market import MarketBar, TechnicalFeature


def compute_features_df(bars: list[MarketBar]) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame()

    df = pd.DataFrame(
        {
            "ts": [b.ts.astimezone(timezone.utc) if b.ts.tzinfo else b.ts.replace(tzinfo=timezone.utc) for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }
    ).sort_values("ts")

    df["ma20"] = df["close"].rolling(20, min_periods=1).mean()
    df["ma200"] = df["close"].rolling(200, min_periods=1).mean()

    rsi = ta.rsi(df["close"], length=14)
    df["rsi14"] = rsi

    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        # column names: MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
        df["macd"] = macd.iloc[:, 0]
        df["macd_signal"] = macd.iloc[:, 1]
    else:
        df["macd"] = None
        df["macd_signal"] = None

    atr = ta.atr(df["high"], df["low"], df["close"], length=14)
    df["atr14"] = atr

    df["vol20_mean"] = df["volume"].rolling(20, min_periods=1).mean()
    df["vol20_ratio"] = (df["volume"] / df["vol20_mean"]).replace(
        [pd.NA, pd.NaT, float("inf"), -float("inf")], pd.NA
    )
    return df


def upsert_technical_features(
    session: Session,
    *,
    instrument_id: int,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> int:
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

    df = compute_features_df(list(bars))
    if df.empty:
        return 0

    min_ts = df["ts"].min().to_pydatetime()
    max_ts = df["ts"].max().to_pydatetime()
    existing = session.exec(
        select(TechnicalFeature.ts).where(
            TechnicalFeature.instrument_id == instrument_id,
            TechnicalFeature.timeframe == timeframe,
            TechnicalFeature.ts >= min_ts,
            TechnicalFeature.ts <= max_ts,
        )
    ).all()
    existing_ts = {x.replace(tzinfo=timezone.utc) if x.tzinfo is None else x.astimezone(timezone.utc) for x in existing}

    def _clean(v):
        if v is None:
            return None
        try:
            # pandas/Numpy NA or NaN
            if pd.isna(v):
                return None
        except Exception:
            pass
        try:
            f = float(v)
        except Exception:
            return None
        if math.isnan(f) or math.isinf(f):
            return None
        return f

    to_add: list[TechnicalFeature] = []
    for row in df.itertuples(index=False):
        ts: datetime = row.ts.to_pydatetime() if hasattr(row.ts, "to_pydatetime") else row.ts
        ts = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if ts in existing_ts:
            continue
        to_add.append(
            TechnicalFeature(
                instrument_id=instrument_id,
                timeframe=timeframe,
                ts=ts,
                ma20=_clean(row.ma20),
                ma200=_clean(row.ma200),
                rsi14=_clean(row.rsi14),
                macd=_clean(row.macd),
                macd_signal=_clean(row.macd_signal),
                atr14=_clean(row.atr14),
                vol20_mean=_clean(row.vol20_mean),
                vol20_ratio=_clean(row.vol20_ratio),
            )
        )

    if not to_add:
        return 0
    session.add_all(to_add)
    session.commit()
    return len(to_add)

