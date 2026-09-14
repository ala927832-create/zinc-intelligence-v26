from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .utils import DATA_DIR, read_json

FIELD_POLICY = {
    "lme_cash": {"expected": "T+1 business day", "max_age_days": 4, "importance": "CORE"},
    "lme_3m": {"expected": "T+1 business day", "max_age_days": 4, "importance": "CORE"},
    "lme_inventory_t": {"expected": "T+1/T+2 business day", "max_age_days": 5, "importance": "CORE"},
    "live_warrants_t": {"expected": "T+1/T+2 business day", "max_age_days": 5, "importance": "CORE"},
    "cancelled_warrants_t": {"expected": "T+1/T+2 business day", "max_age_days": 5, "importance": "CORE"},
    "tc_usd_t": {"expected": "Weekly or better", "max_age_days": 14, "importance": "SECONDARY"},
    "physical_premium_usd_t": {"expected": "Weekly or better", "max_age_days": 14, "importance": "SECONDARY"},
}


def _age_days(value: str | None) -> float | None:
    if not value:
        return None
    try:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        now = pd.Timestamp.now(tz="UTC")
        return max(0.0, (now - ts).total_seconds() / 86400.0)
    except Exception:
        return None


def source_grade(provider: str | None, status: str | None) -> str:
    p = (provider or "").lower()
    s = (status or "").upper()
    if "lme_xml" in p or "OFFICIAL_NEXT_DAY" in s:
        return "A_OFFICIAL_LICENSED"
    if "lme_public" in p:
        return "A_OFFICIAL_PUBLIC"
    if "warehouse" in p and "OFFICIAL" in s:
        return "A_OFFICIAL_REPORT"
    if "manual" in p:
        return "B_MANUAL_VERIFIED"
    if "grillo" in p or "westmetall" in p:
        return "B_PUBLIC_REFERENCE"
    if "smm" in p:
        return "B_MARKET_SOURCE_RESTRICTED"
    if "carry_forward" in p or "CARRY_FORWARD" in s:
        return "C_CARRY_FORWARD"
    return "C_OTHER"


def _previous_market() -> dict:
    snap = read_json(DATA_DIR / "latest_snapshot.json", {})
    return snap.get("market", {}) if isinstance(snap, dict) else {}


def apply_last_known_good(market: dict, previous_market: dict | None = None) -> dict:
    """Fill a temporary provider outage with a prior valid value, never with invented data.

    The original source date is retained and the field is explicitly tagged CARRY_FORWARD.
    Values older than the field's max-age policy are not carried forward.
    """
    previous = previous_market if previous_market is not None else _previous_market()
    if not previous:
        return market
    out = deepcopy(market)
    out.setdefault("field_sources", {})
    out.setdefault("provider_status", {})

    for field, policy in FIELD_POLICY.items():
        if out.get(field) is not None:
            continue
        old_value = previous.get(field)
        old_src = previous.get("field_sources", {}).get(field, {})
        # Older snapshots may have used Grillo's page-modified date as the
        # price date. Never promote those unverified prices via carry-forward.
        if field in {"lme_cash", "lme_3m"} and "grillo" in str(old_src.get("provider", "")).lower():
            continue
        old_as_of = old_src.get("as_of") or previous.get("as_of")
        age = _age_days(old_as_of)
        if old_value is None or age is None or age > float(policy["max_age_days"]):
            continue
        out[field] = old_value
        out["field_sources"][field] = {
            "provider": "carry_forward_last_known_good",
            "status": "CARRY_FORWARD",
            "as_of": old_as_of,
            "original_provider": old_src.get("provider"),
            "original_status": old_src.get("status"),
        }

    if out.get("lme_cash") is not None and out.get("lme_3m") is not None:
        out["cash_3m"] = float(out["lme_cash"]) - float(out["lme_3m"])
    stock = out.get("lme_inventory_t") or out.get("lme_closing_stock_t")
    if stock not in (None, 0) and out.get("cancelled_warrants_t") is not None:
        out["cancelled_ratio_pct"] = float(out["cancelled_warrants_t"]) / float(stock) * 100.0
    return out


def annotate_data_health(market: dict) -> dict:
    health: dict[str, dict[str, Any]] = {}
    for field, policy in FIELD_POLICY.items():
        src = market.get("field_sources", {}).get(field, {})
        age = _age_days(src.get("as_of"))
        if market.get(field) is None:
            freshness = "MISSING"
        elif age is None:
            freshness = "UNKNOWN_DATE"
        elif age <= float(policy["max_age_days"]):
            freshness = "CURRENT_ENOUGH"
        else:
            freshness = "STALE"
        health[field] = {
            "value_present": market.get(field) is not None,
            "source": src.get("provider"),
            "source_grade": source_grade(src.get("provider"), src.get("status")),
            "source_status": src.get("status"),
            "as_of": src.get("as_of"),
            "age_days": round(age, 2) if age is not None else None,
            "expected_update": policy["expected"],
            "max_age_days": policy["max_age_days"],
            "importance": policy["importance"],
            "freshness": freshness,
        }
    market["data_health"] = health
    return market


def core_data_gate(market: dict) -> dict:
    health = market.get("data_health", {})
    core = [k for k, v in FIELD_POLICY.items() if v["importance"] == "CORE"]
    usable = [k for k in core if health.get(k, {}).get("freshness") == "CURRENT_ENOUGH"]
    stale = [k for k in core if health.get(k, {}).get("freshness") == "STALE"]
    missing = [k for k in core if health.get(k, {}).get("freshness") in {"MISSING", "UNKNOWN_DATE"}]
    if len(usable) >= 4:
        status = "HEALTHY"
    elif len(usable) >= 3:
        status = "DEGRADED"
    else:
        status = "BLOCK_DEPLOY"
    return {"status": status, "usable_core": usable, "stale_core": stale, "missing_core": missing}
