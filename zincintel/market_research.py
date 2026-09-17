"""Descriptive market-data coverage and historical variation, never forecasts."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def recover_verified_close_history(snapshots: list[dict], max_age_days: int = 10) -> tuple[pd.DataFrame, dict]:
    """Recover only a recent, previously validated Westmetall Close series.

    A provider timeout must not erase an already verified public history.  The
    recovery is deliberately fail-closed: source identity, grade, dates,
    observation counts and the last value must all agree with the snapshot.
    """
    candidates: list[tuple[pd.Timestamp, pd.DataFrame, dict]] = []
    now = pd.Timestamp.now(tz="UTC").normalize()
    for snapshot in snapshots:
        close = snapshot.get("market_research", {}).get("close_series", {}) if isinstance(snapshot, dict) else {}
        if close.get("status") != "AVAILABLE":
            continue
        if close.get("source") != "westmetall_lme_3m_reference" or close.get("source_grade") != "B_PUBLIC_REFERENCE":
            continue
        points = close.get("chart_points") or []
        records = []
        for point in points:
            ts = pd.to_datetime(point.get("date"), errors="coerce", utc=True)
            value = pd.to_numeric(point.get("close"), errors="coerce")
            if pd.isna(ts) or pd.isna(value) or not np.isfinite(value) or float(value) <= 0:
                records = []
                break
            records.append((ts, float(value)))
        if len(records) < 60:
            continue
        frame = pd.DataFrame(records, columns=["timestamp", "Close"]).set_index("timestamp").sort_index()
        if frame.index.duplicated().any():
            continue
        as_of = pd.to_datetime(close.get("as_of"), errors="coerce", utc=True)
        if pd.isna(as_of) or as_of.normalize() != frame.index[-1].normalize():
            continue
        age_days = int((now - as_of.normalize()).days)
        if age_days < 0 or age_days > max_age_days:
            continue
        if int(close.get("observations") or 0) < len(frame):
            continue
        latest = pd.to_numeric(close.get("latest_close"), errors="coerce")
        if pd.isna(latest) or not np.isclose(float(latest), float(frame["Close"].iloc[-1]), rtol=0, atol=.011):
            continue
        meta = {
            "source": close.get("source"), "source_grade": close.get("source_grade"),
            "as_of": close.get("as_of"), "age_days": age_days,
            "recovered_from_run_time": snapshot.get("run_time"),
        }
        candidates.append((as_of, frame, meta))
    if not candidates:
        return pd.DataFrame(), {}
    _, frame, meta = max(candidates, key=lambda item: item[0])
    return frame, meta


def _trend_state(frame: pd.DataFrame) -> dict:
    missing = {"status": "INSUFFICIENT_DATA", "score": None, "regime": "INSUFFICIENT_DATA",
               "reasons": ["至少需要 40 個連續交易日才能判定趨勢"], "components": {}}
    if len(frame) < 40:
        return missing
    row = frame.iloc[-1]
    if any(pd.isna(row.get(k)) for k in ("Close", "ema20", "sma30", "rsi14")):
        return missing
    close, ema, sma, rsi = (float(row[k]) for k in ("Close", "ema20", "sma30", "rsi14"))
    ema_slope = (ema / float(frame["ema20"].iloc[-6]) - 1) * 100
    sma_slope = (sma / float(frame["sma30"].iloc[-11]) - 1) * 100
    recent = frame["Close"].tail(20)
    span = float(recent.max() - recent.min())
    position = .5 if span == 0 else float((close - recent.min()) / span)
    components = {
        "close_vs_ema20": 20 if close > ema else -20 if close < ema else 0,
        "ema20_vs_sma30": 20 if ema > sma else -20 if ema < sma else 0,
        "ema20_slope_5d": 15 if ema_slope > .05 else -15 if ema_slope < -.05 else 0,
        "sma30_slope_10d": 15 if sma_slope > .05 else -15 if sma_slope < -.05 else 0,
        "rsi14": 20 if 55 <= rsi <= 70 else 10 if 50 <= rsi < 55 or rsi > 70 else -20 if 30 <= rsi <= 45 else -10 if rsi < 30 or 45 < rsi < 50 else 0,
        "close_position_20d": 10 if position >= .75 else -10 if position <= .25 else 0,
    }
    score = int(sum(components.values()))
    regime = "STRONG_BULL" if score >= 60 else "BULL" if score >= 25 else "STRONG_BEAR" if score <= -60 else "BEAR" if score <= -25 else "NEUTRAL"
    reasons = [
        f"Close {'高於' if close > ema else '低於' if close < ema else '等於'} EMA20",
        f"EMA20 {'高於' if ema > sma else '低於' if ema < sma else '等於'} SMA30",
        f"EMA20 近 5 個交易日斜率 {ema_slope:+.2f}%",
        f"SMA30 近 10 個交易日斜率 {sma_slope:+.2f}%",
        f"RSI14 {rsi:.2f}",
        f"Close 位於近 20 日收盤區間的 {position*100:.0f}% 位置",
    ]
    return {"status": "AVAILABLE", "score": score, "regime": regime, "reasons": reasons,
            "components": components, "ema20_slope_5d_pct": round(ema_slope, 2),
            "sma30_slope_10d_pct": round(sma_slope, 2), "close_position_20d_pct": round(position*100, 1)}


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
              "coverage_start": None, "coverage_end": None, "coverage_by_year": {},
              "requested_history_start": "2025-01-01", "requested_start_covered": False,
              "trend": {"status": "INSUFFICIENT_DATA", "score": None, "regime": "INSUFFICIENT_DATA",
                        "persistence_days": 0, "data_confidence": "LOW", "risk_level": "INSUFFICIENT_DATA",
                        "reasons": ["收盤價歷史不足"], "components": {}},
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
    result["coverage_start"] = work.index[0].date().isoformat()
    result["coverage_end"] = work.index[-1].date().isoformat()
    result["coverage_by_year"] = {str(int(year)): int(count) for year, count in work.groupby(work.index.year).size().items()}
    result["requested_start_covered"] = pd.Timestamp(result["coverage_start"]) <= pd.Timestamp(result["requested_history_start"]) + pd.Timedelta(days=7)
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
    trend_frame = chart_frames[-1]
    trend = _trend_state(trend_frame)
    if trend["status"] == "AVAILABLE":
        persistence = 0
        for end in range(len(trend_frame), 39, -1):
            if _trend_state(trend_frame.iloc[:end]).get("regime") != trend["regime"]:
                break
            persistence += 1
        trend["persistence_days"] = persistence
        trend["data_confidence"] = "HIGH" if result["source_grade"] == "A_OFFICIAL" and len(trend_frame) >= 60 else "MEDIUM"
        v20, v60 = result.get("volatility_20_pct"), result.get("volatility_60_pct")
        trend["risk_level"] = ("INSUFFICIENT_DATA" if v20 is None else "ELEVATED" if v60 and v20 > v60*1.2
                               else "SUBDUED" if v60 and v20 < v60*.8 else "NORMAL")
    result["trend"] = trend
    result["status"] = "AVAILABLE" if result["volatility_20_pct"] is not None else "INSUFFICIENT_HISTORY"
    return result
