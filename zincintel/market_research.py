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
    returns = np.log(work["Close"] / work["Close"].shift(1)).dropna()
    for length in (20, 60):
        count = min(length, len(returns))
        result[f"returns_{length}"] = count
        if count == length:
            result[f"volatility_{length}_pct"] = round(float(returns.tail(length).std(ddof=1) * math.sqrt(252) * 100), 2)
    result["status"] = "AVAILABLE" if result["volatility_20_pct"] is not None else "INSUFFICIENT_HISTORY"
    return result
