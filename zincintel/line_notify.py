"""LINE Messaging API summaries. LINE Notify is retired; push API is used."""

from __future__ import annotations

import os

import requests


VALID_NOTIFICATION_MODES = {"daily", "alert_only", "disabled"}


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
    from .daily_brief import build_brief
    lines.extend(f"{i}. {item['title']}：{item['text']}" for i,item in enumerate(build_brief(snapshot),1))
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


def research_session_signature(snapshot: dict) -> tuple:
    """Return the validated market dates that make one daily digest unique."""
    research = snapshot.get("market_research", {})
    cross = research.get("cross_assets", {})
    return (
        research.get("close_series", {}).get("as_of"),
        research.get("shfe_zinc", {}).get("as_of"),
        cross.get("gold", {}).get("as_of"),
        cross.get("usdjpy", {}).get("as_of"),
        cross.get("dxy", {}).get("as_of"),
    )


def alert_market_keys(snapshot: dict, previous: dict) -> list[str]:
    """Select only material, newly observed changes for an afternoon alert."""
    current_markets = snapshot.get("decision_book", {}).get("markets", {})
    previous_markets = previous.get("decision_book", {}).get("markets", {})
    changed = []
    for key, current in current_markets.items():
        old = previous_markets.get(key, {})
        direction_changed = old.get("direction") not in (None, current.get("direction"))
        trigger_started = current.get("trigger_gate") == "TRIGGERED" and old.get("trigger_gate") != "TRIGGERED"
        data_failed = current.get("data_gate") not in (None, "PASS") and old.get("data_gate") != current.get("data_gate")
        if direction_changed or trigger_started or data_failed:
            changed.append(key)
    return changed


def notification_plan(snapshot: dict, previous: dict, mode: str) -> dict:
    """Make LINE delivery deterministic and suppress duplicate holiday digests."""
    mode = (mode or "disabled").strip().lower()
    if mode not in VALID_NOTIFICATION_MODES:
        raise ValueError(f"Unsupported LINE_NOTIFICATION_MODE: {mode}")
    if mode == "disabled":
        return {"daily": False, "alerts": []}
    alerts = alert_market_keys(snapshot, previous) if mode == "alert_only" else []
    daily = mode == "daily" and research_session_signature(snapshot) != research_session_signature(previous)
    return {"daily": daily, "alerts": alerts}


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
