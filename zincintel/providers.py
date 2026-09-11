from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
try:
    import yfinance as yf
except Exception:
    yf = None

from .utils import DATA_DIR, iso_now, read_json, safe_float

EXPECTED_MARKET_KEYS = [
    "lme_cash", "lme_3m", "lme_inventory_t", "cancelled_warrants_t",
    "tc_usd_t", "physical_premium_usd_t", "smelter_margin_usd_t",
    "china_demand_yoy_pct", "global_balance_kt", "smelter_utilization_pct"
]


def _normalize_market(raw: dict, source: str) -> dict:
    out = {k: safe_float(raw.get(k)) for k in EXPECTED_MARKET_KEYS}
    out["as_of"] = raw.get("as_of") or iso_now()
    out["source"] = source
    if out["lme_cash"] is not None and out["lme_3m"] is not None:
        out["cash_3m"] = out["lme_cash"] - out["lme_3m"]
    else:
        out["cash_3m"] = None
    if out["lme_inventory_t"] not in (None, 0) and out["cancelled_warrants_t"] is not None:
        out["cancelled_ratio_pct"] = out["cancelled_warrants_t"] / out["lme_inventory_t"] * 100.0
    else:
        out["cancelled_ratio_pct"] = None
    return out


def fetch_market_snapshot() -> dict:
    url = os.getenv("ZINC_MARKET_API_URL", "").strip()
    api_key = os.getenv("ZINC_MARKET_API_KEY", "").strip()
    if url:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, dict) and any(payload.get(k) is not None for k in EXPECTED_MARKET_KEYS):
                return _normalize_market(payload, "api")
        except Exception as exc:
            api_error = str(exc)
        else:
            api_error = "no expected fields"
    else:
        api_error = None

    manual = read_json(DATA_DIR / "manual_market.json", {})
    out = _normalize_market(manual, "manual")
    out["api_error"] = api_error
    return out


def fetch_macro(tickers: dict[str, str]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    if yf is None:
        return {name: {"value": None, "change_pct": None, "ticker": ticker, "status": "MISSING", "error": "yfinance not installed"} for name, ticker in tickers.items()}
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, period="7d", interval="1d", auto_adjust=True, progress=False, timeout=12)
            if df is None or df.empty:
                raise ValueError("empty response")
            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            close = pd.to_numeric(close, errors="coerce").dropna()
            if close.empty:
                raise ValueError("no close")
            latest = float(close.iloc[-1])
            previous = float(close.iloc[-2]) if len(close) >= 2 else None
            change = ((latest / previous) - 1) * 100 if previous not in (None, 0) else None
            results[name] = {"value": latest, "change_pct": change, "ticker": ticker, "status": "LIVE_OR_DELAYED_PUBLIC"}
        except Exception as exc:
            results[name] = {"value": None, "change_pct": None, "ticker": ticker, "status": "MISSING", "error": str(exc)}
    return results


def _read_candle_csv(path_or_url: str) -> pd.DataFrame:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        r = requests.get(path_or_url, timeout=20)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text))
    p = Path(path_or_url)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[1] / p
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def load_candles(kind: str = "daily") -> tuple[pd.DataFrame, str]:
    env_map = {
        "daily": ("ZINC_DAILY_CSV_URL", "ZINC_DAILY_CSV", "data/lme_zinc_3m_daily.csv"),
        "1h": ("ZINC_1H_CSV_URL", "ZINC_1H_CSV", "data/lme_zinc_3m_1h.csv"),
        "15m": ("ZINC_15M_CSV_URL", "ZINC_15M_CSV", "data/lme_zinc_3m_15m.csv"),
    }
    remote_env, local_env, default_local = env_map[kind]
    candidates = [os.getenv(remote_env, "").strip(), os.getenv(local_env, "").strip(), default_local]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            df = _read_candle_csv(candidate)
            if df.empty:
                continue
            lower = {c.lower(): c for c in df.columns}
            tcol = lower.get("timestamp") or lower.get("date") or lower.get("datetime")
            if not tcol:
                continue
            rename = {tcol: "timestamp"}
            for need in ["open", "high", "low", "close", "volume"]:
                if need in lower:
                    rename[lower[need]] = need.capitalize()
            df = df.rename(columns=rename)
            required = ["timestamp", "Open", "High", "Low", "Close"]
            if any(c not in df.columns for c in required):
                continue
            if "Volume" not in df.columns:
                df["Volume"] = 0.0
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna(subset=["timestamp", "Open", "High", "Low", "Close"]).sort_values("timestamp")
            df = df.drop_duplicates(subset=["timestamp"], keep="last").set_index("timestamp")
            return df, candidate
        except Exception:
            continue
    return pd.DataFrame(), "missing"
