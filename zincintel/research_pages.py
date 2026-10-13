"""Multi-page, auditable public research UI in the ivory/navy visual language."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .utils import PUBLIC_DIR


def _e(value):
    return html.escape(str(value if value is not None else "—"))


STYLE = """
:root{--ivory:#f4f1e9;--white:#fff;--navy:#0b2f4f;--ink:#153552;--muted:#687e90;--line:#d5dde3;--teal:#087b70;--orange:#c8783d;--red:#d94a4f}
*{box-sizing:border-box}body{margin:0;background:var(--ivory);color:var(--ink);font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}.head{background:linear-gradient(112deg,#0a2a48,#123e61);color:#fff;border-bottom:3px solid var(--orange);padding:18px 24px}.head h1{font:700 29px Georgia,serif;margin:0}.head small{color:#d4e0e8}.shell{display:grid;grid-template-columns:190px minmax(0,1fr);max-width:1760px;margin:auto}.nav{min-height:100vh;background:#fbfaf6;border-right:1px solid var(--line);padding:16px 10px}.nav a{display:block;padding:11px;color:#244966;text-decoration:none;border-left:3px solid transparent}.nav a.on,.nav a:hover{background:var(--navy);color:#fff;border-left-color:var(--orange)}main{padding:16px;min-width:0}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:10px}.card{grid-column:span 12;background:#fff;border:1px solid var(--line);border-radius:7px;padding:15px;box-shadow:0 3px 12px rgba(18,50,76,.05)}.half{grid-column:span 6}h2{font:700 16px Georgia,serif;margin:0 0 10px}.pill{display:inline-block;border-radius:99px;padding:4px 9px;font-size:11px;background:#e8edf0}.good{background:#dcf1ec;color:#086d63}.wait{background:#fae9d9;color:#8a552e}.bad{background:#fae0e2;color:#a7333a}.price{font-size:25px;font-weight:800}.muted{color:var(--muted)}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #e1e6e9;padding:8px;text-align:left;vertical-align:top}th{background:#f3f5f4}.gates{display:grid;grid-template-columns:repeat(6,1fr);gap:7px}.gate{background:#f8f6f0;border:1px solid var(--line);padding:9px;border-radius:5px}.gate b,.gate span{display:block}.gate span{font-size:11px;color:var(--muted)}.rules{border-left:4px solid var(--orange);padding:12px;background:#fff8f1}.dark{background:#0b2f4f;color:#fff}.dark .muted{color:#bed0dc}.chart{height:190px;background:linear-gradient(#103c60,#092d4b);border-radius:6px;padding:8px;color:#bed0dc}.chart svg{width:100%;height:100%}.journal{border-left:3px solid var(--teal);padding-left:12px}.footer{padding:25px;color:var(--muted);text-align:center}.status-ok{color:var(--teal);font-weight:700}.status-missing{color:var(--red);font-weight:700}.audit td:first-child{width:32%;font-weight:700}.market-head{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}.market-meta{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:8px;margin:10px 0}.market-meta div{padding:8px;background:#f7f6f2;border:1px solid var(--line);border-radius:5px}.market-meta span{display:block;color:var(--muted);font-size:11px}.primary{border-left:5px solid var(--teal)}@media(max-width:900px){.shell{grid-template-columns:1fr}.nav{min-height:0;display:flex;overflow:auto}.nav a{white-space:nowrap}.half{grid-column:span 12}.gates,.market-meta{grid-template-columns:repeat(2,1fr)}}
"""


def _nav(active: str) -> str:
    items = [("index.html", "Today"), ("markets.html", "Markets"),
             ("radar.html", "Radar"), ("journal.html", "Journal")]
    return "<nav class='nav'>" + "".join(
        f"<a class='{'on' if label == active else ''}' href='{url}'>{label}</a>"
        for url, label in items) + "</nav>"


def _page(title: str, active: str, body: str, run_date: str) -> str:
    return f"<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_e(title)}</title><style>{STYLE}</style></head><body><header class='head'><h1>GLOBAL MACRO RESEARCH DESK</h1><small>{_e(run_date)} · delayed research data · execution requires live quote</small></header><div class='shell'>{_nav(active)}<main>{body}<div class='footer'>RESEARCH ONLY · No data, no signal · No trigger, no order · Actual R:R must be ≥ 1:2</div></main></div></body></html>"


def _sparkline(series: dict) -> str:
    points = []
    for item in series.get("chart_points", [])[-120:]:
        try:
            points.append((str(item.get("date", "")), float(item.get("close"))))
        except (TypeError, ValueError):
            continue
    if len(points) < 2:
        return "<div class='chart'>Validated chart data unavailable.</div>"
    values = [item[1] for item in points]
    low, high = min(values), max(values)
    span = high - low or 1
    coords = " ".join(
        f"{20 + i * 760 / (len(points)-1):.1f},{165 - (value-low)*130/span:.1f}"
        for i, (_, value) in enumerate(points))
    ticks = []
    for index in sorted({0, len(points)//2, len(points)-1}):
        x = 20 + index * 760 / (len(points)-1)
        ticks.append(f"<text x='{x:.1f}' y='184' fill='#bed0dc' font-size='11' text-anchor='middle'>{_e(points[index][0])}</text>")
    return ("<div class='chart'><svg viewBox='0 0 800 190' role='img' aria-label='Validated close history'>"
            "<line x1='20' y1='35' x2='780' y2='35' stroke='#315775'/><line x1='20' y1='165' x2='780' y2='165' stroke='#315775'/>"
            f"<polyline points='{coords}' fill='none' stroke='#61dbc3' stroke-width='2.5'/><text x='25' y='25' fill='#bed0dc' font-size='11'>{high:.2f}</text>"
            f"<text x='25' y='160' fill='#bed0dc' font-size='11'>{low:.2f}</text>{''.join(ticks)}</svg></div>")


def _format_audit(value) -> str:
    if isinstance(value, dict):
        return " · ".join(f"{_e(key)}: {_e(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "；".join(_e(item) for item in value)
    return _e(value)


def _market_card(key: str, plan: dict, series: dict) -> str:
    reference = plan.get("reference", {})
    daily = plan.get("daily_plan", {})
    decision = plan.get("decision", "NO_TRADE")
    klass = "good" if decision == "READY" else "wait" if decision == "WAIT_FOR_TRIGGER" else "bad"
    gates = [("1 DATA", plan.get("data_gate")), ("2 REGIME", plan.get("regime_gate")),
             ("3 STRATEGY", plan.get("strategy_gate")), ("4 TRIGGER", plan.get("trigger_gate")),
             ("5 EXECUTION", plan.get("execution_gate")), ("6 REVIEW", decision)]
    gate_html = "".join(f"<div class='gate'><b>{_e(name)}</b><span>{_e(value)}</span></div>" for name, value in gates)
    reasons = "".join(f"<li>{_e(item)}</li>" for item in plan.get("no_trade_reasons", [])) or "<li>None</li>"
    plan_rows = "".join(f"<tr><td>{_e(name.replace('_', ' ').title())}</td><td>{_e(value)}</td></tr>" for name, value in daily.items()) or "<tr><td colspan='2'>Blocked: no compliant daily trade plan.</td></tr>"
    headline = reference.get("cash") if key == "lme_zinc" else (reference.get("close") or series.get("latest_close"))
    tv = {"lme_zinc": "LME:ZNC1!", "shfe_zinc": "SHFE:ZN1!", "gold": "COMEX:GC1!",
          "gold_spot": "OANDA:XAUUSD", "usdjpy": "FX:USDJPY", "dxy": "TVC:DXY"}.get(key)
    tv_link = f" · <a href='https://www.tradingview.com/chart/?symbol={_e(tv)}' target='_blank' rel='noopener'>TradingView人工比對 ↗</a>" if tv else ""
    identity = series.get("market_identity") or ("LME Cash headline; 3M public technical reference" if key == "lme_zinc" else series.get("market") or series.get("symbol"))
    source_line = f"{_e(series.get('source'))} · {_e(series.get('source_grade'))} · {_e(identity)} · {_e(series.get('retrieval_status', 'CURRENT_OR_MISSING'))}{tv_link}"
    evidence_rows = "".join(
        f"<tr><td>{_e(item.get('factor'))}</td><td class='{'status-missing' if item.get('status') in {'MISSING', 'NOT_INTEGRATED'} else 'status-ok'}'>{_e(item.get('status'))}</td><td>{_e(item.get('value'))}</td></tr>"
        for item in plan.get("evidence", [])) or "<tr><td colspan='3'>No asset-specific evidence registered.</td></tr>"
    labels = ["市場方向", "證據一致性", "風險位置", "准許進場條件", "看錯損失", "出場計畫", "理論風報比", "No-Trade 理由"]
    values = list(plan.get("decision_audit", {}).values())
    audit_rows = "".join(
        f"<tr><td>{index+1}. {_e(label)}</td><td>{_format_audit(values[index] if index < len(values) else 'NOT_EVALUATED')}</td></tr>"
        for index, label in enumerate(labels))
    secondary = (f"3M {_e(reference.get('three_month') or reference.get('close'))} · Cash−3M {_e(reference.get('cash_3m'))}"
                 if key == "lme_zinc" else f"{_e(plan.get('symbol') or series.get('latest_contract') or series.get('symbol'))}")
    return f"<section class='card primary' id='{_e(key)}'><div class='market-head'><div><h2>{_e(plan.get('market', key))}</h2><span class='pill {klass}'>{_e(decision)}</span> <span class='pill'>{_e(plan.get('direction'))}</span></div><div><span class='price'>{_e(headline)}</span> <span class='muted'>{_e(series.get('unit') or ('USD/t' if key == 'lme_zinc' else ''))}</span></div></div><div class='market-meta'><div><span>{'LME Cash headline' if key == 'lme_zinc' else 'Latest validated reference'}</span><b>{_e(headline)}</b></div><div><span>Secondary identity</span><b>{secondary}</b></div><div><span>As-of / observations</span><b>{_e(plan.get('as_of') or series.get('as_of'))} · {_e(series.get('observations'))}</b></div><div><span>Evidence availability %</span><b>{_e(plan.get('evidence_completeness', 'NOT_SCORED'))}</b></div></div><p class='muted'>{source_line}</p><div class='gates'>{gate_html}</div><div class='grid' style='margin-top:10px'><div class='card half'><h2>Validated price structure · latest 120 sessions</h2>{_sparkline(series)}<p class='muted'>Only validated closes are plotted. Candle patterns and ATR require true OHLC.</p></div><div class='card half'><h2>Asset-specific evidence</h2><table><tr><th>Factor</th><th>Status</th><th>Value</th></tr>{evidence_rows}</table><p class='muted'>Availability measures whether a field exists; it is not a confidence, accuracy or win probability score.</p></div><div class='card half'><h2>Conditional plan · RESEARCH ONLY</h2><table>{plan_rows}</table></div><div class='card half dark'><h2>Execution approval boundary</h2><p>Bid / Ask · Spread · Actual fill · Slippage · Actual R:R · Contract quantity</p><p class='muted'>Status: {_e(plan.get('execution_check', {}).get('status'))}. Enter these only in the loopback private tool; this public page never accepts account data or transmits orders.</p><h2>No-Trade / waiting reasons</h2><ul>{reasons}</ul></div><div class='card'><h2>Eight-question decision audit</h2><table class='audit'>{audit_rows}</table></div></div></section>"


def build_research_pages(snapshot: dict) -> list[Path]:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    run_date = snapshot.get("run_date", "—")
    research = snapshot.get("market_research", {})
    decisions = snapshot.get("decision_book", {}).get("markets", {})
    series = {"lme_zinc": research.get("close_series", {}),
              "shfe_zinc": research.get("shfe_zinc", {}), **research.get("cross_assets", {})}
    constitution = "<div class='rules'><b>Decision chain</b><br>Asset-specific evidence → conditional plan → private execution approval → post-trade review. No complete data → no signal; no trigger → no order; no acceptable Bid/Ask → not executable; Actual R:R below 1:2 → reject; unclear structure → No Trade.</div>"
    market_body = constitution + "<div class='grid' style='margin-top:10px'>" + "".join(
        _market_card(key, plan, series.get(key, {})) for key, plan in decisions.items()) + "</div>"
    radar_rows = "".join(
        f"<tr><td>{_e(plan.get('market', key))}</td><td>{_e(plan.get('direction'))}</td><td>{_e(plan.get('evidence_alignment'))}</td><td>{_e(plan.get('evidence_completeness', 'NOT_SCORED'))}</td><td>{_e(plan.get('decision'))}</td><td>{_e('; '.join(plan.get('no_trade_reasons', [])[:1]))}</td></tr>"
        for key, plan in decisions.items())
    radar_body = f"<div class='grid'><section class='card'><h2>Cross-market radar</h2><table><tr><th>Market</th><th>Direction</th><th>Evidence</th><th>Completeness %</th><th>State</th><th>Primary caution</th></tr>{radar_rows}</table></section><section class='card half'><h2>Macro context</h2><p>DXY diagnoses the common pricing wind; Gold and JPY are not assumed to be synchronized safe havens. Zinc must also confirm the curve, inventory, warrants, TC and China demand evidence.</p></section><section class='card half'><h2>Event discipline</h2><p>Before CPI, payrolls, FOMC/BoJ or geopolitical events: reduce planned risk, reject wide spreads and do not chase the first breakout bar. Event headlines are context, never a standalone trigger.</p></section></div>"
    journal_items = "".join(
        f"<div class='journal'><h2>{_e(plan.get('market', key))} · {_e(plan.get('decision'))}</h2><p>Direction: {_e(plan.get('direction'))}. Evidence: {_e(plan.get('evidence_alignment'))}. Next observation: {_e((plan.get('no_trade_reasons') or ['Review trigger and execution quote.'])[0])}</p></div>"
        for key, plan in decisions.items())
    journal_body = f"<div class='grid'><section class='card'><h2>Daily research journal</h2><p class='muted'>Facts → interpretation → invalidation → next observation. Generated from the same snapshot as the charts.</p>{journal_items}</section><section class='card'><h2>Post-trade review boundary</h2><p>Actual fill, fees, slippage, exit and rule adherence belong to the loopback-only private journal. Public research never contains account equity, quantities or fills. Do not score untriggered plans as wins or losses; fewer than 30 closed trades remains an insufficient sample.</p></section></div>"
    health = snapshot.get("market", {}).get("data_health", {})
    status_body = f"<div class='grid'><section class='card'><h2>Data Health · internal operations view</h2><p>This page is intentionally absent from normal navigation.</p><pre>{_e(json.dumps(health, ensure_ascii=False, indent=2))}</pre></section></div>"
    pages = {
        "markets.html": _page("Markets · Global Macro Research", "Markets", market_body, run_date),
        "radar.html": _page("Radar · Global Macro Research", "Radar", radar_body, run_date),
        "journal.html": _page("Journal · Global Macro Research", "Journal", journal_body, run_date),
        "system-status.html": _page("System Status", "", status_body, run_date),
    }
    output = []
    for name, content in pages.items():
        path = PUBLIC_DIR / name
        path.write_text(content, encoding="utf-8")
        output.append(path)
    return output
