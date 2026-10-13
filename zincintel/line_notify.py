"""LINE Messaging API summaries. LINE Notify is retired; push API is used."""

from __future__ import annotations

import os

import requests


def _price(value, digits=2):
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def build_daily_message(snapshot: dict) -> str:
    research = snapshot.get("market_research", {})
    close = research.get("close_series", {})
    shfe = research.get("shfe_zinc", {})
    cross = research.get("cross_assets", {})
    decisions = snapshot.get("decision_book", {}).get("markets", {})
    lines = [f"市場研究日報｜{snapshot.get('run_date','—')}"]
    rows = [
        ("LME Zn 3M Close", close.get("latest_close"), "USD/t", decisions.get("lme_zinc", {})),
        ("SHFE Zn", shfe.get("latest_close"), "CNY/t", decisions.get("shfe_zinc", {})),
    ]
    gold_key = "gold" if cross.get("gold", {}).get("status") == "AVAILABLE" else "gold_spot"
    usd_key = "dxy" if cross.get("dxy", {}).get("status") == "AVAILABLE" else "usd_basket"
    for key, label in ((gold_key, "Gold"), ("usdjpy", "USD/JPY"), (usd_key, "DXY" if usd_key == "dxy" else "USD Basket (not DXY)")):
        item = cross.get(key, {})
        rows.append((label, item.get("latest_session", {}).get("close"), item.get("unit", ""), decisions.get(key, {})))
    for label, value, unit, decision in rows:
        lines.append(f"{label}: {_price(value)} {unit}｜{decision.get('direction','—')}｜{decision.get('decision','NO_TRADE')}")
    lines.extend([
        "執行規則：沒有 Trigger 不下單；沒有可接受 Bid/Ask 不承認可成交。",
        "完整價位、T1/T2 與 No-Trade 理由請見研究面板。",
    ])
    return "\n".join(lines)


def build_alert_message(snapshot: dict, changed_markets: list[str]) -> str:
    decisions = snapshot.get("decision_book", {}).get("markets", {})
    lines = [f"市場異動警示｜{snapshot.get('run_date','—')}"]
    for key in changed_markets:
        item = decisions.get(key, {})
        lines.append(f"{item.get('market',key)}: {item.get('direction','—')} / {item.get('decision','NO_TRADE')}")
        reasons = item.get("no_trade_reasons", [])
        if reasons:
            lines.append(f"注意：{reasons[0]}")
    lines.append("警示是條件變化，不是成交確認；下單前仍須核對 Bid/Ask 與 Actual R:R。")
    return "\n".join(lines)


def send_line_text(text: str) -> bool:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = os.getenv("LINE_USER_ID", "").strip()
    if not token or not user_id:
        return False
    response = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"to": user_id, "messages": [{"type": "text", "text": text[:5000]}]}, timeout=15,
    )
    response.raise_for_status()
    return True
