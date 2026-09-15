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
              "open_status": "MISSING_UNVERIFIED_SOURCE", "chart_points": [],
              "weekly_close_ranges": [],
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
    chart_frames = []
    for _, frame in work.groupby((gaps > 7).cumsum()):
        chart = frame.copy()
        chart["sma14"] = chart["Close"].rolling(14, min_periods=14).mean()
        chart["sma30"] = chart["Close"].rolling(30, min_periods=30).mean()
        chart["ema20"] = chart["Close"].ewm(span=20, adjust=False, min_periods=20).mean()
        delta = chart["Close"].diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        chart["rsi14"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
        chart.loc[(loss == 0) & (gain > 0), "rsi14"] = 100.0
        chart.loc[(loss == 0) & (gain == 0), "rsi14"] = 50.0
        chart_frames.append(chart)
    chart = pd.concat(chart_frames).tail(1250)
    def finite_or_none(value):
        return round(float(value), 2) if pd.notna(value) and np.isfinite(value) else None
    result["chart_points"] = [
        {"date": idx.date().isoformat(), "close": finite_or_none(row.Close),
         "sma14": finite_or_none(row.sma14), "sma30": finite_or_none(row.sma30),
         "ema20": finite_or_none(row.ema20), "rsi14": finite_or_none(row.rsi14)}
        for idx, row in chart.iterrows()
    ]
    weekly = work["Close"].resample("W-FRI").agg(["first", "max", "min", "last", "count"])
    weekly = weekly[weekly["count"] > 0].tail(260)
    result["weekly_close_ranges"] = [
        {"week": idx.date().isoformat(), "first_close": finite_or_none(row["first"]),
         "highest_close": finite_or_none(row["max"]), "lowest_close": finite_or_none(row["min"]),
         "last_close": finite_or_none(row["last"]), "sessions": int(row["count"])}
        for idx, row in weekly.iterrows()
    ]
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
