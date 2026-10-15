"""Multi-page, auditable public research UI in the ivory/navy visual language."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .utils import PUBLIC_DIR
from .visual_language import (SERIES_STYLES, VISUAL_CSS, asset_icon,
                              series_legend, source_badge, source_legend)


def _e(value):
    return html.escape(str(value if value is not None else "—"))


def _first_present(*values):
    return next((value for value in values if value is not None), None)


STYLE = """
:root{--ivory:#f4f1e9;--white:#fff;--navy:#0b2f4f;--ink:#153552;--muted:#687e90;--line:#d5dde3;--teal:#087b70;--orange:#c8783d;--red:#d94a4f}
*{box-sizing:border-box}body{margin:0;background:var(--ivory);color:var(--ink);font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}.head{background:linear-gradient(112deg,#0a2a48,#123e61);color:#fff;border-bottom:3px solid var(--orange);padding:18px 24px}.head h1{font:700 29px Georgia,serif;margin:0}.head small{color:#d4e0e8}.shell{display:grid;grid-template-columns:190px minmax(0,1fr);max-width:1760px;margin:auto}.nav{min-height:100vh;background:#fbfaf6;border-right:1px solid var(--line);padding:16px 10px}.nav a{display:block;padding:11px;color:#244966;text-decoration:none;border-left:3px solid transparent}.nav a.on,.nav a:hover{background:var(--navy);color:#fff;border-left-color:var(--orange)}main{padding:16px;min-width:0}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:10px}.card{grid-column:span 12;background:#fff;border:1px solid var(--line);border-radius:7px;padding:15px;box-shadow:0 3px 12px rgba(18,50,76,.05)}.half{grid-column:span 6}h2{font:700 16px Georgia,serif;margin:0 0 10px}h3{font-size:13px;margin:0 0 7px}.pill{display:inline-block;border-radius:99px;padding:4px 9px;font-size:11px;background:#e8edf0}.good{background:#dcf1ec;color:#086d63}.wait{background:#fae9d9;color:#8a552e}.bad{background:#fae0e2;color:#a7333a}.price{font-size:25px;font-weight:800}.muted{color:var(--muted)}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #e1e6e9;padding:8px;text-align:left;vertical-align:top}th{background:#f3f5f4}.table-wrap{overflow-x:auto}.rules{border-left:4px solid var(--orange);padding:12px;background:#fff8f1}.dark{background:#0b2f4f;color:#fff}.dark .muted{color:#bed0dc}.chart{height:225px;background:linear-gradient(#103c60,#092d4b);border-radius:6px;padding:8px;color:#bed0dc}.chart svg{width:100%;height:100%}.journal{border-left:3px solid var(--teal);padding-left:12px}.footer{padding:25px;color:var(--muted);text-align:center}.status-ok{color:var(--teal);font-weight:700}.status-missing{color:var(--red);font-weight:700}.market-head{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;align-items:flex-start}.market-meta{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:8px;margin:10px 0}.market-meta div{padding:8px;background:#f7f6f2;border:1px solid var(--line);border-radius:5px}.market-meta span{display:block;color:var(--muted);font-size:11px}.market-index{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.market-index a{padding:8px 11px;border:1px solid var(--line);border-radius:99px;background:#fff;color:var(--ink);text-decoration:none}.market-index a:hover{background:var(--navy);color:#fff}.comparison td:first-child{font-weight:750}.state{white-space:nowrap}.market-detail{margin:10px 0;background:#fff;border:1px solid var(--line);border-left:5px solid var(--teal);border-radius:7px;box-shadow:0 3px 12px rgba(18,50,76,.05)}.market-detail>summary{cursor:pointer;list-style:none;padding:14px 16px;display:flex;justify-content:space-between;gap:12px;align-items:center}.market-detail>summary::-webkit-details-marker{display:none}.market-detail>summary:after{content:'＋';font-size:18px}.market-detail[open]>summary:after{content:'−'}.market-detail[open]>summary{border-bottom:1px solid var(--line)}.market-summary{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.market-body{padding:15px}.gate-line{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0}.gate-line span{border:1px solid var(--line);border-radius:99px;padding:5px 8px;background:#f7f6f2;font-size:11px}.decision-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin-top:10px}.decision-block{border:1px solid var(--line);border-radius:6px;padding:12px;background:#fbfaf7}.decision-block dl{margin:0}.decision-block dt{font-weight:750;margin-top:7px}.decision-block dt:first-child{margin-top:0}.decision-block dd{margin:2px 0;color:#526d82}.evidence-count{font-size:11px;color:var(--muted)}.appendix{margin-top:10px;border-top:1px solid var(--line);padding-top:10px}.appendix summary{cursor:pointer;font-weight:750}.blocked{border-left:4px solid var(--red);background:#fff5f5;padding:11px;margin-top:10px}.execution-boundary{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:10px 0}.section-title{display:flex;justify-content:space-between;gap:12px;align-items:end;margin-bottom:8px}.section-title h2{margin:0}.source-line{overflow-wrap:anywhere}.primary{border-left:5px solid var(--teal)}
@media(max-width:900px){.shell{grid-template-columns:1fr}.nav{min-height:0;display:flex;overflow:auto}.nav a{white-space:nowrap}.half{grid-column:span 12}.market-meta,.decision-grid,.execution-boundary{grid-template-columns:1fr 1fr}}
@media(max-width:620px){main{padding:10px}.head{padding:14px}.head h1{font-size:23px}.market-meta,.decision-grid,.execution-boundary{grid-template-columns:1fr}.comparison{min-width:840px}.market-detail>summary{align-items:flex-start}.chart{height:190px}}
"""

STYLE += """
.market-stage{background:#fff;border:1px solid var(--line);border-radius:7px;padding:14px;margin-bottom:10px}.market-stage h2{font-size:20px;margin:0}.market-tabs{display:grid;grid-template-columns:repeat(6,minmax(110px,1fr));border:1px solid var(--line);border-radius:7px;overflow:hidden;margin-bottom:12px}.market-tabs a{padding:10px 8px;text-align:center;text-decoration:none;color:var(--ink);background:#fff;border-right:1px solid var(--line);font-size:12px}.market-tabs a:last-child{border-right:0}.market-tabs a:hover,.market-tabs a.active{background:var(--navy);color:#fff}.market-detail{scroll-margin-top:12px}.market-kpis{display:grid;grid-template-columns:repeat(5,minmax(110px,1fr));gap:8px;margin:10px 0}.market-kpis>div{padding:10px;background:#f7f6f2;border:1px solid var(--line);border-radius:6px}.market-kpis span{display:block;color:var(--muted);font-size:10px;text-transform:uppercase}.market-kpis b{display:block;margin-top:3px;font-size:16px}.chart-first{display:grid;grid-template-columns:minmax(0,1fr) 245px;gap:10px;margin:10px 0}.chart-stack{display:grid;gap:10px}.chart-panel{background:#0b2f4f;border:1px solid #173f5d;border-radius:7px;padding:11px;color:#fff}.chart-panel h2{color:#fff;margin:0}.chart-panel .muted{color:#bed0dc}.chart-panel .chart{height:290px;background:#081f35}.chart-panel.linked .chart{height:185px}.chart-panel .chart-note{margin:7px 0 0;color:#bed0dc;font-size:11px}.period-controls{display:flex;gap:6px;flex-wrap:wrap;margin:9px 0}.period-controls button{border:1px solid #315c7d;border-radius:5px;padding:5px 9px;background:#081f35;color:#bed0dc;cursor:pointer;font:inherit;font-size:11px}.period-controls button:hover,.period-controls button.active{background:#f5a45d;border-color:#f5a45d;color:#102f49}.rsi-chart{margin-top:8px;padding:7px 8px 4px;background:#081f35;border:1px solid #173f5d;border-radius:5px}.rsi-chart svg{display:block;width:100%;height:72px}.rsi-chart span{display:block;color:#bed0dc;font-size:10px}.key-levels{background:#0b2f4f;color:#fff;border-radius:7px;padding:13px;align-self:start}.key-levels h2{color:#fff;border-bottom:1px solid #315c7d;padding-bottom:9px}.key-levels dl{margin:0}.key-levels div{display:flex;justify-content:space-between;gap:8px;padding:10px 0;border-bottom:1px solid #315c7d}.key-levels div:last-child{border-bottom:0}.key-levels dt{color:#bed0dc}.key-levels dd{margin:0;font-weight:750;text-align:right}.key-levels .stop{color:#ff8a98}.key-levels .target{color:#61dbc3}.chart-label-row{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}.market-lower{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.source-strip{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:9px 0;color:var(--muted);font-size:11px}.treasury-placeholder{border-left:5px solid var(--orange)}
@media(max-width:1050px){.market-tabs{grid-template-columns:repeat(3,1fr)}.chart-first{grid-template-columns:1fr}.key-levels{display:grid;grid-template-columns:repeat(2,1fr);gap:0 18px}.key-levels h2{grid-column:1/-1}}
@media(max-width:900px){.market-lower{grid-template-columns:1fr 1fr}.market-kpis{grid-template-columns:repeat(3,1fr)}}
@media(max-width:620px){.market-lower{grid-template-columns:1fr}.chart-panel .chart{height:215px}.market-tabs{grid-template-columns:repeat(2,1fr)}.market-kpis{grid-template-columns:repeat(2,1fr)}.key-levels{grid-template-columns:1fr}}
"""

STYLE += VISUAL_CSS


def _nav(active: str) -> str:
    items = [("index.html", "Today"), ("markets.html", "Markets"),
             ("radar.html", "Radar"), ("journal.html", "Journal")]
    return "<nav class='nav'>" + "".join(
        f"<a class='{'on' if label == active else ''}' href='{url}'>{label}</a>"
        for url, label in items) + "</nav>"


def _page(title: str, active: str, body: str, run_date: str) -> str:
    disclosure = "RESEARCH ONLY · No data, no signal · No trigger, no order · Actual R:R must be ≥ 1:2"
    script = """<script>(()=>{const all=[...document.querySelectorAll('.market-detail')],tabs=[...document.querySelectorAll('[data-market-target]')];function select(id){tabs.forEach(tab=>tab.classList.toggle('active',tab.dataset.marketTarget===id))}all.forEach(item=>item.addEventListener('toggle',()=>{if(item.open){all.forEach(other=>{if(other!==item)other.open=false});select(item.id)}}));tabs.forEach(link=>link.addEventListener('click',()=>{const item=document.getElementById(link.dataset.marketTarget);if(item){item.open=true;select(item.id)}}));document.querySelectorAll('[data-chart-group]').forEach(button=>button.addEventListener('click',()=>{const group=button.dataset.chartGroup,window=button.dataset.chartWindow;document.querySelectorAll(`[data-chart-group="${group}"]`).forEach(item=>item.classList.toggle('active',item===button));document.querySelectorAll(`[data-chart-panel="${group}"]`).forEach(panel=>panel.hidden=panel.dataset.chartWindow!==window)}))})()</script>"""
    return f"<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_e(title)}</title><style>{STYLE}</style></head><body><header class='head'><h1>GLOBAL MACRO RESEARCH DESK</h1><small>{_e(run_date)} · delayed research data · execution requires live quote</small></header><div class='shell'>{_nav(active)}<main>{source_legend()}{body}<div class='footer'>{disclosure}</div></main></div>{script}</body></html>"


def _sparkline(series: dict, *, group: str | None = None, window: int | None = 120) -> str:
    if group:
        specs = [(20, "20D"), (60, "60D"), (120, "120D"), (252, "1Y"), (None, "ALL")]
        buttons = "".join(
            f"<button type='button' class='{'active' if days == 120 else ''}' data-chart-group='{_e(group)}' data-chart-window='{days or 'all'}'>{label}</button>"
            for days, label in specs
        )
        panels = "".join(
            f"<div class='chart-window' data-chart-panel='{_e(group)}' data-chart-window='{days or 'all'}' {'hidden' if days != 120 else ''}>{_sparkline(series, window=days)}</div>"
            for days, _ in specs
        )
        return f"<div class='period-controls'>{buttons}</div>{panels}"
    raw_points = []
    source_points = series.get("chart_points", [])
    if window is not None:
        source_points = source_points[-window:]
    for item in source_points:
        try:
            raw_points.append({**item, "date": str(item.get("date", "")), "close": float(item.get("close"))})
        except (TypeError, ValueError):
            continue
    if len(raw_points) < 2:
        return "<div class='chart'>Validated chart data unavailable.</div>"
    points = [(item["date"], item["close"]) for item in raw_points]
    has_ohlc = all(all(item.get(field) is not None for field in ("open", "high", "low", "close")) for item in raw_points)
    line_specs = [
        (field, SERIES_STYLES[field]["color"], SERIES_STYLES[field]["label"], SERIES_STYLES[field]["dash"])
        for field in ("ema20", "sma14", "sma20", "sma30", "sma50", "sma60")
    ]
    line_specs = [spec for spec in line_specs if any(item.get(spec[0]) is not None for item in raw_points)]
    values = ([float(item[field]) for item in raw_points for field in ("high", "low")] if has_ohlc
              else [item[1] for item in points])
    values.extend(float(item[field]) for item in raw_points for field, _, _, _ in line_specs if item.get(field) is not None)
    low, high = min(values), max(values)
    span = high - low or 1
    x = lambda index: 20 + index * 760 / (len(points)-1)
    y = lambda value: 165 - (float(value)-low)*130/span
    ticks = []
    for index in sorted({0, len(points)//2, len(points)-1}):
        anchor = "start" if index == 0 else "end" if index == len(points) - 1 else "middle"
        ticks.append(f"<text x='{x(index):.1f}' y='184' fill='#bed0dc' font-size='11' text-anchor='{anchor}'>{_e(points[index][0])}</text>")
    if has_ohlc:
        width = max(2.0, min(6.0, 520 / len(raw_points)))
        plot = []
        for index, item in enumerate(raw_points):
            color = SERIES_STYLES["up"]["color"] if float(item["close"]) >= float(item["open"]) else SERIES_STYLES["down"]["color"]
            top, bottom = min(y(item["open"]), y(item["close"])), max(y(item["open"]), y(item["close"]))
            plot.append(f"<line x1='{x(index):.1f}' y1='{y(item['high']):.1f}' x2='{x(index):.1f}' y2='{y(item['low']):.1f}' stroke='{color}'/>")
            plot.append(f"<rect x='{x(index)-width/2:.1f}' y='{top:.1f}' width='{width:.1f}' height='{max(1.0,bottom-top):.1f}' fill='{color}'/>")
        body, label, mode = "".join(plot), "Validated daily OHLC candlestick history", "OHLC"
    else:
        coords = " ".join(f"{x(i):.1f},{y(value):.1f}" for i, (_, value) in enumerate(points))
        body = f"<polyline points='{coords}' fill='none' stroke='{SERIES_STYLES['close']['color']}' stroke-width='{SERIES_STYLES['close']['width']}'/>"
        label, mode = "Validated close-only history", "CLOSE_ONLY"
    overlays = []
    for field, color, _, dash in line_specs:
        segments, segment = [], []
        for index, item in enumerate(raw_points):
            value = item.get(field)
            if value is None:
                if segment:
                    segments.append(segment)
                    segment = []
                continue
            segment.append(f"{x(index):.1f},{y(value):.1f}")
        if segment:
            segments.append(segment)
        overlays.extend(
            f"<polyline points='{' '.join(coords)}' fill='none' stroke='{color}' stroke-width='{SERIES_STYLES[field]['width']}' stroke-dasharray='{dash}' opacity='.95'/>"
            for coords in segments if len(coords) > 1
        )
    legend_keys = (["up", "down"] if has_ohlc else ["close"]) + [field for field, _, _, _ in line_specs]
    return (f"<div class='chart' data-chart-mode='{mode}'><svg viewBox='0 0 800 190' role='img' aria-label='{label}'>"
            "<line x1='20' y1='35' x2='780' y2='35' stroke='#315775'/><line x1='20' y1='165' x2='780' y2='165' stroke='#315775'/>"
            f"{body}{''.join(overlays)}<text x='25' y='25' fill='#bed0dc' font-size='11'>{high:.2f}</text>"
            f"<text x='25' y='160' fill='#bed0dc' font-size='11'>{low:.2f}</text>{''.join(ticks)}</svg>"
            f"{series_legend(legend_keys)}</div>")


def _format_audit(value) -> str:
    if isinstance(value, dict):
        return " · ".join(f"{_e(key)}: {_e(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "；".join(_e(item) for item in value)
    return _e(value)


def _rsi_chart(series: dict, window: int = 120) -> str:
    points = []
    for item in series.get("chart_points", [])[-window:]:
        try:
            value = item.get("rsi14")
            if value is not None:
                points.append((str(item.get("date", "")), float(value)))
        except (TypeError, ValueError):
            continue
    if len(points) < 2:
        return ""
    x = lambda index: 20 + index * 760 / (len(points) - 1)
    y = lambda value: 64 - max(0.0, min(100.0, value)) * .56
    coords = " ".join(f"{x(index):.1f},{y(value):.1f}" for index, (_, value) in enumerate(points))
    latest = points[-1][1]
    return ("<div class='rsi-chart' data-indicator='RSI14'><svg viewBox='0 0 800 72' role='img' "
            "aria-label='Close based RSI14 latest 120 validated sessions'>"
            f"<line x1='20' y1='{y(70):.1f}' x2='780' y2='{y(70):.1f}' stroke='#8f5d67' stroke-dasharray='4 4'/>"
            f"<line x1='20' y1='{y(30):.1f}' x2='780' y2='{y(30):.1f}' stroke='#4c806f' stroke-dasharray='4 4'/>"
            f"<polyline points='{coords}' fill='none' stroke='{SERIES_STYLES['rsi14']['color']}' stroke-width='{SERIES_STYLES['rsi14']['width']}'/>"
            f"<text x='25' y='{y(70)-3:.1f}' fill='#bed0dc' font-size='10'>70</text>"
            f"<text x='25' y='{y(30)-3:.1f}' fill='#bed0dc' font-size='10'>30</text>"
            f"<text x='775' y='14' text-anchor='end' fill='{SERIES_STYLES['rsi14']['color']}' font-size='11'>RSI14 {latest:.2f}</text>"
            "</svg><span>Close-based RSI14 · latest 120 validated sessions · 30/70 guides</span></div>")


def _headline(key: str, plan: dict, series: dict):
    reference = plan.get("reference") or {}
    if key == "lme_zinc":
        return reference.get("cash")
    return _first_present(reference.get("close"), series.get("latest_close"))


def _evidence_count(plan: dict) -> tuple[int, int]:
    evidence = plan.get("evidence", [])
    total = len(evidence)
    available = sum(
        1 for item in evidence
        if str(item.get("status", "")).upper() not in {"", "MISSING", "NOT_INTEGRATED", "UNAVAILABLE"}
    )
    return available, total


def _comparison_table(decisions: dict, series_map: dict) -> str:
    rows = []
    links = []
    for key, plan in decisions.items():
        series = series_map.get(key, {})
        reason = (plan.get("no_trade_reasons") or ["No blocker registered."])[0]
        available, total = _evidence_count(plan)
        price = _headline(key, plan, series)
        unit = series.get("unit") or ("USD/t" if key == "lme_zinc" else "")
        as_of = plan.get("as_of") or series.get("as_of") or "—"
        links.append(f"<a href='#{_e(key)}' data-market-target='{_e(key)}'>{asset_icon(key, compact=True)}{_e(plan.get('market', key))}</a>")
        rows.append(
            f"<tr><td><a class='asset-identity' href='#{_e(key)}' data-market-target='{_e(key)}'>{asset_icon(key, compact=True)}{_e(plan.get('market', key))}</a></td>"
            f"<td>{_e(price)} <span class='muted'>{_e(unit)}</span><br><small class='muted'>{_e(as_of)}</small></td>"
            f"<td>{_e(plan.get('direction'))}</td><td>{_e(plan.get('evidence_alignment'))}<br>"
            f"<small class='muted'>required evidence {available}/{total}</small></td>"
            f"<td class='state'><span class='pill {'wait' if plan.get('decision') == 'WAIT_FOR_TRIGGER' else 'good' if plan.get('decision') == 'READY' else 'bad'}'>{_e(plan.get('decision'))}</span></td>"
            f"<td>{_e(reason)}</td></tr>"
        )
    return (
        "<section class='card'><div class='section-title'><div><h2>Market comparison · first decision layer</h2>"
        "<div class='muted'>Compare direction, evidence and permission before opening an individual market.</div></div>"
        "<span class='pill'>one market open at a time</span></div>"
        f"<nav class='market-index' aria-label='Market detail'>{''.join(links)}</nav>"
        "<div class='table-wrap'><table class='comparison'><tr><th>Market</th><th>Validated reference</th>"
        "<th>Technical direction</th><th>Evidence</th><th>Trade state</th><th>Next condition / blocker</th></tr>"
        f"{''.join(rows)}</table></div></section>"
    )


def _lme_fundamentals(snapshot: dict) -> str:
    market = snapshot.get("market", {})
    tc = snapshot.get("china_tc", {})
    health = market.get("data_health", {})
    core_fields = [
        ("lme_cash", "LME Cash", market.get("lme_cash"), "USD/t"),
        ("lme_3m", "LME 3M", market.get("lme_3m"), "USD/t"),
        ("lme_inventory_t", "Opening / Total Stock", market.get("lme_inventory_t"), "t"),
        ("live_warrants_t", "Live Warrants", market.get("live_warrants_t"), "t"),
        ("cancelled_warrants_t", "Cancelled Warrants", market.get("cancelled_warrants_t"), "t"),
    ]
    core_rows = "".join(
        f"<tr><td>{_e(label)}</td><td>{_e(value)} {_e(unit)}</td><td>{_e(health.get(field, {}).get('as_of'))}</td>"
        f"<td>{source_badge(health.get(field, {}).get('source_grade'), health.get(field, {}).get('freshness'))} {_e(health.get(field, {}).get('source'))}</td></tr>"
        for field, label, value, unit in core_fields
    )
    tc_specs = [
        ("import_weekly", "China Import TC · Weekly"),
        ("domestic_weekly", "China Domestic TC · Weekly"),
        ("domestic_monthly", "China Domestic TC · Monthly"),
        ("annual_benchmark", "Annual Benchmark TC"),
    ]
    tc_rows = "".join(
        f"<tr><td>{_e(label)}</td><td>{_e(tc.get(key, {}).get('value'))} {_e(tc.get(key, {}).get('unit'))}</td>"
        f"<td>{_e(tc.get(key, {}).get('as_of'))}</td><td>{_e(tc.get(key, {}).get('age_days'))} d</td>"
        f"<td>{_e(tc.get(key, {}).get('expected_update'))}</td><td>{_e(tc.get(key, {}).get('status'))}</td>"
        f"<td>{source_badge(tc.get(key, {}).get('source_grade'), tc.get(key, {}).get('status'))} {_e(tc.get(key, {}).get('source'))}</td></tr>"
        for key, label in tc_specs
    )
    return f"""<details class='appendix'><summary>LME physical context · Cash / curve / inventory / TC</summary>
    <div class='table-wrap'><table><tr><th>Core field</th><th>Value</th><th>As of</th><th>Source</th></tr>{core_rows}</table></div>
    <p><b>Cash−3M:</b> {_e(market.get('cash_3m'))} USD/t · <b>Cancelled ratio:</b> {_e(market.get('cancelled_ratio_pct'))}%</p>
    <div class='table-wrap'><table><tr><th>TC series</th><th>Value / original basis</th><th>As of</th><th>Age</th><th>Cadence</th><th>Status</th><th>Source</th></tr>{tc_rows}</table></div>
    <p class='muted'>Physical-market evidence is separate from the Close-only technical direction. Different TC bases are not blended. Public privacy mode keeps exact internal inventory, demand and position sizing out of this page.</p></details>"""


def _key_levels(daily: dict) -> str:
    if not daily:
        return ("<aside class='key-levels'><h2>Key levels</h2><dl>"
                "<div><dt>Setup</dt><dd>NOT AVAILABLE</dd></div>"
                "<div><dt>Permission</dt><dd>NO TRADE</dd></div>"
                "<div><dt>Reason</dt><dd>Structure not aligned</dd></div></dl></aside>")
    setup = daily.get("setup_zone")
    setup_text = " – ".join(str(item) for item in setup) if isinstance(setup, list) else str(setup or "—")
    return f"""<aside class='key-levels'><h2>Key levels · research only</h2><dl>
    <div><dt>Setup</dt><dd>{_e(setup_text)}</dd></div>
    <div><dt>Trigger</dt><dd>{_e(daily.get('trigger_price'))}</dd></div>
    <div><dt>Maximum entry</dt><dd>{_e(daily.get('maximum_entry'))}</dd></div>
    <div><dt>Hard stop</dt><dd class='stop'>{_e(daily.get('hard_stop'))}</dd></div>
    <div><dt>Close invalidation</dt><dd class='stop'>{_e(daily.get('close_invalidation'))}</dd></div>
    <div><dt>T1</dt><dd class='target'>{_e(daily.get('t1'))}</dd></div>
    <div><dt>T2</dt><dd class='target'>{_e(daily.get('t2'))}</dd></div>
    <div><dt>Planned R:R</dt><dd>{_e(daily.get('planned_rr_t1'))} / {_e(daily.get('planned_rr_t2'))}</dd></div>
    </dl></aside>"""


def _market_tabs() -> str:
    items = [("lme_zinc", "LME Zinc"), ("shfe_zinc", "SHFE Zinc"), ("gold", "Gold"),
             ("usdjpy", "USD/JPY"), ("dxy", "DXY"), ("us_treasury", "US Treasury")]
    return "<nav class='market-tabs' aria-label='Market detail'>" + "".join(
        f"<a class='{'active' if key == 'lme_zinc' else ''}' href='#{key}' data-market-target='{key}'>{asset_icon(key, compact=True)}{label}</a>"
        for key, label in items
    ) + "</nav>"


def _treasury_placeholder() -> str:
    return """<details class='market-detail treasury-placeholder' id='us_treasury'>
    <summary><span class='market-summary'><span class='asset-identity'>%s<b>US Treasury 10Y</b></span>%s<span class='pill'>UNDETERMINED</span></span><span><b>N/A</b></span></summary>
    <div class='market-body'><div class='market-stage'><h2>US Treasury · data source not integrated</h2>
    <p>No verified 2Y, 10Y or real-yield series is present in the current snapshot. No chart, trend or cross-market conclusion is generated.</p>
    <p class='rules'><b>Required before activation:</b> permitted source, series identity, date, frequency, history, gap validation and source grade.</p></div></div></details>""" % (asset_icon("us_treasury", compact=True), source_badge(None, "MISSING"))


def _market_card(key: str, plan: dict, series: dict, snapshot: dict, open_by_default: bool = False) -> str:
    reference = plan.get("reference") or {}
    daily = plan.get("daily_plan", {})
    decision = plan.get("decision", "NO_TRADE")
    klass = "good" if decision == "READY" else "wait" if decision == "WAIT_FOR_TRIGGER" else "bad"
    gates = [("1 DATA", plan.get("data_gate")), ("2 REGIME", plan.get("regime_gate")),
             ("3 STRATEGY", plan.get("strategy_gate")), ("4 TRIGGER", plan.get("trigger_gate")),
             ("5 EXECUTION", plan.get("execution_gate")), ("6 REVIEW", decision)]
    gate_html = "".join(f"<span><b>{_e(name)}</b> · {_e(value)}</span>" for name, value in gates)
    reasons = "".join(f"<li>{_e(item)}</li>" for item in plan.get("no_trade_reasons", [])) or "<li>None</li>"
    plan_rows = "".join(f"<tr><td>{_e(name.replace('_', ' ').title())}</td><td>{_e(value)}</td></tr>" for name, value in daily.items()) or "<tr><td colspan='2'>Blocked: no compliant daily trade plan.</td></tr>"
    headline = _headline(key, plan, series)
    tv = {"lme_zinc": "LME:ZNC1!", "shfe_zinc": "SHFE:ZN1!", "gold": "COMEX:GC1!",
          "gold_spot": "OANDA:XAUUSD", "usdjpy": "FX:USDJPY", "dxy": "TVC:DXY"}.get(key)
    tv_link = f" · <a href='https://www.tradingview.com/chart/?symbol={_e(tv)}' target='_blank' rel='noopener'>TradingView人工比對 ↗</a>" if tv else ""
    identity = series.get("market_identity") or ("LME Cash headline; 3M public technical reference" if key == "lme_zinc" else series.get("market") or series.get("symbol"))
    retrieval_status = series.get("retrieval_status", "CURRENT_OR_MISSING")
    source_line = f"{source_badge(series.get('source_grade'), retrieval_status)} {_e(series.get('source'))} · {_e(identity)} · {_e(retrieval_status)}{tv_link}"
    evidence_rows = "".join(
        f"<tr><td>{_e(item.get('factor'))}</td><td class='{'status-missing' if item.get('status') in {'MISSING', 'NOT_INTEGRATED'} else 'status-ok'}'>{_e(item.get('status'))}</td><td>{_e(item.get('value'))}</td></tr>"
        for item in plan.get("evidence", [])) or "<tr><td colspan='3'>No asset-specific evidence registered.</td></tr>"
    labels = ["市場方向", "證據一致性", "風險位置", "准許進場條件", "看錯損失", "出場計畫", "理論風報比", "No-Trade 理由"]
    values = list(plan.get("decision_audit", {}).values())
    audit_items = [
        f"<dt>{index+1}. {_e(label)}</dt><dd>{_format_audit(values[index] if index < len(values) else 'NOT_EVALUATED')}</dd>"
        for index, label in enumerate(labels)
    ]
    audit_blocks = "".join(
        f"<section class='decision-block'><h3>{title}</h3><dl>{''.join(audit_items[start:start+2])}</dl></section>"
        for title, start in (("Direction & evidence", 0), ("Location & permission", 2),
                             ("Risk & exits", 4), ("No-Trade discipline", 6))
    )
    secondary = (f"3M {_e(reference.get('three_month') or reference.get('close'))} · Cash−3M {_e(reference.get('cash_3m'))}"
                 if key == "lme_zinc" else f"{_e(plan.get('symbol') or series.get('latest_contract') or series.get('symbol'))}")
    indicator_fields = [
        ("Close", _first_present(reference.get("close"), series.get("latest_close"))),
        ("SMA14", _first_present(reference.get("sma14"), series.get("sma_14"))),
        ("SMA30", _first_present(reference.get("sma30"), series.get("sma_30"))),
        ("EMA20", _first_present(reference.get("ema20"), series.get("ema_20"))),
        ("SMA60", reference.get("sma60")),
        ("RSI14", _first_present(reference.get("rsi14"), series.get("rsi_14"))),
        ("ATR14", reference.get("atr14")),
    ]
    indicator_cells = "".join(
        f"<div><span>{_e(label)}</span><b>{_e(value)}</b></div>" for label, value in indicator_fields if value is not None
    ) or "<div><span>Indicators</span><b>INSUFFICIENT DATA</b></div>"
    available, total = _evidence_count(plan)
    physical = _lme_fundamentals(snapshot) if key == "lme_zinc" else ""
    blocked = "" if daily else f"<div class='blocked'><b>No compliant setup is published.</b><ul>{reasons}</ul></div>"
    sample = next(iter(series.get("chart_points", [])), {})
    chart_note = ("Verified exchange OHLC is rendered as candlesticks; contract identity and roll boundaries remain in the source series."
                  if all(sample.get(field) is not None for field in ("open", "high", "low", "close"))
                  else "Only validated closes are plotted. Candle patterns and ATR require verified OHLC.")
    chart_title = ("LME 3M · CLOSE-ONLY" if key == "lme_zinc" else
                   f"{plan.get('market', key)} · {'VERIFIED OHLC' if all(sample.get(field) is not None for field in ('open', 'high', 'low', 'close')) else 'CLOSE-ONLY'}")
    linked_chart = ""
    if key == "lme_zinc":
        shfe = snapshot.get("market_research", {}).get("shfe_zinc", {})
        if shfe.get("status") == "AVAILABLE":
            linked_chart = ("<section class='chart-panel linked'><div class='chart-label-row'><h2>SHFE Zinc · VERIFIED OHLC · CNY/t</h2>"
                            f"<span class='muted'>{_e(shfe.get('latest_contract'))} · {_e(shfe.get('as_of'))}</span></div>"
                            f"{_sparkline(shfe, group='lme_linked_shfe')}{_rsi_chart(shfe)}<p class='chart-note'>Separate China-market contract for cross-market confirmation; never labelled as LME OHLC.</p></section>")
    return f"""<details class='market-detail' id='{_e(key)}' {'open' if open_by_default else ''}>
    <summary><span class='market-summary'><span class='asset-identity'>{asset_icon(key, compact=True)}<b>{_e(plan.get('market', key))}</b></span><span class='pill {klass}'>{_e(decision)}</span><span class='pill'>{_e(plan.get('direction'))}</span></span><span><b>{_e(headline)}</b> <span class='muted'>{_e(series.get('unit') or ('USD/t' if key == 'lme_zinc' else ''))}</span></span></summary>
    <div class='market-body'><div class='market-kpis'><div><span>{'LME Cash headline' if key == 'lme_zinc' else 'Validated reference'}</span><b>{_e(headline)}</b></div><div><span>Secondary identity</span><b>{secondary}</b></div><div><span>Technical direction</span><b>{_e(plan.get('direction'))}</b></div><div><span>Trade state</span><b>{_e(decision)}</b></div><div><span>As-of / observations</span><b>{_e(plan.get('as_of') or series.get('as_of'))} · {_e(series.get('observations'))}</b></div></div>
    <div class='chart-first'><div class='chart-stack'><section class='chart-panel'><div class='chart-label-row'><h2>{_e(chart_title)}</h2><span class='muted'>20D / 60D / 120D / 1Y / all validated sessions</span></div>{_sparkline(series, group=key)}{_rsi_chart(series)}<p class='chart-note'>{_e(chart_note)}</p></section>{linked_chart}</div>{_key_levels(daily)}</div>
    <div class='source-strip'><span>{source_line}</span><span>{_e(series.get('coverage_start'))} → {_e(series.get('coverage_end'))} · required evidence {available}/{total}</span></div>
    <div class='market-meta' aria-label='Validated indicators'>{indicator_cells}</div><div class='gate-line' aria-label='Decision gates'>{gate_html}</div>{blocked}
    <div class='market-lower'><section class='card'><h2>Asset-specific evidence</h2><div class='table-wrap'><table><tr><th>Factor</th><th>Status</th><th>Value</th></tr>{evidence_rows}</table></div></section><section class='card'><h2>Identity & data quality</h2><p>{_e(identity)}</p><p class='muted'>Data gate: {_e(plan.get('data_gate'))}. Evidence availability is not a win probability or confidence score.</p></section></div>
    {physical}<section aria-label='Eight-question decision audit'><div class='section-title'><h2>Decision brief · eight required questions</h2><span class='pill'>single source of truth</span></div><div class='decision-grid'>{audit_blocks}</div></section>
    <details class='appendix'><summary>Conditional plan · RESEARCH ONLY</summary><div class='table-wrap'><table>{plan_rows}</table></div></details>
    <p class='rules'><b>Private execution status:</b> {_e(plan.get('execution_check', {}).get('status'))}. Bid / Ask, spread, actual fill, slippage, Actual R:R and contract quantity remain private inputs.</p>
    </div></details>"""


def build_research_pages(snapshot: dict) -> list[Path]:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    run_date = snapshot.get("run_date", "—")
    research = snapshot.get("market_research", {})
    decisions = snapshot.get("decision_book", {}).get("markets", {})
    series = {"lme_zinc": research.get("close_series", {}),
              "shfe_zinc": research.get("shfe_zinc", {}), **research.get("cross_assets", {})}
    constitution = ("<section class='rules'><b>Decision chain</b><br>Asset-specific evidence → conditional plan → "
                    "private execution approval → post-trade review. No complete data → no signal; no trigger → no order; "
                    "no acceptable Bid/Ask → not executable; Actual R:R below 1:2 → reject; unclear structure → No Trade.</section>")
    primary_keys = ["lme_zinc", "shfe_zinc", "gold", "usdjpy", "dxy"]
    visible_decisions = [(key, decisions[key]) for key in primary_keys if key in decisions]
    details = "".join(
        _market_card(key, plan, series.get(key, {}), snapshot, open_by_default=index == 0)
        for index, (key, plan) in enumerate(visible_decisions)
    ) + _treasury_placeholder()
    execution_boundary = ("<section class='card dark'><div class='execution-boundary'><div><h2>Execution approval boundary</h2>"
                          "<p>Bid / Ask · Spread · Actual fill · Slippage · Actual R:R · Contract quantity</p></div>"
                          "<p class='muted'>This public page publishes research levels only. Executability is evaluated once, in the private loopback tool, after a trigger exists.</p></div></section>")
    market_intro = ("<section class='market-stage'><div class='section-title'><div><div class='muted'>CHARTS BEFORE COMMENTARY</div>"
                    "<h2>Markets · price structure and conditional plans</h2></div><span class='pill'>delayed research data</span></div>"
                    "<p class='muted'>Choose a market. Verified price structure, key levels and source identity appear before evidence and interpretation.</p>"
                    f"{_market_tabs()}</section>")
    market_body = (market_intro + "<section aria-label='Market details'>" + details + "</section>" +
                   execution_boundary + constitution)
    radar_rows = "".join(
        f"<tr><td><span class='radar-market'>{asset_icon(key, compact=True)}{_e(plan.get('market', key))}</span></td><td>{_e(plan.get('direction'))}</td><td>{_e(plan.get('evidence_alignment'))}</td><td>{_e(plan.get('evidence_completeness', 'NOT_SCORED'))}</td><td>{_e(plan.get('decision'))}</td><td>{_e('; '.join(plan.get('no_trade_reasons', [])[:1]))}</td></tr>"
        for key, plan in decisions.items())
    radar_body = f"<div class='grid'><section class='card'><h2>Cross-market radar</h2><table><tr><th>Market</th><th>Direction</th><th>Evidence</th><th>Completeness %</th><th>State</th><th>Primary caution</th></tr>{radar_rows}</table></section><section class='card half'><h2>Macro context</h2><p>DXY diagnoses the common pricing wind; Gold and JPY are not assumed to be synchronized safe havens. Zinc must also confirm the curve, inventory, warrants, TC and China demand evidence.</p></section><section class='card half'><h2>Event discipline</h2><p>Before CPI, payrolls, FOMC/BoJ or geopolitical events: reduce planned risk, reject wide spreads and do not chase the first breakout bar. Event headlines are context, never a standalone trigger.</p></section></div>"
    journal_items = "".join(
        f"<div class='journal'><h2>{asset_icon(key, compact=True)}{_e(plan.get('market', key))} · {_e(plan.get('decision'))}</h2><p>Direction: {_e(plan.get('direction'))}. Evidence: {_e(plan.get('evidence_alignment'))}. Next observation: {_e((plan.get('no_trade_reasons') or ['Review trigger and execution quote.'])[0])}</p></div>"
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
