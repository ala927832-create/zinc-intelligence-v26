from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .utils import DATA_DIR, read_json, safe_float

SMM_IMPORT_WEEKLY_URL = "https://www-old.metal.com/Zinc/202506030011"
SMM_DOMESTIC_WEEKLY_URL = "https://www-old.metal.com/Zinc/202004070002"
SMM_DOMESTIC_MONTHLY_URL = "https://www-old.metal.com/Zinc/201312030008"
BENCHMARK_FILE = DATA_DIR / "tc_benchmark.json"


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36 ZincIntelligence/2.7",
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
        m = re.search(r"(-?[\d,.]+)\s+(USD/dmt|USD/tonne|yuan/tonne)", text, flags=re.I)
        if m:
            avg = safe_float(m.group(1).replace(",", ""))
            unit = m.group(2)

    unit_match = re.search(r"Price,\s*(USD/dmt|USD/tonne|yuan/tonne)", text, flags=re.I)
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
    imported = _fetch_smm(SMM_IMPORT_WEEKLY_URL, "Weekly", "China import zinc concentrate TC")
    domestic_weekly = _fetch_smm(SMM_DOMESTIC_WEEKLY_URL, "Weekly", "China domestic zinc concentrate TC (weekly)")
    domestic_monthly = _fetch_smm(SMM_DOMESTIC_MONTHLY_URL, "Monthly", "China domestic zinc concentrate TC (monthly)")
    benchmark = _benchmark()

    # Keep units/bases separate. Do not convert or combine RMB/metal-tonne and USD/dmt implicitly.
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
            "SMM public values may be delayed weekly/monthly; accuracy and source date take priority over recency.",
            "Annual benchmark is a separately verified industry reference, not a spot TC.",
        ],
    }
