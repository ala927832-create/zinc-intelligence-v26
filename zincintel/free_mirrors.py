from __future__ import annotations

import io
import os
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .utils import safe_float

GRILLO_ZINC_URL = "https://www.grillohandel.de/en/handelsprogramm/course-detail/zinc/"
WESTMETALL_ZINC_URL = "https://www.westmetall.com/en/markdaten.php?action=table&field=LME_Zn_cash&year={year}"
SMM_TC_URL = "https://www-old.metal.com/Zinc/202506030011"
SMM_PREMIUM_URL = "https://www-old.metal.com/Zinc/201906260005"


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36 ZincIntelligence/2.6.3",
        "Accept-Language": "en-GB,en;q=0.9",
    }


def _eu_num(value: Any) -> float | None:
    """Parse both EN and EU formats: 3,685.50 / 3.685,50 / 105,800 / 105.800."""
    if value is None:
        return None
    s = str(value).strip().replace("\xa0", "").replace(" ", "")
    s = re.sub(r"[^0-9,.-]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    return safe_float(s)


def _norm(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _date_iso(text: str | None) -> str | None:
    if not text:
        return None
    raw = str(text).strip()
    for dayfirst in (True, False):
        try:
            ts = pd.to_datetime(raw, errors="raise", dayfirst=dayfirst, utc=True)
            return ts.date().isoformat()
        except Exception:
            pass
    return raw


def _age_days(as_of: str | None) -> float | None:
    if not as_of:
        return None
    try:
        ts = pd.Timestamp(as_of)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return (pd.Timestamp.now(tz="UTC") - ts).total_seconds() / 86400.0
    except Exception:
        return None


def _fill(market: dict, values: dict, provider: str, status: str, as_of: str | None) -> None:
    market.setdefault("field_sources", {})
    for key, value in values.items():
        if value is not None and market.get(key) is None:
            market[key] = value
            market["field_sources"][key] = {"provider": provider, "status": status, "as_of": as_of}


def parse_grillo(html_text: str) -> tuple[dict, str | None]:
    text = BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)
    values: dict[str, float | None] = {
        "lme_cash": None, "lme_3m": None,
        "lme_cash_bid": None, "lme_cash_offer": None,
        "lme_3m_bid": None, "lme_3m_offer": None,
        "lme_settlement": None, "lme_inventory_t": None,
        "live_warrants_t": None, "cancelled_warrants_t": None,
    }

    cash = re.search(
        r"Cash\s+desk.*?Money:\s*([\d.,]+)\s*\$/t.*?Letter:\s*([\d.,]+)\s*\$/t",
        text, flags=re.I | re.S,
    )
    m3 = re.search(
        r"3[- ]?months?.*?Money:\s*([\d.,]+)\s*\$/t.*?Letter:\s*([\d.,]+)\s*\$/t",
        text, flags=re.I | re.S,
    )
    if cash:
        values["lme_cash_bid"] = _eu_num(cash.group(1))
        values["lme_cash_offer"] = _eu_num(cash.group(2))
        values["lme_cash"] = values["lme_cash_offer"]
        values["lme_settlement"] = values["lme_cash_offer"]
    if m3:
        values["lme_3m_bid"] = _eu_num(m3.group(1))
        values["lme_3m_offer"] = _eu_num(m3.group(2))
        values["lme_3m"] = values["lme_3m_offer"]

    stock = re.search(
        r"LME[- ]?Zinc\s+Stock.*?\((\d{1,2}\.\d{1,2}\.\d{4})\).*?Opening\s+stock\s+([\d.,]+).*?Live\s+warrants\s+([\d.,]+).*?Cancelled\s+warrants\s+([\d.,]+)",
        text, flags=re.I | re.S,
    )
    stock_date = None
    if stock:
        stock_date = _date_iso(stock.group(1))
        values["lme_inventory_t"] = _eu_num(stock.group(2))
        values["live_warrants_t"] = _eu_num(stock.group(3))
        values["cancelled_warrants_t"] = _eu_num(stock.group(4))

    # The page's Last modified date is not the market date. The stock section
    # carries its own report date; prices need separate row-level dating.
    return values, stock_date


def fetch_grillo() -> tuple[dict, str | None, str, str | None]:
    if os.getenv("ENABLE_GRILLO_FALLBACK", "1").strip().lower() in {"0", "false", "no"}:
        return {}, None, "DISABLED", None
    try:
        r = requests.get(GRILLO_ZINC_URL, headers=_headers(), timeout=25)
        r.raise_for_status()
        values, as_of = parse_grillo(r.text)
        # Until price-table dates are parsed individually, use Grillo only for
        # dated warehouse fields. Westmetall/official feeds can fill prices.
        values = {key: value for key, value in values.items()
                  if key in {"lme_inventory_t", "live_warrants_t", "cancelled_warrants_t"}}
        if as_of is None:
            return {}, None, "UNKNOWN_MARKET_DATE", None
        age = _age_days(as_of)
        status = "PUBLIC_MIRROR_DAY_DELAYED" if any(v is not None for v in values.values()) else "MISSING"
        if age is not None and age > 10:
            status = "STALE_PUBLIC_MIRROR"
        return values, as_of, status, None
    except Exception as exc:
        return {}, None, "ERROR", str(exc)


def parse_westmetall(html_text: str) -> tuple[dict, str | None, pd.DataFrame]:
    """Parse Westmetall without letting pandas coerce stock thousands separators.

    Westmetall may render English numbers (115,675) or German numbers (115.675).
    Reading raw cell text preserves the distinction before normalization.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    records: list[dict[str, Any]] = []

    for table in soup.find_all("table"):
        indices: dict[str, int] | None = None
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if not cells:
                continue
            norms = [_norm(c) for c in cells]
            if any(x in {"date", "datum"} for x in norms) and any("cashsettlement" in x for x in norms):
                def idx(predicate):
                    return next((i for i, x in enumerate(norms) if predicate(x)), None)
                date_i = idx(lambda x: x in {"date", "datum"})
                cash_i = idx(lambda x: "cashsettlement" in x)
                m3_i = idx(lambda x: "3month" in x or "3months" in x or "3monate" in x)
                stock_i = idx(lambda x: "zincstock" in x or "zinkbest" in x)
                if date_i is not None and cash_i is not None and m3_i is not None:
                    indices = {"date": date_i, "cash": cash_i, "m3": m3_i}
                    if stock_i is not None:
                        indices["stock"] = stock_i
                continue
            if not indices:
                continue
            if max(indices.values()) >= len(cells):
                continue
            ts = pd.to_datetime(cells[indices["date"]], errors="coerce", dayfirst=True, utc=True)
            cash = _eu_num(cells[indices["cash"]])
            m3 = _eu_num(cells[indices["m3"]])
            stock = _eu_num(cells[indices["stock"]]) if "stock" in indices else None
            if pd.isna(ts) or cash is None or m3 is None:
                continue
            records.append({"timestamp": ts, "Cash": cash, "Close": m3, "Stock": stock})

    # Fallback to pandas for unusual but still tabular HTML. This is secondary only.
    if not records:
        try:
            tables = pd.read_html(io.StringIO(html_text))
        except Exception:
            tables = []
        for df in tables:
            if df.empty:
                continue
            norm = {_norm(c): c for c in df.columns}
            date_col = next((c for k, c in norm.items() if k in {"date", "datum"}), None)
            cash_col = next((c for k, c in norm.items() if "cashsettlement" in k), None)
            m3_col = next((c for k, c in norm.items() if "3month" in k or "3months" in k or "3monate" in k), None)
            stock_col = next((c for k, c in norm.items() if "zincstock" in k or "zinkbest" in k), None)
            if not (date_col and cash_col and m3_col):
                continue
            for _, row in df.iterrows():
                ts = pd.to_datetime(row.get(date_col), errors="coerce", dayfirst=True, utc=True)
                cash = _eu_num(row.get(cash_col))
                m3 = _eu_num(row.get(m3_col))
                stock = _eu_num(row.get(stock_col)) if stock_col else None
                if pd.isna(ts) or cash is None or m3 is None:
                    continue
                records.append({"timestamp": ts, "Cash": cash, "Close": m3, "Stock": stock})

    if not records:
        return {}, None, pd.DataFrame()

    work = pd.DataFrame(records).sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    latest = work.iloc[-1]
    values = {
        "lme_cash": float(latest["Cash"]),
        "lme_cash_offer": float(latest["Cash"]),
        "lme_settlement": float(latest["Cash"]),
        "lme_3m": float(latest["Close"]),
        "lme_3m_offer": float(latest["Close"]),
        "lme_inventory_t": float(latest["Stock"]) if pd.notna(latest.get("Stock")) else None,
    }
    hist = work[["timestamp", "Close"]].set_index("timestamp")
    return values, latest["timestamp"].date().isoformat(), hist


def fetch_westmetall() -> tuple[dict, str | None, str, str | None, pd.DataFrame]:
    if os.getenv("ENABLE_WESTMETALL_FALLBACK", "1").strip().lower() in {"0", "false", "no"}:
        return {}, None, "DISABLED", None, pd.DataFrame()
    current_year = datetime.now(timezone.utc).year
    try:
        start_year = max(2008, min(current_year, int(os.getenv("WESTMETALL_HISTORY_START_YEAR", "2025"))))
    except ValueError:
        start_year = 2025
    histories, candidates, errors = [], [], []
    for year in range(start_year, current_year + 1):
        url = WESTMETALL_ZINC_URL.format(year=year)
        try:
            r = requests.get(url, headers=_headers(), timeout=25)
            r.raise_for_status()
            values, as_of, hist = parse_westmetall(r.text)
            if not hist.empty:
                histories.append(hist)
            if values and as_of:
                candidates.append((as_of, values))
            elif hist.empty:
                errors.append(f"{year}: no parseable rows")
        except Exception as exc:
            errors.append(f"{year}: {exc}")
    if not histories or not candidates:
        return {}, None, "ERROR" if errors else "MISSING", "; ".join(errors) or None, pd.DataFrame()
    hist = pd.concat(histories).sort_index()
    hist = hist[~hist.index.duplicated(keep="last")]
    as_of, values = max(candidates, key=lambda item: item[0])
    age = _age_days(as_of)
    status = "PUBLIC_REFERENCE_DAY_DELAYED"
    if age is not None and age > 10:
        status = "STALE_PUBLIC_REFERENCE"
    return values, as_of, status, "; ".join(errors) or None, hist


def _parse_smm_single(html_text: str) -> tuple[float | None, str | None]:
    text = BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)
    avg = None
    m = re.search(r"Avg\.\s*:\s*(-?\d+(?:\.\d+)?)", text, flags=re.I)
    if m:
        avg = safe_float(m.group(1))
    if avg is None:
        m = re.search(r"(-?\d+(?:\.\d+)?)\s+USD/(?:dmt|tonne)", text, flags=re.I)
        if m:
            avg = safe_float(m.group(1))
    dm = re.search(r"\b([A-Z][a-z]{2}\s+\d{1,2},\s+20\d{2})\b", text)
    return avg, _date_iso(dm.group(1)) if dm else None


def fetch_smm_direct(url: str, label: str) -> tuple[float | None, str | None, str, str | None]:
    try:
        r = requests.get(url, headers=_headers(), timeout=25)
        r.raise_for_status()
        value, as_of = _parse_smm_single(r.text)
        return value, as_of, "PUBLIC_WEB_DELAYED" if value is not None else "MISSING", None
    except Exception as exc:
        return None, None, "ERROR", f"{label}: {exc}"


def enrich_market_with_free_mirrors(market: dict) -> tuple[dict, pd.DataFrame, str]:
    market.setdefault("provider_status", {})
    mirror_history = pd.DataFrame()
    history_source = "missing"

    g_values, g_asof, g_status, g_error = fetch_grillo()
    market["provider_status"]["grillo_lme_zinc"] = {"status": g_status, "as_of": g_asof, "error": g_error}
    if not str(g_status).startswith("STALE"):
        _fill(market, g_values, "grillo_lme_zinc", g_status, g_asof)

    w_values, w_asof, w_status, w_error, w_hist = fetch_westmetall()
    market["provider_status"]["westmetall_lme_zinc"] = {"status": w_status, "as_of": w_asof, "error": w_error}
    if not str(w_status).startswith("STALE"):
        _fill(market, w_values, "westmetall_lme_zinc", w_status, w_asof)
    if not w_hist.empty:
        mirror_history = w_hist
        history_source = "westmetall_lme_3m_reference"

    if market.get("tc_usd_t") is None:
        tc, as_of, status, error = fetch_smm_direct(SMM_TC_URL, "SMM TC")
        market["provider_status"]["smm_tc_direct"] = {"status": status, "as_of": as_of, "error": error, "redistribution_caution": True}
        if tc is not None:
            _fill(market, {"tc_usd_t": tc, "tc_smelter_usd_t": tc}, "smm_tc_direct", status, as_of)

    if market.get("physical_premium_usd_t") is None:
        prem, as_of, status, error = fetch_smm_direct(SMM_PREMIUM_URL, "SMM premium")
        market["provider_status"]["smm_premium_direct"] = {"status": status, "as_of": as_of, "error": error, "redistribution_caution": True}
        if prem is not None:
            _fill(market, {"physical_premium_usd_t": prem}, "smm_premium_direct", status, as_of)

    if market.get("lme_cash") is not None and market.get("lme_3m") is not None:
        market["cash_3m"] = float(market["lme_cash"]) - float(market["lme_3m"])
    stock = market.get("lme_inventory_t") or market.get("lme_closing_stock_t")
    if stock not in (None, 0) and market.get("cancelled_warrants_t") is not None:
        market["cancelled_ratio_pct"] = float(market["cancelled_warrants_t"]) / float(stock) * 100.0

    return market, mirror_history, history_source
