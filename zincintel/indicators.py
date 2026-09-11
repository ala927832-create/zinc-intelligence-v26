from __future__ import annotations

import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["Close"].astype(float)
    h = out["High"].astype(float)
    l = out["Low"].astype(float)

    out["EMA20"] = c.ewm(span=20, adjust=False).mean()
    out["EMA50"] = c.ewm(span=50, adjust=False).mean()
    out["EMA200"] = c.ewm(span=200, adjust=False).mean()
    out["SMA20"] = c.rolling(20).mean()
    std20 = c.rolling(20).std(ddof=0)
    out["BB_UPPER"] = out["SMA20"] + 2 * std20
    out["BB_LOWER"] = out["SMA20"] - 2 * std20

    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI14"] = 100 - (100 / (1 + rs))
    out.loc[(avg_loss == 0) & (avg_gain > 0), "RSI14"] = 100
    out.loc[(avg_loss == 0) & (avg_gain == 0), "RSI14"] = 50

    prev_close = c.shift(1)
    tr = pd.concat([(h - l).abs(), (h - prev_close).abs(), (l - prev_close).abs()], axis=1).max(axis=1)
    out["ATR14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    out["ROC20"] = c.pct_change(20) * 100
    out["ROC60"] = c.pct_change(60) * 100
    out["RET1"] = c.pct_change() * 100
    return out


def add_close_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Indicators valid on an exact close-only series; never fabricates OHLC."""
    if df is None or df.empty or "Close" not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    c = pd.to_numeric(out["Close"], errors="coerce")
    out["EMA20"] = c.ewm(span=20, adjust=False).mean()
    out["EMA50"] = c.ewm(span=50, adjust=False).mean()
    out["EMA200"] = c.ewm(span=200, adjust=False).mean()
    out["SMA20"] = c.rolling(20).mean()
    std20 = c.rolling(20).std(ddof=0)
    out["BB_UPPER"] = out["SMA20"] + 2 * std20
    out["BB_LOWER"] = out["SMA20"] - 2 * std20
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI14"] = 100 - (100 / (1 + rs))
    out.loc[(avg_loss == 0) & (avg_gain > 0), "RSI14"] = 100
    out.loc[(avg_loss == 0) & (avg_gain == 0), "RSI14"] = 50
    out["ATR14"] = np.nan
    out["ROC20"] = c.pct_change(20) * 100
    out["ROC60"] = c.pct_change(60) * 100
    out["RET1"] = c.pct_change() * 100
    return out


def latest_indicator_dict(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    x = df.iloc[-1]
    keys = ["Close", "EMA20", "EMA50", "EMA200", "RSI14", "ATR14", "ROC20", "ROC60", "BB_UPPER", "BB_LOWER"]
    out = {}
    for k in keys:
        try:
            v = float(x[k])
            out[k] = v if np.isfinite(v) else None
        except Exception:
            out[k] = None
    return out
