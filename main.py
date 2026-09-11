from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from zincintel.config import load_settings
from zincintel.dashboard import build_dashboard
from zincintel.discord import send_discord
from zincintel.free_data import enrich_market_with_free_sources, update_close_history
from zincintel.free_mirrors import enrich_market_with_free_mirrors
from zincintel.indicators import add_close_indicators, add_indicators, latest_indicator_dict
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


def _merge_close_histories(primary: pd.DataFrame, mirror: pd.DataFrame) -> pd.DataFrame:
    frames = [x[["Close"]].copy() for x in [mirror, primary] if x is not None and not x.empty and "Close" in x.columns]
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


def main() -> None:
    settings = load_settings()
    model_version = settings.get("model_version", "2.6.3")
    run_time = iso_now()
    run_date = datetime.now(timezone.utc).date().isoformat()

    proc_state = update_procurement_state(
        os.getenv("CURRENT_INVENTORY_T", ""),
        os.getenv("DEMAND_60D_T", "")
    )

    # Source priority:
    # licensed/API/manual adapter chain -> LME public page -> robust public mirrors.
    # Each layer fills only missing fields and leaves provenance in field_sources.
    market = enrich_market_with_free_sources(fetch_market_snapshot())
    market, mirror_history, mirror_history_source = enrich_market_with_free_mirrors(market)

    macro = fetch_macro(settings.get("macro_tickers", {}))
    events = read_json(DATA_DIR / "event_risk.json", [])
    ev_overlay = event_overlay(events)

    daily_raw, candle_source = load_candles("daily")
    h1_raw, candle_1h_source = load_candles("1h")
    m15_raw, candle_15m_source = load_candles("15m")
    saved_close_history, close_history_source = update_close_history(market)
    close_history = _merge_close_histories(saved_close_history, mirror_history)
    if not mirror_history.empty:
        close_history_source = mirror_history_source

    daily = add_indicators(daily_raw) if not daily_raw.empty else pd.DataFrame()
    weekly = pd.DataFrame()
    if not daily_raw.empty:
        weekly = daily_raw.resample("W-FRI").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna(subset=["Open","High","Low","Close"])
        weekly = add_indicators(weekly)
        technical_df = daily
        technical_mode = "FULL_OHLC"
    elif not close_history.empty:
        technical_df = add_close_indicators(close_history)
        technical_mode = "CLOSE_ONLY"
    else:
        technical_df = pd.DataFrame()
        technical_mode = "MISSING"
    indicators = latest_indicator_dict(technical_df)

    market_quality = assess_market_quality(market, technical_mode, macro, ev_overlay)
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
    min_coverage = float(settings.get("data_quality", {}).get("min_component_coverage_for_regime", 0.35))
    regime = market_regime(score) if market_quality["confidence"] >= 55 and coverage >= min_coverage else "NO_DATA"
    horizons = multi_horizon_scores(score, components.get("technical"))
    procurement = procurement_metrics(proc_state, regime, settings)

    trades = load_trades()
    # Paper-trade execution requires true OHLC. Close-only mode remains analysis-only.
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
        if technical_mode != "FULL_OHLC" and rec.get("action") not in {"NO_SIGNAL", "NO_TRADE"}:
            rec["action"] = "ANALYSIS_ONLY"
            rec["reason"] = "close-only technical mode: true OHLC/ATR required for paper execution"
        investment[name] = rec
        if technical_mode == "FULL_OHLC":
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
        "candle_sources": {"daily": candle_source, "1h": candle_1h_source, "15m": candle_15m_source, "close_history": close_history_source},
        "technical_mode": technical_mode,
        "free_close_history_points": int(len(close_history)),
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
        "free_data_limitations": market.get("free_data_limitations", []),
        "notes": [
            "No synthetic LME zinc OHLC is generated.",
            "Free/public mirror data can be day-delayed and is tagged with source/as-of metadata.",
            "Close-only technical mode is analysis-only; paper execution still requires true OHLC.",
            "Investment book is paper-trading research only; no broker/order execution is included.",
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
