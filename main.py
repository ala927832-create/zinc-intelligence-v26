from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from zincintel.config import load_settings
from zincintel.dashboard import build_dashboard
from zincintel.discord import send_discord
from zincintel.indicators import add_indicators, latest_indicator_dict
from zincintel.models import (
    event_overlay, macro_score, market_regime, market_structure_score, multi_horizon_scores,
    physical_score, procurement_metrics, smelter_score, strategy_recommendation,
    supply_demand_score, technical_score, weighted_score,
)
from zincintel.paper import empirical_stats, performance_summary, process_paper_trades, queue_trade_if_actionable
from zincintel.providers import fetch_macro, fetch_market_snapshot, load_candles
from zincintel.quality import assess_market_quality, procurement_quality
from zincintel.state import (
    append_history, append_signal, load_trades, save_latest, save_trades, update_procurement_state,
)
from zincintel.utils import DATA_DIR, iso_now, read_json


def main() -> None:
    settings = load_settings()
    model_version = settings.get("model_version", "2.6.0")
    run_time = iso_now()
    run_date = datetime.now(timezone.utc).date().isoformat()

    # Procurement state: blank inputs intentionally carry forward prior valid values.
    proc_state = update_procurement_state(
        os.getenv("CURRENT_INVENTORY_T", ""),
        os.getenv("DEMAND_60D_T", "")
    )

    market = fetch_market_snapshot()
    macro = fetch_macro(settings.get("macro_tickers", {}))
    events = read_json(DATA_DIR / "event_risk.json", [])
    ev_overlay = event_overlay(events)

    daily_raw, candle_source = load_candles("daily")
    h1_raw, candle_1h_source = load_candles("1h")
    m15_raw, candle_15m_source = load_candles("15m")
    daily = add_indicators(daily_raw) if not daily_raw.empty else pd.DataFrame()
    weekly = pd.DataFrame()
    if not daily_raw.empty:
        weekly = daily_raw.resample("W-FRI").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna(subset=["Open","High","Low","Close"])
        weekly = add_indicators(weekly)
    indicators = latest_indicator_dict(daily)

    market_quality = assess_market_quality(market, not daily.empty, macro, ev_overlay)
    proc_quality = procurement_quality(proc_state, settings)

    components = {
        "market_structure": market_structure_score(market),
        "supply_demand": supply_demand_score(market),
        "smelter_economics": smelter_score(market),
        "physical_market": physical_score(market),
        "macro": macro_score(macro),
        "technical": technical_score(indicators),
    }
    score, coverage = weighted_score(components, settings["market_weights"])
    regime = market_regime(score) if market_quality["confidence"] >= 55 and coverage >= 0.50 else "NO_DATA"
    horizons = multi_horizon_scores(score, components.get("technical"))
    procurement = procurement_metrics(proc_state, regime, settings)

    trades = load_trades()
    # First update any older pending/open paper trades using the newly available bar(s).
    trades = process_paper_trades(trades, daily, settings)

    investment = {}
    for name in ["conservative", "aggressive"]:
        empirical = empirical_stats(trades, name)
        rec = strategy_recommendation(
            name=name,
            horizon_score=horizons.get("20D"),
            data_conf=max(0.0, market_quality["confidence"] - ev_overlay["confidence_penalty"]),
            ind=indicators,
            settings=settings,
            empirical=empirical,
        )
        investment[name] = rec
        # Queue only; actual simulated entry occurs on the next available daily bar.
        trades = queue_trade_if_actionable(
            trades, rec, daily.index[-1].isoformat() if not daily.empty else run_time,
            model_version, regime, market_quality["confidence"]
        )

    save_trades(trades)
    perf = {name: performance_summary(trades, name) for name in ["conservative", "aggressive"]}

    public_include_private = os.getenv("PUBLIC_DASHBOARD_INCLUDE_PRIVATE", "").strip().lower() in {"1","true","yes"}
    if not public_include_private:
        public_include_private = bool(settings.get("privacy", {}).get("public_dashboard_include_procurement_details", False))

    snapshot = {
        "run_time": run_time,
        "run_date": run_date,
        "model_version": model_version,
        "market": market,
        "macro": macro,
        "event_overlay": ev_overlay,
        "candle_sources": {"daily": candle_source, "1h": candle_1h_source, "15m": candle_15m_source},
        "indicators": indicators,
        "components": components,
        "component_coverage": coverage,
        "market_score": score,
        "market_regime": regime,
        "horizons": horizons,
        "market_quality": market_quality,
        "procurement_state": proc_state,
        "procurement_quality": proc_quality,
        "procurement": procurement,
        "privacy": {"public_dashboard_include_private": public_include_private},
        "investment": investment,
        "performance": perf,
        "notes": [
            "No synthetic LME zinc OHLC is generated.",
            "Investment book is paper-trading research only; no broker/order execution is included.",
            "Event Risk Overlay reduces confidence/raises caution rather than mechanically forcing price direction."
        ]
    }

    save_latest(snapshot)
    append_history({
        "run_time": run_time, "run_date": run_date, "model_version": model_version,
        "market_score": score, "market_regime": regime, "horizons": horizons,
        "lme_cash": market.get("lme_cash"), "lme_3m": market.get("lme_3m"),
        "inventory_t": market.get("lme_inventory_t"), "cancelled_warrants_t": market.get("cancelled_warrants_t"),
        "tc_usd_t": market.get("tc_usd_t"), "premium_usd_t": market.get("physical_premium_usd_t"),
        "current_inventory_t": proc_state.get("current_inventory_t"), "demand_60d_t": proc_state.get("demand_60d_t"),
        "coverage_days": procurement.get("coverage_days"), "procurement_action": procurement.get("action"),
        "market_confidence": market_quality.get("confidence"), "procurement_confidence": proc_quality.get("confidence")
    })
    append_signal({
        "run_time": run_time, "run_date": run_date, "model_version": model_version,
        "market_score": score, "market_regime": regime,
        "conservative_action": investment.get("conservative", {}).get("action"),
        "aggressive_action": investment.get("aggressive", {}).get("action"),
        "conservative_probability": investment.get("conservative", {}).get("probability", {}).get("p_profit"),
        "aggressive_probability": investment.get("aggressive", {}).get("probability", {}).get("p_profit"),
        "data_confidence": market_quality.get("confidence"), "event_overlay": ev_overlay.get("level")
    })

    out = build_dashboard(snapshot, {"daily": daily, "weekly": weekly, "1h": h1_raw, "15m": m15_raw}, trades, perf)
    print(f"Dashboard written to {out}")
    if os.getenv("DISCORD_WEBHOOK_URL"):
        try:
            send_discord(snapshot)
            print("Discord sent")
        except Exception as exc:
            print(f"Discord error: {exc}")


if __name__ == "__main__":
    main()
