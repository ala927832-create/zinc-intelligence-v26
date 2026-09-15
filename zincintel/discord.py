from __future__ import annotations

import os
import requests


def _number(value, digits=2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def build_discord_payload(snapshot: dict) -> dict:
    close = snapshot.get("market_research", {}).get("close_series", {})
    trend = close.get("trend", {})
    reasons = "\n".join(f"• {item}" for item in trend.get("reasons", [])[:4]) or "• 資料不足"
    dashboard_url = os.getenv("PUBLIC_DASHBOARD_URL", "https://ala927832-create.github.io/zinc-intelligence-v26/")
    return {
        "username": "Zinc Intelligence Research",
        "embeds": [
            {
                "title": f"LME Zinc 3M Close Research · {trend.get('regime','INSUFFICIENT_DATA')}",
                "description": "Close-only historical research · not a trading instruction",
                "color": 3066993,
                "fields": [
                    {"name":"Close / moving averages","value":f"Close {_number(close.get('latest_close'))} USD/t\nSMA14 {_number(close.get('sma_14'))} · SMA30 {_number(close.get('sma_30'))}\nEMA20 {_number(close.get('ema_20'))} · RSI14 {_number(close.get('rsi_14'))}", "inline":False},
                    {"name":"Trend","value":f"Score {_number(trend.get('score'),0)}/100\nPersistence {trend.get('persistence_days',0)} trading days\nRisk {trend.get('risk_level','—')}", "inline":True},
                    {"name":"Data","value":f"Confidence {trend.get('data_confidence','LOW')}\nValid {close.get('observations',0)} sessions\nAs of {close.get('as_of','—')}", "inline":True},
                    {"name":"Reasons","value":reasons, "inline":False},
                ]
            },
            {
                "title": "Source & verification",
                "color": 16753920,
                "fields": [
                    {"name":"Provider","value":str(close.get('source') or '—'), "inline":True},
                    {"name":"Grade","value":str(close.get('source_grade') or '—'), "inline":True},
                    {"name":"Coverage","value":f"{close.get('coverage_start','—')} → {close.get('coverage_end','—')}", "inline":False},
                    {"name":"Dashboard","value":dashboard_url, "inline":False},
                ],
                "footer":{"text":"No OHLC, ATR, private inventory, forecast probability or expected profit is included."}
            }
        ]
    }


def send_discord(snapshot: dict) -> bool:
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        return False
    payload = build_discord_payload(snapshot)
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return True
