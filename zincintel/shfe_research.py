"""Official SHFE zinc daily OHLC for a clearly-labelled cross-market panel.

This is not LME data.  One representative SHFE contract is selected per
trading day using highest open interest, then volume.  Contract identity and
roll boundaries are retained so a roll jump is never treated as an ordinary
one-day return.
"""

from __future__ import annotations

import csv
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import requests

from .utils import DATA_DIR


DAILY_URL = "https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{date}.dat"
SOURCE_PAGE = "https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/"
HISTORY_FILE = DATA_DIR / "history" / "shfe_zinc_main_daily.csv"
FIELDS = ["date", "market", "product", "contract", "open", "high", "low", "close",
          "settlement", "volume", "open_interest", "open_interest_change", "roll",
          "currency", "unit", "source", "source_grade", "selection_rule", "source_url"]


def _number(value, integer: bool = False):
    try:
        result = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return int(result) if integer else result


def parse_daily_payload(payload: dict, trade_date: date) -> dict | None:
    candidates = []
    for raw in payload.get("o_curinstrument", []):
        if str(raw.get("PRODUCTID", "")).strip().lower() != "zn_f":
            continue
        o = _number(raw.get("OPENPRICE")); h = _number(raw.get("HIGHESTPRICE"))
        l = _number(raw.get("LOWESTPRICE")); c = _number(raw.get("CLOSEPRICE"))
        settlement = _number(raw.get("SETTLEMENTPRICE"))
        volume = _number(raw.get("VOLUME"), True)
        interest = _number(raw.get("OPENINTEREST"), True)
        interest_change = _number(raw.get("OPENINTERESTCHG"), True)
        month = str(raw.get("DELIVERYMONTH", "")).strip()
        if None in (o, h, l, c, volume, interest) or not month:
            continue
        if min(o, h, l, c) <= 0 or l > min(o, c) or h < max(o, c) or h < l:
            continue
        if volume <= 0 or interest < 0:
            continue
        candidates.append((interest, volume, month, o, h, l, c, settlement, interest_change))
    if not candidates:
        return None
    interest, volume, month, o, h, l, c, settlement, interest_change = max(candidates)
    url = DAILY_URL.format(date=trade_date.strftime("%Y%m%d"))
    return {
        "date": trade_date.isoformat(), "market": "SHFE", "product": "Zinc",
        "contract": f"zn{month}", "open": o, "high": h, "low": l, "close": c,
        "settlement": settlement, "volume": volume, "open_interest": interest,
        "open_interest_change": interest_change, "roll": False, "currency": "CNY",
        "unit": "CNY/tonne", "source": "SHFE official daily trading data",
        "source_grade": "A_OFFICIAL_EXCHANGE",
        "selection_rule": "highest_open_interest_then_volume", "source_url": url,
    }


def fetch_day(trade_date: date, timeout: int = 25) -> dict | None:
    url = DAILY_URL.format(date=trade_date.strftime("%Y%m%d"))
    req = Request(url, headers={"User-Agent": "zinc-intelligence-research/2.8"})
    try:
        with urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    return parse_daily_payload(payload, trade_date)


def _fetch_chunk(dates: list[date], timeout: int = 25) -> list[dict]:
    """Reuse one TLS connection per worker; a full backfill stays practical."""
    rows = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "zinc-intelligence-research/2.8"})
        for trade_date in dates:
            url = DAILY_URL.format(date=trade_date.strftime("%Y%m%d"))
            try:
                response = session.get(url, timeout=timeout)
                response.raise_for_status()
                row = parse_daily_payload(response.json(), trade_date)
                if row:
                    rows.append(row)
            except (requests.RequestException, ValueError):
                continue
    return rows


def load_history(path: Path = HISTORY_FILE) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=FIELDS)
    frame = pd.read_csv(path)
    if frame.empty:
        return pd.DataFrame(columns=FIELDS)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date.astype(str)
    return frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")


def save_history(rows: pd.DataFrame, path: Path = HISTORY_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = rows.copy().sort_values("date").drop_duplicates("date", keep="last")
    rows["roll"] = rows["contract"].ne(rows["contract"].shift(1))
    if len(rows):
        rows.loc[rows.index[0], "roll"] = False
    rows[FIELDS].to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)


def update_history(path: Path = HISTORY_FILE, start: date | None = None, end: date | None = None) -> pd.DataFrame:
    existing = load_history(path)
    end = end or (date.today() - timedelta(days=1))
    configured = os.getenv("SHFE_HISTORY_START", "2025-01-01")
    start = start or (date.fromisoformat(configured) if existing.empty else date.fromisoformat(existing.iloc[-1]["date"]) + timedelta(days=1))
    known = set(existing["date"].astype(str))
    candidates = [start + timedelta(days=i) for i in range(max(0, (end-start).days+1))]
    candidates = [d for d in candidates if d.weekday() < 5 and d.isoformat() not in known]
    fetched = []
    workers = max(1, min(int(os.getenv("SHFE_FETCH_WORKERS", "10")), 16))
    chunks = [candidates[i::workers] for i in range(workers)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_fetch_chunk, chunk) for chunk in chunks if chunk]
        for future in as_completed(futures):
            fetched.extend(future.result())
    combined = pd.concat([existing, pd.DataFrame(fetched)], ignore_index=True) if fetched else existing
    if not combined.empty:
        # A conflicting replacement for the same date is rejected, not silently overwritten.
        for _, group in combined.groupby("date"):
            if len(group) > 1 and group[["contract", "open", "high", "low", "close"]].drop_duplicates().shape[0] > 1:
                raise ValueError(f"Conflicting SHFE daily rows for {group.iloc[0]['date']}")
        save_history(combined, path)
    return load_history(path)


def describe_history(frame: pd.DataFrame) -> dict:
    base = {"status": "MISSING", "market": "SHFE", "series": "SHFE zinc main-contract daily OHLC",
            "source": "SHFE official daily trading data", "source_grade": "A_OFFICIAL_EXCHANGE",
            "source_page": SOURCE_PAGE, "selection_rule": "highest_open_interest_then_volume",
            "as_of": None, "observations": 0, "chart_points": [], "roll_count": 0,
            "coverage_start": None, "coverage_end": None, "trend": {"regime": "INSUFFICIENT_DATA"}}
    if frame is None or frame.empty:
        return base
    work = frame.copy().sort_values("date")
    for col in ("open", "high", "low", "close", "volume", "open_interest"):
        work[col] = pd.to_numeric(work[col], errors="coerce")
    valid = work.dropna(subset=["open", "high", "low", "close", "contract"])
    valid = valid[(valid.low <= valid[["open", "close"]].min(axis=1)) & (valid.high >= valid[["open", "close"]].max(axis=1))]
    if valid.empty:
        return base
    valid["roll"] = valid["contract"].ne(valid["contract"].shift(1))
    valid.loc[valid.index[0], "roll"] = False
    valid["sma20"] = valid.close.rolling(20, min_periods=20).mean()
    valid["sma50"] = valid.close.rolling(50, min_periods=50).mean()
    valid["ema20"] = valid.close.ewm(span=20, adjust=False, min_periods=20).mean()
    def val(x): return round(float(x), 2) if pd.notna(x) and math.isfinite(float(x)) else None
    points = []
    for _, r in valid.tail(500).iterrows():
        points.append({"date": str(r.date), "contract": str(r.contract), "open": val(r.open),
                       "high": val(r.high), "low": val(r.low), "close": val(r.close),
                       "sma20": val(r.sma20), "sma50": val(r.sma50), "ema20": val(r.ema20),
                       "volume": int(r.volume), "open_interest": int(r.open_interest), "roll": bool(r.roll)})
    latest = valid.iloc[-1]
    regime = "INSUFFICIENT_DATA"
    if pd.notna(latest.sma20) and pd.notna(latest.sma50):
        score = (1 if latest.close > latest.sma20 else -1) + (1 if latest.sma20 > latest.sma50 else -1)
        regime = "BULL" if score == 2 else "BEAR" if score == -2 else "NEUTRAL"
    base.update({"status": "AVAILABLE", "as_of": str(latest.date), "observations": len(valid),
                 "coverage_start": str(valid.iloc[0].date), "coverage_end": str(latest.date),
                 "latest_contract": str(latest.contract), "latest_close": val(latest.close),
                 "latest_open_interest": int(latest.open_interest), "roll_count": int(valid.roll.sum()),
                 "chart_points": points, "trend": {"regime": regime, "method": "Close vs SMA20 and SMA20 vs SMA50"}})
    return base
