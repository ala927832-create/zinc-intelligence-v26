"""Multi-page research UI in the existing ivory/navy visual language."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .utils import PUBLIC_DIR


def _e(value): return html.escape(str(value if value is not None else "—"))


STYLE = """
:root{--ivory:#f4f1e9;--white:#fff;--navy:#0b2f4f;--ink:#153552;--muted:#687e90;--line:#d5dde3;--teal:#087b70;--orange:#c8783d;--red:#d94a4f}
*{box-sizing:border-box}body{margin:0;background:var(--ivory);color:var(--ink);font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}.head{background:linear-gradient(112deg,#0a2a48,#123e61);color:#fff;border-bottom:3px solid var(--orange);padding:18px 24px}.head h1{font:700 29px Georgia,serif;margin:0}.head small{color:#d4e0e8}.shell{display:grid;grid-template-columns:190px minmax(0,1fr);max-width:1760px;margin:auto}.nav{min-height:100vh;background:#fbfaf6;border-right:1px solid var(--line);padding:16px 10px}.nav a{display:block;padding:11px;color:#244966;text-decoration:none;border-left:3px solid transparent}.nav a.on,.nav a:hover{background:var(--navy);color:#fff;border-left-color:var(--orange)}main{padding:16px;min-width:0}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:10px}.card{grid-column:span 12;background:#fff;border:1px solid var(--line);border-radius:7px;padding:15px;box-shadow:0 3px 12px rgba(18,50,76,.05)}.half{grid-column:span 6}.third{grid-column:span 4}h2{font:700 16px Georgia,serif;margin:0 0 10px}.pill{display:inline-block;border-radius:99px;padding:4px 9px;font-size:11px;background:#e8edf0}.good{background:#dcf1ec;color:#086d63}.wait{background:#fae9d9;color:#8a552e}.bad{background:#fae0e2;color:#a7333a}.price{font-size:25px;font-weight:800}.muted{color:var(--muted)}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #e1e6e9;padding:8px;text-align:left;vertical-align:top}th{background:#f3f5f4}.gates{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.gate{background:#f8f6f0;border:1px solid var(--line);padding:9px;border-radius:5px}.gate b,.gate span{display:block}.gate span{font-size:11px;color:var(--muted)}.rules{border-left:4px solid var(--orange);padding:12px;background:#fff8f1}.dark{background:#0b2f4f;color:#fff}.dark .muted{color:#bed0dc}.chart{height:180px;background:linear-gradient(#103c60,#092d4b);border-radius:6px;display:grid;place-items:center;color:#bed0dc}.journal{border-left:3px solid var(--teal);padding-left:12px}.footer{padding:25px;color:var(--muted);text-align:center}@media(max-width:900px){.shell{grid-template-columns:1fr}.nav{min-height:0;display:flex;overflow:auto}.nav a{white-space:nowrap}.half,.third{grid-column:span 12}.gates{grid-template-columns:repeat(2,1fr)}}
"""


def _nav(active: str) -> str:
    items = [("index.html","Today"),("markets.html","Markets"),("radar.html","Radar"),("journal.html","Journal")]
    return "<nav class='nav'>" + "".join(f"<a class='{'on' if label==active else ''}' href='{url}'>{label}</a>" for url,label in items) + "</nav>"


def _page(title: str, active: str, body: str, run_date: str) -> str:
    return f"<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_e(title)}</title><style>{STYLE}</style></head><body><header class='head'><h1>GLOBAL MACRO RESEARCH DESK</h1><small>{_e(run_date)} · delayed research data · execution requires live quote</small></header><div class='shell'>{_nav(active)}<main>{body}<div class='footer'>RESEARCH ONLY · No data, no signal · No trigger, no order · Actual R:R must be ≥ 1:2</div></main></div></body></html>"


def _market_card(key: str, plan: dict, series: dict) -> str:
    ref = plan.get("reference", {})
    daily = plan.get("daily_plan", {})
    decision = plan.get("decision", "NO_TRADE")
    klass = "good" if decision == "READY" else "wait" if decision == "WAIT_FOR_TRIGGER" else "bad"
    gates = [
        ("1 DATA",plan.get("data_gate")),("2 REGIME",plan.get("regime_gate")),
        ("3 STRATEGY",plan.get("strategy_gate")),("4 TRIGGER",plan.get("trigger_gate")),
        ("5 EXECUTION",plan.get("execution_gate")),("6 REVIEW",decision),
    ]
    gate_html = "".join(f"<div class='gate'><b>{_e(n)}</b><span>{_e(v)}</span></div>" for n,v in gates)
    reasons = "".join(f"<li>{_e(x)}</li>" for x in plan.get("no_trade_reasons", [])) or "<li>None</li>"
    plan_rows = "".join(f"<tr><td>{_e(k.replace('_',' ').title())}</td><td>{_e(v)}</td></tr>" for k,v in daily.items()) or "<tr><td colspan='2'>Blocked: no compliant daily trade plan.</td></tr>"
    close = ref.get("close") or series.get("latest_close")
    tv = {"lme_zinc":"LME:ZNC1!","shfe_zinc":"SHFE:ZN1!","gold":"COMEX:GC1!",
          "gold_spot":"OANDA:XAUUSD","usdjpy":"FX:USDJPY","dxy":"TVC:DXY"}.get(key)
    tv_link = f" · <a href='https://www.tradingview.com/chart/?symbol={_e(tv)}' target='_blank' rel='noopener'>TradingView人工比對 ↗</a>" if tv else ""
    source_line = f"{_e(series.get('source'))} · {_e(series.get('source_grade'))} · {_e(series.get('market_identity'))} · {_e(series.get('retrieval_status','CURRENT_OR_MISSING'))}{tv_link}"
    deviation = series.get("cross_source_deviation_pct")
    deviation_line = f"<p class='muted'>Cross-source deviation: {_e(deviation)}%</p>" if deviation is not None else ""
    return f"<section class='card' id='{_e(key)}'><h2>{_e(plan.get('market',key))}</h2><span class='pill {klass}'>{_e(decision)}</span> <span class='pill'>{_e(plan.get('direction'))}</span><p><span class='price'>{_e(close)}</span> <span class='muted'>{_e(series.get('unit',''))} · As of {_e(plan.get('as_of') or series.get('as_of'))}</span></p><p class='muted'>{source_line}</p>{deviation_line}<div class='gates'>{gate_html}</div><div class='grid' style='margin-top:10px'><div class='card half'><h2>Daily planning layer</h2><table>{plan_rows}</table></div><div class='card half dark'><h2>Execution-time layer</h2><p>Bid / Ask · Spread · Actual fill · Slippage · Actual R:R · Contract quantity</p><p class='muted'>Status: {_e(plan.get('execution_check',{}).get('status'))}</p><h2>No-Trade / waiting reasons</h2><ul>{reasons}</ul></div></div></section>"


def build_research_pages(snapshot: dict) -> list[Path]:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    date = snapshot.get("run_date", "—")
    research = snapshot.get("market_research", {})
    decisions = snapshot.get("decision_book", {}).get("markets", {})
    series = {"lme_zinc": research.get("close_series", {}), "shfe_zinc": research.get("shfe_zinc", {}), **research.get("cross_assets", {})}
    market_body = "<div class='rules'><b>Execution constitution</b><br>No complete data → no signal; no trigger → no order; no acceptable Bid/Ask → not executable; Actual R:R below 1:2 → reject; unclear structure → No Trade.</div><div class='grid' style='margin-top:10px'>" + "".join(_market_card(k, p, series.get(k, {})) for k,p in decisions.items()) + "</div>"
    radar_rows = "".join(f"<tr><td>{_e(p.get('market',k))}</td><td>{_e(p.get('direction'))}</td><td>{_e(p.get('evidence_alignment'))}</td><td>{_e(p.get('decision'))}</td><td>{_e('; '.join(p.get('no_trade_reasons',[])[:1]))}</td></tr>" for k,p in decisions.items())
    radar_body = f"<div class='grid'><section class='card'><h2>Cross-market radar</h2><table><tr><th>Market</th><th>Direction</th><th>Evidence</th><th>State</th><th>Primary caution</th></tr>{radar_rows}</table></section><section class='card half'><h2>Macro context</h2><p>DXY diagnoses the common pricing wind; Gold and JPY are not assumed to be synchronized safe havens. Zinc must also confirm inventory, TC and China demand evidence.</p></section><section class='card half'><h2>Event discipline</h2><p>Before CPI, payrolls, FOMC/BoJ or major geopolitical events: reduce planned risk, reject wide spreads and do not chase the first breakout bar.</p></section></div>"
    journal_items = "".join(f"<div class='journal'><h2>{_e(p.get('market',k))} · {_e(p.get('decision'))}</h2><p>Direction: {_e(p.get('direction'))}. Evidence: {_e(p.get('evidence_alignment'))}. Next observation: {_e((p.get('no_trade_reasons') or ['Review trigger and execution quote.'])[0])}</p></div>" for k,p in decisions.items())
    journal_body = f"<div class='grid'><section class='card'><h2>Daily research journal</h2><p class='muted'>Facts → interpretation → invalidation → next observation. Generated from the same snapshot as the charts.</p>{journal_items}</section><section class='card'><h2>Long-term learning record</h2><p>Record whether the setup triggered, whether bid/ask was acceptable, actual fill/slippage, Actual R:R and the invalidation outcome. Do not score untriggered plans as wins or losses.</p></section></div>"
    health = snapshot.get("market", {}).get("data_health", {})
    status_body = f"<div class='grid'><section class='card'><h2>Data Health · internal operations view</h2><p>This page is intentionally absent from normal navigation.</p><pre>{_e(json.dumps(health, ensure_ascii=False, indent=2))}</pre></section></div>"
    pages = {
        "markets.html": _page("Markets · Global Macro Research", "Markets", market_body, date),
        "radar.html": _page("Radar · Global Macro Research", "Radar", radar_body, date),
        "journal.html": _page("Journal · Global Macro Research", "Journal", journal_body, date),
        "system-status.html": _page("System Status", "", status_body, date),
    }
    out = []
    for name, content in pages.items():
        path = PUBLIC_DIR / name
        path.write_text(content, encoding="utf-8")
        out.append(path)
    return out
