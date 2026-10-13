"""Auditable six-gate research plans with an explicit execution boundary."""

from __future__ import annotations

import math


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


def _blocked(name: str, reason: str, data_status: str = "MISSING") -> dict:
    return {
        "market": name, "decision": "NO_TRADE", "direction": "UNDETERMINED",
        "evidence_alignment": "INSUFFICIENT", "data_gate": data_status,
        "strategy_gate": "BLOCKED", "trigger_gate": "BLOCKED", "execution_gate": "BLOCKED",
        "daily_plan": {}, "execution_check": {"status": "NOT_AVAILABLE"},
        "no_trade_reasons": [reason],
    }


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
        return {
            **_blocked(series.get("name", "Market"), "Close, EMA20 and SMA60 are not directionally aligned.", "PASS"),
            "direction": "NEUTRAL", "evidence_alignment": "MIXED", "regime_gate": "RANGE_OR_TRANSITION",
            "reference": {"close": close, "ema20": ema, "sma60": sma, "rsi14": rsi, "atr14": atr},
        }
    plan = {
        "setup_zone": [round(min(ema, close), 4), round(max(ema, close), 4)],
        "trigger_price": round(trigger, 4), "maximum_entry": round(maximum, 4),
        "hard_stop": round(stop, 4), "close_invalidation": round(invalidation, 4),
        "t1": round(t1, 4), "t2": round(t2, 4), "planned_rr_t1": _rr(trigger, stop, t1),
        "planned_rr_t2": _rr(trigger, stop, t2), "conditional_order": "STOP_LIMIT_AFTER_DAILY_CONFIRMATION",
    }
    return {
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
    }


def build_lme_close_only_plan(close_series: dict) -> dict:
    name = "LME Zinc 3M reference"
    if close_series.get("status") != "AVAILABLE" or close_series.get("observations", 0) < 60:
        return _blocked(name, "Validated same-source close history is insufficient.")
    latest = _num(close_series.get("latest_close"))
    trend = close_series.get("trend", {})
    return {
        "market": name, "as_of": close_series.get("as_of"), "decision": "NO_TRADE",
        "direction": trend.get("regime", "UNDETERMINED"), "evidence_alignment": "CLOSE_ONLY",
        "data_gate": "PASS_CLOSE_ONLY", "regime_gate": trend.get("regime", "UNDETERMINED"),
        "strategy_gate": "RESEARCH_ONLY", "trigger_gate": "BLOCKED_NO_LME_OHLC",
        "execution_gate": "BLOCKED_NO_BID_ASK", "daily_plan": {},
        "reference": {"close": latest, "sma14": _num(close_series.get("sma_14")),
                      "sma30": _num(close_series.get("sma_30")), "ema20": _num(close_series.get("ema_20")),
                      "rsi14": _num(close_series.get("rsi_14"))},
        "execution_check": {"status": "NOT_AVAILABLE"},
        "no_trade_reasons": [
            "LME series is close-only; no candle trigger or ATR may be inferred.",
            "No verified executable contract bid/ask, spread or fill.",
        ],
    }


def build_close_reference_plan(series: dict) -> dict:
    name = series.get("name", "Close-only reference")
    if series.get("status") != "AVAILABLE" or series.get("observations", 0) < 60:
        return _blocked(name, "At least 60 validated close sessions are required.")
    latest = series.get("latest_session", {})
    close, ema, sma, rsi = (_num(latest.get(k)) for k in ("close","ema20","sma60","rsi14"))
    direction = "BULL" if None not in (close,ema,sma) and close > ema > sma else "BEAR" if None not in (close,ema,sma) and close < ema < sma else "NEUTRAL"
    return {"market":name, "symbol":series.get("symbol"), "as_of":series.get("as_of"),
            "decision":"NO_TRADE", "direction":direction, "evidence_alignment":"CLOSE_ONLY",
            "data_gate":"PASS_CLOSE_ONLY", "regime_gate":direction, "strategy_gate":"RESEARCH_ONLY",
            "trigger_gate":"BLOCKED_NO_OHLC", "execution_gate":"BLOCKED_NO_BID_ASK",
            "daily_plan":{}, "execution_check":{"status":"NOT_AVAILABLE"},
            "reference":{"close":close,"ema20":ema,"sma60":sma,"rsi14":rsi},
            "no_trade_reasons":["Close-only series cannot produce candle/ATR triggers.",
                                "No verified executable bid/ask, spread or fill."]}


def build_decision_book(close_series: dict, shfe: dict, cross_assets: dict) -> dict:
    return {
        "policy": "NO_DATA_NO_SIGNAL__NO_TRIGGER_NO_ORDER__LIVE_QUOTE_REQUIRED__RR_MIN_2",
        "minimum_actual_rr": 2.0,
        "markets": {
            "lme_zinc": build_lme_close_only_plan(close_series),
            "shfe_zinc": build_ohlc_plan({**shfe, "name": "SHFE Zinc", "symbol": shfe.get("latest_contract")}),
            **{key: (build_close_reference_plan(value) if value.get("series_type") == "CLOSE_ONLY" else build_ohlc_plan(value))
               for key, value in cross_assets.items()},
        },
    }
