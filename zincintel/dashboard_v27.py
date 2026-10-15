from __future__ import annotations

import html
import json
import math
from pathlib import Path

import pandas as pd

from .dashboard import build_dashboard as build_legacy_dashboard, fmt, pct
from .utils import PUBLIC_DIR
from .visual_language import (SERIES_STYLES, VISUAL_CSS, asset_icon,
                              series_legend, source_badge, source_legend)


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
    return f"{source_badge(grade, h.get('freshness'))} <span>{_esc(src)}</span>"


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
        f"{source_badge(h.get('source_grade'), freshness)}"
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
      <div class='kv'><span>Risk probability</span><b>NOT CALIBRATED</b></div>
      <div class='kv'><span>Reference</span><b>{_esc(reference_label)}</b></div>
      <div class='muted'>Market as-of {_esc(health.get('as_of'))} · {_esc(health.get('source_grade'))}</div>
      <div class='muted'>Research inputs: {_esc(snapshot.get('technical_mode'))} · historical estimates require validation</div>
      <div class='source'>DESCRIPTIVE RESEARCH ONLY · no execution or return forecast</div>
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


def _interactive_close_script() -> str:
    script = """<script>
(() => {
  const source = document.getElementById('close-chart-data');
  const svg = document.getElementById('close-price-chart');
  const tip = document.getElementById('close-chart-tooltip');
  if (!source || !svg || !tip) return;
  const all = JSON.parse(source.textContent);
  const NS = 'http://www.w3.org/2000/svg', W=960, H=390, L=64, R=72, T=18, B=82;
  const esc = s => String(s).replace(/[&<>\"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  const mondayKey = d => { const x=new Date(d); x.setUTCDate(x.getUTCDate()-((x.getUTCDay()+6)%7)); return x.toISOString().slice(0,10); };
  const niceStep = range => { const raw=range/6, power=10**Math.floor(Math.log10(Math.max(raw,1))), n=raw/power; return (n<=1?1:n<=2?2:n<=5?5:10)*power; };
  function render(days) {
    const data = days==='all' ? all : all.slice(-Number(days));
    if (data.length < 2) return;
    const dates=data.map(d=>new Date(d.date+'T00:00:00Z')), t0=+dates[0], t1=+dates[dates.length-1];
    const vals=data.flatMap(d=>['close','sma14','sma30','ema20'].map(k=>d[k]).filter(Number.isFinite));
    const step=niceStep(Math.max(...vals)-Math.min(...vals)), ymin=Math.floor(Math.min(...vals)/step)*step, ymax=Math.ceil(Math.max(...vals)/step)*step;
    const x=t=>L+(W-L-R)*(+t-t0)/Math.max(t1-t0,1), y=v=>T+(H-T-B)*(ymax-v)/Math.max(ymax-ymin,1);
    let out=`<rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" class="chart-frame"/>`;
    for(let v=ymin;v<=ymax+.001;v+=step) out+=`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" class="chart-grid"/><text x="4" y="${y(v)+4}" class="chart-label">${v.toLocaleString()}</text>`;
    let lastWeek='';
    data.forEach((d,i)=>{ const wk=mondayKey(dates[i]), first=wk!==lastWeek; lastWeek=wk; const show=data.length<=20 || (data.length<=60 && [1,3,5].includes(dates[i].getUTCDay())) || first; out+=`<line x1="${x(dates[i])}" y1="${T}" x2="${x(dates[i])}" y2="${H-B}" class="${first?'chart-week-grid':'chart-day-grid'}"/>`; if(show) out+=`<text x="${x(dates[i])}" y="${H-57}" text-anchor="middle" class="chart-label">${d.date.slice(5)}</text><text x="${x(dates[i])}" y="${H-42}" text-anchor="middle" class="chart-day-label">${['日','一','二','三','四','五','六'][dates[i].getUTCDay()]}</text>`; });
    const series=[['close','__CLOSE__',''],['sma14','__SMA14__','__SMA14_DASH__'],['sma30','__SMA30__','__SMA30_DASH__'],['ema20','__EMA20__','']];
    series.forEach(([key,color,dash])=>{ let path='', open=false; data.forEach((d,i)=>{ if(!Number.isFinite(d[key])) {open=false;return;} path+=(open?' L':'M')+x(dates[i]).toFixed(1)+','+y(d[key]).toFixed(1);open=true; }); out+=`<path d="${path}" class="chart-line ${key}" stroke="${color}" ${dash?`stroke-dasharray="${dash}"`:''}/>`; });
    const last=data[data.length-1], lx=x(dates[dates.length-1]); out+=`<circle cx="${lx}" cy="${y(last.close)}" r="4" class="last-close"/><text x="${W-R+7}" y="${y(last.close)+4}" class="last-price">${Number(last.close).toLocaleString()} Close</text><text x="${W/2}" y="${H-8}" text-anchor="middle" class="chart-axis-title">實際交易日期（日／週分隔）</text><rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" fill="transparent" data-hover/>`;
    svg.innerHTML=out; svg.setAttribute('aria-label',`LME zinc 3M Close chart from ${data[0].date} to ${last.date}, ${data.length} trading days`);
    const hover=svg.querySelector('[data-hover]');
    hover.addEventListener('pointermove',e=>{ const box=svg.getBoundingClientRect(), px=(e.clientX-box.left)*W/box.width, target=t0+(px-L)/(W-L-R)*(t1-t0); let best=0; dates.forEach((d,i)=>{if(Math.abs(+d-target)<Math.abs(+dates[best]-target))best=i;}); const d=data[best]; tip.hidden=false; tip.innerHTML=`<b>${esc(d.date)} · 星期${['日','一','二','三','四','五','六'][dates[best].getUTCDay()]}</b><br>Close ${Number(d.close).toLocaleString()} USD/t<br>SMA14 ${d.sma14??'—'} · SMA30 ${d.sma30??'—'}<br>EMA20 ${d.ema20??'—'} · RSI14 ${d.rsi14??'—'}`; tip.style.left=Math.min(e.clientX-box.left+12,box.width-210)+'px'; tip.style.top=Math.max(e.clientY-box.top-74,4)+'px'; });
    hover.addEventListener('pointerleave',()=>tip.hidden=true);
    document.getElementById('close-period-label').textContent=`${data[0].date} → ${last.date} · ${data.length} 個交易日`;
  }
  document.querySelectorAll('[data-close-days]').forEach(btn=>btn.addEventListener('click',()=>{ document.querySelectorAll('[data-close-days]').forEach(b=>b.classList.remove('active')); btn.classList.add('active'); render(btn.dataset.closeDays); }));
  render('60');
})();
</script>"""
    replacements = {
        "__CLOSE__": SERIES_STYLES["close"]["color"],
        "__SMA14__": SERIES_STYLES["sma14"]["color"],
        "__SMA14_DASH__": SERIES_STYLES["sma14"]["dash"],
        "__SMA30__": SERIES_STYLES["sma30"]["color"],
        "__SMA30_DASH__": SERIES_STYLES["sma30"]["dash"],
        "__EMA20__": SERIES_STYLES["ema20"]["color"],
    }
    for token, value in replacements.items():
        script = script.replace(token, str(value))
    return script


def _close_charts(close: dict) -> str:
    points = close.get("chart_points") or []
    if len(points) < 2:
        return "<div class='notice warn'>長期收盤價圖：資料不足。</div>"
    chart_json = json.dumps(points, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    width, left, right, plot_h = 960, 58, 18, 244
    plot_w = width - left - right
    values = [float(p[k]) for p in points for k in ("close", "sma14", "sma30", "ema20") if p.get(k) is not None]
    low, high = min(values), max(values)
    pad = max((high-low)*.08, 1.0); low -= pad; high += pad
    x = lambda i: left + plot_w*i/max(len(points)-1, 1)
    y = lambda v: 18 + (high-v)*plot_h/max(high-low, 1)
    colors = {key: SERIES_STYLES[key]["color"] for key in ("close", "sma14", "sma30", "ema20")}
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
    return f"""<div class='chart-title'><b>長期 Close＋SMA14／SMA30／EMA20</b><span id='close-period-label'>交易日時間軸：{_esc(points[0]['date'])} → {_esc(points[-1]['date'])} · {len(points)} 個有效交易日</span></div>
    <div class='period-controls' aria-label='收盤價圖期間'><button type='button' data-close-days='20'>20交易日</button><button type='button' data-close-days='60' class='active'>60交易日</button><button type='button' data-close-days='120'>120交易日</button><button type='button' data-close-days='all'>全部</button></div>
    {series_legend(["close", "sma14", "sma30", "ema20"], extra=f"Open: {close.get('open_status') or 'MISSING'}")}
    <div class='interactive-chart'><svg id='close-price-chart' viewBox='0 0 {width} 390' role='img' aria-label='Long-term LME zinc 3M reference Close with moving averages by trading day'><rect x='{left}' y='18' width='{plot_w}' height='{plot_h}' class='chart-frame'/>{ticks}{time_ticks}{paths}<text x='{width/2:.1f}' y='318' text-anchor='middle' class='chart-axis-title'>交易日（只含已完成的同源 Close）</text></svg><div id='close-chart-tooltip' class='chart-tooltip' hidden></div></div>
    <div class='chart-title'><b>RSI14 · Close-only</b><span>30 / 50 / 70 reference levels</span></div>
    <svg viewBox='0 0 {width} 175' role='img' aria-label='Close-only RSI14'><rect x='{left}' y='18' width='{plot_w}' height='124' class='chart-frame'/><line x1='{left}' y1='55.2' x2='{width-right}' y2='55.2' class='rsi-band'/><line x1='{left}' y1='80' x2='{width-right}' y2='80' class='chart-grid'/><line x1='{left}' y1='104.8' x2='{width-right}' y2='104.8' class='rsi-band'/><path class='chart-line rsi' d='{rsi_path}'/><text x='25' y='59' class='chart-label'>70</text><text x='25' y='84' class='chart-label'>50</text><text x='25' y='109' class='chart-label'>30</text></svg>
    <div class='chart-title'><b>週收盤價區間圖</b><span>Weekly Close-Range · 非真實 OHLC／週 K</span></div>{weekly_svg}
    <p class='source'>直線是每週每日收盤價最高至最低區間，圓點是該週最後收盤價；不包含盤中 Open／High／Low。</p>
    <div class='notice warn'>外部互動 K 線尚未啟用：目前沒有完成合約身分與公開展示條款核對的免費來源。私人 OHLC CSV 仍與公開部署隔離。</div>
    <script type='application/json' id='close-chart-data'>{chart_json}</script>{_interactive_close_script()}"""


def _trend_panel(close: dict) -> str:
    trend = close.get("trend") or {}
    regime = trend.get("regime", "INSUFFICIENT_DATA")
    components = trend.get("components") or {}
    component_labels = {"close_vs_ema20":"Close vs EMA20", "ema20_vs_sma30":"EMA20 vs SMA30",
                        "ema20_slope_5d":"EMA20 slope 5D", "sma30_slope_10d":"SMA30 slope 10D",
                        "rsi14":"RSI14", "close_position_20d":"Close position 20D"}
    rows = "".join(f"<tr><td>{_esc(component_labels.get(k,k))}</td><td>{int(v):+d}</td></tr>" for k,v in components.items())
    reasons = "".join(f"<li>{_esc(reason)}</li>" for reason in trend.get("reasons", []))
    return f"""<div class='trend-panel'>
      <div class='trend-summary'><div><div class='eyebrow'>Close-only trend regime</div><div class='trend-regime'>{_esc(regime)}</div><div class='muted'>描述歷史趨勢，不是買賣指令</div></div>
      <div><div class='eyebrow'>Trend Score</div><div class='trend-score'>{_esc(trend.get('score'))}<small> / 100</small></div></div>
      <div><div class='eyebrow'>Persistence</div><div class='trend-score'>{_esc(trend.get('persistence_days',0))}<small> 交易日</small></div></div>
      <div><div class='eyebrow'>Data / Risk</div><div><b>{_esc(trend.get('data_confidence'))}</b> · {_esc(trend.get('risk_level'))}</div></div></div>
      <div class='trend-detail'><div><h3>判定原因</h3><ul>{reasons}</ul></div><div><h3>透明計分</h3><table><tr><th>組成</th><th>分數</th></tr>{rows}</table></div></div>
      <p class='source'>Strong Bull ≥ +60；Bull +25～+59；Neutral −24～+24；Bear −59～−25；Strong Bear ≤ −60。新狀態需以持續天數核對；歷史波動只表示風險程度，不決定方向。</p>
    </div>"""


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
      <p class='muted'>取得狀態：{_esc(close.get('retrieval_status') or 'CURRENT_FETCH')} · 當前來源狀態 {_esc(close.get('current_provider_status') or '—')}{' · 沿用最近一次已驗證歷史，未新增或改寫價格' if close.get('retrieval_status') == 'CARRY_FORWARD_LAST_VERIFIED' else ''}</p>
      <p class='muted'>資料缺口：超過 7 日的中斷 {_esc(close.get('material_gap_count', 0))} 次 · 最長相鄰日期間隔 {_esc(close.get('largest_gap_days'))} 日。此規則不是交易所假日曆；中斷前的數值不參與本期指標與歷史波動。</p>
      <p class='muted'>歷史覆蓋：{_esc(close.get('coverage_start'))} → {_esc(close.get('coverage_end'))} · 分年筆數 {_esc(close.get('coverage_by_year'))} · 目標起始 {_esc(close.get('requested_history_start'))} · {'已覆蓋' if close.get('requested_start_covered') else '尚有缺口'}</p>
      <div class='market-cards'>
        <div class='mcard'><div class='eyebrow'>最新收盤價 / SMA14</div><div class='mvalue'>{close_metric('latest_close', 1)}</div><div class='muted'>SMA14：{close_metric('sma_14', 14)}</div></div>
        <div class='mcard'><div class='eyebrow'>SMA30 / EMA20</div><div class='mvalue'>{close_metric('sma_30', 30)}</div><div class='muted'>EMA20：{close_metric('ema_20', 20)}</div></div>
        <div class='mcard'><div class='eyebrow'>收盤價版 RSI14</div><div class='mvalue'>{close_metric('rsi_14', 15, '/100')}</div><div class='muted'>只依同源 Close，非盤中資料；需 14 筆相鄰收盤變化。</div></div>
      </div>
      <p class='source'>SMA14／SMA30 是過去 14／30 筆有效交易日收盤價的算術平均；EMA20 是 20 期指數加權平均。來源中斷超過 7 個日曆日會重啟指標視窗。均線與 RSI 描述歷史，不預測下一日。</p>
      <p class='muted'>本面板只使用已完成交易日的同源收盤價，不呈現盤中價格。</p>
      {_trend_panel(close)}
      <div class='close-chart' data-chart-points='{_esc(len(close.get("chart_points") or []))}'>{_close_charts(close)}</div>
      <div class='market-cards'>
        <div class='mcard'><div class='eyebrow'>20 筆報酬的歷史波動</div><div class='mvalue'>{fmt(close.get('volatility_20_pct'),2)}<small> % 年化</small></div><div class='muted'>有效報酬 {_esc(close.get('returns_20',0))}/20</div></div>
        <div class='mcard'><div class='eyebrow'>60 筆報酬的歷史波動</div><div class='mvalue'>{fmt(close.get('volatility_60_pct'),2)}<small> % 年化</small></div><div class='muted'>有效報酬 {_esc(close.get('returns_60',0))}/60</div></div>
        <div class='mcard'><div class='eyebrow'>同源收盤價序列</div><div class='mvalue'>{_esc(close.get('observations',0))}<small> 筆</small></div><div class='muted'>截至 {_esc(close.get('as_of'))} · {_esc(close.get('source_grade'))}</div></div>
      </div>
      <p class='source'>來源 {_esc(close.get('source'))} · {_esc(close.get('series'))}；方法：{_esc(close.get('method'))}。這是已觀察到的變動程度，不是未來漲跌或獲利機率。</p>
    </section>"""


def _compass(close: dict) -> str:
    trend = close.get("trend", {})
    regime = trend.get("regime", "INSUFFICIENT_DATA")
    levels = ["STRONG_BEAR", "BEAR", "NEUTRAL", "BULL", "STRONG_BULL"]
    labels = ["Strong Bear", "Bear", "Neutral", "Bull", "Strong Bull"]
    colors = ["#d94a4f", "#ef8a83", "#c7ced1", "#8dd8cf", "#087b70"]
    cx, cy, outer, inner = 150.0, 148.0, 126.0, 76.0
    def point(radius: float, angle: float) -> tuple[float, float]:
        rad = math.radians(angle)
        return cx + radius * math.cos(rad), cy - radius * math.sin(rad)
    segments = []
    for i, (level, label, color) in enumerate(zip(levels, labels, colors)):
        a0, a1 = 180 - i * 36, 180 - (i + 1) * 36
        x0, y0 = point(outer, a0); x1, y1 = point(outer, a1)
        ix1, iy1 = point(inner, a1); ix0, iy0 = point(inner, a0)
        path = f"M{x0:.1f},{y0:.1f} A{outer},{outer} 0 0 1 {x1:.1f},{y1:.1f} L{ix1:.1f},{iy1:.1f} A{inner},{inner} 0 0 0 {ix0:.1f},{iy0:.1f} Z"
        tx, ty = point(101, (a0 + a1) / 2)
        selected = " gauge-selected" if level == regime else ""
        segments.append(f"<path d='{path}' fill='{color}' class='gauge-segment{selected}'/><text x='{tx:.1f}' y='{ty:.1f}' text-anchor='middle' class='gauge-label'>{_esc(label)}</text>")
    angle = {level: 162 - i * 36 for i, level in enumerate(levels)}.get(regime, 90)
    nx, ny = point(73, angle)
    reasons = "".join(f"<li>{_esc(x)}</li>" for x in trend.get("reasons", [])[:4])
    return f"""<aside class='cockpit-side'><div class='eyebrow'>LME CLOSE-ONLY · TREND COMPASS</div>
      <svg class='compass-gauge' viewBox='0 0 300 176' role='img' aria-label='Five-level historical trend compass'>{''.join(segments)}<line x1='{cx}' y1='{cy}' x2='{nx:.1f}' y2='{ny:.1f}' class='gauge-needle'/><circle cx='{cx}' cy='{cy}' r='10' class='gauge-hub'/></svg>
      <div class='compass-result'>{_esc(regime.replace('_',' '))}</div>
      <div class='score-line'><b>Trend Score {_esc(trend.get('score'))} / 100</b><span>{_esc(trend.get('persistence_days',0))} sessions</span></div>
      <ul class='compact-reasons'>{reasons}</ul>
      <p class='source'>描述已發生的趨勢，不是買賣指令或獲利機率。</p></aside>"""


def _trend_band(close: dict) -> str:
    current = close.get("trend", {}).get("regime", "INSUFFICIENT_DATA")
    levels = [("STRONG_BEAR", "Strong Bear"), ("BEAR", "Bear"), ("NEUTRAL", "Neutral"),
              ("BULL", "Bull"), ("STRONG_BULL", "Strong Bull")]
    items = "".join(
        f"<div class='band-item band-{key.lower()} {'active' if key == current else ''}'><b>{label}</b><span>{'目前狀態' if key == current else ''}</span></div>"
        for key, label in levels
    )
    return f"""<section class='panel s12 trend-ribbon' id='trend-regime'><div class='section-head'><h2>TREND REGIME · FIVE-LEVEL HISTORICAL STATE</h2><span class='muted'>Close-only · descriptive, not a forecast</span></div><div class='trend-band'>{items}</div></section>"""


def _shfe_panel(snapshot: dict) -> str:
    shfe = snapshot.get("market_research", {}).get("shfe_zinc", {})
    points = shfe.get("chart_points") or []
    if not points:
        return "<section class='panel s12'><h2>SHFE ZINC · TRUE DAILY OHLC</h2><div class='notice warn'>MISSING · 本次沒有通過驗證的 SHFE 日線，因此不顯示舊圖。</div></section>"
    payload = json.dumps(points, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"""<section class='panel s12 shfe-panel' id='shfe-zinc'><div class='section-head'><div><h2>SHFE ZINC · TRUE DAILY OHLC</h2>
      <div class='muted'>獨立跨市場參考，絕非 LME K 線 · {_esc(shfe.get('source_grade'))} · 截至 {_esc(shfe.get('as_of'))}</div></div>
      <div class='status-chip'>VALIDATED · {_esc(shfe.get('observations'))} sessions</div></div>
      <div class='period-controls shfe-controls'><button data-shfe-days='20'>20</button><button data-shfe-days='60'>60</button><button class='active' data-shfe-days='120'>120</button><button data-shfe-days='all'>全部</button></div>
      {series_legend(["up", "down", "sma20", "sma50", "ema20"], extra="◆ Contract roll")}
      <div class='interactive-chart'><svg id='shfe-candle-chart' viewBox='0 0 1120 480' role='img' aria-label='SHFE Zinc validated daily OHLC candlestick chart'></svg><div id='shfe-tooltip' class='chart-tooltip' hidden></div></div>
      <div class='research-strip'><div><span>Latest</span><b>{fmt(shfe.get('latest_close'),0)} CNY/t</b></div><div><span>Contract</span><b>{_esc(shfe.get('latest_contract'))}</b></div><div><span>Rolls</span><b>{_esc(shfe.get('roll_count'))}</b></div><div><span>Rule</span><b>Max open interest</b></div></div>
      <p class='source'>來源：SHFE official daily trading data · 每日以持倉量最高、成交量作同分判定選代表合約；合約代碼與換月日完整保留。換月跳空不作普通單日報酬解讀。</p>
      <script type='application/json' id='shfe-chart-data'>{payload}</script>
      <script>{_shfe_chart_script()}</script></section>"""


def _shfe_chart_script() -> str:
    return r"""(() => {
 const src=document.getElementById('shfe-chart-data'), svg=document.getElementById('shfe-candle-chart'), tip=document.getElementById('shfe-tooltip'); if(!src||!svg)return;
 const all=JSON.parse(src.textContent), W=1120,H=480,L=72,R=82,T=22,B=72;
 const nice=r=>{const raw=r/6,p=10**Math.floor(Math.log10(Math.max(raw,1))),n=raw/p;return(n<=1?1:n<=2?2:n<=5?5:10)*p};
 function render(days){const d=days==='all'?all:all.slice(-Number(days));if(!d.length)return;const lo=Math.min(...d.map(x=>x.low)),hi=Math.max(...d.map(x=>x.high)),step=nice(hi-lo),y0=Math.floor(lo/step)*step,y1=Math.ceil(hi/step)*step;
  const x=i=>L+(W-L-R)*(i+.5)/d.length,y=v=>T+(H-T-B)*(y1-v)/(y1-y0||1),cw=Math.max(2,Math.min(10,(W-L-R)/d.length*.62));let out=`<rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" class="chart-frame"/>`;
  for(let v=y0;v<=y1+.01;v+=step)out+=`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" class="chart-grid"/><text x="5" y="${y(v)+4}" class="chart-label">${v.toLocaleString()}</text>`;
  d.forEach((p,i)=>{const c=p.close>=p.open?'#2ce6a6':'#ff6879';out+=`<line x1="${x(i)}" y1="${y(p.high)}" x2="${x(i)}" y2="${y(p.low)}" stroke="${c}"/><rect x="${x(i)-cw/2}" y="${Math.min(y(p.open),y(p.close))}" width="${cw}" height="${Math.max(1,Math.abs(y(p.open)-y(p.close)))}" fill="${c}"/>`;if(p.roll)out+=`<path d="M${x(i)-4},${T+7} l4,-7 l4,7 z" fill="#ffb253"/>`;});
  [['sma20','#ffb253'],['sma50','#c991ff'],['ema20','#5cd4ff']].forEach(([k,c])=>{let path='',open=false;d.forEach((p,i)=>{if(!Number.isFinite(p[k])){open=false;return}path+=(open?' L':'M')+x(i).toFixed(1)+','+y(p[k]).toFixed(1);open=true});out+=`<path d="${path}" class="chart-line" stroke="${c}"/>`});
  const tick=Math.max(1,Math.ceil(d.length/10));d.forEach((p,i)=>{if(i%tick===0||i===d.length-1)out+=`<text x="${x(i)}" y="${H-40}" text-anchor="middle" class="chart-label">${p.date.slice(5)}</text>`});out+=`<text x="${W/2}" y="${H-10}" text-anchor="middle" class="chart-axis-title">SHFE 交易日 · CNY/tonne</text><rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" fill="transparent" data-hover/>`;svg.innerHTML=out;
  svg.onmousemove=e=>{const r=svg.getBoundingClientRect(),px=(e.clientX-r.left)*W/r.width,i=Math.max(0,Math.min(d.length-1,Math.floor((px-L)/(W-L-R)*d.length))),p=d[i];tip.hidden=false;tip.innerHTML=`<b>${p.date} · ${p.contract}</b><br>O ${p.open.toLocaleString()} · H ${p.high.toLocaleString()}<br>L ${p.low.toLocaleString()} · C ${p.close.toLocaleString()}<br>OI ${p.open_interest.toLocaleString()}${p.roll?' · 換月':''}`;tip.style.left=Math.min(e.offsetX+14,r.width-220)+'px';tip.style.top=Math.max(8,e.offsetY-80)+'px'};svg.onmouseleave=()=>tip.hidden=true;
 }
 document.querySelectorAll('[data-shfe-days]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-shfe-days]').forEach(x=>x.classList.remove('active'));b.classList.add('active');render(b.dataset.shfeDays)});render(120);
})()"""


def _cockpit_cards(snapshot: dict) -> str:
    market=snapshot.get("market",{}); close=snapshot.get("market_research",{}).get("close_series",{}); shfe=snapshot.get("market_research",{}).get("shfe_zinc",{}); tc=snapshot.get("china_tc",{}).get("import_weekly",{})
    def direction(regime: str) -> int:
        return 1 if "BULL" in regime else -1 if "BEAR" in regime else 0
    lme_direction = direction(close.get("trend",{}).get("regime", ""))
    shfe_direction = direction(shfe.get("trend",{}).get("regime", ""))
    align = "同向" if lme_direction and lme_direction == shfe_direction else "分歧" if lme_direction and shfe_direction else "待確認"
    return f"""<section class='panel s12' id='inventory'><h2>INVENTORY &amp; TC · RESEARCH SYSTEM MAP</h2><div class='icon-cards'>
    <div><i>▥</i><span>LME STOCK</span><b>{fmt(market.get('lme_inventory_t'),0)} t</b></div>
    <div><i>◎</i><span>SHFE OPEN INTEREST</span><b>{fmt(shfe.get('latest_open_interest'),0)}</b></div>
    <div><i>⚙</i><span>IMPORT TC</span><b>{fmt(tc.get('value'),2)} {_esc(tc.get('unit'))}</b></div>
    <div><i>∿</i><span>LME VOLATILITY 20</span><b>{fmt(close.get('volatility_20_pct'),2)}%</b></div>
    <div><i>⇄</i><span>CROSS-MARKET</span><b>{align}</b></div>
    <div><i>!</i><span>DATA GAP</span><b>LME OHLC 0 · private</b></div></div></section>"""


def _global_decision_strip(snapshot: dict) -> str:
    plans = snapshot.get("decision_book", {}).get("markets", {})
    cards = []
    for key, plan in plans.items():
        ref = plan.get("reference", {})
        value = ref.get("cash") if key == "lme_zinc" else ref.get("close")
        if value is None:
            value = snapshot.get("market_research", {}).get("cross_assets", {}).get(key, {}).get("latest_close")
        label = "LME Cash" if key == "lme_zinc" else plan.get("market", key)
        reasons = plan.get("no_trade_reasons", [])
        cards.append(
            f"<div><span>{_esc(label)}</span><b>{fmt(value,2)}</b>"
            f"<small>{_esc(plan.get('direction'))} · {_esc(plan.get('decision'))}</small>"
            f"<small>{_esc(plan.get('as_of'))} · {_esc((reasons or ['No blocker'])[0])}</small></div>"
        )
    return ("<div class='research-strip'>" + "".join(cards) + "</div>" if cards else
            "<div class='notice warn'>Decision book unavailable; no cross-market conclusion is published.</div>")


def _decision_reference(snapshot: dict, key: str, plan: dict):
    reference = plan.get("reference") or {}
    if key == "lme_zinc":
        return reference.get("cash"), "USD/t"
    value = reference.get("close")
    series = snapshot.get("market_research", {}).get("cross_assets", {}).get(key, {})
    if key == "shfe_zinc":
        series = snapshot.get("market_research", {}).get("shfe_zinc", {})
    return value if value is not None else series.get("latest_close"), series.get("unit") or ("CNY/t" if key == "shfe_zinc" else "")


def _decision_class(value: str | None) -> str:
    return "ok" if value == "READY" else "warn" if value == "WAIT_FOR_TRIGGER" else "bad"


def _market_series(snapshot: dict, key: str) -> dict:
    research = snapshot.get("market_research", {})
    if key == "lme_zinc":
        return research.get("close_series", {})
    if key == "shfe_zinc":
        return research.get("shfe_zinc", {})
    return research.get("cross_assets", {}).get(key, {})


def _number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _change_pct(current, prior):
    current, prior = _number(current), _number(prior)
    if current is None or prior in (None, 0):
        return None
    return (current / prior - 1) * 100


def _change_text(value) -> tuple[str, str]:
    value = _number(value)
    if value is None:
        return "N/A", "flat"
    if abs(value) < 0.005:
        return "0.00%", "flat"
    return f"{'▲' if value > 0 else '▼'} {value:+.2f}%", "up" if value > 0 else "down"


def _direction_at(point: dict, long_key: str) -> str:
    close = _number(point.get("close"))
    ema = _number(point.get("ema20"))
    long_average = _number(point.get(long_key))
    if None in (close, ema, long_average):
        return "UNDETERMINED"
    if close > ema > long_average:
        return "BULL"
    if close < ema < long_average:
        return "BEAR"
    return "NEUTRAL"


def _today_market_metrics(snapshot: dict, key: str, plan: dict | None = None) -> dict:
    """Derive display-only market context from already validated history.

    These values never change the decision book. LME returns and levels use the
    3M close series, while the headline card continues to show Cash as primary.
    """
    plan = plan or snapshot.get("decision_book", {}).get("markets", {}).get(key, {})
    series = _market_series(snapshot, key)
    points = [item for item in series.get("chart_points", []) if _number(item.get("close")) is not None]
    closes = [_number(item.get("close")) for item in points]
    latest = closes[-1] if closes else None

    def period_change(sessions: int):
        return _change_pct(latest, closes[-sessions - 1]) if len(closes) > sessions else None

    latest_session = series.get("latest_session") or (points[-1] if points else {})
    reference = plan.get("reference") or {}
    ema20 = _number(reference.get("ema20"))
    if ema20 is None:
        ema20 = _number(latest_session.get("ema20"))
    if ema20 is None and key == "lme_zinc":
        ema20 = _number(series.get("ema_20"))

    long_key, long_label = ("sma30", "SMA30") if key == "lme_zinc" else ("sma60", "SMA60")
    long_average = _number(reference.get(long_key))
    if long_average is None:
        long_average = _number(latest_session.get(long_key))
    if long_average is None and key == "lme_zinc":
        long_average = _number(series.get("sma_30"))

    recent = points[-20:]
    series_type = series.get("series_type") or ("CLOSE_ONLY" if key == "lme_zinc" else None)
    if series_type == "FULL_OHLC" and recent:
        lows = [_number(item.get("low")) for item in recent]
        highs = [_number(item.get("high")) for item in recent]
        lows, highs = [x for x in lows if x is not None], [x for x in highs if x is not None]
        support, resistance, range_basis = (min(lows), max(highs), "20D H/L") if lows and highs else (None, None, "20D H/L")
    else:
        recent_closes = [_number(item.get("close")) for item in recent]
        recent_closes = [x for x in recent_closes if x is not None]
        support, resistance, range_basis = ((min(recent_closes), max(recent_closes), "20D Close")
                                              if recent_closes else (None, None, "20D Close"))
    if _number(reference.get("support20")) is not None:
        support = _number(reference.get("support20"))
    if _number(reference.get("resistance20")) is not None:
        resistance = _number(reference.get("resistance20"))

    range_position = None
    if None not in (latest, support, resistance) and resistance > support:
        range_position = max(0.0, min(100.0, (latest - support) / (resistance - support) * 100))

    trigger = _number((plan.get("daily_plan") or {}).get("trigger_price"))
    trigger_gap = _change_pct(trigger, latest)
    direction = plan.get("direction") or "UNDETERMINED"
    if key == "lme_zinc":
        persistence = _number(series.get("trend", {}).get("persistence_days"))
    else:
        target = "BULL" if "BULL" in direction else "BEAR" if "BEAR" in direction else direction
        persistence = 0
        for point in reversed(points):
            if _direction_at(point, long_key) != target:
                break
            persistence += 1
        persistence = persistence or None
    trend_since = None
    if persistence is not None and points and int(persistence) <= len(points):
        trend_since = points[-int(persistence)].get("date")

    return {
        "change_1d": period_change(1), "change_5d": period_change(5), "change_20d": period_change(20),
        "technical_close": latest, "ema20": ema20, "long_average": long_average, "long_label": long_label,
        "ema_distance_pct": _change_pct(latest, ema20), "long_distance_pct": _change_pct(latest, long_average),
        "support": support, "resistance": resistance, "range_basis": range_basis,
        "range_position_pct": range_position, "trigger": trigger, "trigger_gap_pct": trigger_gap,
        "trend_sessions": int(persistence) if persistence is not None else None,
        "trend_since": trend_since,
        "change_basis": "LME 3M Close" if key == "lme_zinc" else "Daily Close",
    }


def _market_summary(snapshot: dict, key: str, plan: dict, metrics: dict) -> str:
    direction = plan.get("direction") or "UNDETERMINED"
    decision = plan.get("decision") or "NO_TRADE"
    one_day, _ = _change_text(metrics.get("change_1d"))
    ema_distance = metrics.get("ema_distance_pct")
    ema_text = (f"高於 EMA20 {abs(ema_distance):.1f}%" if ema_distance is not None and ema_distance >= 0
                else f"低於 EMA20 {abs(ema_distance):.1f}%" if ema_distance is not None else "EMA20位置不足")
    trigger_gap = metrics.get("trigger_gap_pct")
    next_condition = (f"距Trigger {trigger_gap:+.1f}%" if trigger_gap is not None
                      else "目前沒有合格Trigger")
    if key == "lme_zinc":
        curve = _number((plan.get("reference") or {}).get("cash_3m"))
        curve_text = (f"現貨升水 {curve:.1f} USD/t" if curve is not None and curve > 0
                      else f"現貨貼水 {abs(curve):.1f} USD/t" if curve is not None and curve < 0
                      else "Cash−3M曲線近乎持平" if curve == 0 else "Cash−3M曲線資料不足")
        return f"{curve_text}，但3M技術方向為 {direction}；{next_condition}，{decision}。"
    return f"1D {one_day}，Close {ema_text}，方向 {direction}；{next_condition}，{decision}。"


def _spark_path(points: list[dict]) -> str:
    values = []
    for item in points[-30:]:
        try:
            values.append(float(item.get("close")))
        except (TypeError, ValueError):
            continue
    if len(values) < 2:
        return "<span class='spark-missing'>NO SERIES</span>"
    lo, hi = min(values), max(values)
    span = hi - lo or 1.0
    coords = " ".join(
        f"{index * 116 / (len(values) - 1):.1f},{34 - (value - lo) * 28 / span:.1f}"
        for index, value in enumerate(values)
    )
    tone = "spark-up" if values[-1] >= values[0] else "spark-down"
    return (f"<svg class='market-spark {tone}' viewBox='0 0 116 38' aria-hidden='true'>"
            f"<polyline points='{coords}'/></svg>")


def _market_card(snapshot: dict, key: str, title: str, *, placeholder: bool = False) -> str:
    if placeholder:
        return ("<article class='quote-card quote-pending' data-market='us_treasury'>"
                f"<div class='quote-top'><div class='asset-identity'>{asset_icon('us_treasury')}<div><span class='quote-kicker'>RATES</span><h2>US TREASURY 10Y</h2></div></div>"
                f"<span class='pill warn'>SOURCE PENDING</span>{source_badge(None, 'MISSING')}</div><div class='quote-main'><strong>N/A</strong>"
                "<span class='spark-missing'>NO VERIFIED SERIES</span></div>"
                "<div class='quote-changes'><div><span>1D</span><b>N/A</b></div><div><span>5D</span><b>N/A</b></div><div><span>20D</span><b>N/A</b></div></div>"
                "<div class='quote-position'><span>vs EMA20 <b>N/A</b></span><span>vs SMA60 <b>N/A</b></span></div>"
                "<div class='quote-location'><div><span>20D H/L</span><b>N/A</b><small>Position N/A</small></div><div><span>Next trigger</span><b>BLOCKED</b><small>No verified series</small></div></div>"
                "<p class='quote-summary'><b>今日重點</b>2Y／10Y／實質殖利率尚未接入；不判斷利率方向，也不產生交易條件。</p>"
                "<div class='quote-foot'><span>As of —</span><span>NOT_AVAILABLE</span></div></article>")

    plans = snapshot.get("decision_book", {}).get("markets", {})
    plan = plans.get(key, {})
    series = _market_series(snapshot, key)
    value, unit = _decision_reference(snapshot, key, plan)
    as_of = plan.get("as_of") or series.get("as_of") or "—"
    direction = plan.get("direction") or "UNDETERMINED"
    decision = plan.get("decision") or "NO_TRADE"
    source_grade = series.get("source_grade")
    retrieval_status = series.get("retrieval_status") or series.get("status")
    metrics = _today_market_metrics(snapshot, key, plan)
    changes = []
    for label, field in (("1D", "change_1d"), ("5D", "change_5d"), ("20D", "change_20d")):
        text, tone = _change_text(metrics.get(field))
        changes.append(f"<div><span>{label}</span><b class='{tone}'>{_esc(text)}</b></div>")

    def signed_position(value):
        value = _number(value)
        if value is None:
            return "N/A", "flat"
        return f"{value:+.2f}%", "up" if value >= 0 else "down"

    ema_text, ema_tone = signed_position(metrics.get("ema_distance_pct"))
    long_text, long_tone = signed_position(metrics.get("long_distance_pct"))
    range_position = metrics.get("range_position_pct")
    range_text = (f"{fmt(metrics.get('support'),2)} – {fmt(metrics.get('resistance'),2)}"
                  if None not in (metrics.get("support"), metrics.get("resistance")) else "N/A")
    position_text = f"{range_position:.0f}%" if range_position is not None else "N/A"
    trigger_gap = metrics.get("trigger_gap_pct")
    trigger_text = (f"{fmt(metrics.get('trigger'),2)} ({trigger_gap:+.2f}%)"
                    if trigger_gap is not None else "NO VALIDATED TRIGGER")
    trend_sessions = metrics.get("trend_sessions")
    trend_age = (f"{trend_sessions} sessions · since {metrics.get('trend_since')}"
                 if trend_sessions is not None and metrics.get("trend_since") else "N/A")
    secondary = ""
    if key == "lme_zinc":
        reference = plan.get("reference") or {}
        secondary = (f"<div class='quote-sub-grid'><span>3M <b>{fmt(reference.get('three_month'),2)}</b></span>"
                     f"<span>Cash−3M <b>{fmt(reference.get('cash_3m'),2)}</b></span></div>")
    else:
        latest_contract = series.get("latest_contract")
        if latest_contract:
            secondary = f"<p class='quote-sub'>Contract {_esc(latest_contract)}</p>"
    return f"""<article class='quote-card' data-market='{_esc(key)}'>
    <div class='quote-top'><div class='asset-identity'>{asset_icon(key)}<div><span class='quote-kicker'>{'SPOT PRIMARY' if key == 'lme_zinc' else 'VALIDATED REFERENCE'}</span><h2>{_esc(title)}</h2></div></div><span class='pill {_decision_class(decision)}'>{_esc(direction)}</span></div>
    <div class='quote-main'><strong>{fmt(value,2)}</strong><span class='quote-unit'>{_esc(unit)}</span>{_spark_path(series.get('chart_points', []))}</div>
    {secondary}<a href='market-{_esc(key)}.html'>查看圖表與市場證據 →</a><div class='quote-changes'>{''.join(changes)}</div>
    <div class='quote-position'><span>vs EMA20 <b class='{ema_tone}'>{_esc(ema_text)}</b></span><span>vs {_esc(metrics.get('long_label'))} <b class='{long_tone}'>{_esc(long_text)}</b></span></div>
    <div class='quote-location'><div><span>{_esc(metrics.get('range_basis'))}</span><b>{_esc(range_text)}</b><small>Position {_esc(position_text)}</small></div><div><span>Next trigger</span><b>{_esc(trigger_text)}</b><small>Trend age {_esc(trend_age)}</small></div></div>
    <p class='quote-summary'><b>今日重點</b>{_esc(_market_summary(snapshot, key, plan, metrics))}</p>
    <div class='quote-foot'><span>As of {_esc(as_of)} · {_esc(metrics.get('change_basis'))} · {_esc(decision)}</span>{source_badge(source_grade, retrieval_status)}</div></article>"""


def _today_market_cards(snapshot: dict) -> str:
    cards = [
        _market_card(snapshot, "lme_zinc", "LME ZINC"),
        _market_card(snapshot, "shfe_zinc", "SHFE ZINC"),
        _market_card(snapshot, "gold", "COMEX GOLD"),
        _market_card(snapshot, "usdjpy", "USD/JPY"),
        _market_card(snapshot, "dxy", "US DOLLAR INDEX"),
        _market_card(snapshot, "us_treasury", "US TREASURY 10Y", placeholder=True),
    ]
    return ("<section class='panel s12 quote-board' id='market-snapshot'><div class='section-head'>"
            "<div><div class='eyebrow'>FIRST LOOK · PRICES BEFORE OPINIONS</div><h2>MARKET SNAPSHOT</h2></div>"
            f"<span class='muted'>As of {_esc(snapshot.get('run_date'))}</span></div>"
            f"<div class='quote-grid'>{''.join(cards)}</div></section>")


def _today_changes(snapshot: dict) -> str:
    plans = snapshot.get("decision_book", {}).get("markets", {})
    preferred = ["lme_zinc", "shfe_zinc", "gold", "usdjpy", "dxy"]
    ranked = []
    for key in preferred:
        plan = plans.get(key, {})
        if not plan:
            continue
        metrics = _today_market_metrics(snapshot, key, plan)
        ranked.append((abs(metrics.get("change_1d")) if metrics.get("change_1d") is not None else -1,
                       key, plan, metrics))
    ranked.sort(reverse=True, key=lambda item: item[0])
    rows = []
    for _, key, plan, metrics in ranked[:3]:
        change_text, tone = _change_text(metrics.get("change_1d"))
        rows.append(
            f"<div><span class='watch-asset'>{asset_icon(key, compact=True)}<span><b>{_esc(plan.get('market', key))}</b>"
            f"<small><i class='{tone}'>{_esc(change_text)} 1D</i> · {_esc(plan.get('direction'))} · {_esc(plan.get('decision'))}</small></span></span>"
            f"<p>{_esc(_market_summary(snapshot, key, plan, metrics))}</p></div>"
        )
    return ("<section class='panel s6 today-watch'><div class='eyebrow'>RULE-BASED · VALIDATED CLOSES ONLY</div>"
            f"<h2>TODAY'S LARGEST MOVES / CONDITIONS</h2>{''.join(rows)}</section>")


def _today_posture(snapshot: dict) -> str:
    plans = snapshot.get("decision_book", {}).get("markets", {})
    decisions = [plan.get("decision") for plan in plans.values()]
    if "READY" in decisions:
        posture, explanation = "SETUP READY", "At least one research setup has passed its pre-execution gates; a private live-quote check is still required."
    elif "WAIT_FOR_TRIGGER" in decisions:
        posture, explanation = "WAIT FOR TRIGGER", "A conditional research plan exists, but its trigger has not been confirmed. No order is permitted."
    else:
        posture, explanation = "NO TRADE", "No market currently has a compliant conditional setup. Capital preservation is the active decision."
    actionable = sum(item in {"READY", "WAIT_FOR_TRIGGER"} for item in decisions)
    blocked = sum(item == "NO_TRADE" for item in decisions)
    return f"""<section class='panel s6 today-hero' id='overview'><div><div class='eyebrow'>TODAY'S MARKET POSTURE</div><div class='posture'>{_esc(posture)}</div><p>{_esc(explanation)}</p></div><div class='today-metrics'><div><span>Core data</span><b>{_esc(snapshot.get('core_data_gate', {}).get('status'))}</b></div><div><span>Watch / ready</span><b>{actionable}</b></div><div><span>No Trade</span><b>{blocked}</b></div><div><span>Snapshot</span><b>{_esc(snapshot.get('run_date'))}</b></div></div></section>"""


def _today_market_matrix(snapshot: dict) -> str:
    plans = snapshot.get("decision_book", {}).get("markets", {})
    rows = []
    for key, plan in plans.items():
        value, unit = _decision_reference(snapshot, key, plan)
        reason = (plan.get("no_trade_reasons") or ["No blocker registered."])[0]
        as_of = plan.get("as_of")
        if not as_of:
            if key == "shfe_zinc":
                as_of = snapshot.get("market_research", {}).get("shfe_zinc", {}).get("as_of")
            else:
                as_of = snapshot.get("market_research", {}).get("cross_assets", {}).get(key, {}).get("as_of")
        rows.append(
            f"<tr><td><b>{_esc(plan.get('market', key))}</b></td><td>{fmt(value,2)} {_esc(unit)}<br><small>{_esc(as_of)}</small></td>"
            f"<td>{_esc(plan.get('direction'))}</td><td>{_esc(plan.get('evidence_alignment'))}</td>"
            f"<td><span class='pill {_decision_class(plan.get('decision'))}'>{_esc(plan.get('decision'))}</span></td>"
            f"<td>{_esc(reason)}</td></tr>"
        )
    return f"""<section class='panel s12'><div class='section-head'><div><div class='eyebrow'>FIRST DECISION LAYER</div><h2>CROSS-MARKET DECISION MATRIX</h2></div><a href='markets.html'>Open market evidence and levels →</a></div><div class='health-scroll'><table class='decision-matrix'><tr><th>Market</th><th>Validated reference</th><th>Technical direction</th><th>Evidence</th><th>Trade state</th><th>Next condition / blocker</th></tr>{''.join(rows)}</table></div></section>"""


def _primary_watch(snapshot: dict) -> str:
    plans = snapshot.get("decision_book", {}).get("markets", {})
    ranked = sorted(plans.items(), key=lambda item: {"READY": 3, "WAIT_FOR_TRIGGER": 2, "NO_TRADE": 1}.get(item[1].get("decision"), 0), reverse=True)
    if not ranked:
        return "<section class='panel s12'><h2>PRIMARY WATCH</h2><div class='notice bad'>Decision book unavailable.</div></section>"
    key, plan = ranked[0]
    daily = plan.get("daily_plan") or {}
    reason = (plan.get("no_trade_reasons") or ["No blocker registered."])[0]
    if daily:
        fields = [
            ("Setup zone", daily.get("setup_zone")), ("Trigger", daily.get("trigger_price")),
            ("Hard stop", daily.get("hard_stop")), ("T1 / T2", f"{daily.get('t1')} / {daily.get('t2')}"),
        ]
        levels = "".join(f"<div><span>{_esc(label)}</span><b>{_esc(value)}</b></div>" for label, value in fields)
    else:
        levels = "<div><span>Setup</span><b>NOT AVAILABLE</b></div><div><span>Entry permission</span><b>BLOCKED</b></div>"
    return f"""<section class='panel s8'><div class='section-head'><div><div class='eyebrow'>PRIMARY WATCH · EXISTING DECISION ONLY</div><h2>{_esc(plan.get('market', key))}</h2></div><span class='pill {_decision_class(plan.get('decision'))}'>{_esc(plan.get('decision'))}</span></div><div class='watch-levels'>{levels}</div><p><b>Current blocker:</b> {_esc(reason)}</p><p class='muted'>These are delayed research levels, not executable quotes. Bid/Ask, spread, fill, quantity and Actual R:R remain private execution inputs.</p></section>"""


def _zinc_context(snapshot: dict) -> str:
    plan = snapshot.get("decision_book", {}).get("markets", {}).get("lme_zinc", {})
    return f"""<section class='panel s4'><div class='eyebrow'>DO NOT CONFUSE THE LAYERS</div><h2>LME ZINC · CONTEXT SPLIT</h2><div class='context-row'><span>Physical / procurement condition</span><b>{_esc(snapshot.get('market_regime'))}</b></div><div class='context-row'><span>Close-only technical trend</span><b>{_esc(plan.get('direction'))}</b></div><div class='context-row'><span>Trade permission</span><b>{_esc(plan.get('decision'))}</b></div><p class='muted'>Physical tightness and price direction can diverge. Only the existing trigger and execution gates determine whether action is permitted.</p><a href='markets.html#lme_zinc'>Review LME evidence →</a></section>"""


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
<title>Today · Global Macro Research</title>
<style>
:root{{--bg:#06111f;--panel:#0b1d31;--panel2:#0e263f;--line:#1c4668;--text:#edf7ff;--muted:#8ca9c1;--cyan:#5cd4ff;--green:#2ce6a6;--orange:#ffb253;--red:#ff6879}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 10% 0,#123454 0,#06111f 36%);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}}
a{{color:#8addff}}.wrap{{max-width:1600px;margin:auto;padding:18px}}.top{{display:flex;justify-content:space-between;gap:16px;align-items:flex-end;padding:8px 2px 18px;border-bottom:1px solid var(--line);margin-bottom:14px}}
h1{{margin:0;font-size:28px;line-height:1.12}}h2{{font-size:14px;letter-spacing:.08em;color:#9edfff;margin:0 0 12px}}.muted{{color:var(--muted)}}.eyebrow{{font-size:11px;letter-spacing:.08em;color:#91b8d4;text-transform:uppercase}}.grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:12px}}.panel{{background:linear-gradient(180deg,rgba(14,38,63,.98),rgba(8,26,45,.98));border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 12px 30px rgba(0,0,0,.16)}}.s12{{grid-column:span 12}}.s8{{grid-column:span 8}}.s6{{grid-column:span 6}}.s4{{grid-column:span 4}}.s3{{grid-column:span 3}}.hero{{font-size:34px;font-weight:850;color:var(--green);letter-spacing:-.02em}}.market-cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.mcard,.tc-card,.paper-card{{position:relative;overflow:hidden;background:linear-gradient(145deg,#0a2138,#081a2d);border:1px solid #1c4a70;border-radius:12px;padding:14px}}.mcard:before,.tc-card:before{{content:'';position:absolute;inset:0 auto 0 0;width:3px;background:linear-gradient(180deg,var(--cyan),var(--green));opacity:.8}}.mvalue,.tc-value{{font-size:26px;font-weight:850;letter-spacing:-.025em;margin:5px 0 3px}}small{{font-size:11px;color:var(--muted);letter-spacing:0}}.meta,.kv,.card-meta{{display:flex;justify-content:space-between;gap:8px;margin-top:8px;font-size:12px}}.card-meta{{align-items:center;color:#7fa4bf;font-size:10px;padding-top:8px;border-top:1px solid rgba(93,157,199,.14)}}.source{{font-size:10px;color:#7192ad;margin-top:8px;overflow-wrap:anywhere}}.pill{{display:inline-block;padding:3px 7px;border-radius:99px;font-size:10px;font-weight:750;white-space:nowrap}}.ok{{color:var(--green);background:#073d34}}.warn{{color:var(--orange);background:#452f0e}}.bad{{color:#ff8a98;background:#48151c}}.health-scroll{{width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;border-radius:10px}}table{{width:100%;border-collapse:collapse}}.health-scroll table{{min-width:760px}}th,td{{padding:9px 8px;border-bottom:1px solid #173b59;text-align:left;vertical-align:top}}th{{font-size:11px;color:#8fbad7;position:sticky;top:0;background:#0b1d31}}.tc-grid,.paper-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.paper-grid{{grid-template-columns:1fr 1fr}}.paper-action{{font-size:18px;font-weight:800;color:var(--cyan);margin:5px 0}}.notice{{padding:12px;border-radius:9px;margin:8px 0}}img{{width:100%;border-radius:9px}}details{{margin-top:8px}}.footer{{text-align:center;color:#6786a0;padding:24px}}
.close-chart{{margin-top:14px}}.close-chart svg{{width:100%;height:auto;display:block;margin:4px 0 12px}}.chart-frame{{fill:#071827;stroke:#1c4668}}.chart-grid{{stroke:#173b59;stroke-width:1}}.chart-time-grid{{stroke:#214866;stroke-width:1;stroke-dasharray:3 5}}.chart-line{{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}}.chart-line.close{{stroke-width:2.8}}.chart-line.rsi{{stroke:#5cd4ff}}.rsi-band{{stroke:#ffb253;stroke-width:1;stroke-dasharray:5 5}}.chart-label,.chart-day-label,.chart-axis-title{{fill:#8ca9c1;font-size:11px}}.chart-day-label{{fill:#6f91aa}}.chart-axis-title{{fill:#9edfff}}.chart-title,.chart-legend{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:13px 0 6px}}.chart-title span,.chart-legend{{color:#8ca9c1;font-size:11px}}.chart-legend{{justify-content:flex-start}}.range-line{{stroke:#5cd4ff;stroke-width:3;opacity:.7}}.range-close{{fill:#ffb253}}
.interactive-chart{{position:relative;overflow-x:auto}}.period-controls{{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0}}.period-controls button{{border:1px solid #285679;background:#081a2d;color:#9edfff;border-radius:8px;padding:7px 11px;cursor:pointer}}.period-controls button.active{{background:#155071;color:#fff}}.chart-day-grid{{stroke:#112f48;stroke-width:.7}}.chart-week-grid{{stroke:#39749c;stroke-width:1.4}}.last-close{{fill:#fff;stroke:#5cd4ff;stroke-width:2}}.last-price{{fill:#edf7ff;font-size:12px;font-weight:700}}.chart-tooltip{{position:absolute;z-index:4;min-width:200px;padding:9px 11px;border:1px solid #2d6084;border-radius:8px;background:#06111f;color:#edf7ff;font-size:11px;pointer-events:none;box-shadow:0 8px 24px rgba(0,0,0,.35)}}.trend-panel{{margin:14px 0;padding:14px;border:1px solid #245274;border-radius:12px;background:#081a2d}}.trend-summary{{display:grid;grid-template-columns:2fr repeat(3,1fr);gap:12px;align-items:center}}.trend-regime{{font-size:27px;font-weight:850;color:var(--cyan)}}.trend-score{{font-size:24px;font-weight:800}}.trend-detail{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:12px}}.trend-detail ul{{margin:6px 0;padding-left:20px;color:#a9c1d3}}.trend-detail table{{min-width:0}}
.cockpit-banner{{display:grid;grid-template-columns:1.45fr .55fr;gap:14px;align-items:stretch}}.cockpit-copy,.cockpit-side{{padding:18px;background:#071827;border:1px solid #245274;border-radius:14px}}.cockpit-copy h2{{font-size:21px;margin:4px 0}}.compass{{display:grid;grid-template-columns:repeat(5,1fr);height:54px;margin:15px 0 8px;border-radius:10px;overflow:hidden}}.compass-cell{{display:grid;place-items:center;background:#27384a;border-right:1px solid #071827;color:#8ca9c1;font-size:10px;text-align:center}}.compass-cell:nth-child(1){{background:#431b2a}}.compass-cell:nth-child(2){{background:#493025}}.compass-cell:nth-child(4){{background:#17423b}}.compass-cell:nth-child(5){{background:#07503f}}.compass-cell.selected{{outline:3px solid white;outline-offset:-4px;color:white;font-weight:800}}.compass-result{{font-size:27px;font-weight:850;color:var(--cyan)}}.score-line,.section-head{{display:flex;justify-content:space-between;gap:12px;align-items:center}}.compact-reasons{{color:#9bb5c8;padding-left:18px;margin:10px 0}}.status-chip{{border:1px solid #247a6a;background:#073d34;color:var(--green);border-radius:99px;padding:6px 11px;font-size:10px}}.up{{color:var(--green)}}.down{{color:var(--red)}}.research-strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:10px 0}}.research-strip>div{{background:#071827;border:1px solid #173f5d;border-radius:9px;padding:10px}}.research-strip span{{display:block;color:var(--muted);font-size:10px}}.research-strip b{{display:block;margin-top:4px}}.icon-cards{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}}.icon-cards>div{{display:flex;flex-direction:column;gap:4px;background:#071827;border:1px solid #1b4768;border-radius:12px;padding:13px}}.icon-cards i{{font-style:normal;font-size:25px;color:var(--cyan)}}.icon-cards span{{font-size:9px;color:var(--muted);letter-spacing:.08em}}.icon-cards b{{font-size:14px}}
@media(max-width:1180px){{.tc-grid{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:1000px){{.s8,.s6,.s4,.s3{{grid-column:span 12}}.market-cards{{grid-template-columns:repeat(3,1fr)}}.cockpit-banner{{grid-template-columns:1fr}}.icon-cards{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:680px){{.wrap{{padding:10px}}.top{{align-items:flex-start;flex-direction:column;padding:6px 2px 14px}}h1{{font-size:23px}}.panel{{padding:13px;border-radius:12px}}.hero{{font-size:30px}}.market-cards,.tc-grid,.paper-grid,.trend-summary,.trend-detail,.research-strip{{grid-template-columns:1fr}}.icon-cards{{grid-template-columns:repeat(2,1fr)}}.mvalue,.tc-value{{font-size:25px}}.meta,.kv{{gap:12px}}.health-scroll{{margin:0 -2px;width:calc(100% + 4px)}}.interactive-chart svg{{min-width:760px}}}}
/* Final ivory industrial research theme */
:root{{--bg:#f4f1e9;--panel:#fff;--panel2:#f8f6f0;--line:#d7dde2;--text:#153552;--muted:#64798b;--cyan:#147fa3;--green:#087b70;--orange:#c8783d;--red:#d94a4f;--navy:#0b2f4f}}
html{{scroll-behavior:smooth;scroll-padding-top:92px}}body{{background:#f4f1e9;color:var(--text)}}a{{color:#145f91}}
.site-header{{background:linear-gradient(112deg,#0a2a48,#123e61);color:#fff;border-bottom:3px solid #c8783d;box-shadow:0 5px 18px rgba(11,47,79,.18)}}
.site-header .top{{max-width:1760px;margin:0 auto;padding:18px 24px;border:0;align-items:center}}.site-header h1{{font-family:Georgia,serif;font-size:31px;letter-spacing:.035em;color:#fff}}.site-header .muted{{color:#d4e0e8}}
.site-shell{{max-width:1760px;margin:0 auto;display:grid;grid-template-columns:174px minmax(0,1fr);align-items:start}}.wrap{{max-width:none;width:100%;margin:0;padding:16px;min-width:0}}
.side-nav{{position:sticky;top:0;align-self:start;min-height:100vh;padding:18px 10px;background:#fbfaf6;border-right:1px solid #d4dce2;z-index:8}}.side-nav a{{display:flex;align-items:center;gap:10px;padding:11px 10px;margin:2px 0;border-left:3px solid transparent;border-radius:5px;color:#244966;text-decoration:none;font-size:11px;font-weight:750;letter-spacing:.02em}}.side-nav a:hover{{background:#edf2f5}}.side-nav a.active{{background:#0b2f4f;color:#fff;border-left-color:#c8783d}}.side-nav .nav-icon{{width:19px;text-align:center;font-size:16px}}.side-nav .nav-sep{{height:1px;background:#d8dfe4;margin:12px 5px}}
.grid{{gap:10px}}.panel{{background:#fff;border:1px solid #d5dde3;border-radius:7px;padding:14px;box-shadow:0 3px 12px rgba(18,50,76,.055)}}h2{{color:#173d5e;font-family:Georgia,serif;font-size:14px}}h3{{color:#173d5e}}.muted{{color:#687e90}}.eyebrow{{color:#55758e}}.hero{{color:#087b70}}
.mcard,.tc-card,.paper-card{{background:#fbfaf7;border:1px solid #d8e0e5;border-radius:7px;color:#173750}}.mcard:before,.tc-card:before{{background:#c8783d}}.card-meta{{color:#617b8e;border-top-color:#e1e6e9}}.source{{color:#647d8f}}.ok{{color:#086d63;background:#dcf1ec}}.warn{{color:#8a552e;background:#fae9d9}}.bad{{color:#a7333a;background:#fae0e2}}
th{{color:#264f70;background:#f3f5f4}}th,td{{border-bottom-color:#dfe5e8}}.chart-frame{{fill:#fff;stroke:#cbd7df}}.chart-grid{{stroke:#dfe7ec}}.chart-time-grid,.chart-day-grid{{stroke:#edf1f3}}.chart-week-grid{{stroke:#bdcbd5}}.chart-label,.chart-day-label,.chart-axis-title{{fill:#526f85}}.chart-axis-title{{fill:#173f62}}.chart-line.close{{stroke:#123e76!important}}.chart-line.rsi{{stroke:#6d4cc9!important}}.range-line{{stroke:#147fa3}}.range-close{{fill:#c8783d}}
.period-controls button{{border-color:#c9d5dd;background:#fff;color:#234f70}}.period-controls button.active{{background:#0b2f4f;color:#fff;border-color:#0b2f4f}}.chart-tooltip{{border-color:#315c7d;background:#0b2f4f;color:#fff}}
.trend-panel{{background:#f8f6f0;border-color:#d8dfe3}}.trend-regime{{color:#0b5f78}}.trend-detail ul{{color:#536e82}}.cockpit-banner{{grid-template-columns:minmax(0,1.5fr) minmax(285px,.5fr);gap:10px}}.cockpit-copy{{background:#fff;border-color:#d5dde3;color:#173750}}.cockpit-side{{background:#0b2f4f;border-color:#0b2f4f;color:#fff}}.cockpit-side .eyebrow,.cockpit-side .source{{color:#bed0dc}}.cockpit-side .compact-reasons{{color:#e1ebf1}}.compass-gauge{{display:block;width:100%;max-width:330px;margin:6px auto -4px}}.gauge-segment{{stroke:#fff;stroke-width:1.4;opacity:.94}}.gauge-segment.gauge-selected{{stroke:#f2a05d;stroke-width:5;opacity:1}}.gauge-label{{fill:#173750;font-size:8px;font-weight:800;text-transform:uppercase}}.gauge-needle{{stroke:#fff;stroke-width:5;stroke-linecap:round}}.gauge-hub{{fill:#0b2f4f;stroke:#fff;stroke-width:3}}.compass-result{{color:#fff;text-align:center;font-family:Georgia,serif}}
.status-chip{{border-color:#9fcac2;background:#e0f2ee;color:#086d63}}.research-strip>div,.icon-cards>div{{background:#fbfaf7;border-color:#d8e0e5}}.icon-cards i{{color:#164f78}}
.quote-board{{padding:14px}}.quote-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.quote-card{{background:#fff;border:1px solid #d5dde3;border-radius:8px;padding:15px;box-shadow:0 3px 10px rgba(18,50,76,.04);min-height:350px;display:flex;flex-direction:column}}.quote-top{{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}}.quote-top h2{{font-size:17px;margin:2px 0 0}}.quote-kicker{{display:block;color:#687e90;font-size:9px;letter-spacing:.1em}}.quote-main{{display:flex;align-items:flex-end;gap:7px;margin:15px 0 9px;min-width:0}}.quote-main strong{{font:800 31px Georgia,serif;color:#0b2f4f;line-height:1}}.quote-unit{{color:#526f85;font-weight:650;white-space:nowrap}}.market-spark{{width:116px;height:38px;margin-left:auto;overflow:visible}}.market-spark polyline{{fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}}.spark-up polyline{{stroke:#087b70}}.spark-down polyline{{stroke:#d94a4f}}.spark-missing{{margin-left:auto;color:#8a552e;font-size:10px;letter-spacing:.04em}}.quote-sub,.quote-sub-grid{{color:#536e82;font-size:11px;margin:5px 0}}.quote-sub-grid{{display:flex;gap:18px}}.quote-sub-grid b{{color:#173d5e}}.quote-changes{{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin:9px 0}}.quote-changes>div{{background:#f5f7f6;border:1px solid #e0e6e9;border-radius:5px;padding:6px 7px}}.quote-changes span,.quote-location span{{display:block;color:#687e90;font-size:9px;letter-spacing:.04em;text-transform:uppercase}}.quote-changes b{{display:block;margin-top:2px;font-size:12px}}.quote-position{{display:flex;gap:13px;flex-wrap:wrap;color:#536e82;font-size:10px;margin:1px 0 8px}}.quote-position b{{margin-left:3px}}.quote-location{{display:grid;grid-template-columns:1fr 1fr;gap:6px}}.quote-location>div{{padding:7px 8px;border-left:3px solid #9bb4c5;background:#f8f6f0}}.quote-location b,.quote-location small{{display:block}}.quote-location b{{font-size:11px;margin-top:2px}}.quote-location small{{color:#687e90;font-size:9px;margin-top:2px}}.quote-summary{{margin:9px 0;padding:8px 9px;background:#eef5f6;border-left:3px solid #147fa3;color:#294e69;font-size:11px;line-height:1.45}}.quote-summary b{{display:block;color:#0b2f4f;font-size:9px;letter-spacing:.06em;text-transform:uppercase;margin-bottom:2px}}.quote-foot{{display:flex;justify-content:space-between;gap:8px;margin-top:auto;padding-top:10px;border-top:1px solid #e2e7ea;color:#687e90;font-size:9px}}.quote-pending{{background:#fbfaf7}}.today-hero{{display:grid;grid-template-columns:1fr;gap:13px;align-items:center;border-left:5px solid #c8783d}}.today-hero .posture{{font:800 32px Georgia,serif;color:#0b2f4f;margin:5px 0}}.today-hero p{{max-width:760px;margin:4px 0}}.today-metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}.today-metrics>div,.watch-levels>div{{background:#f8f6f0;border:1px solid #d8e0e5;border-radius:6px;padding:10px}}.today-metrics span,.watch-levels span{{display:block;color:#687e90;font-size:10px;text-transform:uppercase;letter-spacing:.05em}}.today-metrics b{{font-size:15px}}.today-watch>div:not(.eyebrow){{display:grid;grid-template-columns:minmax(220px,.75fr) 1.25fr;gap:14px;padding:10px 0;border-bottom:1px solid #e0e5e8}}.today-watch>div:last-child{{border-bottom:0}}.today-watch span,.today-watch small{{display:block}}.today-watch small{{color:#687e90;margin-top:2px}}.today-watch small i{{display:inline;font-style:normal;font-weight:800}}.today-watch p{{margin:0;color:#536e82}}.watch-asset{{display:flex!important;align-items:center;gap:8px}}.watch-levels{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0}}.watch-levels b{{font-size:16px}}.context-row{{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid #dfe5e8}}.context-row span{{color:#687e90}}.today-rules{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}.today-rules>div{{padding:11px;background:#fbfaf7;border:1px solid #d8e0e5;border-radius:6px}}.today-rules b,.today-rules span{{display:block}}.today-rules span{{color:#687e90;font-size:11px;margin-top:4px}}
.trend-ribbon{{padding:12px 14px}}.trend-ribbon h2{{margin:0}}.trend-band{{display:grid;grid-template-columns:repeat(5,1fr);margin-top:9px;border-radius:5px;overflow:hidden}}.band-item{{min-height:48px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#173750;border-right:1px solid rgba(255,255,255,.8);text-transform:uppercase;font-size:11px}}.band-item span{{min-height:14px;font-size:9px;text-transform:none}}.band-strong_bear{{background:#d94a4f;color:#fff}}.band-bear{{background:#ef8a83}}.band-neutral{{background:#c7ced1}}.band-bull{{background:#8dd8cf}}.band-strong_bull{{background:#087b70;color:#fff}}.band-item.active{{box-shadow:inset 0 0 0 4px #f1a15e;font-weight:900}}
.notice.warn{{background:#fff3e8;color:#7d4d29}}.footer{{color:#62798a}}
@media(max-width:1100px){{.site-shell{{grid-template-columns:1fr}}.side-nav{{position:sticky;top:0;min-height:0;display:flex;gap:4px;overflow-x:auto;padding:7px 10px;border-right:0;border-bottom:1px solid #d4dce2}}.side-nav a{{white-space:nowrap;margin:0}}.side-nav .nav-sep{{display:none}}.cockpit-banner,.today-hero{{grid-template-columns:1fr}}.quote-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:680px){{.site-header .top{{padding:14px}}.site-header h1{{font-size:22px}}.side-nav .nav-icon{{display:none}}.trend-band{{min-width:560px}}.trend-ribbon{{overflow-x:auto}}.today-metrics,.watch-levels,.today-rules{{grid-template-columns:1fr 1fr}}.today-hero .posture{{font-size:31px}}.quote-grid{{grid-template-columns:1fr}}.quote-main strong{{font-size:29px}}.today-watch>div:not(.eyebrow){{grid-template-columns:1fr}}}}
{VISUAL_CSS}
</style></head><body>
<header class='site-header'><div class='top'><div><h1>GLOBAL MACRO RESEARCH DESK</h1><div class='muted'>Daily decision brief · evidence first · execution requires a private live quote</div></div><div><b>{_esc(snapshot.get('run_date'))}</b><br><span class='muted'>Model {_esc(snapshot.get('model_version'))} · RESEARCH ONLY</span></div></div></header>
<div class='site-shell'><nav class='side-nav' aria-label='Research sections'>
<a class='active' href='index.html'><span class='nav-icon'>⌂</span>TODAY</a>
<a href='markets.html'><span class='nav-icon'>◫</span>MARKETS</a>
<a href='radar.html'><span class='nav-icon'>⌁</span>RADAR</a>
<a href='journal.html'><span class='nav-icon'>□</span>JOURNAL</a></nav>
<main class='wrap'><div class='grid'>
<section class='s12'>{source_legend()}</section>
{_today_market_cards(snapshot)}
{_today_posture(snapshot)}
{_today_changes(snapshot)}
<section class='panel s12' id='data-health' hidden aria-hidden='true'><h2>DATA HEALTH · SOURCE / AS-OF / DELAY</h2><div class='health-scroll'><table><tr><th>Field</th><th>As of</th><th>Age</th><th>Expected update</th><th>Source grade / provider</th><th>Freshness</th></tr>{_health_rows(snapshot)}</table></div></section>
{_primary_watch(snapshot)}
{_zinc_context(snapshot)}
<section class='panel s12'><div class='section-head'><div><div class='eyebrow'>OPERATING CONSTITUTION</div><h2>WHAT PERMITS ACTION</h2></div><span class='pill warn'>RESEARCH ONLY</span></div><div class='today-rules'><div><b>1 · Verified data</b><span>No complete data → no signal</span></div><div><b>2 · Confirmed trigger</b><span>No trigger → no order</span></div><div><b>3 · Private quote check</b><span>Bid/Ask and spread must be acceptable</span></div><div><b>4 · Risk approval</b><span>Actual R:R below 1:2 → reject</span></div></div></section>
</div><div class='footer'>GLOBAL MACRO RESEARCH DESK · RESEARCH ONLY · Today shows decisions once; Markets holds evidence and levels · private inputs are never deployed.</div></main></div></body></html>"""

    out = PUBLIC_DIR / "index.html"
    out.write_text(page, encoding="utf-8")
    return out
