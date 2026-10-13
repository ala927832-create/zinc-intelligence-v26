"""Delayed public-reference research for the cross-asset dashboard.

These series are deliberately labelled as references, not executable quotes.
They may support end-of-day regime research but never supply bid/ask, fills or
contract sizing.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date

import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional provider failure is a data state
    yf = None


@dataclass(frozen=True)
class Instrument:
    key: str
    name: str
    symbol: str
    market_identity: str
    unit: str


INSTRUMENTS = (
    Instrument("gold", "COMEX Gold continuous reference", "GC=F", "Yahoo continuous futures reference", "USD/oz"),
    Instrument("usdjpy", "USD/JPY", "JPY=X", "Yahoo FX spot reference", "JPY per USD"),
    Instrument("dxy", "US Dollar Index", "DX-Y.NYB", "Yahoo index reference", "index"),
)

ALPHA_URL = "https://www.alphavantage.co/query"
USD_BASKET_COMPONENTS = {
    "eurusd": ("EUR", "USD", -0.576), "usdjpy": ("USD", "JPY", 0.136),
    "gbpusd": ("GBP", "USD", -0.119), "usdcad": ("USD", "CAD", 0.091),
    "usdsek": ("USD", "SEK", 0.042), "usdchf": ("USD", "CHF", 0.036),
}


def _series(frame: pd.DataFrame, name: str) -> pd.Series:
    data = frame[name]
    if isinstance(data, pd.DataFrame):
        data = data.iloc[:, 0]
    return pd.to_numeric(data, errors="coerce")


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = gain / loss.replace(0, float("nan"))
    result = 100 - 100 / (1 + rs)
    result = result.mask((loss == 0) & (gain > 0), 100.0)
    result = result.mask((loss == 0) & (gain == 0), 50.0)
    return result


def describe_history(frame: pd.DataFrame, instrument: Instrument) -> dict:
    base = {
        "status": "MISSING", "key": instrument.key, "name": instrument.name,
        "symbol": instrument.symbol, "market_identity": instrument.market_identity,
        "unit": instrument.unit, "source": "Yahoo Finance public reference via yfinance",
        "source_grade": "B_PUBLIC_REFERENCE", "as_of": None, "observations": 0,
        "coverage_start": None, "coverage_end": None, "chart_points": [], "series_type": "FULL_OHLC",
        "execution_quote": "UNAVAILABLE", "limitations": [
            "Delayed end-of-day public reference; not an exchange-certified settlement feed.",
            "No bid/ask, spread, actual fill or slippage.",
        ],
    }
    if frame is None or frame.empty or not {"Open", "High", "Low", "Close"}.issubset(frame.columns):
        return base
    work = pd.DataFrame({c.lower(): _series(frame, c) for c in ("Open", "High", "Low", "Close")})
    work["volume"] = _series(frame, "Volume") if "Volume" in frame.columns else 0.0
    work = work.dropna(subset=["open", "high", "low", "close"]).sort_index()
    work = work[(work[["open", "high", "low", "close"]] > 0).all(axis=1)]
    work = work[(work.high >= work[["open", "close"]].max(axis=1)) & (work.low <= work[["open", "close"]].min(axis=1))]
    if work.empty:
        return base
    work["sma20"] = work.close.rolling(20, min_periods=20).mean()
    work["sma60"] = work.close.rolling(60, min_periods=60).mean()
    work["ema20"] = work.close.ewm(span=20, adjust=False, min_periods=20).mean()
    prior = work.close.shift(1)
    tr = pd.concat([(work.high - work.low), (work.high - prior).abs(), (work.low - prior).abs()], axis=1).max(axis=1)
    work["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    work["rsi14"] = _rsi(work.close)

    def value(raw):
        return round(float(raw), 4) if pd.notna(raw) and math.isfinite(float(raw)) else None

    points = []
    for idx, row in work.tail(400).iterrows():
        points.append({"date": pd.Timestamp(idx).date().isoformat(), **{
            name: value(row[name]) for name in ("open", "high", "low", "close", "sma20", "sma60", "ema20", "atr14", "rsi14")
        }, "volume": value(row.volume)})
    latest = work.iloc[-1]
    as_of = pd.Timestamp(work.index[-1]).date().isoformat()
    base.update({
        "status": "AVAILABLE", "as_of": as_of, "observations": int(len(work)),
        "coverage_start": pd.Timestamp(work.index[0]).date().isoformat(), "coverage_end": as_of,
        "latest_session": {k: value(latest[k]) for k in ("open", "high", "low", "close", "sma20", "sma60", "ema20", "atr14", "rsi14")},
        "chart_points": points,
    })
    return base


def describe_close_history(close: pd.Series, *, key: str, name: str, symbol: str,
                           identity: str, unit: str, source: str, grade: str = "B_PUBLIC_REFERENCE") -> dict:
    base = {"status":"MISSING", "key":key, "name":name, "symbol":symbol,
            "market_identity":identity, "unit":unit, "source":source, "source_grade":grade,
            "series_type":"CLOSE_ONLY", "as_of":None, "observations":0, "chart_points":[],
            "execution_quote":"UNAVAILABLE", "limitations":[
                "Close-only research series; no candle pattern or ATR may be inferred.",
                "No bid/ask, spread, actual fill or slippage."]}
    if close is None or close.empty:
        return base
    values = pd.to_numeric(close, errors="coerce").dropna().sort_index()
    values = values[values > 0]
    if values.empty:
        return base
    frame = pd.DataFrame({"close": values})
    frame["sma20"] = frame.close.rolling(20, min_periods=20).mean()
    frame["sma60"] = frame.close.rolling(60, min_periods=60).mean()
    frame["ema20"] = frame.close.ewm(span=20, adjust=False, min_periods=20).mean()
    frame["rsi14"] = _rsi(frame.close)
    def val(raw): return round(float(raw), 4) if pd.notna(raw) and math.isfinite(float(raw)) else None
    points = [{"date":pd.Timestamp(idx).date().isoformat(), **{k:val(row[k]) for k in ("close","sma20","sma60","ema20","rsi14")}}
              for idx,row in frame.tail(400).iterrows()]
    latest = frame.iloc[-1]
    as_of = pd.Timestamp(frame.index[-1]).date().isoformat()
    base.update({"status":"AVAILABLE", "as_of":as_of, "observations":len(frame),
                 "coverage_start":pd.Timestamp(frame.index[0]).date().isoformat(), "coverage_end":as_of,
                 "latest_session":{k:val(latest[k]) for k in ("close","sma20","sma60","ema20","rsi14")},
                 "chart_points":points})
    return base


def _alpha_payload(params: dict, api_key: str) -> dict:
    response = requests.get(ALPHA_URL, params={**params, "apikey":api_key}, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if any(k in payload for k in ("Error Message", "Information", "Note")):
        raise ValueError("provider_limit_or_error")
    return payload


def _alpha_fx(api_key: str, from_currency: str, to_currency: str) -> pd.DataFrame:
    payload = _alpha_payload({"function":"FX_DAILY", "from_symbol":from_currency,
                              "to_symbol":to_currency, "outputsize":"full"}, api_key)
    raw = payload.get("Time Series FX (Daily)", {})
    rows = [{"date":d, "Open":v.get("1. open"), "High":v.get("2. high"),
             "Low":v.get("3. low"), "Close":v.get("4. close"), "Volume":0} for d,v in raw.items()]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index(pd.to_datetime(pd.Series([x["date"] for x in rows])).values).drop(columns="date").sort_index()


def _alpha_gold_close(api_key: str) -> pd.Series:
    payload = _alpha_payload({"function":"GOLD_SILVER_HISTORY", "symbol":"GOLD", "interval":"daily"}, api_key)
    raw = payload.get("data") or payload.get("Data") or []
    if not isinstance(raw, list):
        return pd.Series(dtype=float)
    dates, values = [], []
    for row in raw:
        when, value = row.get("date") or row.get("timestamp"), row.get("value") or row.get("price") or row.get("close")
        if when is not None and value is not None:
            dates.append(pd.Timestamp(when)); values.append(value)
    return pd.Series(values, index=dates, dtype="float64").sort_index() if dates else pd.Series(dtype=float)


def _usd_basket(api_key: str) -> pd.Series:
    components = {}
    for key, (base, quote, _) in USD_BASKET_COMPONENTS.items():
        frame = _alpha_fx(api_key, base, quote)
        if frame.empty:
            return pd.Series(dtype=float)
        components[key] = pd.to_numeric(frame["Close"], errors="coerce")
    aligned = pd.concat(components, axis=1, join="inner").dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    basket = pd.Series(50.14348112, index=aligned.index, dtype=float)
    for key, (_, _, exponent) in USD_BASKET_COMPONENTS.items():
        basket *= aligned[key] ** exponent
    return basket.rename("Close")


def fetch_reference_markets(period: str = "18mo") -> dict[str, dict]:
    results = {}
    try:
        if yf is None:
            raise RuntimeError("yfinance not installed")
        batch = yf.download([x.symbol for x in INSTRUMENTS], period=period, interval="1d", auto_adjust=False,
                            group_by="ticker", progress=False, timeout=20, threads=True)
        for instrument in INSTRUMENTS:
            frame = batch[instrument.symbol].copy() if isinstance(batch.columns, pd.MultiIndex) else batch.copy()
            if frame is not None and not frame.empty:
                dates = pd.to_datetime(frame.index, errors="coerce").date
                frame = frame.loc[[d < date.today() for d in dates]]
            results[instrument.key] = describe_history(frame, instrument)
    except Exception as exc:
        for instrument in INSTRUMENTS:
            results[instrument.key] = describe_history(pd.DataFrame(), instrument)
            results[instrument.key]["error"] = type(exc).__name__
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    if api_key:
        try:
            fx = _alpha_fx(api_key, "USD", "JPY")
            alpha_usdjpy = describe_history(fx, Instrument("usdjpy", "USD/JPY", "USDJPY",
                "Alpha Vantage FX daily reference", "JPY per USD"))
            alpha_usdjpy["source"] = "Alpha Vantage FX_DAILY"
            alpha_usdjpy["source_grade"] = "B_PUBLIC_API"
            if alpha_usdjpy["status"] == "AVAILABLE":
                backup = results.get("usdjpy", {})
                alpha_usdjpy["fallback_provider"] = backup.get("source")
                if backup.get("status") == "AVAILABLE" and backup.get("as_of") == alpha_usdjpy.get("as_of"):
                    a = alpha_usdjpy["latest_session"]["close"]; b = backup["latest_session"]["close"]
                    alpha_usdjpy["cross_source_deviation_pct"] = round((a / b - 1) * 100, 4) if b else None
                results["usdjpy"] = alpha_usdjpy
        except Exception as exc:
            results.setdefault("usdjpy", {})["alpha_vantage_error"] = type(exc).__name__
        try:
            results["gold_spot"] = describe_close_history(_alpha_gold_close(api_key), key="gold_spot",
                name="Gold spot research", symbol="GOLD", identity="Alpha Vantage gold historical close",
                unit="USD/oz", source="Alpha Vantage GOLD_SILVER_HISTORY", grade="B_PUBLIC_API")
        except Exception as exc:
            results["gold_spot"] = describe_close_history(pd.Series(dtype=float), key="gold_spot",
                name="Gold spot research", symbol="GOLD", identity="Alpha Vantage gold historical close",
                unit="USD/oz", source="Alpha Vantage GOLD_SILVER_HISTORY", grade="B_PUBLIC_API")
            results["gold_spot"]["error"] = type(exc).__name__
        if os.getenv("ENABLE_USD_RESEARCH_BASKET", "1").lower() not in {"0","false","no"}:
            try:
                results["usd_basket"] = describe_close_history(_usd_basket(api_key), key="usd_basket",
                    name="USD Research Basket", symbol="USD_RESEARCH_BASKET",
                    identity="Research basket; explicitly not official ICE DXY", unit="index",
                    source="Derived from Alpha Vantage FX_DAILY", grade="B_DERIVED_PUBLIC_API")
            except Exception as exc:
                results["usd_basket"] = describe_close_history(pd.Series(dtype=float), key="usd_basket",
                    name="USD Research Basket", symbol="USD_RESEARCH_BASKET",
                    identity="Research basket; explicitly not official ICE DXY", unit="index",
                    source="Derived from Alpha Vantage FX_DAILY", grade="B_DERIVED_PUBLIC_API")
                results["usd_basket"]["error"] = type(exc).__name__
    return results


def recover_last_verified(current: dict[str, dict], prior_snapshots: list[dict], max_age_days: int = 5) -> dict[str, dict]:
    """Carry forward a validated prior series briefly; retain its original as-of."""
    today = date.today()
    recovered = dict(current)
    instruments = list(INSTRUMENTS) + [
        Instrument("gold_spot", "Gold spot research", "GOLD", "Alpha Vantage gold historical close", "USD/oz"),
        Instrument("usd_basket", "USD Research Basket", "USD_RESEARCH_BASKET", "Research basket; not official ICE DXY", "index"),
    ]
    for instrument in instruments:
        if recovered.get(instrument.key, {}).get("status") == "AVAILABLE":
            recovered[instrument.key]["retrieval_status"] = "CURRENT_FETCH"
            continue
        for snapshot in prior_snapshots:
            candidate = snapshot.get("market_research", {}).get("cross_assets", {}).get(instrument.key, {})
            try:
                age = (today - date.fromisoformat(candidate.get("as_of"))).days
            except (TypeError, ValueError):
                continue
            if candidate.get("status") != "AVAILABLE" or not candidate.get("chart_points") or age > max_age_days:
                continue
            carried = dict(candidate)
            carried["retrieval_status"] = "CARRY_FORWARD_LAST_VERIFIED"
            carried["retrieval_age_days"] = age
            carried["current_provider_error"] = recovered.get(instrument.key, {}).get("error")
            recovered[instrument.key] = carried
            break
    return recovered
