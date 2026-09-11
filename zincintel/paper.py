from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .utils import clamp


def empirical_stats(trades: list[dict], strategy: str) -> dict:
    closed = [t for t in trades if t.get("strategy") == strategy and t.get("status") == "CLOSED"]
    wins = sum(1 for t in closed if (t.get("net_pnl_usd") or 0) > 0)
    return {"n": len(closed), "wins": wins}


def _same_day(ts1: Any, ts2: Any) -> bool:
    try:
        return pd.Timestamp(ts1).date() == pd.Timestamp(ts2).date()
    except Exception:
        return False


def _next_bar_after(df: pd.DataFrame, signal_ts: str) -> pd.Series | None:
    if df.empty:
        return None
    signal = pd.Timestamp(signal_ts)
    if signal.tzinfo is None:
        signal = signal.tz_localize("UTC")
    later = df[df.index > signal]
    if later.empty:
        return None
    return later.iloc[0]


def _bar_timestamp(row: pd.Series) -> str:
    try:
        return row.name.isoformat()
    except Exception:
        return str(row.name)


def queue_trade_if_actionable(trades: list[dict], recommendation: dict, signal_time: str, model_version: str, market_regime: str, data_confidence: float) -> list[dict]:
    action = recommendation.get("action", "")
    if action not in ("LONG_NEXT_SESSION", "SHORT_NEXT_SESSION"):
        return trades
    strategy = recommendation["strategy"]
    active = [t for t in trades if t.get("strategy") == strategy and t.get("status") in ("PENDING", "OPEN")]
    if active:
        return trades
    direction = "LONG" if action.startswith("LONG") else "SHORT"
    trade_id = f"{strategy[:3].upper()}-{pd.Timestamp(signal_time).strftime('%Y%m%d')}-{sum(1 for t in trades if t.get('strategy') == strategy)+1:03d}"
    trades.append({
        "trade_id": trade_id,
        "strategy": strategy,
        "status": "PENDING",
        "direction": direction,
        "signal_time": signal_time,
        "model_version": model_version,
        "market_regime": market_regime,
        "data_confidence": data_confidence,
        "forecast_probability": recommendation.get("probability", {}).get("p_profit"),
        "probability_status": recommendation.get("probability", {}).get("status"),
        "strategy_score": recommendation.get("strategy_score"),
        "reference_price": recommendation.get("reference_price"),
        "planned_stop_distance": abs((recommendation.get("reference_price") or 0) - (recommendation.get("suggested_stop") or 0)),
        "planned_target_r": recommendation.get("reward_risk"),
        "max_holding_sessions": recommendation.get("max_holding_sessions"),
        "simulated_lots": recommendation.get("simulated_lots", 1),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "paper_only": True
    })
    return trades


def process_paper_trades(trades: list[dict], daily_df: pd.DataFrame, settings: dict) -> list[dict]:
    if daily_df.empty:
        return trades
    lot_t = settings["lme_lot_tonnes"]
    slippage_per_t = settings["paper_trading"]["slippage_usd_per_t"]
    commission_per_lot = settings["paper_trading"]["commission_usd_per_lot_roundtrip"]

    for t in trades:
        strategy = t.get("strategy")
        if t.get("status") == "PENDING":
            next_bar = _next_bar_after(daily_df, t["signal_time"])
            if next_bar is None:
                continue
            direction = t["direction"]
            lots = float(t.get("simulated_lots", 1))
            entry_raw = float(next_bar["Open"])
            entry = entry_raw + slippage_per_t if direction == "LONG" else entry_raw - slippage_per_t
            stop_distance = float(t.get("planned_stop_distance") or 0)
            cfg = settings["paper_trading"][strategy]
            if stop_distance <= 0:
                atr_guess = abs(float(next_bar["High"]) - float(next_bar["Low"]))
                stop_distance = max(atr_guess * cfg["stop_atr"], entry * 0.01)
            stop = entry - stop_distance if direction == "LONG" else entry + stop_distance
            target = entry + cfg["target_r_multiple"] * stop_distance if direction == "LONG" else entry - cfg["target_r_multiple"] * stop_distance
            t.update({
                "status": "OPEN", "entry_time": _bar_timestamp(next_bar), "entry_price": entry,
                "stop_price": stop, "target_price": target, "mae_usd": 0.0, "mfe_usd": 0.0,
                "sessions_held": 0, "last_mark_price": entry, "unrealized_pnl_usd": 0.0
            })

        if t.get("status") != "OPEN":
            continue

        entry_ts = pd.Timestamp(t["entry_time"])
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.tz_localize("UTC")
        bars = daily_df[daily_df.index >= entry_ts]
        if bars.empty:
            continue

        direction = t["direction"]
        entry = float(t["entry_price"])
        stop = float(t["stop_price"])
        target = float(t["target_price"])
        lots = float(t.get("simulated_lots", 1))
        mult = lot_t * lots
        max_hold = int(t.get("max_holding_sessions") or settings["paper_trading"][strategy]["max_holding_sessions"])
        closed = False

        for i, (ts, row) in enumerate(bars.iterrows(), start=1):
            if t.get("processed_through") and pd.Timestamp(ts) <= pd.Timestamp(t["processed_through"]):
                continue
            high, low, close = float(row["High"]), float(row["Low"]), float(row["Close"])
            if direction == "LONG":
                adverse = min(0.0, (low - entry) * mult)
                favorable = max(0.0, (high - entry) * mult)
                stop_hit = low <= stop
                target_hit = high >= target
            else:
                adverse = min(0.0, (entry - high) * mult)
                favorable = max(0.0, (entry - low) * mult)
                stop_hit = high >= stop
                target_hit = low <= target
            t["mae_usd"] = min(float(t.get("mae_usd", 0.0)), adverse)
            t["mfe_usd"] = max(float(t.get("mfe_usd", 0.0)), favorable)
            t["sessions_held"] = int(t.get("sessions_held", 0)) + 1
            t["processed_through"] = pd.Timestamp(ts).isoformat()

            # Conservative rule: if both stop and target are touched in same bar, stop is assumed first.
            exit_price = None
            exit_reason = None
            if stop_hit:
                exit_price = stop - slippage_per_t if direction == "LONG" else stop + slippage_per_t
                exit_reason = "STOP"
            elif target_hit:
                exit_price = target - slippage_per_t if direction == "LONG" else target + slippage_per_t
                exit_reason = "TARGET"
            elif t["sessions_held"] >= max_hold:
                exit_price = close - slippage_per_t if direction == "LONG" else close + slippage_per_t
                exit_reason = "TIME_EXIT"

            if exit_price is not None:
                gross = (exit_price - entry) * mult if direction == "LONG" else (entry - exit_price) * mult
                fees = commission_per_lot * lots
                net = gross - fees
                initial_risk = abs(entry - stop) * mult + fees + 2 * slippage_per_t * mult
                t.update({
                    "status": "CLOSED", "exit_time": pd.Timestamp(ts).isoformat(), "exit_price": exit_price,
                    "exit_reason": exit_reason, "gross_pnl_usd": gross, "fees_usd": fees, "net_pnl_usd": net,
                    "r_multiple": (net / initial_risk if initial_risk else None), "unrealized_pnl_usd": 0.0
                })
                closed = True
                break
            else:
                mtm = (close - entry) * mult if direction == "LONG" else (entry - close) * mult
                t["last_mark_price"] = close
                t["unrealized_pnl_usd"] = mtm

        if closed:
            continue
    return trades


def performance_summary(trades: list[dict], strategy: str) -> dict:
    rows = [t for t in trades if t.get("strategy") == strategy and t.get("status") == "CLOSED"]
    if not rows:
        return {"trades": 0, "wins": 0, "win_rate": None, "net_pnl_usd": 0.0, "profit_factor": None, "expectancy_r": None, "max_drawdown_usd": 0.0, "brier_score": None, "calibration_error": None}
    pnls = [float(t.get("net_pnl_usd") or 0) for t in rows]
    rs = [float(t.get("r_multiple") or 0) for t in rows]
    wins = sum(1 for x in pnls if x > 0)
    gross_win = sum(x for x in pnls if x > 0)
    gross_loss = abs(sum(x for x in pnls if x < 0))
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for x in pnls:
        equity += x
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    probs = [float(t.get("forecast_probability")) for t in rows if t.get("forecast_probability") is not None]
    outcomes = [1.0 if float(t.get("net_pnl_usd") or 0) > 0 else 0.0 for t in rows if t.get("forecast_probability") is not None]
    brier = sum((p-y)**2 for p,y in zip(probs,outcomes))/len(probs) if probs else None
    cal_error = abs(sum(probs)/len(probs) - sum(outcomes)/len(outcomes)) if probs else None
    return {
        "trades": len(rows), "wins": wins, "win_rate": wins / len(rows), "net_pnl_usd": sum(pnls),
        "profit_factor": (gross_win / gross_loss if gross_loss > 0 else None),
        "expectancy_r": sum(rs) / len(rs), "max_drawdown_usd": max_dd,
        "brier_score": brier, "calibration_error": cal_error
    }
