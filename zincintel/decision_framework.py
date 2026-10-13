"""Auditable six-gate research plans with an explicit execution boundary."""

from __future__ import annotations

import math
from statistics import median


def _num(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _rr(entry, stop, target):
    values = [_num(x) for x in (entry, stop, target)]
    if any(x is None for x in values):
        return None
    entry, stop, target = values
    risk = abs(entry - stop)
    return round(abs(target - entry) / risk, 2) if risk else None


def _decision_audit(plan: dict) -> dict:
    """Answer the eight questions without crossing the live-execution boundary."""
    daily = plan.get("daily_plan", {})
    entry = _num(daily.get("maximum_entry") or daily.get("trigger_price"))
    stop = _num(daily.get("hard_stop"))
    loss = round(abs(entry - stop), 4) if entry is not None and stop is not None else None
    reasons = plan.get("no_trade_reasons", [])
    return {
        "1_market_direction": plan.get("direction", "UNDETERMINED"),
        "2_evidence_consistency": plan.get("evidence_alignment", "INSUFFICIENT"),
        "3_risk_location": daily.get("setup_zone") or "NO_VALIDATED_SETUP_ZONE",
        "4_entry_permission": (
            {"trigger": daily.get("trigger_price"), "maximum_entry": daily.get("maximum_entry"),
             "condition": daily.get("conditional_order"), "execution_check": plan.get("execution_gate")}
            if daily else "ENTRY_NOT_PERMITTED"
        ),
        "5_loss_if_wrong": (
            {"price_units_per_contract_unit": loss, "note": "Account loss requires live fill, multiplier, fees and quantity."}
            if loss is not None else "NOT_COMPUTABLE"
        ),
        "6_exit_plan": ({"t1": daily.get("t1"), "t2": daily.get("t2"),
                         "close_invalidation": daily.get("close_invalidation")} if daily else "NOT_AVAILABLE"),
        "7_planned_rr": ({"t1": daily.get("planned_rr_t1"), "t2": daily.get("planned_rr_t2")}
                         if daily else "NOT_AVAILABLE"),
        "8_no_trade_reason": reasons or ["No blocking reason recorded."],
    }


def _finalize(plan: dict) -> dict:
    plan["decision_audit"] = _decision_audit(plan)
    return plan


def _blocked(name: str, reason: str, data_status: str = "MISSING") -> dict:
    return _finalize({
        "market": name, "decision": "NO_TRADE", "direction": "UNDETERMINED",
        "evidence_alignment": "INSUFFICIENT", "data_gate": data_status,
        "strategy_gate": "BLOCKED", "trigger_gate": "BLOCKED", "execution_gate": "BLOCKED",
        "daily_plan": {}, "execution_check": {"status": "NOT_AVAILABLE"},
        "no_trade_reasons": [reason],
        "evidence": [],
    })


def build_ohlc_plan(series: dict) -> dict:
    """Create candidate levels; never call them executable without live quote checks."""
    deviation = _num(series.get("cross_source_deviation_pct"))
    if deviation is not None and abs(deviation) > 0.5:
        return _blocked(series.get("name", "Market"),
                        f"Cross-source close deviation {deviation:.2f}% exceeds the 0.50% tolerance.", "DATA_CONFLICT")
    if series.get("status") != "AVAILABLE" or len(series.get("chart_points", [])) < 60:
        return _blocked(series.get("name", "Market"), "At least 60 validated daily OHLC sessions are required.")
    points = series["chart_points"]
    latest = series.get("latest_session") or points[-1]
    close, ema, sma, atr, rsi = (_num(latest.get(k)) for k in ("close", "ema20", "sma60", "atr14", "rsi14"))
    if None in (close, ema, sma, atr, rsi) or atr <= 0:
        return _blocked(series.get("name", "Market"), "Required EMA20/SMA60/ATR14/RSI14 values are incomplete.", "PARTIAL")
    recent = points[-20:]
    support = min(_num(p.get("low")) for p in recent if _num(p.get("low")) is not None)
    resistance = max(_num(p.get("high")) for p in recent if _num(p.get("high")) is not None)
    if close > ema > sma:
        direction, setup = "BULL", "BREAKOUT_OR_PULLBACK_LONG"
        trigger = resistance + 0.05 * atr
        stop = min(ema, support) - 0.15 * atr
        maximum = trigger + 0.20 * atr
        t1, t2 = trigger + 2 * (trigger - stop), trigger + 3 * (trigger - stop)
        invalidation = ema
    elif close < ema < sma:
        direction, setup = "BEAR", "BREAKDOWN_OR_RALLY_SHORT"
        trigger = support - 0.05 * atr
        stop = max(ema, resistance) + 0.15 * atr
        maximum = trigger - 0.20 * atr
        t1, t2 = trigger - 2 * (stop - trigger), trigger - 3 * (stop - trigger)
        invalidation = ema
    else:
        return _finalize({
            **_blocked(series.get("name", "Market"), "Close, EMA20 and SMA60 are not directionally aligned.", "PASS"),
            "direction": "NEUTRAL", "evidence_alignment": "MIXED", "regime_gate": "RANGE_OR_TRANSITION",
            "reference": {"close": close, "ema20": ema, "sma60": sma, "rsi14": rsi, "atr14": atr},
            "evidence": [
                {"factor":"Trend structure", "status":"MIXED", "value":f"Close {close}; EMA20 {ema}; SMA60 {sma}"},
                {"factor":"Momentum", "status":"AVAILABLE", "value":f"RSI14 {rsi}"},
                {"factor":"Observed volatility", "status":"AVAILABLE", "value":f"ATR14 {atr}"},
            ],
        })
    plan = {
        "setup_zone": [round(min(ema, close), 4), round(max(ema, close), 4)],
        "trigger_price": round(trigger, 4), "maximum_entry": round(maximum, 4),
        "hard_stop": round(stop, 4), "close_invalidation": round(invalidation, 4),
        "t1": round(t1, 4), "t2": round(t2, 4), "planned_rr_t1": _rr(trigger, stop, t1),
        "planned_rr_t2": _rr(trigger, stop, t2), "conditional_order": "STOP_LIMIT_AFTER_DAILY_CONFIRMATION",
    }
    return _finalize({
        "market": series.get("name"), "symbol": series.get("symbol"), "as_of": series.get("as_of"),
        "decision": "WAIT_FOR_TRIGGER", "direction": direction, "evidence_alignment": "ALIGNED",
        "data_gate": "PASS", "regime_gate": direction, "strategy_gate": setup,
        "trigger_gate": "NOT_TRIGGERED", "execution_gate": "PENDING_LIVE_QUOTE",
        "daily_plan": plan,
        "execution_check": {"status": "REQUIRED_AT_ORDER_TIME", "required": [
            "bid", "ask", "spread", "actual_fill", "slippage", "actual_rr", "contract_quantity"
        ]},
        "reference": {"close": close, "ema20": ema, "sma60": sma, "rsi14": rsi, "atr14": atr},
        "no_trade_reasons": ["Trigger has not been confirmed.", "Live bid/ask and acceptable spread are unavailable."],
        "evidence": [
            {"factor":"Trend structure", "status":"SUPPORTS", "value":f"Close {close}; EMA20 {ema}; SMA60 {sma}"},
            {"factor":"Momentum", "status":"SUPPORTS" if 40 <= rsi <= 70 else "CAUTION", "value":f"RSI14 {rsi}"},
            {"factor":"Observed volatility", "status":"AVAILABLE", "value":f"ATR14 {atr}"},
        ],
    })


def build_lme_close_only_plan(close_series: dict, market: dict | None = None) -> dict:
    market = market or {}
    name = "LME Zinc Cash primary / 3M technical reference"
    if close_series.get("status") != "AVAILABLE" or close_series.get("observations", 0) < 60:
        return _blocked(name, "Validated same-source close history is insufficient.")
    latest = _num(close_series.get("latest_close"))
    trend = close_series.get("trend", {})
    direction = trend.get("regime", "UNDETERMINED")
    points = [p for p in close_series.get("chart_points", []) if _num(p.get("close")) is not None]
    closes = [_num(p.get("close")) for p in points[-20:]]
    daily = {}
    reasons = ["Live bid/ask and acceptable spread are unavailable."]
    if latest is not None and len(closes) >= 20 and ("BULL" in direction or "BEAR" in direction):
        support, resistance = min(closes), max(closes)
        moves = [abs(b-a) for a,b in zip(closes, closes[1:]) if a is not None and b is not None]
        buffer = max(0.5, round(median(moves) * 0.10, 1)) if moves else 0.5
        ema = _num(close_series.get("ema_20")); sma = _num(close_series.get("sma_30"))
        if "BULL" in direction:
            trigger = resistance + buffer; stop = support - buffer
            setup = [min(x for x in (ema, latest) if x is not None), max(x for x in (ema, latest) if x is not None)]
            t1 = trigger + 2 * (trigger-stop); t2 = trigger + 3 * (trigger-stop)
        else:
            trigger = support - buffer; stop = resistance + buffer
            setup = [min(x for x in (ema, latest) if x is not None), max(x for x in (ema, latest) if x is not None)]
            t1 = trigger - 2 * (stop-trigger); t2 = trigger - 3 * (stop-trigger)
        daily = {"plan_basis":"LME_3M_CLOSE_ONLY_RESEARCH", "setup_zone":[round(x,2) for x in setup],
                 "trigger_price":round(trigger,2), "maximum_entry":round(trigger,2),
                 "hard_stop":round(stop,2), "close_invalidation":round(sma,2) if sma is not None else None,
                 "t1":round(t1,2), "t2":round(t2,2), "planned_rr_t1":2.0, "planned_rr_t2":3.0,
                 "conditional_order":"DAILY_CLOSE_CONFIRMATION_RESEARCH_ONLY"}
        reasons.insert(0, "Close-based trigger has not been confirmed; no candle pattern or ATR is inferred.")
    else:
        reasons.insert(0, "Close trend is neutral/insufficient; no directional setup is permitted.")
    plan = {
        "market": name, "as_of": close_series.get("as_of"), "decision": "WAIT_FOR_TRIGGER" if daily else "NO_TRADE",
        "direction": direction, "evidence_alignment": "PARTIAL_CLOSE_AND_FUNDAMENTAL",
        "data_gate": "PASS_CLOSE_ONLY", "regime_gate": trend.get("regime", "UNDETERMINED"),
        "strategy_gate": "CLOSE_CONFIRMED_RESEARCH_ONLY", "trigger_gate": "NOT_TRIGGERED_CLOSE_ONLY" if daily else "BLOCKED_NO_SETUP",
        "execution_gate": "PENDING_PRIVATE_EXECUTION_CHECK" if daily else "BLOCKED_NO_BID_ASK", "daily_plan": daily,
        "reference": {"cash":_num(market.get("lme_cash")), "three_month":_num(market.get("lme_3m")),
                      "cash_3m":_num(market.get("cash_3m")), "close": latest,
                      "price_basis":"Cash headline; 3M close-only technical levels",
                      "sma14": _num(close_series.get("sma_14")),
                      "sma30": _num(close_series.get("sma_30")), "ema20": _num(close_series.get("ema_20")),
                      "rsi14": _num(close_series.get("rsi_14"))},
        "execution_check": {"status": "PRIVATE_INPUT_REQUIRED", "required":[
            "contract", "quote_time", "bid", "ask", "account_risk", "multiplier", "fees"
        ]},
        "no_trade_reasons": reasons,
        "evidence": [
            {"factor":"Cash headline", "status":"AVAILABLE" if market.get("lme_cash") is not None else "MISSING", "value":market.get("lme_cash")},
            {"factor":"3M technical reference", "status":"AVAILABLE", "value":latest},
            {"factor":"Cash−3M curve", "status":"BACKWARDATION" if _num(market.get("cash_3m")) and _num(market.get("cash_3m")) > 0 else "CONTANGO_OR_FLAT", "value":market.get("cash_3m")},
            {"factor":"Inventory", "status":"AVAILABLE" if market.get("lme_inventory_t") is not None else "MISSING", "value":market.get("lme_inventory_t")},
            {"factor":"Cancelled warrants", "status":"AVAILABLE" if market.get("cancelled_ratio_pct") is not None else "MISSING", "value":market.get("cancelled_ratio_pct")},
            {"factor":"TC", "status":"AVAILABLE" if market.get("tc_usd_t") is not None else "MISSING", "value":market.get("tc_usd_t")},
        ],
    }
    return _finalize(plan)


def build_close_reference_plan(series: dict) -> dict:
    name = series.get("name", "Close-only reference")
    if series.get("status") != "AVAILABLE" or series.get("observations", 0) < 60:
        return _blocked(name, "At least 60 validated close sessions are required.")
    latest = series.get("latest_session", {})
    close, ema, sma, rsi = (_num(latest.get(k)) for k in ("close","ema20","sma60","rsi14"))
    direction = "BULL" if None not in (close,ema,sma) and close > ema > sma else "BEAR" if None not in (close,ema,sma) and close < ema < sma else "NEUTRAL"
    return _finalize({"market":name, "symbol":series.get("symbol"), "as_of":series.get("as_of"),
            "decision":"NO_TRADE", "direction":direction, "evidence_alignment":"CLOSE_ONLY",
            "data_gate":"PASS_CLOSE_ONLY", "regime_gate":direction, "strategy_gate":"RESEARCH_ONLY",
            "trigger_gate":"BLOCKED_NO_OHLC", "execution_gate":"BLOCKED_NO_BID_ASK",
            "daily_plan":{}, "execution_check":{"status":"NOT_AVAILABLE"},
            "reference":{"close":close,"ema20":ema,"sma60":sma,"rsi14":rsi},
            "no_trade_reasons":["Close-only series cannot produce candle/ATR triggers.",
                                "No verified executable bid/ask, spread or fill."],
            "evidence":[{"factor":"Close-only trend", "status":direction, "value":f"Close {close}; EMA20 {ema}; SMA60 {sma}"},
                        {"factor":"Momentum", "status":"AVAILABLE", "value":f"RSI14 {rsi}"}]})


def build_decision_book(close_series: dict, shfe: dict, cross_assets: dict, market: dict | None = None) -> dict:
    plans = {
            "lme_zinc": build_lme_close_only_plan(close_series, market),
            "shfe_zinc": build_ohlc_plan({**shfe, "name": "SHFE Zinc", "symbol": shfe.get("latest_contract")}),
            **{key: (build_close_reference_plan(value) if value.get("series_type") == "CLOSE_ONLY" else build_ohlc_plan(value))
               for key, value in cross_assets.items()},
        }
    # Explicitly record missing asset-specific institutional inputs rather than
    # pretending that generic OHLC indicators are sufficient evidence.
    missing = {
        "gold":["COMEX contract-specific OI", "real yield", "ETF flow", "COT positioning"],
        "usdjpy":["US-Japan 2Y yield spread", "BoJ/Fed policy differential", "intervention risk"],
        "dxy":["Fed rate path", "US 2Y yield", "constituent contribution"],
        "shfe_zinc":["cross-market FX-adjusted parity", "verified LME/SHFE arbitrage costs"],
    }
    for key, fields in missing.items():
        if key in plans:
            plans[key].setdefault("evidence", []).extend(
                {"factor":field, "status":"NOT_INTEGRATED", "value":None} for field in fields
            )
            if plans[key].get("decision") != "NO_TRADE":
                plans[key]["evidence_alignment"] = "PARTIAL_TECHNICAL_ONLY"
                plans[key].setdefault("no_trade_reasons", []).append(
                    "Asset-specific institutional evidence is incomplete; treat levels as technical research, not execution approval."
                )
            plans[key]["decision_audit"] = _decision_audit(plans[key])
    for plan in plans.values():
        evidence = plan.get("evidence", [])
        unavailable = {"MISSING", "NOT_INTEGRATED"}
        plan["evidence_completeness"] = round(
            100 * sum(item.get("status") not in unavailable for item in evidence) / len(evidence), 1
        ) if evidence else 0.0
        plan["decision_audit"] = _decision_audit(plan)
    return {
        "policy": "NO_DATA_NO_SIGNAL__NO_TRIGGER_NO_ORDER__LIVE_QUOTE_REQUIRED__RR_MIN_2",
        "minimum_actual_rr": 2.0,
        "markets": plans,
    }
