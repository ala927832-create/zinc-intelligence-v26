"""Descriptive market-data coverage and historical variation, never forecasts."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def describe_close_series(history: pd.DataFrame, source: str) -> dict:
    """Use only one date-stamped 3M reference series for observed volatility."""
    result = {"status": "MISSING", "source": source if source != "missing" else None,
              "source_grade": "B_PUBLIC_REFERENCE" if source == "westmetall_lme_3m_reference" else None,
              "series": "LME zinc 3M reference (Westmetall table)",
              "as_of": None, "observations": 0, "returns_20": 0,
              "latest_close": None, "sma_14": None, "sma_30": None,
              "ema_20": None, "rsi_14": None, "close_indicator_sessions": 0,
              "material_gap_count": 0, "largest_gap_days": None,
              "returns_60": 0, "volatility_20_pct": None, "volatility_60_pct": None,
              "method": "Sample standard deviation of daily log returns × √252; historical, not a forecast"}
    if source != "westmetall_lme_3m_reference" or history is None or history.empty or "Close" not in history:
        return result
    work = history[["Close"]].copy()
    work.index = pd.to_datetime(work.index, errors="coerce", utc=True)
    work["Close"] = pd.to_numeric(work["Close"], errors="coerce")
    work = work[work.index.notna() & work["Close"].notna() & np.isfinite(work["Close"]) & (work["Close"] > 0)]
    work = work.sort_index()
    # A reference quote dated today is not a completed prior-day observation.
    work = work[work.index.date < pd.Timestamp.now(tz="UTC").date()]
    if work.index.duplicated().any():
        return result
    result["observations"] = int(len(work))
    if work.empty:
        return result
    result["as_of"] = work.index[-1].date().isoformat()
    # A material interruption invalidates rolling indicators until a new
    # contiguous segment is established. Weekends and ordinary holidays fit
    # the seven-calendar-day allowance; this is not a full exchange calendar.
    gaps = work.index.to_series().diff().dt.total_seconds().div(86400)
    result["material_gap_count"] = int((gaps > 7).sum())
    result["largest_gap_days"] = int(gaps.max()) if gaps.notna().any() else None
    last_break = gaps[gaps > 7].index.max() if (gaps > 7).any() else None
    segment = work.loc[last_break:] if last_break is not None else work
    close = segment["Close"]
    result["close_indicator_sessions"] = len(close)
    result["latest_close"] = round(float(close.iloc[-1]), 2)
    for window in (14, 30):
        if len(close) >= window:
            result[f"sma_{window}"] = round(float(close.tail(window).mean()), 2)
    if len(close) >= 20:
        result["ema_20"] = round(float(close.ewm(span=20, adjust=False).mean().iloc[-1]), 2)
    if len(close) >= 15:
        delta = close.diff()
        gains = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        losses = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        gain, loss = gains.iloc[-1], losses.iloc[-1]
        result["rsi_14"] = round(float(100 - 100 / (1 + gain / loss)), 2) if loss > 0 else (100.0 if gain > 0 else 50.0)
    # Do not treat a price jump over missing sessions as a daily return.
    returns = np.log(close / close.shift(1)).dropna()
    for length in (20, 60):
        count = min(length, len(returns))
        result[f"returns_{length}"] = count
        if count == length:
            result[f"volatility_{length}_pct"] = round(float(returns.tail(length).std(ddof=1) * math.sqrt(252) * 100), 2)
    result["status"] = "AVAILABLE" if result["volatility_20_pct"] is not None else "INSUFFICIENT_HISTORY"
    return result
