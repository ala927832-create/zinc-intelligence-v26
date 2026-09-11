from __future__ import annotations

import math
from typing import Any

from .utils import clamp


def _scaled(value: float | None, center: float, width: float, invert: bool = False) -> float | None:
    if value is None or width <= 0:
        return None
    score = 50 + 50 * math.tanh((value - center) / width)
    if invert:
        score = 100 - score
    return clamp(score, 0, 100)


def technical_score(ind: dict) -> float | None:
    if not ind or ind.get("Close") is None:
        return None
    vals: list[float] = []
    close = ind.get("Close")
    e20, e50, e200 = ind.get("EMA20"), ind.get("EMA50"), ind.get("EMA200")
    rsi, roc20, roc60 = ind.get("RSI14"), ind.get("ROC20"), ind.get("ROC60")
    if close and e20:
        vals.append(_scaled((close/e20 - 1) * 100, 0, 2.5) or 50)
    if e20 and e50:
        vals.append(_scaled((e20/e50 - 1) * 100, 0, 2.0) or 50)
    if e50 and e200:
        vals.append(_scaled((e50/e200 - 1) * 100, 0, 4.0) or 50)
    if rsi is not None:
        vals.append(clamp(50 + (rsi - 50) * 0.7, 0, 100))
    if roc20 is not None:
        vals.append(_scaled(roc20, 0, 6) or 50)
    if roc60 is not None:
        vals.append(_scaled(roc60, 0, 12) or 50)
    return sum(vals) / len(vals) if vals else None


def market_structure_score(market: dict) -> float | None:
    vals: list[float] = []
    cash3m = market.get("cash_3m")
    cancelled_ratio = market.get("cancelled_ratio_pct")
    if cash3m is not None:
        vals.append(_scaled(cash3m, 0, 30) or 50)
    if cancelled_ratio is not None:
        vals.append(_scaled(cancelled_ratio, 15, 10) or 50)
    return sum(vals) / len(vals) if vals else None


def smelter_score(market: dict) -> float | None:
    vals: list[float] = []
    tc = market.get("tc_usd_t")
    margin = market.get("smelter_margin_usd_t")
    utilization = market.get("smelter_utilization_pct")
    if tc is not None:
        # Lower TC can indicate concentrate tightness; bullish for refined-zinc supply risk.
        vals.append(_scaled(tc, 80, 35, invert=True) or 50)
    if margin is not None:
        # Lower smelter margin raises cut-risk; translate to higher zinc tightness score.
        vals.append(_scaled(margin, 150, 120, invert=True) or 50)
    if utilization is not None:
        vals.append(_scaled(utilization, 88, 8, invert=True) or 50)
    return sum(vals) / len(vals) if vals else None


def physical_score(market: dict) -> float | None:
    premium = market.get("physical_premium_usd_t")
    if premium is None:
        return None
    return _scaled(premium, 30, 25)


def supply_demand_score(market: dict) -> float | None:
    vals: list[float] = []
    china = market.get("china_demand_yoy_pct")
    balance = market.get("global_balance_kt")
    if china is not None:
        vals.append(_scaled(china, 0, 4) or 50)
    if balance is not None:
        vals.append(_scaled(balance, 0, 100, invert=True) or 50)
    return sum(vals) / len(vals) if vals else None


def macro_score(macro: dict) -> float | None:
    vals: list[float] = []
    dxy = macro.get("DXY", {}).get("change_pct")
    oil = macro.get("Brent Oil", {}).get("change_pct")
    copper = macro.get("Copper", {}).get("change_pct")
    if dxy is not None:
        vals.append(clamp(50 - dxy * 10, 0, 100))
    if oil is not None:
        vals.append(clamp(50 + oil * 3, 0, 100))
    if copper is not None:
        vals.append(clamp(50 + copper * 8, 0, 100))
    return sum(vals) / len(vals) if vals else None


def weighted_score(components: dict[str, float | None], weights: dict[str, float]) -> tuple[float | None, float]:
    num = 0.0
    den = 0.0
    for key, weight in weights.items():
        value = components.get(key)
        if value is not None:
            num += value * weight
            den += weight
    if den == 0:
        return None, 0.0
    return num / den, den / max(sum(weights.values()), 1e-9)


def market_regime(score: float | None) -> str:
    if score is None:
        return "NO_DATA"
    if score >= 75:
        return "STRONG_BULL"
    if score >= 60:
        return "BULL"
    if score > 40:
        return "NEUTRAL"
    if score > 25:
        return "BEAR"
    return "STRONG_BEAR"


def multi_horizon_scores(base: float | None, tech: float | None) -> dict:
    if base is None and tech is None:
        return {"5D": None, "20D": None, "60D": None}
    b = base if base is not None else 50
    t = tech if tech is not None else 50
    # Short horizon gives more weight to technicals; long horizon to structural data.
    return {
        "5D": 0.70 * t + 0.30 * b,
        "20D": 0.45 * t + 0.55 * b,
        "60D": 0.25 * t + 0.75 * b,
    }


def estimated_probability(score: float | None, data_confidence: float, empirical: dict | None = None) -> dict:
    if score is None:
        return {"p_profit": None, "status": "UNAVAILABLE", "sample_size": 0}
    raw = clamp(0.50 + (score - 50) * 0.004, 0.35, 0.67)
    conf_shrink = clamp(data_confidence / 100, 0, 1)
    raw = 0.5 + (raw - 0.5) * conf_shrink
    n = int((empirical or {}).get("n", 0))
    if n >= 30:
        wins = float(empirical.get("wins", 0))
        empirical_p = (wins + 2) / (n + 4)  # beta shrinkage
        p = 0.6 * empirical_p + 0.4 * raw
        status = "CALIBRATING"
    else:
        p = raw
        status = "PROVISIONAL"
    return {"p_profit": clamp(p, 0.01, 0.99), "status": status, "sample_size": n}


def event_overlay(events: list[dict]) -> dict:
    severity_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    active = [e for e in events if str(e.get("status", "ACTIVE")).upper() == "ACTIVE"]
    severity = max([severity_map.get(str(e.get("severity", "LOW")).upper(), 1) for e in active], default=0)
    label = {0: "NONE", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}[severity]
    # Risk overlay does not directly force a direction. It reduces confidence at high uncertainty.
    confidence_penalty = {0: 0, 1: 0, 2: 3, 3: 8, 4: 15}[severity]
    return {"level": label, "confidence_penalty": confidence_penalty, "active_events": active}


def procurement_metrics(state: dict, regime: str, settings: dict) -> dict:
    inv = state.get("current_inventory_t")
    demand = state.get("demand_60d_t")
    if inv is None or demand in (None, 0):
        return {"status": "INPUT_REQUIRED"}
    daily = demand / 60.0
    coverage = inv / daily if daily > 0 else None
    uncovered = max(demand - inv, 0)

    pset = settings["procurement"]
    if coverage < pset["critical_days"]:
        inv_band = "CRITICAL"
    elif coverage < pset["low_days"]:
        inv_band = "LOW"
    elif coverage <= pset["normal_high_days"]:
        inv_band = "NORMAL"
    elif coverage <= pset["high_days"]:
        inv_band = "HIGH"
    else:
        inv_band = "EXCESS"

    if coverage < pset["critical_days"]:
        action = "EMERGENCY_REPLENISH"
        override = True
        cover_ratio = max(pset["target_cover_ratios"].get(regime, 0.45), 0.80)
    else:
        override = False
        matrix = {
            "STRONG_BULL": {"LOW": "ACCELERATE", "NORMAL": "PARTIAL_COVER", "HIGH": "HOLD", "EXCESS": "HOLD"},
            "BULL": {"LOW": "ACCELERATE", "NORMAL": "NORMALIZE", "HIGH": "WAIT", "EXCESS": "WAIT"},
            "NEUTRAL": {"LOW": "REPLENISH", "NORMAL": "MAINTAIN", "HIGH": "WAIT", "EXCESS": "WAIT"},
            "BEAR": {"LOW": "JIT", "NORMAL": "DEFER", "HIGH": "DEFER", "EXCESS": "DEFER"},
            "STRONG_BEAR": {"LOW": "JIT", "NORMAL": "DEFER", "HIGH": "STOP_DISCRETIONARY", "EXCESS": "STOP_DISCRETIONARY"},
        }
        band = inv_band if inv_band in ["LOW", "NORMAL", "HIGH", "EXCESS"] else "LOW"
        action = matrix.get(regime, matrix["NEUTRAL"])[band]
        cover_ratio = pset["target_cover_ratios"].get(regime, 0.45)
        if inv_band in ("HIGH", "EXCESS"):
            cover_ratio = min(cover_ratio, 0.25)

    suggested_cover = uncovered * cover_ratio
    lots = suggested_cover / settings["lme_lot_tonnes"] if settings["lme_lot_tonnes"] else None
    return {
        "status": "OK", "daily_demand_t": daily, "coverage_days": coverage, "inventory_band": inv_band,
        "uncovered_demand_t": uncovered, "action": action, "production_safety_override": override,
        "target_cover_ratio": cover_ratio, "suggested_cover_t": suggested_cover, "equivalent_lme_lots": lots,
        "safety_stock_days": pset["default_safety_stock_days"]
    }


def strategy_recommendation(name: str, horizon_score: float | None, data_conf: float, ind: dict, settings: dict, empirical: dict | None = None) -> dict:
    cfg = settings["paper_trading"][name]
    if horizon_score is None or not ind or ind.get("Close") is None or ind.get("ATR14") is None:
        return {"strategy": name, "action": "NO_SIGNAL", "reason": "insufficient candle/indicator data"}
    score = horizon_score
    prob = estimated_probability(score, data_conf, empirical)
    close = float(ind["Close"])
    atr = float(ind["ATR14"])
    e20, e50, e200 = ind.get("EMA20"), ind.get("EMA50"), ind.get("EMA200")
    roc20 = ind.get("ROC20")
    bull = score >= 60
    bear = score <= 40
    direction = "LONG" if bull else "SHORT" if bear else "FLAT"
    action = "NO_TRADE"
    reason = "edge below threshold"

    if data_conf < cfg["min_data_confidence"]:
        action, reason = "NO_TRADE", "data confidence below strategy gate"
    elif score >= cfg["min_strategy_score"] and bull:
        if name == "conservative":
            pullback_ok = e20 is not None and abs(close - e20) <= max(atr, close * 0.01) and (e50 is None or close >= e50)
            if pullback_ok:
                action, reason = "LONG_NEXT_SESSION", "bullish regime + pullback near EMA20"
            else:
                action, reason = "WAIT_PULLBACK", "bullish regime but entry not in conservative pullback zone"
        else:
            momentum_ok = e20 is not None and close >= e20 and (e50 is None or e20 >= e50) and (roc20 is None or roc20 > 0)
            if momentum_ok:
                action, reason = "LONG_NEXT_SESSION", "bullish regime + momentum confirmation"
            else:
                action, reason = "WAIT_CONFIRMATION", "bullish score without momentum confirmation"
    elif score <= (100 - cfg["min_strategy_score"]) and bear:
        if name == "conservative":
            pullback_ok = e20 is not None and abs(close - e20) <= max(atr, close * 0.01) and (e50 is None or close <= e50)
            action, reason = ("SHORT_NEXT_SESSION", "bearish regime + rebound near EMA20") if pullback_ok else ("WAIT_REBOUND", "bearish regime but entry not in conservative rebound zone")
        else:
            momentum_ok = e20 is not None and close <= e20 and (e50 is None or e20 <= e50) and (roc20 is None or roc20 < 0)
            action, reason = ("SHORT_NEXT_SESSION", "bearish regime + downside momentum") if momentum_ok else ("WAIT_CONFIRMATION", "bearish score without downside momentum confirmation")

    if direction == "LONG":
        stop = close - cfg["stop_atr"] * atr
        target = close + cfg["target_r_multiple"] * (close - stop)
    elif direction == "SHORT":
        stop = close + cfg["stop_atr"] * atr
        target = close - cfg["target_r_multiple"] * (stop - close)
    else:
        stop = target = None

    risk_per_t = abs(close - stop) if stop is not None else None
    reward_per_t = abs(target - close) if target is not None else None
    lots = settings["paper_trading"]["simulated_lots"]
    lot_t = settings["lme_lot_tonnes"]
    commission = settings["paper_trading"]["commission_usd_per_lot_roundtrip"] * lots
    slippage = settings["paper_trading"]["slippage_usd_per_t"] * lot_t * lots * 2
    risk_usd = risk_per_t * lot_t * lots + commission + slippage if risk_per_t is not None else None
    reward_usd = reward_per_t * lot_t * lots - commission - slippage if reward_per_t is not None else None
    p = prob.get("p_profit")
    ev = (p * reward_usd - (1-p) * risk_usd) if p is not None and reward_usd is not None and risk_usd is not None else None

    return {
        "strategy": name, "action": action, "direction": direction, "reason": reason,
        "strategy_score": score, "probability": prob, "reference_price": close, "atr": atr,
        "suggested_stop": stop, "suggested_target": target,
        "risk_usd_per_sim_trade": risk_usd, "reward_usd_per_sim_trade": reward_usd,
        "expected_value_usd": ev, "reward_risk": (reward_usd / risk_usd if risk_usd and reward_usd is not None else None),
        "simulated_lots": lots, "paper_only": True, "max_holding_sessions": cfg["max_holding_sessions"]
    }
