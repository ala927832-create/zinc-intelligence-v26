from __future__ import annotations

from .utils import age_days, clamp


def assess_market_quality(market: dict, candles_available: bool, macro: dict, event_overlay: dict) -> dict:
    fields = ["lme_cash", "lme_3m", "lme_inventory_t", "cancelled_warrants_t", "tc_usd_t", "physical_premium_usd_t"]
    present = sum(1 for f in fields if market.get(f) is not None)
    base = 35 + (present / len(fields)) * 50
    if candles_available:
        base += 10
    if any(v.get("value") is not None for v in macro.values()):
        base += 5
    base -= event_overlay.get("confidence_penalty", 0)
    confidence = clamp(base, 0, 100)
    return {
        "confidence": confidence,
        "status": "PASS" if confidence >= 75 else "CAUTION" if confidence >= 55 else "BLOCK",
        "missing_fields": [f for f in fields if market.get(f) is None],
        "candle_status": "AVAILABLE" if candles_available else "MISSING"
    }


def procurement_quality(proc_state: dict, settings: dict) -> dict:
    if proc_state.get("current_inventory_t") is None or proc_state.get("demand_60d_t") is None:
        return {"confidence": 0, "status": "INPUT_REQUIRED", "max_age_days": None}
    inv_age = age_days(proc_state.get("inventory_updated_at")) or 0
    dem_age = age_days(proc_state.get("demand_updated_at")) or 0
    max_age = max(inv_age, dem_age)
    dq = settings["data_quality"]
    if max_age < dq["stale_procurement_days_yellow"]:
        conf, status = 95, "CURRENT"
    elif max_age < dq["stale_procurement_days_orange"]:
        conf, status = 80, "CARRY_FORWARD"
    elif max_age < dq["stale_procurement_days_red"]:
        conf, status = 60, "STALE"
    else:
        conf, status = 35, "REVIEW_REQUIRED"
    return {"confidence": conf, "status": status, "max_age_days": max_age}
