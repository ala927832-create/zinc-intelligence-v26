from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from .dashboard import build_dashboard as build_legacy_dashboard, fmt, pct
from .utils import PUBLIC_DIR


def _esc(value) -> str:
    return html.escape(str(value if value is not None else "—"))


def _freshness_class(value: str | None) -> str:
    v = (value or "").upper()
    if v in {"CURRENT_ENOUGH", "HEALTHY", "PASS", "AVAILABLE", "VERIFIED_REFERENCE"}:
        return "ok"
    if v in {"CARRY_FORWARD", "DEGRADED", "CAUTION", "STALE", "UNKNOWN_DATE"}:
        return "warn"
    return "bad"


def _age(value) -> str:
    try:
        return f"{float(value):.1f} d"
    except Exception:
        return "—"


def _source_label(h: dict) -> str:
    grade = h.get("source_grade") or "—"
    src = h.get("source") or "—"
    return f"{_esc(grade)} · {_esc(src)}"


def _health_rows(snapshot: dict) -> str:
    health = snapshot.get("market", {}).get("data_health", {})
    labels = {
        "lme_cash": "LME Cash",
        "lme_3m": "LME 3M",
        "lme_inventory_t": "Opening / Total Stock",
        "live_warrants_t": "Live Warrants",
        "cancelled_warrants_t": "Cancelled Warrants",
        "tc_usd_t": "TC (legacy model field)",
        "physical_premium_usd_t": "Physical Premium",
    }
    rows = []
    for field, label in labels.items():
        h = health.get(field, {})
        rows.append(
            "<tr>"
            f"<td><b>{_esc(label)}</b></td>"
            f"<td>{_esc(h.get('as_of'))}</td>"
            f"<td>{_age(h.get('age_days'))}</td>"
            f"<td>{_esc(h.get('expected_update'))}</td>"
            f"<td>{_source_label(h)}</td>"
            f"<td><span class='pill {_freshness_class(h.get('freshness'))}'>{_esc(h.get('freshness'))}</span></td>"
            "</tr>"
        )
    return "".join(rows)


def _core_meta(snapshot: dict, field: str) -> str:
    h = snapshot.get("market", {}).get("data_health", {}).get(field, {})
    freshness = h.get("freshness")
    return (
        "<div class='card-meta'>"
        f"<span>{_esc(h.get('as_of'))} · {_age(h.get('age_days'))}</span>"
        f"<span class='pill {_freshness_class(freshness)}'>{_esc(h.get('source_grade'))}</span>"
        "</div>"
    )


def _tc_card(item: dict, title: str, basis: str) -> str:
    status = item.get("status")
    return f"""
    <div class='tc-card'>
      <div class='eyebrow'>{_esc(title)}</div>
      <div class='tc-value'>{fmt(item.get('value'),2)} <small>{_esc(item.get('unit'))}</small></div>
      <div class='muted'>{_esc(basis)}</div>
      <div class='meta'><span>As of {_esc(item.get('as_of'))}</span><span>Age {_age(item.get('age_days'))}</span></div>
      <div class='meta'><span>{_esc(item.get('expected_update'))}</span><span class='pill {_freshness_class(status)}'>{_esc(status)}</span></div>
      <div class='source'>{_esc(item.get('source_grade'))} · {_esc(item.get('source'))}</div>
    </div>"""


def _paper_card(rec: dict, label: str, snapshot: dict) -> str:
    p = rec.get("probability", {})
    health = snapshot.get("market", {}).get("data_health", {}).get("lme_3m", {})
    reference = rec.get("reference_price")
    reference_label = f"{fmt(reference,1)} · model" if reference is not None else (
        f"{fmt(snapshot.get('market', {}).get('lme_3m'),1)} · LME 3M market reference" if snapshot.get('market', {}).get('lme_3m') is not None else "Unavailable"
    )
    return f"""
    <div class='paper-card'>
      <div class='eyebrow'>{_esc(label)}</div>
      <div class='paper-action'>{_esc(rec.get('action'))}</div>
      <div class='muted'>{_esc(rec.get('reason'))}</div>
      <div class='kv'><span>Score</span><b>{fmt(rec.get('strategy_score'),1)}</b></div>
      <div class='kv'><span>Probability</span><b>{pct(p.get('p_profit'))}</b></div>
      <div class='kv'><span>Reference</span><b>{_esc(reference_label)}</b></div>
      <div class='muted'>Market as-of {_esc(health.get('as_of'))} · {_esc(health.get('source_grade'))}</div>
      <div class='muted'>Research inputs: {_esc(snapshot.get('technical_mode'))} · historical estimates require validation</div>
      <div class='source'>PAPER RESEARCH ONLY</div>
    </div>"""


def _line_path(points: list[dict], field: str, x, y) -> str:
    chunks, current = [], []
    for i, point in enumerate(points):
        value = point.get(field)
        if value is None:
            if current:
                chunks.append("M" + " L".join(current)); current = []
        else:
            current.append(f"{x(i):.1f},{y(float(value)):.1f}")
    if current:
        chunks.append("M" + " L".join(current))
    return " ".join(chunks)


def _close_charts(close: dict) -> str:
    points = close.get("chart_points") or []
    if len(points) < 2:
        return "<div class='notice warn'>長期收盤價圖：資料不足。</div>"
    width, left, right, plot_h = 960, 58, 18, 244
    plot_w = width - left - right
    values = [float(p[k]) for p in points for k in ("close", "sma14", "sma30", "ema20") if p.get(k) is not None]
    low, high = min(values), max(values)
    pad = max((high-low)*.08, 1.0); low -= pad; high += pad
    x = lambda i: left + plot_w*i/max(len(points)-1, 1)
    y = lambda v: 18 + (high-v)*plot_h/max(high-low, 1)
    colors = {"close":"#5cd4ff", "sma14":"#2ce6a6", "sma30":"#ffb253", "ema20":"#c991ff"}
    paths = "".join(f"<path class='chart-line {k}' d='{_line_path(points,k,x,y)}' stroke='{c}'/>" for k,c in colors.items())
    ticks = "".join(f"<line x1='{left}' y1='{18+i*61}' x2='{width-right}' y2='{18+i*61}' class='chart-grid'/><text x='4' y='{22+i*61}' class='chart-label'>{high-(high-low)*i/4:.0f}</text>" for i in range(5))
    time_indexes = sorted({round(i*(len(points)-1)/4) for i in range(5)})
    time_ticks = "".join(
        f"<line x1='{x(i):.1f}' y1='18' x2='{x(i):.1f}' y2='262' class='chart-time-grid'/>"
        f"<text x='{x(i):.1f}' y='281' text-anchor='{'start' if i == 0 else 'end' if i == len(points)-1 else 'middle'}' class='chart-label'>{_esc(points[i]['date'])}</text>"
        f"<text x='{x(i):.1f}' y='299' text-anchor='{'start' if i == 0 else 'end' if i == len(points)-1 else 'middle'}' class='chart-day-label'>第 {i+1}/{len(points)} 交易日</text>"
        for i in time_indexes
    )
    rsi = [(i,p) for i,p in enumerate(points) if p.get("rsi14") is not None]
    rsi_path = "M" + " L".join(f"{x(i):.1f},{18+(100-float(p['rsi14']))*1.24:.1f}" for i,p in rsi) if rsi else ""
    weekly = close.get("weekly_close_ranges") or []
    wvalues = [float(w[k]) for w in weekly for k in ("highest_close","lowest_close") if w.get(k) is not None]
    weekly_svg = "<div class='notice warn'>週收盤價區間：資料不足。</div>"
    if wvalues:
        wlow, whigh = min(wvalues), max(wvalues); wpad=max((whigh-wlow)*.08,1.0); wlow-=wpad; whigh+=wpad
        wx=lambda i:left+plot_w*i/max(len(weekly)-1,1); wy=lambda v:15+(whigh-v)*145/max(whigh-wlow,1)
        bars="".join(f"<line x1='{wx(i):.1f}' y1='{wy(float(w['highest_close'])):.1f}' x2='{wx(i):.1f}' y2='{wy(float(w['lowest_close'])):.1f}' class='range-line'/><circle cx='{wx(i):.1f}' cy='{wy(float(w['last_close'])):.1f}' r='2.2' class='range-close'/>" for i,w in enumerate(weekly))
        weekly_svg=f"<svg viewBox='0 0 {width} 190' role='img' aria-label='Weekly close-range bars, not OHLC candlesticks'><rect x='{left}' y='15' width='{plot_w}' height='145' class='chart-frame'/>{bars}<text x='{left}' y='182' class='chart-label'>{_esc(weekly[0]['week'])}</text><text x='{width-right}' y='182' text-anchor='end' class='chart-label'>{_esc(weekly[-1]['week'])}</text></svg>"
    return f"""<div class='chart-title'><b>長期 Close＋SMA14／SMA30／EMA20</b><span>交易日時間軸：{_esc(points[0]['date'])} → {_esc(points[-1]['date'])} · {len(points)} 個有效交易日</span></div>
    <div class='chart-legend'><span style='color:#5cd4ff'>━ Close</span><span style='color:#2ce6a6'>━ SMA14</span><span style='color:#ffb253'>━ SMA30</span><span style='color:#c991ff'>━ EMA20</span><span>Open：{_esc(close.get('open_status'))}</span></div>
    <svg viewBox='0 0 {width} 322' role='img' aria-label='Long-term LME zinc 3M reference Close with moving averages by trading day'><rect x='{left}' y='18' width='{plot_w}' height='{plot_h}' class='chart-frame'/>{ticks}{time_ticks}{paths}<text x='{width/2:.1f}' y='318' text-anchor='middle' class='chart-axis-title'>交易日（只含已完成的同源 Close）</text></svg>
    <div class='chart-title'><b>RSI14 · Close-only</b><span>30 / 50 / 70 reference levels</span></div>
    <svg viewBox='0 0 {width} 175' role='img' aria-label='Close-only RSI14'><rect x='{left}' y='18' width='{plot_w}' height='124' class='chart-frame'/><line x1='{left}' y1='55.2' x2='{width-right}' y2='55.2' class='rsi-band'/><line x1='{left}' y1='80' x2='{width-right}' y2='80' class='chart-grid'/><line x1='{left}' y1='104.8' x2='{width-right}' y2='104.8' class='rsi-band'/><path class='chart-line rsi' d='{rsi_path}'/><text x='25' y='59' class='chart-label'>70</text><text x='25' y='84' class='chart-label'>50</text><text x='25' y='109' class='chart-label'>30</text></svg>
    <div class='chart-title'><b>週收盤價區間圖</b><span>Weekly Close-Range · 非真實 OHLC／週 K</span></div>{weekly_svg}
    <p class='source'>直線是每週每日收盤價最高至最低區間，圓點是該週最後收盤價；不包含盤中 Open／High／Low。</p>
    <div class='notice warn'>外部互動 K 線尚未啟用：目前沒有完成合約身分與公開展示條款核對的免費來源。私人 OHLC CSV 仍與公開部署隔離。</div>"""


def _research_panel(snapshot: dict) -> str:
    market = snapshot.get("market", {})
    health = market.get("data_health", {})
    close = snapshot.get("market_research", {}).get("close_series", {})
    core_rows = "".join(
        "<tr>"
        f"<td>{_esc(label)}</td><td>{_esc(health.get(key, {}).get('as_of'))}</td>"
        f"<td>{_esc(health.get(key, {}).get('source'))}</td>"
        f"<td>{_esc(health.get(key, {}).get('source_grade'))}</td>"
        "</tr>"
        for key, label in (("lme_cash", "Cash"), ("lme_3m", "3M"), ("lme_inventory_t", "Warehouse stock"))
    )
    def close_metric(key: str, minimum: int, suffix: str = "USD/t") -> str:
        value = close.get(key)
        return (f"{fmt(value, 2)} {suffix}" if value is not None and int(close.get('close_indicator_sessions') or 0) >= minimum
                else f"資料不足（需要 {minimum} 筆有效交易日）")
    return f"""
    <section class='panel s12' id='market-research'><h2>市場資料研究 · 來源與缺口</h2>
      <div class='health-scroll'><table><tr><th>資料</th><th>交易日</th><th>來源</th><th>來源等級</th></tr>{core_rows}</table></div>
      <h3>收盤價趨勢：{'可分析' if close.get('latest_close') is not None else '資料不足'}</h3>
      <p class='muted'>同源 LME 3M 參考收盤價 · 最後交易日 {_esc(close.get('as_of'))} · 有效歷史 {_esc(close.get('observations', 0))} 筆 · 連續指標視窗 {_esc(close.get('close_indicator_sessions', 0))} 筆 · {_esc(close.get('source_grade'))} / {_esc(close.get('source'))}</p>
      <p class='muted'>資料缺口：超過 7 日的中斷 {_esc(close.get('material_gap_count', 0))} 次 · 最長相鄰日期間隔 {_esc(close.get('largest_gap_days'))} 日。此規則不是交易所假日曆；中斷前的數值不參與本期指標與歷史波動。</p>
      <div class='market-cards'>
        <div class='mcard'><div class='eyebrow'>最新收盤價 / SMA14</div><div class='mvalue'>{close_metric('latest_close', 1)}</div><div class='muted'>SMA14：{close_metric('sma_14', 14)}</div></div>
        <div class='mcard'><div class='eyebrow'>SMA30 / EMA20</div><div class='mvalue'>{close_metric('sma_30', 30)}</div><div class='muted'>EMA20：{close_metric('ema_20', 20)}</div></div>
        <div class='mcard'><div class='eyebrow'>收盤價版 RSI14</div><div class='mvalue'>{close_metric('rsi_14', 15, '/100')}</div><div class='muted'>只依同源 Close，非盤中資料；需 14 筆相鄰收盤變化。</div></div>
      </div>
      <p class='source'>SMA14／SMA30 是過去 14／30 筆有效交易日收盤價的算術平均；EMA20 是 20 期指數加權平均。來源中斷超過 7 個日曆日會重啟指標視窗。均線與 RSI 描述歷史，不預測下一日。</p>
      <p class='muted'>本面板只使用已完成交易日的同源收盤價，不呈現盤中價格。</p>
      <div class='close-chart' data-chart-points='{_esc(len(close.get("chart_points") or []))}'>{_close_charts(close)}</div>
      <div class='market-cards'>
        <div class='mcard'><div class='eyebrow'>20 筆報酬的歷史波動</div><div class='mvalue'>{fmt(close.get('volatility_20_pct'),2)}<small> % 年化</small></div><div class='muted'>有效報酬 {_esc(close.get('returns_20',0))}/20</div></div>
        <div class='mcard'><div class='eyebrow'>60 筆報酬的歷史波動</div><div class='mvalue'>{fmt(close.get('volatility_60_pct'),2)}<small> % 年化</small></div><div class='muted'>有效報酬 {_esc(close.get('returns_60',0))}/60</div></div>
        <div class='mcard'><div class='eyebrow'>同源收盤價序列</div><div class='mvalue'>{_esc(close.get('observations',0))}<small> 筆</small></div><div class='muted'>截至 {_esc(close.get('as_of'))} · {_esc(close.get('source_grade'))}</div></div>
      </div>
      <p class='source'>來源 {_esc(close.get('source'))} · {_esc(close.get('series'))}；方法：{_esc(close.get('method'))}。這是已觀察到的變動程度，不是未來漲跌或獲利機率。</p>
    </section>"""


def build_dashboard_v27(snapshot: dict, candle_frames: dict[str, pd.DataFrame], trades: list[dict], perf: dict) -> Path:
    build_legacy_dashboard(snapshot, candle_frames, trades, perf)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    market = snapshot.get("market", {})
    gate = snapshot.get("core_data_gate", {})
    tc = snapshot.get("china_tc", {})
    iq = snapshot.get("market_quality", {})
    proc = snapshot.get("procurement", {})
    proc_state = snapshot.get("procurement_state", {})
    proc_q = snapshot.get("procurement_quality", {})
    inv = snapshot.get("investment", {})
    technical_mode = snapshot.get("technical_mode", "MISSING")
    include_private = bool(snapshot.get("privacy", {}).get("public_dashboard_include_private", False))

    def private_value(value, digits=0, suffix=""):
        return fmt(value, digits, suffix) if include_private else "••••"

    tc_html = "".join([
        _tc_card(tc.get("import_weekly", {}), "China Import TC · Weekly", "CIF China main ports · USD/dmt"),
        _tc_card(tc.get("domestic_weekly", {}), "China Domestic TC · Weekly", "Zn50 domestic concentrate · source unit retained"),
        _tc_card(tc.get("domestic_monthly", {}), "China Domestic TC · Monthly", "Zn50 domestic concentrate · monthly reference"),
        _tc_card(tc.get("annual_benchmark", {}), "Annual Benchmark TC", "Industry annual benchmark · not spot TC"),
    ])

    gate_class = _freshness_class(gate.get("status"))
    candle_daily = Path(PUBLIC_DIR / "assets" / "candle_daily.png")
    candle_weekly = Path(PUBLIC_DIR / "assets" / "candle_weekly.png")
    for stale_chart in (candle_daily, candle_weekly):
        stale_chart.unlink(missing_ok=True)
    candle_block = "<div class='notice warn'>Close-only research: SMA14 / SMA30 / EMA20 / RSI14 are historical descriptors; no intraday prices or execution.</div>"

    page = f"""<!doctype html>
<html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Zinc Intelligence V2.7</title>
<style>
:root{{--bg:#06111f;--panel:#0b1d31;--panel2:#0e263f;--line:#1c4668;--text:#edf7ff;--muted:#8ca9c1;--cyan:#5cd4ff;--green:#2ce6a6;--orange:#ffb253;--red:#ff6879}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 10% 0,#123454 0,#06111f 36%);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}}
a{{color:#8addff}}.wrap{{max-width:1600px;margin:auto;padding:18px}}.top{{display:flex;justify-content:space-between;gap:16px;align-items:flex-end;padding:8px 2px 18px;border-bottom:1px solid var(--line);margin-bottom:14px}}
h1{{margin:0;font-size:28px;line-height:1.12}}h2{{font-size:14px;letter-spacing:.08em;color:#9edfff;margin:0 0 12px}}.muted{{color:var(--muted)}}.eyebrow{{font-size:11px;letter-spacing:.08em;color:#91b8d4;text-transform:uppercase}}.grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:12px}}.panel{{background:linear-gradient(180deg,rgba(14,38,63,.98),rgba(8,26,45,.98));border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 12px 30px rgba(0,0,0,.16)}}.s12{{grid-column:span 12}}.s8{{grid-column:span 8}}.s6{{grid-column:span 6}}.s4{{grid-column:span 4}}.s3{{grid-column:span 3}}.hero{{font-size:34px;font-weight:850;color:var(--green);letter-spacing:-.02em}}.market-cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.mcard,.tc-card,.paper-card{{position:relative;overflow:hidden;background:linear-gradient(145deg,#0a2138,#081a2d);border:1px solid #1c4a70;border-radius:12px;padding:14px}}.mcard:before,.tc-card:before{{content:'';position:absolute;inset:0 auto 0 0;width:3px;background:linear-gradient(180deg,var(--cyan),var(--green));opacity:.8}}.mvalue,.tc-value{{font-size:26px;font-weight:850;letter-spacing:-.025em;margin:5px 0 3px}}small{{font-size:11px;color:var(--muted);letter-spacing:0}}.meta,.kv,.card-meta{{display:flex;justify-content:space-between;gap:8px;margin-top:8px;font-size:12px}}.card-meta{{align-items:center;color:#7fa4bf;font-size:10px;padding-top:8px;border-top:1px solid rgba(93,157,199,.14)}}.source{{font-size:10px;color:#7192ad;margin-top:8px;overflow-wrap:anywhere}}.pill{{display:inline-block;padding:3px 7px;border-radius:99px;font-size:10px;font-weight:750;white-space:nowrap}}.ok{{color:var(--green);background:#073d34}}.warn{{color:var(--orange);background:#452f0e}}.bad{{color:#ff8a98;background:#48151c}}.health-scroll{{width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;border-radius:10px}}table{{width:100%;border-collapse:collapse}}.health-scroll table{{min-width:760px}}th,td{{padding:9px 8px;border-bottom:1px solid #173b59;text-align:left;vertical-align:top}}th{{font-size:11px;color:#8fbad7;position:sticky;top:0;background:#0b1d31}}.tc-grid,.paper-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.paper-grid{{grid-template-columns:1fr 1fr}}.paper-action{{font-size:18px;font-weight:800;color:var(--cyan);margin:5px 0}}.notice{{padding:12px;border-radius:9px;margin:8px 0}}img{{width:100%;border-radius:9px}}details{{margin-top:8px}}.footer{{text-align:center;color:#6786a0;padding:24px}}
.close-chart{{margin-top:14px}}.close-chart svg{{width:100%;height:auto;display:block;margin:4px 0 12px}}.chart-frame{{fill:#071827;stroke:#1c4668}}.chart-grid{{stroke:#173b59;stroke-width:1}}.chart-time-grid{{stroke:#214866;stroke-width:1;stroke-dasharray:3 5}}.chart-line{{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}}.chart-line.close{{stroke-width:2.8}}.chart-line.rsi{{stroke:#5cd4ff}}.rsi-band{{stroke:#ffb253;stroke-width:1;stroke-dasharray:5 5}}.chart-label,.chart-day-label,.chart-axis-title{{fill:#8ca9c1;font-size:11px}}.chart-day-label{{fill:#6f91aa}}.chart-axis-title{{fill:#9edfff}}.chart-title,.chart-legend{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:13px 0 6px}}.chart-title span,.chart-legend{{color:#8ca9c1;font-size:11px}}.chart-legend{{justify-content:flex-start}}.range-line{{stroke:#5cd4ff;stroke-width:3;opacity:.7}}.range-close{{fill:#ffb253}}
@media(max-width:1180px){{.tc-grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:1000px){{.s8,.s6,.s4,.s3{{grid-column:span 12}}.market-cards{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:680px){{.wrap{{padding:10px}}.top{{align-items:flex-start;flex-direction:column;padding:6px 2px 14px}}h1{{font-size:23px}}.panel{{padding:13px;border-radius:12px}}.hero{{font-size:30px}}.market-cards,.tc-grid,.paper-grid{{grid-template-columns:1fr}}.mvalue,.tc-value{{font-size:25px}}.meta,.kv{{gap:12px}}.health-scroll{{margin:0 -2px;width:calc(100% + 4px)}}}}
</style></head><body><div class='wrap'>
<div class='top'><div><h1>Zn · ZINC INTELLIGENCE V2.7</h1><div class='muted'>Accuracy-first · Official-first · Freshness-aware · Procurement privacy preserved</div></div><div><b>{_esc(snapshot.get('run_date'))}</b><br><span class='muted'>Model {_esc(snapshot.get('model_version'))}</span></div></div>
<div class='grid'>
<section class='panel s3'><h2>CORE DATA GATE</h2><div class='hero'>{_esc(gate.get('status'))}</div><span class='pill {gate_class}'>{len(gate.get('usable_core',[]))} core usable</span><p class='muted'>Stale: {_esc(', '.join(gate.get('stale_core',[])) or 'None')}<br>Missing: {_esc(', '.join(gate.get('missing_core',[])) or 'None')}</p></section>
<section class='panel s3'><h2>MARKET REGIME</h2><div class='hero'>{_esc(snapshot.get('market_regime'))}</div><div>ZTI / Score <b>{fmt(snapshot.get('market_score'),1)}</b></div><div>Confidence <b>{fmt(iq.get('confidence'),0)}/100</b></div></section>
<section class='panel s6'><h2>LME ZINC · CORE REFERENCES</h2><div class='market-cards'>
<div class='mcard'><div class='eyebrow'>Cash</div><div class='mvalue'>{fmt(market.get('lme_cash'),1)} <small>USD/t</small></div><div class='muted'>Cash−3M {fmt(market.get('cash_3m'),1)}</div>{_core_meta(snapshot,'lme_cash')}</div>
<div class='mcard'><div class='eyebrow'>3M</div><div class='mvalue'>{fmt(market.get('lme_3m'),1)} <small>USD/t</small></div><div class='muted'>Technical mode {_esc(technical_mode)}</div>{_core_meta(snapshot,'lme_3m')}</div>
<div class='mcard'><div class='eyebrow'>Inventory</div><div class='mvalue'>{fmt(market.get('lme_inventory_t'),0)} <small>t</small></div><div class='muted'>Live {fmt(market.get('live_warrants_t'),0)} · Cancelled {fmt(market.get('cancelled_warrants_t'),0)} · Ratio {fmt(market.get('cancelled_ratio_pct'),1)}%</div>{_core_meta(snapshot,'lme_inventory_t')}</div>
</div></section>
<section class='panel s12'><h2>DATA HEALTH · SOURCE / AS-OF / DELAY</h2><div class='health-scroll' role='region' aria-label='Data health table' tabindex='0'><table><tr><th>Field</th><th>As of</th><th>Age</th><th>Expected update</th><th>Source grade / provider</th><th>Freshness</th></tr>{_health_rows(snapshot)}</table></div></section>
{_research_panel(snapshot)}
<section class='panel s12'><h2>CHINA ZINC CONCENTRATE TC</h2><div class='tc-grid'>{tc_html}</div><p class='muted'>不同 basis 不混算：Import TC、Domestic TC、Annual Benchmark 分開保存與判讀。延遲一日/一週/月度可接受，但日期與來源必須可追溯。</p></section>
<section class='panel s6'><h2>🏭 PROCUREMENT</h2>{"<div class='notice warn'>Public privacy mode：精確庫存、60D需求與建議採購噸數已遮罩。</div>" if not include_private else ''}<div class='market-cards'>
<div class='mcard'><div class='eyebrow'>Coverage</div><div class='mvalue'>{fmt(proc.get('coverage_days'),1)} <small>days</small></div><div class='muted'>{_esc(proc.get('inventory_band'))}</div></div>
<div class='mcard'><div class='eyebrow'>Action</div><div class='mvalue'>{_esc(proc.get('action'))}</div><div class='muted'>Input {_esc(proc_q.get('status'))}</div></div>
<div class='mcard'><div class='eyebrow'>Private inputs</div><div class='mvalue'>{private_value(proc_state.get('current_inventory_t'),0)} / {private_value(proc_state.get('demand_60d_t'),0)}</div><div class='muted'>inventory / 60D demand</div></div>
</div></section>
<section class='panel s6'><h2>📈 PAPER RESEARCH</h2><div class='paper-grid'>{_paper_card(inv.get('conservative',{}),'Conservative',snapshot)}{_paper_card(inv.get('aggressive',{}),'Aggressive',snapshot)}</div></section>
<section class='panel s8'><h2>TECHNICAL DATA</h2>{candle_block}</section>
<section class='panel s4'><h2>MODEL / PIPELINE STATUS</h2><table><tr><td>Technical mode</td><td>{_esc(technical_mode)}</td></tr><tr><td>Close-history points</td><td>{_esc(snapshot.get('free_close_history_points'))}</td></tr><tr><td>Market confidence</td><td>{fmt(iq.get('confidence'),0)}</td></tr><tr><td>Provider failures</td><td>{sum(1 for v in market.get('provider_status',{}).values() if str(v.get('status')).upper()=='ERROR')}</td></tr></table><p><a href='research.html'>Research Lab →</a></p></section>
</div><div class='footer'>Zinc Intelligence V2.7 · Public dashboard uses masked procurement inputs · Investment module is paper research only.</div></div></body></html>"""

    out = PUBLIC_DIR / "index.html"
    out.write_text(page, encoding="utf-8")
    return out
