from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .utils import DATA_DIR, iso_now, safe_float

LME_ZINC_URL = "https://www.lme.com/en/metals/non-ferrous/lme-zinc"
SMM_ZINC_URL = "https://www-old.metal.com/Zinc"
CLOSE_HISTORY_PATH = DATA_DIR / "lme_3m_close_history.csv"


def _norm(v: Any) -> str:
    return "".join(ch.lower() for ch in str(v or "") if ch.isalnum())


def _mid(a: Any, b: Any) -> float | None:
    x, y = safe_float(a), safe_float(b)
    if x is not None and y is not None:
        return (x + y) / 2.0
    return x if x is not None else y


def _fill(market: dict, values: dict, provider: str, status: str, as_of: str | None) -> None:
    market.setdefault("field_sources", {})
    for key, value in values.items():
        if value is not None and market.get(key) is None:
            market[key] = value
            market["field_sources"][key] = {"provider": provider, "status": status, "as_of": as_of}


def _extract_lme_public(html_text: str) -> tuple[dict, str | None]:
    values = {
        "lme_cash": None, "lme_3m": None,
        "lme_cash_bid": None, "lme_cash_offer": None,
        "lme_3m_bid": None, "lme_3m_offer": None,
        "lme_settlement": None, "lme_closing_3m": None,
        "lme_inventory_t": None, "live_warrants_t": None,
        "cancelled_warrants_t": None,
    }
    try:
        tables = pd.read_html(io.StringIO(html_text))
    except Exception:
        tables = []

    for df in tables:
        cols = {_norm(c): c for c in df.columns}
        if "contract" in cols and "bid" in cols and "offer" in cols:
            for _, row in df.iterrows():
                label = str(row.get(cols["contract"], "")).strip().lower()
                if label == "cash":
                    values["lme_cash_bid"] = safe_float(row.get(cols["bid"]))
                    values["lme_cash_offer"] = safe_float(row.get(cols["offer"]))
                elif label in {"3-month", "3month", "3m"}:
                    values["lme_3m_bid"] = safe_float(row.get(cols["bid"]))
                    values["lme_3m_offer"] = safe_float(row.get(cols["offer"]))
        if "contract" in cols and "price" in cols:
            for _, row in df.iterrows():
                label = str(row.get(cols["contract"], "")).strip().lower()
                if label in {"3-month", "3month", "3m"}:
                    values["lme_closing_3m"] = safe_float(row.get(cols["price"]))
        if "stocks" in cols and "amount" in cols:
            for _, row in df.iterrows():
                label = str(row.get(cols["stocks"], "")).strip().lower()
                amount = safe_float(row.get(cols["amount"]))
                if "opening" in label:
                    values["lme_inventory_t"] = amount
                elif "live" in label:
                    values["live_warrants_t"] = amount
                elif "cancel" in label:
                    values["cancelled_warrants_t"] = amount

    text = BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)
    def number(pattern: str) -> float | None:
        m = re.search(pattern, text, flags=re.I)
        return safe_float(m.group(1).replace(",", "")) if m else None

    if values["lme_cash_bid"] is None:
        values["lme_cash_bid"] = number(r"Cash\s+([\d,]+(?:\.\d+)?)\s+[\d,]+(?:\.\d+)?")
    if values["lme_cash_offer"] is None:
        m = re.search(r"Cash\s+[\d,]+(?:\.\d+)?\s+([\d,]+(?:\.\d+)?)", text, flags=re.I)
        values["lme_cash_offer"] = safe_float(m.group(1).replace(",", "")) if m else None
    if values["lme_3m_bid"] is None:
        values["lme_3m_bid"] = number(r"3[- ]?month\s+([\d,]+(?:\.\d+)?)\s+[\d,]+(?:\.\d+)?")
    if values["lme_3m_offer"] is None:
        m = re.search(r"3[- ]?month\s+[\d,]+(?:\.\d+)?\s+([\d,]+(?:\.\d+)?)", text, flags=re.I)
        values["lme_3m_offer"] = safe_float(m.group(1).replace(",", "")) if m else None
    if values["lme_inventory_t"] is None:
        values["lme_inventory_t"] = number(r"Opening Stock\s+([\d,]+(?:\.\d+)?)")
    if values["live_warrants_t"] is None:
        values["live_warrants_t"] = number(r"Live warrants\s+([\d,]+(?:\.\d+)?)")
    if values["cancelled_warrants_t"] is None:
        values["cancelled_warrants_t"] = number(r"Cancelled warrants\s+([\d,]+(?:\.\d+)?)")

    values["lme_cash"] = _mid(values["lme_cash_bid"], values["lme_cash_offer"])
    values["lme_3m"] = _mid(values["lme_3m_bid"], values["lme_3m_offer"])
    values["lme_settlement"] = values["lme_cash_offer"]

    dates = re.findall(r"\b\d{1,2}\s+[A-Z][a-z]{2}\s+20\d{2}\b", text)
    as_of = None
    if dates:
        try:
            as_of = pd.Timestamp(dates[0]).date().isoformat()
        except Exception:
            as_of = dates[0]
    return values, as_of


def fetch_lme_public() -> tuple[dict, str | None, str, str | None]:
    url = os.getenv("LME_PUBLIC_ZINC_URL", LME_ZINC_URL).strip() or LME_ZINC_URL
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 ZincIntelligence/2.6.2", "Accept-Language": "en-GB,en;q=0.9"}, timeout=25)
        r.raise_for_status()
        values, as_of = _extract_lme_public(r.text)
        status = "PUBLIC_WEB_DELAYED" if any(v is not None for v in values.values()) else "MISSING"
        return values, as_of, status, None
    except Exception as exc:
        return {}, None, "ERROR", str(exc)


def _extract_smm_public(html_text: str) -> tuple[dict, str | None]:
    tc = premium = None
    as_of = None
    try:
        tables = pd.read_html(io.StringIO(html_text))
    except Exception:
        tables = []
    for df in tables:
        cols = {_norm(c): c for c in df.columns}
        desc = next((orig for key, orig in cols.items() if "pricedescription" in key or key == "description"), None)
        avg = next((orig for key, orig in cols.items() if key in {"avg", "average"} or "avg" in key), None)
        date = next((orig for key, orig in cols.items() if key == "date" or "date" in key), None)
        if not desc or not avg:
            continue
        for _, row in df.iterrows():
            label = str(row.get(desc, ""))
            if "Zinc Concentrate TC Index" in label:
                tc = safe_float(row.get(avg))
                as_of = str(row.get(date)) if date else as_of
            if "Zinc Ingot premium (USD/tonne)" in label:
                premium = safe_float(row.get(avg))
                as_of = as_of or (str(row.get(date)) if date else None)
    return {"tc_usd_t": tc, "physical_premium_usd_t": premium}, as_of


def fetch_smm_public() -> tuple[dict, str | None, str, str | None]:
    if os.getenv("ENABLE_SMM_PUBLIC_ZINC", "1").strip().lower() in {"0", "false", "no"}:
        return {}, None, "DISABLED", None
    url = os.getenv("SMM_PUBLIC_ZINC_URL", SMM_ZINC_URL).strip() or SMM_ZINC_URL
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 ZincIntelligence/2.6.2"}, timeout=25)
        r.raise_for_status()
        values, as_of = _extract_smm_public(r.text)
        status = "PUBLIC_WEB_WEEKLY_OR_DAILY" if any(v is not None for v in values.values()) else "MISSING"
        return values, as_of, status, None
    except Exception as exc:
        return {}, None, "ERROR", str(exc)


def enrich_market_with_free_sources(market: dict) -> dict:
    market.setdefault("provider_status", {})
    values, as_of, status, error = fetch_lme_public()
    market["provider_status"]["lme_public_summary"] = {"status": status, "as_of": as_of, "error": error}
    _fill(market, values, "lme_public_summary", status, as_of)

    values, as_of, status, error = fetch_smm_public()
    market["provider_status"]["smm_public_zinc"] = {"status": status, "as_of": as_of, "error": error, "redistribution_caution": True}
    _fill(market, values, "smm_public_zinc", status, as_of)

    if market.get("lme_cash") is not None and market.get("lme_3m") is not None:
        market["cash_3m"] = market["lme_cash"] - market["lme_3m"]
    stock = market.get("lme_inventory_t") or market.get("lme_closing_stock_t")
    if stock not in (None, 0) and market.get("cancelled_warrants_t") is not None:
        market["cancelled_ratio_pct"] = market["cancelled_warrants_t"] / stock * 100.0

    market["free_data_limitations"] = [
        "True LME Zinc 3M Daily OHLC is not exposed as a stable unauthenticated free API; free current-year viewing/download may require an LME account.",
        "LME 15m/1H OHLC suitable for automated candlestick backtests is not available as a stable anonymous free feed.",
        "Delivered-in/out warehouse movements are not shown on the public Zinc Summary; the delayed stock-breakdown XLS may require LME site access/download.",
        "SMM TC/premium public values carry redistribution/licensing restrictions and are tagged as a fallback, not official LME data.",
        "Smelter utilization, global balance and China-demand series have no single stable free daily feed of equivalent quality and remain optional/manual enrichments.",
    ]
    return market


def update_close_history(market: dict) -> tuple[pd.DataFrame, str]:
    close = safe_float(market.get("lme_closing_3m"))
    if close is None:
        return load_close_history(), "missing"
    src = market.get("field_sources", {}).get("lme_closing_3m", {})
    ts = pd.to_datetime(src.get("as_of") or market.get("as_of") or iso_now(), errors="coerce", utc=True)
    if pd.isna(ts):
        ts = pd.Timestamp.now(tz="UTC").normalize()
    row = pd.DataFrame([{"timestamp": ts.isoformat(), "Close": close, "source": src.get("provider", "unknown")}])
    if CLOSE_HISTORY_PATH.exists():
        try:
            old = pd.read_csv(CLOSE_HISTORY_PATH)
            all_rows = pd.concat([old, row], ignore_index=True)
        except Exception:
            all_rows = row
    else:
        all_rows = row
    all_rows["timestamp"] = pd.to_datetime(all_rows["timestamp"], errors="coerce", utc=True)
    all_rows["Close"] = pd.to_numeric(all_rows["Close"], errors="coerce")
    all_rows = all_rows.dropna(subset=["timestamp", "Close"]).sort_values("timestamp")
    all_rows["business_date"] = all_rows["timestamp"].dt.date.astype(str)
    all_rows = all_rows.drop_duplicates("business_date", keep="last").drop(columns=["business_date"])
    CLOSE_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_rows.to_csv(CLOSE_HISTORY_PATH, index=False)
    return all_rows.set_index("timestamp")[["Close"]], str(src.get("provider") or "lme_public_summary")


def load_close_history() -> pd.DataFrame:
    if not CLOSE_HISTORY_PATH.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(CLOSE_HISTORY_PATH)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
        return df.dropna(subset=["timestamp", "Close"]).sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")[["Close"]]
    except Exception:
        return pd.DataFrame()
