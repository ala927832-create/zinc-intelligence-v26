from __future__ import annotations

import os
import requests


def send_discord(snapshot: dict) -> bool:
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        return False
    proc = snapshot.get("procurement", {})
    inv = snapshot.get("investment", {})
    con, agg = inv.get("conservative", {}), inv.get("aggressive", {})
    def p(strategy):
        x = strategy.get("probability", {}).get("p_profit")
        return "—" if x is None else f"{x*100:.1f}%"
    payload = {
        "username": "Zinc Intelligence V2.6",
        "embeds": [
            {
                "title": f"Market {snapshot.get('market_regime')} · 20D {snapshot.get('horizons',{}).get('20D','—')}",
                "description": "One Market View → Procurement + Paper Research",
                "color": 3066993,
                "fields": [
                    {"name":"🏭 Procurement","value":f"Action: **{proc.get('action','INPUT REQUIRED')}**\nCoverage: {proc.get('coverage_days','—')} d\nSuggested cover: {proc.get('suggested_cover_t','—')} t", "inline":True},
                    {"name":"🛡 Conservative (Paper)","value":f"{con.get('action','NO SIGNAL')}\nP(profit): {p(con)}\nEV: {con.get('expected_value_usd','—')} USD", "inline":True},
                    {"name":"🚀 Aggressive (Paper)","value":f"{agg.get('action','NO SIGNAL')}\nP(profit): {p(agg)}\nEV: {agg.get('expected_value_usd','—')} USD", "inline":True},
                ]
            },
            {
                "title": "Data & Risk",
                "color": 16753920,
                "fields": [
                    {"name":"Market confidence","value":f"{snapshot.get('market_quality',{}).get('confidence','—')}/100", "inline":True},
                    {"name":"Procurement input","value":snapshot.get('procurement_quality',{}).get('status','—'), "inline":True},
                    {"name":"Event overlay","value":snapshot.get('event_overlay',{}).get('level','NONE'), "inline":True},
                ],
                "footer":{"text":"Investment module is paper simulation only."}
            }
        ]
    }
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return True
