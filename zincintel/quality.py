from __future__ import annotations

from .utils import age_days, clamp


def assess_market_quality(market: dict, technical_mode: str, macro: dict, event_overlay: dict) -> dict:
    core_weights = {
        "lme_cash": 14,
        "lme_3m": 14,
        "lme_inventory_t": 14,
        "cancelled_warrants_t": 12,
    }
    secondary_weights = {
        "tc_usd_t": 10,
        "physical_premium_usd_t": 4,
        "global_balance_kt": 3,
        "china_demand_yoy_pct": 3,
    }
    confidence = 18.0
    for field, weight in core_weights.items():
        if market.get(field) is not None:
            confidence += weight
    for field, weight in secondary_weights.items():
        if market.get(field) is not None:
            confidence += weight

    mode = (technical_mode or "MISSING").upper()
    if mode == "FULL_OHLC":
        confidence += 12
    elif mode == "CLOSE_ONLY":
        confidence += 7

    if any(v.get("value") is not None for v in macro.values()):
        confidence += 5

    source_statuses = [str(v.get("status", "")).upper() for v in market.get("field_sources", {}).values()]
    # Public/day-delayed mirrors are usable for research/procurement context but are not
    # treated as equivalent to licensed official feeds.
    if source_statuses:
        if all(any(tag in s for tag in ["PUBLIC", "MIRROR", "REFERENCE", "MANUAL"]) for s in source_statuses):
            confidence -= 5
        if any("STALE" in s for s in source_statuses):
            confidence -= 8

    confidence -= event_overlay.get("confidence_penalty", 0)
    confidence = clamp(confidence, 0, 100)
    missing_core = [f for f in core_weights if market.get(f) is None]
    missing_secondary = [f for f in secondary_weights if market.get(f) is None]
    status = "PASS" if confidence >= 75 and len(missing_core) <= 1 else "CAUTION" if confidence >= 55 else "BLOCK"
    return {
        "confidence": confidence,
        "status": status,
        "missing_fields": missing_core + missing_secondary,
        "missing_core": missing_core,
        "missing_secondary": missing_secondary,
        "candle_status": "AVAILABLE" if mode == "FULL_OHLC" else "CLOSE_ONLY" if mode == "CLOSE_ONLY" else "MISSING",
        "technical_mode": mode,
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
