from __future__ import annotations

import re
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .utils import DATA_DIR, read_json, safe_float

SMM_ZINC_MAIN_URL = "https://www-old.metal.com/Zinc"
SMM_IMPORT_WEEKLY_URL = "https://www-old.metal.com/Zinc/202506030011"
SMM_DOMESTIC_WEEKLY_URL = "https://www-old.metal.com/Zinc/202004070002"
SMM_DOMESTIC_MONTHLY_URL = "https://www-old.metal.com/Zinc/201312030008"
BENCHMARK_FILE = DATA_DIR / "tc_benchmark.json"


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36 ZincIntelligence/2.7.1",
        "Accept-Language": "en-GB,en;q=0.9",
    }


def _to_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        ts = pd.to_datetime(value, errors="raise", utc=True)
        return ts.date().isoformat()
    except Exception:
        return value


def _age_days(value: str | None) -> float | None:
    if not value:
        return None
    try:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return max(0.0, (pd.Timestamp.now(tz="UTC") - ts).total_seconds() / 86400.0)
    except Exception:
        return None


def _unit_from_text(text: str) -> str | None:
    m = re.search(r"\((USD/dmt|USD/tonne|yuan/tonne|yuan/mt(?:\s*\(metal content\))?)\)", text, flags=re.I)
    if m:
        return m.group(1)
    m = re.search(r"\b(USD/dmt|USD/tonne|yuan/tonne|yuan/mt(?:\s*\(metal content\))?)\b", text, flags=re.I)
    return m.group(1) if m else None


def _parse_smm_product(html_text: str) -> dict[str, Any]:
    """Parse one SMM public zinc price page without inventing missing fields."""
    text = BeautifulSoup(html_text, "html.parser").get_text(" ", strip=True)
    avg = None
    unit = None
    as_of = None
    update_time = None

    m = re.search(r"Avg\.\s*:\s*(-?[\d,.]+)", text, flags=re.I)
    if m:
        avg = safe_float(m.group(1).replace(",", ""))
    if avg is None:
        m = re.search(r"(-?[\d,.]+)\s+(USD/dmt|USD/tonne|yuan/tonne|yuan/mt(?:\s*\(metal content\))?)", text, flags=re.I)
        if m:
            avg = safe_float(m.group(1).replace(",", ""))
            unit = m.group(2)

    unit_match = re.search(r"Price,\s*(USD/dmt|USD/tonne|yuan/tonne|yuan/mt(?:\s*\(metal content\))?)", text, flags=re.I)
    if unit_match:
        unit = unit_match.group(1)

    date_match = re.search(r"\b([A-Z][a-z]{2}\s+\d{1,2},\s+20\d{2})\b", text)
    if date_match:
        as_of = _to_iso(date_match.group(1))

    update_match = re.search(r"Update Time:\s*([^\n]+?GMT\+8)", text, flags=re.I)
    if update_match:
        update_time = update_match.group(1).strip()

    return {"value": avg, "unit": unit, "as_of": as_of, "update_time": update_time}


def _fetch_smm(url: str, expected_update: str, label: str) -> dict[str, Any]:
    try:
        r = requests.get(url, headers=_headers(), timeout=25)
        r.raise_for_status()
        parsed = _parse_smm_product(r.text)
        status = "AVAILABLE" if parsed.get("value") is not None else "MISSING"
        return {
            "label": label,
            **parsed,
            "status": status,
            "source": "SMM_PUBLIC",
            "source_grade": "B_MARKET_SOURCE",
            "expected_update": expected_update,
            "age_days": round(_age_days(parsed.get("as_of")), 2) if _age_days(parsed.get("as_of")) is not None else None,
            "url": url,
            "error": None,
        }
    except Exception as exc:
        return {
            "label": label,
            "value": None,
            "unit": None,
            "as_of": None,
            "status": "ERROR",
            "source": "SMM_PUBLIC",
            "source_grade": "B_MARKET_SOURCE",
            "expected_update": expected_update,
            "age_days": None,
            "url": url,
            "error": str(exc),
        }


def _parse_smm_zinc_table(html_text: str) -> dict[str, dict[str, Any]]:
    """Parse the SMM Zinc landing-page TC table while retaining the published unit."""
    targets = {
        "import_weekly": "SMM Zinc Concentrate TC Index (Weekly)",
        "domestic_weekly": "Domestic Zinc Concentrate TC (Weekly)",
        "domestic_monthly": "Domestic Zinc Concentrate TC (Monthly)",
    }
    out: dict[str, dict[str, Any]] = {}
    soup = BeautifulSoup(html_text, "html.parser")
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) < 3:
            continue
        desc = cells[0]
        key = next((k for k, needle in targets.items() if needle.lower() in desc.lower()), None)
        if key is None:
            continue
        unit = _unit_from_text(desc)
        # SMM layout is Description | Price Range | Avg. | Change | Date.
        avg = safe_float(str(cells[2]).replace(",", "")) if len(cells) >= 3 else None
        date_text = next((c for c in reversed(cells) if re.search(r"[A-Z][a-z]{2}\s+\d{1,2},\s+20\d{2}", c)), None)
        out[key] = {
            "value": avg,
            "unit": unit,
            "as_of": _to_iso(date_text),
            "update_time": None,
        }
    return out


def _fetch_smm_zinc_table() -> tuple[dict[str, dict[str, Any]], str | None]:
    try:
        r = requests.get(SMM_ZINC_MAIN_URL, headers=_headers(), timeout=25)
        r.raise_for_status()
        return _parse_smm_zinc_table(r.text), None
    except Exception as exc:
        return {}, str(exc)


def _series_from_table(parsed: dict[str, dict[str, Any]], key: str, expected_update: str, label: str, table_error: str | None) -> dict[str, Any]:
    item = parsed.get(key, {})
    value = item.get("value")
    as_of = item.get("as_of")
    return {
        "label": label,
        **item,
        "status": "AVAILABLE" if value is not None else ("ERROR" if table_error else "MISSING"),
        "source": "SMM_ZINC_TABLE",
        "source_grade": "B_MARKET_SOURCE",
        "expected_update": expected_update,
        "age_days": round(_age_days(as_of), 2) if _age_days(as_of) is not None else None,
        "url": SMM_ZINC_MAIN_URL,
        "error": table_error if value is None else None,
    }


def _prefer(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    return primary if primary.get("value") is not None else fallback


def _benchmark() -> dict[str, Any]:
    raw = read_json(BENCHMARK_FILE, {})
    as_of = raw.get("as_of")
    return {
        "label": "Annual benchmark TC",
        "value": safe_float(raw.get("value_usd_dmt")),
        "unit": "USD/dmt",
        "as_of": as_of,
        "status": "VERIFIED_REFERENCE" if raw.get("value_usd_dmt") is not None else "MISSING",
        "source": raw.get("source", "MANUAL_VERIFIED_REFERENCE"),
        "source_grade": "B_VERIFIED_BENCHMARK",
        "expected_update": "Annual",
        "age_days": round(_age_days(as_of), 2) if _age_days(as_of) is not None else None,
        "url": raw.get("source_url"),
        "notes": raw.get("notes"),
    }


def fetch_china_tc() -> dict[str, Any]:
    """Return separate China zinc concentrate TC series with explicit basis/freshness."""
    table, table_error = _fetch_smm_zinc_table()

    # The dedicated import index page can update later than the landing table, so retain it as primary.
    imported = _prefer(
        _fetch_smm(SMM_IMPORT_WEEKLY_URL, "Weekly", "China import zinc concentrate TC"),
        _series_from_table(table, "import_weekly", "Weekly", "China import zinc concentrate TC", table_error),
    )
    # Domestic legacy product URLs have become unreliable; the current Zinc landing table is primary.
    domestic_weekly = _prefer(
        _series_from_table(table, "domestic_weekly", "Weekly", "China domestic zinc concentrate TC (weekly)", table_error),
        _fetch_smm(SMM_DOMESTIC_WEEKLY_URL, "Weekly", "China domestic zinc concentrate TC (weekly)"),
    )
    domestic_monthly = _prefer(
        _series_from_table(table, "domestic_monthly", "Monthly", "China domestic zinc concentrate TC (monthly)", table_error),
        _fetch_smm(SMM_DOMESTIC_MONTHLY_URL, "Monthly", "China domestic zinc concentrate TC (monthly)"),
    )
    benchmark = _benchmark()

    return {
        "import_weekly": imported,
        "domestic_weekly": domestic_weekly,
        "domestic_monthly": domestic_monthly,
        "annual_benchmark": benchmark,
        "primary_import_tc_usd_dmt": imported.get("value"),
        "primary_domestic_tc": domestic_weekly.get("value") if domestic_weekly.get("value") is not None else domestic_monthly.get("value"),
        "primary_domestic_unit": domestic_weekly.get("unit") or domestic_monthly.get("unit"),
        "notes": [
            "Import and domestic TC are separate market series and are not arithmetically blended.",
            "Domestic TC on the English SMM public table may be displayed as a USD/tonne conversion; the source unit is retained exactly as published.",
            "China-native market commentary commonly quotes domestic TC in yuan/mt Zn metal content; do not silently convert between bases.",
            "SMM public values may be delayed weekly/monthly; accuracy and source date take priority over recency.",
            "Annual benchmark is a separately verified industry reference, not a spot TC.",
        ],
    }
