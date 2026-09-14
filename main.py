from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from zincintel.china_tc import fetch_china_tc
from zincintel.config import load_settings
from zincintel.dashboard_v27 import build_dashboard_v27
from zincintel.data_governance import annotate_data_health, apply_last_known_good, core_data_gate
from zincintel.discord import send_discord
from zincintel.free_data import enrich_market_with_free_sources, update_close_history
from zincintel.free_mirrors import enrich_market_with_free_mirrors
from zincintel.indicators import add_close_indicators, add_indicators, latest_indicator_dict
from zincintel.market_research import describe_close_series
from zincintel.models import (
    event_overlay, macro_score, market_regime, market_structure_score, multi_horizon_scores,
    physical_score, procurement_metrics, smelter_score, strategy_recommendation,
    supply_demand_score, technical_score, weighted_score,
)
from zincintel.paper import empirical_stats, performance_summary, process_paper_trades, queue_trade_if_actionable
from zincintel.providers import fetch_macro, fetch_market_snapshot
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
    return out[~out.index.duplicated(keep="last")]


def _apply_china_tc_to_legacy_model_field(market: dict, china_tc: dict) -> dict:
    """Use China import weekly TC as the legacy smelter-economics TC only when no better TC source exists.

    Domestic China TC and annual benchmark remain separate and are never blended into tc_usd_t.
    """
    if market.get("tc_usd_t") is not None:
        return market
    imported = china_tc.get("import_weekly", {})
    value = imported.get("value")
    if value is None:
        return market
    market["tc_usd_t"] = value
    market.setdefault("field_sources", {})["tc_usd_t"] = {
        "provider": "smm_china_import_tc_weekly",
        "status": "PUBLIC_MARKET_WEEKLY",
        "as_of": imported.get("as_of"),
    }
    return market


def main() -> None:
    settings = load_settings()
    model_version = settings.get("model_version", "2.7.0")
    run_time = iso_now()
    run_date = datetime.now(timezone.utc).date().isoformat()

    proc_state = update_procurement_state(
        os.getenv("CURRENT_INVENTORY_T", ""),
        os.getenv("DEMAND_60D_T", "")
    )

    # Accuracy-first source priority:
    # licensed/official adapters -> official public LME -> public reference mirrors -> verified carry-forward.
    market = enrich_market_with_free_sources(fetch_market_snapshot())
    market, mirror_history, mirror_history_source = enrich_market_with_free_mirrors(market)

    china_tc = fetch_china_tc()
    market = _apply_china_tc_to_legacy_model_field(market, china_tc)

    # A temporary provider outage may reuse a prior verified value only inside an explicit freshness window.
    # The old as-of date and original provider are retained; nothing synthetic is created.
    market = apply_last_known_good(market)
    market = annotate_data_health(market)
    data_gate = core_data_gate(market)

    macro = fetch_macro(settings.get("macro_tickers", {}))
    events = read_json(DATA_DIR / "event_risk.json", [])
    ev_overlay = event_overlay(events)

    # This entry point builds the public Pages site. Never ingest private OHLC here,
    # even if a local file or legacy candle environment variable is present.
    daily_raw, candle_source = pd.DataFrame(), "PRIVATE_ONLY"
    h1_raw, candle_1h_source = pd.DataFrame(), "PRIVATE_ONLY"
    m15_raw, candle_15m_source = pd.DataFrame(), "PRIVATE_ONLY"
    saved_close_history, close_history_source = update_close_history(market)
    close_history = _merge_close_histories(saved_close_history, mirror_history)
    if not mirror_history.empty:
        close_history_source = mirror_history_source
    research_close = describe_close_series(mirror_history, mirror_history_source)

    daily = add_indicators(daily_raw) if not daily_raw.empty else pd.DataFrame()
    weekly = pd.DataFrame()
    if len(daily_raw) >= 60:
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
    candle_status = {
        "status": "COMPLETE_HISTORY" if len(daily_raw) >= 60 else "INSUFFICIENT_HISTORY" if not daily_raw.empty else "MISSING",
        "complete_sessions": int(len(daily_raw)),
        "minimum_sessions": 60,
        "last_complete_date": daily_raw.index[-1].date().isoformat() if not daily_raw.empty else None,
        "source": candle_source,
    }

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
        "core_data_gate": data_gate,
        "china_tc": china_tc,
        "macro": macro,
        "event_overlay": ev_overlay,
        "candle_sources": {"daily": candle_source, "1h": candle_1h_source, "15m": candle_15m_source, "close_history": close_history_source},
        "technical_mode": technical_mode,
        "daily_candle_status": candle_status,
        "market_research": {"close_series": research_close},
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
            "Accuracy and source traceability take priority over real-time freshness.",
            "No synthetic LME zinc OHLC, stock, TC or price is generated.",
            "China import TC, domestic TC and annual benchmark remain separate series.",
            "Close-only technical mode is analysis-only; paper execution requires true OHLC.",
            "Public procurement inputs remain masked by default.",
        ]
    }

    save_latest(snapshot)
    append_history({
        "run_time": run_time, "run_date": run_date, "model_version": model_version,
        "market_score": score, "market_regime": regime, "horizons": horizons,
        "lme_cash": market.get("lme_cash"), "lme_3m": market.get("lme_3m"),
        "inventory_t": market.get("lme_inventory_t"), "cancelled_warrants_t": market.get("cancelled_warrants_t"),
        "tc_usd_t": market.get("tc_usd_t"),
        "china_import_tc_usd_dmt": china_tc.get("primary_import_tc_usd_dmt"),
        "china_domestic_tc": china_tc.get("primary_domestic_tc"),
        "china_domestic_tc_unit": china_tc.get("primary_domestic_unit"),
        "annual_benchmark_tc_usd_dmt": china_tc.get("annual_benchmark", {}).get("value"),
        "premium_usd_t": market.get("physical_premium_usd_t"),
        "current_inventory_t": proc_state.get("current_inventory_t"), "demand_60d_t": proc_state.get("demand_60d_t"),
        "coverage_days": procurement.get("coverage_days"), "procurement_action": procurement.get("action"),
        "market_confidence": market_quality.get("confidence"), "procurement_confidence": proc_quality.get("confidence"),
        "core_data_gate": data_gate.get("status"),
    })
    append_signal({
        "run_time": run_time, "run_date": run_date, "model_version": model_version,
        "market_score": score, "market_regime": regime,
        "conservative_action": investment.get("conservative", {}).get("action"),
        "aggressive_action": investment.get("aggressive", {}).get("action"),
        "conservative_probability": investment.get("conservative", {}).get("probability", {}).get("p_profit"),
        "aggressive_probability": investment.get("aggressive", {}).get("probability", {}).get("p_profit"),
        "data_confidence": market_quality.get("confidence"), "event_overlay": ev_overlay.get("level"),
        "core_data_gate": data_gate.get("status"),
    })

    out = build_dashboard_v27(snapshot, {"daily": daily, "weekly": weekly, "1h": h1_raw, "15m": m15_raw}, trades, perf)
    # The chart digest is known only after rendering and must travel with the
    # exact snapshot used by the production verifier.
    save_latest(snapshot)
    print(f"Dashboard written to {out}")
    print(f"Core data gate: {data_gate['status']} | usable={data_gate['usable_core']} | stale={data_gate['stale_core']} | missing={data_gate['missing_core']}")

    if os.getenv("DISCORD_WEBHOOK_URL"):
        try:
            send_discord(snapshot)
            print("Discord sent")
        except Exception as exc:
            print(f"Discord error: {exc}")


if __name__ == "__main__":
    main()
