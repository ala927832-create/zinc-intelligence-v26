"""Private-only execution simulation and post-trade audit calculations."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from threading import Lock


_LOCK = Lock()
SIDES = {"LONG": 1, "SHORT": -1}


def _number(raw, name: str, *, allow_zero: bool = False) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or (value < 0 if allow_zero else value <= 0):
        raise ValueError(f"{name} must be {'non-negative' if allow_zero else 'positive'}")
    return value


def _timestamp(raw: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("quote_timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("quote_timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def simulate_execution(raw: dict, *, now: datetime | None = None) -> dict:
    """Validate a manually observed quote and calculate risk without placing an order."""
    if not isinstance(raw, dict):
        raise ValueError("Execution input must be an object")
    market = str(raw.get("market", "")).strip()
    contract = str(raw.get("contract", "")).strip()
    side = str(raw.get("side", "")).upper().strip()
    if not market or not contract or side not in SIDES:
        raise ValueError("market, contract and LONG/SHORT side are required")
    quote_time = _timestamp(raw.get("quote_timestamp", ""))
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_seconds = (now - quote_time).total_seconds()
    if age_seconds < -30:
        raise ValueError("quote_timestamp is in the future")

    bid = _number(raw.get("bid"), "bid"); ask = _number(raw.get("ask"), "ask")
    if bid > ask:
        raise ValueError("bid cannot exceed ask")
    entry = ask if side == "LONG" else bid
    stop = _number(raw.get("hard_stop"), "hard_stop")
    t1 = _number(raw.get("t1"), "t1"); t2 = _number(raw.get("t2"), "t2")
    equity = _number(raw.get("account_equity"), "account_equity")
    risk_pct = _number(raw.get("risk_pct"), "risk_pct")
    multiplier = _number(raw.get("contract_multiplier"), "contract_multiplier")
    tick = _number(raw.get("tick_size"), "tick_size")
    fees = _number(raw.get("fees_per_contract", 0), "fees_per_contract", allow_zero=True)
    slippage_ticks = _number(raw.get("slippage_ticks", 0), "slippage_ticks", allow_zero=True)
    max_spread_ticks = _number(raw.get("max_spread_ticks", 4), "max_spread_ticks")
    max_quote_age = _number(raw.get("max_quote_age_seconds", 120), "max_quote_age_seconds")
    if risk_pct > 2:
        raise ValueError("risk_pct cannot exceed 2%")
    if side == "LONG" and not (stop < entry < t1 <= t2):
        raise ValueError("LONG requires stop < entry < T1 <= T2")
    if side == "SHORT" and not (stop > entry > t1 >= t2):
        raise ValueError("SHORT requires stop > entry > T1 >= T2")

    spread = ask - bid
    spread_ticks = spread / tick
    slippage_buffer = slippage_ticks * tick * multiplier
    risk_per_contract = abs(entry-stop) * multiplier + fees + slippage_buffer
    risk_budget = equity * risk_pct / 100
    quantity = math.floor(risk_budget / risk_per_contract) if risk_per_contract else 0
    direction = SIDES[side]
    reward1 = (t1-entry) * multiplier * direction - fees - slippage_buffer
    reward2 = (t2-entry) * multiplier * direction - fees - slippage_buffer
    rr1 = reward1 / risk_per_contract if risk_per_contract else None
    rr2 = reward2 / risk_per_contract if risk_per_contract else None
    blockers = []
    if age_seconds > max_quote_age: blockers.append("QUOTE_STALE")
    if spread_ticks > max_spread_ticks: blockers.append("SPREAD_TOO_WIDE")
    if quantity < 1: blockers.append("RISK_BUDGET_TOO_SMALL")
    if rr1 is None or rr1 < 2: blockers.append("ACTUAL_PLANNED_RR_BELOW_2")
    result = {
        "status":"APPROVED_FOR_SIMULATION" if not blockers else "REJECTED",
        "research_only":True, "order_transmitted":False, "market":market, "contract":contract, "side":side,
        "quote_timestamp":quote_time.isoformat(), "quote_age_seconds":round(max(0, age_seconds), 1),
        "bid":bid, "ask":ask, "spread":round(spread, 8), "spread_ticks":round(spread_ticks, 2),
        "simulated_entry":entry, "hard_stop":stop, "t1":t1, "t2":t2,
        "risk_budget":round(risk_budget, 2), "risk_per_contract":round(risk_per_contract, 2),
        "contract_multiplier":multiplier, "tick_size":tick, "fees_per_contract":fees,
        "slippage_ticks":slippage_ticks,
        "contract_quantity":quantity, "planned_rr_t1":round(rr1, 2) if rr1 is not None else None,
        "planned_rr_t2":round(rr2, 2) if rr2 is not None else None, "blockers":blockers,
    }
    if str(raw.get("mark_price", "")).strip():
        result.update(mark_to_market(result, raw["mark_price"]))
    return result


def mark_to_market(simulation: dict, mark_price) -> dict:
    mark = _number(mark_price, "mark_price")
    side = simulation.get("side")
    if side not in SIDES or simulation.get("contract_quantity", 0) < 1:
        raise ValueError("A valid simulation is required")
    multiplier = _number(simulation.get("contract_multiplier", 1), "contract_multiplier")
    quantity = int(simulation["contract_quantity"])
    gross = (mark - _number(simulation.get("simulated_entry"), "simulated_entry")) * multiplier * quantity * SIDES[side]
    fees = _number(simulation.get("fees_per_contract", 0), "fees_per_contract", allow_zero=True) * quantity
    slippage = (_number(simulation.get("slippage_ticks", 0), "slippage_ticks", allow_zero=True)
                * _number(simulation.get("tick_size", 0), "tick_size", allow_zero=True) * multiplier * quantity)
    return {"mark_price": mark, "gross_unrealized_pnl": round(gross, 2),
            "assumed_costs": round(fees + slippage, 2),
            "unrealized_pnl": round(gross - fees - slippage, 2)}


def normalize_trade(raw: dict) -> dict:
    required = ("setup_id", "market", "contract", "side", "planned_entry", "hard_stop", "t1", "t2",
                "actual_fill", "exit_price", "quantity", "contract_multiplier", "fees", "opened_at", "closed_at")
    if not isinstance(raw, dict) or any(str(raw.get(k, "")).strip() == "" for k in required):
        raise ValueError("Complete planned, fill, exit, size, fee and timestamp fields are required")
    side = str(raw["side"]).upper()
    if side not in SIDES:
        raise ValueError("side must be LONG or SHORT")
    opened = _timestamp(raw["opened_at"]); closed = _timestamp(raw["closed_at"])
    if closed < opened:
        raise ValueError("closed_at cannot precede opened_at")
    planned = _number(raw["planned_entry"], "planned_entry"); fill = _number(raw["actual_fill"], "actual_fill")
    exit_price = _number(raw["exit_price"], "exit_price"); stop = _number(raw["hard_stop"], "hard_stop")
    multiplier = _number(raw["contract_multiplier"], "contract_multiplier")
    quantity_raw = _number(raw["quantity"], "quantity")
    if not quantity_raw.is_integer():
        raise ValueError("quantity must be a whole number")
    quantity = int(quantity_raw); fees = _number(raw["fees"], "fees", allow_zero=True)
    direction = SIDES[side]
    initial_risk = abs(fill-stop) * multiplier * quantity + fees
    net_pnl = (exit_price-fill) * multiplier * quantity * direction - fees
    actual_r = net_pnl / initial_risk if initial_risk else None
    slippage = (fill-planned) * direction
    return {k:str(raw[k]).strip() for k in ("setup_id","market","contract")} | {
        "side":side, "planned_entry":planned, "hard_stop":stop, "t1":_number(raw["t1"], "t1"),
        "t2":_number(raw["t2"], "t2"), "actual_fill":fill, "exit_price":exit_price,
        "quantity":quantity, "contract_multiplier":multiplier, "fees":fees,
        "opened_at":opened.isoformat(), "closed_at":closed.isoformat(),
        "slippage_price_units":round(slippage, 8), "initial_risk":round(initial_risk, 2),
        "net_pnl":round(net_pnl, 2), "actual_r":round(actual_r, 3) if actual_r is not None else None,
        "exit_reason":str(raw.get("exit_reason", "")).strip()[:200],
        "rule_followed":bool(raw.get("rule_followed")),
    }


def read_trades(path: Path) -> list[dict]:
    if not path.exists(): return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def append_trade(path: Path, raw: dict) -> dict:
    trade = normalize_trade(raw)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with _LOCK:
        existing = read_trades(path)
        if any(x.get("setup_id") == trade["setup_id"] for x in existing):
            raise ValueError("setup_id already exists")
        with os.fdopen(os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600), "a", encoding="utf-8") as stream:
            stream.write(json.dumps(trade, ensure_ascii=False) + "\n")
            stream.flush(); os.fsync(stream.fileno())
    return trade


def performance_summary(trades: list[dict]) -> dict:
    if not trades:
        return {"closed_trades":0, "status":"INSUFFICIENT_SAMPLE", "minimum_for_preliminary":30}
    r_values = [float(x["actual_r"]) for x in trades if x.get("actual_r") is not None]
    wins = [x for x in r_values if x > 0]; losses = [x for x in r_values if x <= 0]
    return {"closed_trades":len(r_values), "status":"PRELIMINARY" if len(r_values) >= 30 else "INSUFFICIENT_SAMPLE",
            "win_rate_pct":round(100*len(wins)/len(r_values),1) if r_values else None,
            "average_r":round(sum(r_values)/len(r_values),3) if r_values else None,
            "average_win_r":round(sum(wins)/len(wins),3) if wins else None,
            "average_loss_r":round(sum(losses)/len(losses),3) if losses else None,
            "minimum_for_preliminary":30}
