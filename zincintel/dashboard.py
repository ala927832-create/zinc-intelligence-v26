from __future__ import annotations

import html
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd

from .utils import PUBLIC_DIR, DATA_DIR, display_time, read_json


def fmt(v, digits=1, suffix=""):
    if v is None:
        return "—"
    try:
        return f"{float(v):,.{digits}f}{suffix}"
    except Exception:
        return html.escape(str(v))


def pct(v):
    return "—" if v is None else f"{float(v)*100:.1f}%"


def _make_candle_chart(df: pd.DataFrame, trades: list[dict], label: str="Daily", filename: str="candle_daily.png", tail: int=140) -> str | None:
    out = PUBLIC_DIR / "assets" / filename
    if df.empty:
        if out.exists():
            out.unlink()
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    plot_df = df.tail(tail).copy()
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(12,6), sharex=True, gridspec_kw={"height_ratios":[4,1]})
    fig.patch.set_facecolor("#071426")
    for a in (ax, axv):
        a.set_facecolor("#071426")
        a.grid(True, alpha=.15)
        a.tick_params(colors="white")
        for spine in a.spines.values(): spine.set_color("#17304d")
    x = mdates.date2num(plot_df.index.to_pydatetime())
    width = max(0.25, (x[1]-x[0])*0.6) if len(x)>1 else 0.6
    for xi, (_, row) in zip(x, plot_df.iterrows()):
        o,h,l,c = map(float, [row["Open"],row["High"],row["Low"],row["Close"]])
        color = "#2ce6a6" if c >= o else "#ff6474"
        ax.vlines(xi, l, h, color=color, linewidth=1)
        y=min(o,c); height=max(abs(c-o), max(abs(c)*0.0005,0.01))
        ax.add_patch(Rectangle((xi-width/2,y), width, height, facecolor=color, edgecolor=color, linewidth=.7))
        vol=float(row.get("Volume",0) or 0)
        axv.bar(xi, vol, width=width, color=color, alpha=.7)
    for col, color in [("EMA20", "#38bdf8"), ("EMA50", "#f59e0b"), ("EMA200", "#a78bfa")]:
        if col in plot_df.columns:
            ax.plot(x, plot_df[col].astype(float), label=col, color=color, linewidth=1.0)
    # Mark frozen paper entries/exits that fall within the visible window.
    if len(plot_df):
        tmin, tmax = plot_df.index.min(), plot_df.index.max()
        for t in trades:
            for time_key, price_key, marker, color in [("entry_time","entry_price","^","#37c7ff"),("exit_time","exit_price","x","#ffad42")]:
                if not t.get(time_key) or t.get(price_key) is None:
                    continue
                try:
                    ts = pd.Timestamp(t[time_key])
                    if ts.tzinfo is None: ts = ts.tz_localize("UTC")
                    if tmin <= ts <= tmax:
                        ax.scatter(mdates.date2num(ts.to_pydatetime()), float(t[price_key]), marker=marker, s=55, color=color, zorder=5)
                except Exception:
                    pass
    ax.set_title(f"LME Zinc 3M Candle Lab — {label}", color="white", fontsize=12)
    ax.legend(loc="upper left", facecolor="#071426", labelcolor="white")
    ax.xaxis_date(); axv.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.autofmt_xdate()
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="#071426")
    plt.close(fig)
    return f"assets/{filename}"


def _make_equity_chart(trades: list[dict]) -> str | None:
    closed = [t for t in trades if t.get("status") == "CLOSED" and t.get("exit_time")]
    if not closed:
        return None
    rows = []
    for strat in ["conservative", "aggressive"]:
        equity = 0.0
        for t in sorted([x for x in closed if x.get("strategy") == strat], key=lambda x: x["exit_time"]):
            equity += float(t.get("net_pnl_usd") or 0)
            rows.append((pd.Timestamp(t["exit_time"]), strat, equity))
    if not rows:
        return None
    out = PUBLIC_DIR / "assets" / "strategy_equity.png"
    fig, ax = plt.subplots(figsize=(9,3.5))
    for strat in ["conservative", "aggressive"]:
        pts = [(d,e) for d,s,e in rows if s == strat]
        if pts:
            ax.plot([x[0] for x in pts], [x[1] for x in pts], label=strat.title())
    ax.set_title("Paper Strategy Equity (USD)")
    ax.grid(True, alpha=.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return "assets/strategy_equity.png"


def build_dashboard(snapshot: dict, candle_frames: dict[str, pd.DataFrame], trades: list[dict], perf: dict) -> Path:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    daily_df = candle_frames.get("daily", pd.DataFrame())
    candle_imgs = {
        "Daily": _make_candle_chart(daily_df, trades, "Daily", "candle_daily.png", 140),
        "Weekly": _make_candle_chart(candle_frames.get("weekly", pd.DataFrame()), trades, "Weekly", "candle_weekly.png", 130),
        "1H": _make_candle_chart(candle_frames.get("1h", pd.DataFrame()), trades, "1 Hour", "candle_1h.png", 240),
        "15M": _make_candle_chart(candle_frames.get("15m", pd.DataFrame()), trades, "15 Minutes", "candle_15m.png", 260),
    }
    candle_img = candle_imgs.get("Daily")
    equity_img = _make_equity_chart(trades)
    market = snapshot.get("market", {})
    proc = snapshot.get("procurement", {})
    ps = snapshot.get("procurement_state", {})
    include_private = bool(snapshot.get("privacy", {}).get("public_dashboard_include_private", False))
    pq = snapshot.get("procurement_quality", {})
    iq = snapshot.get("market_quality", {})
    inv = snapshot.get("investment", {})
    h = snapshot.get("horizons", {})
    macro = snapshot.get("macro", {})
    events = snapshot.get("event_overlay", {})
    indicators = snapshot.get("indicators", {})
    signal_rows = read_json(DATA_DIR / "signal_journal.json", [])[-12:][::-1]
    open_trades = [t for t in trades if t.get("status") in ("OPEN", "PENDING")][-10:]

    def pfmt(v, digits=0, suffix=""):
        return fmt(v, digits, suffix) if include_private else "••••"

    def strategy_card(name):
        r = inv.get(name, {})
        prob = r.get("probability", {})
        return f"""
        <div class='strategy {'green' if name=='conservative' else 'orange'}'>
          <div class='strategy-title'>{'🛡️ 穩健型 Conservative' if name=='conservative' else '🚀 積極型 Aggressive'} <span>{fmt(r.get('strategy_score'),0)}/100</span></div>
          <div class='action'>{html.escape(str(r.get('action','—')))}</div>
          <div class='muted'>{html.escape(str(r.get('reason','')))}</div>
          <div class='metric-grid'>
            <div><b>方向</b><span>{r.get('direction','—')}</span></div>
            <div><b>獲利機率</b><span>{pct(prob.get('p_profit'))}</span></div>
            <div><b>機率狀態</b><span>{prob.get('status','—')}</span></div>
            <div><b>樣本</b><span>{prob.get('sample_size',0)}</span></div>
            <div><b>參考價</b><span>{fmt(r.get('reference_price'),1)}</span></div>
            <div><b>停損</b><span>{fmt(r.get('suggested_stop'),1)}</span></div>
            <div><b>目標</b><span>{fmt(r.get('suggested_target'),1)}</span></div>
            <div><b>R:R</b><span>{fmt(r.get('reward_risk'),2)}</span></div>
            <div><b>模擬風險</b><span>${fmt(r.get('risk_usd_per_sim_trade'),0)}</span></div>
            <div><b>模擬獲利</b><span>${fmt(r.get('reward_usd_per_sim_trade'),0)}</span></div>
            <div><b>EV</b><span>${fmt(r.get('expected_value_usd'),0)}</span></div>
            <div><b>用途</b><span>PAPER ONLY</span></div>
          </div>
        </div>"""

    macro_html = "".join(f"<tr><td>{html.escape(k)}</td><td>{fmt(v.get('value'),2)}</td><td>{fmt(v.get('change_pct'),2,'%')}</td></tr>" for k,v in macro.items())
    event_html = "".join(f"<li><b>{html.escape(str(e.get('type','Event')))}</b> · {html.escape(str(e.get('severity','')))} · {html.escape(str(e.get('description','')))}</li>" for e in events.get("active_events", [])) or "<li>目前沒有已登錄的 Active Event Risk。</li>"
    trades_html = "".join(f"<tr><td>{t.get('trade_id')}</td><td>{t.get('strategy')}</td><td>{t.get('direction')}</td><td>{t.get('status')}</td><td>{fmt(t.get('entry_price'),1)}</td><td>{fmt(t.get('last_mark_price'),1)}</td><td>${fmt(t.get('unrealized_pnl_usd'),0)}</td></tr>" for t in open_trades) or "<tr><td colspan='7'>目前沒有模擬持倉。</td></tr>"
    candle_tabs = "".join(
        f"<details {'open' if label=='Daily' else ''}><summary>{label}</summary><img src='{src}' alt='{label} candle'></details>"
        for label, src in candle_imgs.items() if src
    ) or "<p class='warn'>尚未提供真實 LME 3M OHLC CSV / API，因此不生成假 K 線。</p>"
    journal_html = "".join(f"<tr><td>{r.get('run_date')}</td><td>{r.get('market_regime')}</td><td>{r.get('conservative_action')}</td><td>{r.get('aggressive_action')}</td><td>{fmt(r.get('market_score'),1)}</td><td>{r.get('model_version')}</td></tr>" for r in signal_rows) or "<tr><td colspan='6'>尚無歷史。</td></tr>"

    html_doc = f"""<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Zinc Intelligence V2.6</title><style>
:root{{--bg:#06111f;--panel:#0a1b2f;--line:#164269;--text:#e8f4ff;--muted:#87a5bf;--cyan:#37c7ff;--green:#2ce6a6;--orange:#ffad42;--red:#ff6474}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 20% 0,#0b2945 0,#06111f 35%);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}} .wrap{{max-width:1580px;margin:auto;padding:16px}} h1{{font-size:25px;margin:0}} h2{{font-size:15px;color:#9bdcff;margin:0 0 12px}} .sub{{color:var(--muted)}} .top{{display:flex;justify-content:space-between;gap:16px;align-items:center;border-bottom:1px solid #1b527e;padding:8px 4px 16px;margin-bottom:14px}} .grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:12px}} .panel{{background:linear-gradient(180deg,rgba(12,35,59,.96),rgba(7,24,42,.96));border:1px solid var(--line);border-radius:11px;padding:14px;box-shadow:0 10px 30px rgba(0,0,0,.18)}} .span12{{grid-column:span 12}} .span8{{grid-column:span 8}} .span7{{grid-column:span 7}} .span6{{grid-column:span 6}} .span5{{grid-column:span 5}} .span4{{grid-column:span 4}} .span3{{grid-column:span 3}} .hero{{font-size:30px;font-weight:800;color:var(--green)}} .badge{{display:inline-block;padding:4px 10px;border-radius:99px;background:#083b34;color:var(--green);font-weight:700}} .metric-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:10px}} .metric-grid div{{border:1px solid #173d61;border-radius:8px;padding:8px;display:flex;justify-content:space-between;gap:8px}} .metric-grid b{{font-size:12px;color:var(--muted)}} .strategy-wrap{{display:grid;grid-template-columns:1fr 1fr;gap:10px}} .strategy{{border:1px solid #2f698e;border-radius:10px;padding:12px}} .strategy.green{{box-shadow:inset 0 0 0 1px rgba(44,230,166,.2)}} .strategy.orange{{box-shadow:inset 0 0 0 1px rgba(255,173,66,.25)}} .strategy-title{{font-size:17px;font-weight:800;display:flex;justify-content:space-between}} .action{{font-size:19px;font-weight:800;margin-top:8px;color:var(--cyan)}} .muted{{color:var(--muted);font-size:12px}} table{{width:100%;border-collapse:collapse}} th,td{{padding:8px;border-bottom:1px solid #143652;text-align:left}} th{{color:#8fc7e8;font-size:12px}} img{{width:100%;border-radius:8px}} .proc-action{{font-size:20px;color:var(--green);font-weight:800;padding:10px;border:1px solid #157a64;border-radius:8px;background:#07372e}} ul{{margin:5px 0 0;padding-left:18px}} .warn{{color:var(--orange)}} .footer{{text-align:center;color:#6888a3;padding:24px}} @media(max-width:1000px){{.span8,.span7,.span6,.span5,.span4,.span3{{grid-column:span 12}} .strategy-wrap{{grid-template-columns:1fr}}}}
</style></head><body><div class='wrap'>
<div class='top'><div><h1>Zn · ZINC PROCUREMENT & INVESTMENT INTELLIGENCE V2.6</h1><div class='sub'>Predict → Freeze → Simulate → Observe → Score → Diagnose → Improve</div></div><div><b>{snapshot.get('run_date')}</b><br><span class='sub'>Model {snapshot.get('model_version')}</span></div></div>
<div class='grid'>
<section class='panel span3'><h2>MARKET REGIME</h2><div class='hero'>{snapshot.get('market_regime','—')}</div><div>ZTI / Market Score <b>{fmt(snapshot.get('market_score'),1)}/100</b></div><div>20D <span class='badge'>{fmt(h.get('20D'),1)}</span></div></section>
<section class='panel span5'><h2>KEY MARKET DATA</h2><table><tr><td>LME Cash</td><td>{fmt(market.get('lme_cash'),1)} USD/t</td></tr><tr><td>LME 3M</td><td>{fmt(market.get('lme_3m'),1)} USD/t</td></tr><tr><td>Cash−3M</td><td>{fmt(market.get('cash_3m'),1)} USD/t</td></tr><tr><td>Inventory</td><td>{fmt(market.get('lme_inventory_t'),0)} t</td></tr><tr><td>Cancelled</td><td>{fmt(market.get('cancelled_warrants_t'),0)} t</td></tr><tr><td>TC</td><td>{fmt(market.get('tc_usd_t'),1)} USD/t</td></tr></table></section>
<section class='panel span4'><h2>DATA QUALITY</h2><div class='hero'>{fmt(iq.get('confidence'),0)}/100</div><div class='badge'>{iq.get('status')}</div><p class='sub'>Candles: {iq.get('candle_status')}<br>Missing: {', '.join(iq.get('missing_fields',[])) or 'None'}</p></section>
<section class='panel span6'><h2>🏭 PROCUREMENT BOOK</h2>{"<div class='warn'>Public-site privacy mode: exact inventory / demand / tonnage masked.</div>" if not include_private else ''}<div class='metric-grid'><div><b>現有庫存</b><span>{pfmt(ps.get('current_inventory_t'),0)} t</span></div><div><b>60D需求</b><span>{pfmt(ps.get('demand_60d_t'),0)} t</span></div><div><b>Coverage</b><span>{fmt(proc.get('coverage_days'),1)} days</span></div><div><b>Uncovered</b><span>{pfmt(proc.get('uncovered_demand_t'),0)} t</span></div><div><b>Suggested Cover</b><span>{pfmt(proc.get('suggested_cover_t'),0)} t</span></div><div><b>Equivalent LME</b><span>{pfmt(proc.get('equivalent_lme_lots'),1)} lots</span></div><div><b>Input Status</b><span>{pq.get('status')}</span></div><div><b>Input Age</b><span>{fmt(pq.get('max_age_days'),1)} d</span></div></div><p class='proc-action'>{proc.get('action','INPUT REQUIRED')}</p>{"<p class='warn'>⚠ Production Safety Override</p>" if proc.get('production_safety_override') else ''}</section>
<section class='panel span6'><h2>📈 FUTURES INVESTMENT BOOK — PAPER RESEARCH ONLY</h2><div class='strategy-wrap'>{strategy_card('conservative')}{strategy_card('aggressive')}</div></section>
<section class='panel span8'><h2>🕯 CANDLE LAB — LME ZINC 3M</h2>{candle_tabs}</section>
<section class='panel span4'><h2>EVENT RISK OVERLAY</h2><div class='hero'>{events.get('level')}</div><ul>{event_html}</ul><h2 style='margin-top:18px'>MACRO & RELATED</h2><table>{macro_html}</table></section>
<section class='panel span7'><h2>OPEN PAPER TRADES</h2><table><tr><th>ID</th><th>Strategy</th><th>Side</th><th>Status</th><th>Entry</th><th>Mark</th><th>P/L</th></tr>{trades_html}</table>{f"<img src='{equity_img}' alt='equity chart'>" if equity_img else ''}</section>
<section class='panel span5'><h2>STRATEGY PERFORMANCE</h2><table><tr><th></th><th>Conservative</th><th>Aggressive</th></tr><tr><td>Trades</td><td>{perf['conservative']['trades']}</td><td>{perf['aggressive']['trades']}</td></tr><tr><td>Win rate</td><td>{pct(perf['conservative']['win_rate'])}</td><td>{pct(perf['aggressive']['win_rate'])}</td></tr><tr><td>Expectancy R</td><td>{fmt(perf['conservative']['expectancy_r'],2)}</td><td>{fmt(perf['aggressive']['expectancy_r'],2)}</td></tr><tr><td>Profit Factor</td><td>{fmt(perf['conservative']['profit_factor'],2)}</td><td>{fmt(perf['aggressive']['profit_factor'],2)}</td></tr><tr><td>Max DD</td><td>${fmt(perf['conservative']['max_drawdown_usd'],0)}</td><td>${fmt(perf['aggressive']['max_drawdown_usd'],0)}</td></tr></table></section>
<section class='panel span12'><h2>DAILY SIGNAL JOURNAL</h2><table><tr><th>Date</th><th>Regime</th><th>Conservative</th><th>Aggressive</th><th>Score</th><th>Version</th></tr>{journal_html}</table></section>
</div><div class='footer'><a href='research.html' style='color:#9bdcff'>Open Research Lab</a> · Zinc Intelligence V2.6 · Investment section is paper simulation, not live order execution.</div></div></body></html>"""
    out = PUBLIC_DIR / "index.html"
    out.write_text(html_doc, encoding="utf-8")

    closed = [t for t in trades if t.get("status") == "CLOSED"][::-1]
    closed_html = "".join(
        f"<tr><td>{t.get('trade_id')}</td><td>{t.get('strategy')}</td><td>{t.get('direction')}</td><td>{t.get('entry_time','—')}</td><td>{t.get('exit_time','—')}</td><td>{fmt(t.get('net_pnl_usd'),0)}</td><td>{fmt(t.get('r_multiple'),2)}</td><td>{fmt(t.get('mae_usd'),0)}</td><td>{fmt(t.get('mfe_usd'),0)}</td><td>{t.get('model_version')}</td></tr>" for t in closed[:250]
    ) or "<tr><td colspan='10'>尚無已完成 Paper Trade。</td></tr>"
    research = f"""<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Zinc V2.6 Research Lab</title><style>body{{background:#06111f;color:#e8f4ff;font:14px Segoe UI,Arial;margin:0}}main{{max-width:1500px;margin:auto;padding:20px}}a{{color:#9bdcff}}table{{width:100%;border-collapse:collapse;background:#0a1b2f}}th,td{{padding:8px;border:1px solid #173d61;text-align:left}}th{{color:#9bdcff}}.cards{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.card{{background:#0a1b2f;border:1px solid #164269;border-radius:10px;padding:14px}}@media(max-width:900px){{.cards{{grid-template-columns:1fr}}}}</style></head><body><main><p><a href='index.html'>← Dashboard</a></p><h1>Strategy Research Lab</h1><p>Frozen signals + Paper trades + calibration evidence. No live broker execution.</p><div class='cards'><div class='card'><h2>Conservative</h2><p>Trades {perf['conservative']['trades']} · Win {pct(perf['conservative']['win_rate'])} · Expectancy {fmt(perf['conservative']['expectancy_r'],2)}R · Brier {fmt(perf['conservative'].get('brier_score'),3)} · Calibration error {pct(perf['conservative'].get('calibration_error'))}</p></div><div class='card'><h2>Aggressive</h2><p>Trades {perf['aggressive']['trades']} · Win {pct(perf['aggressive']['win_rate'])} · Expectancy {fmt(perf['aggressive']['expectancy_r'],2)}R · Brier {fmt(perf['aggressive'].get('brier_score'),3)} · Calibration error {pct(perf['aggressive'].get('calibration_error'))}</p></div></div><h2>Closed Paper Trades</h2><table><tr><th>ID</th><th>Strategy</th><th>Side</th><th>Entry time</th><th>Exit time</th><th>Net P/L USD</th><th>R</th><th>MAE</th><th>MFE</th><th>Model</th></tr>{closed_html}</table><h2>Signal Journal</h2><table><tr><th>Date</th><th>Regime</th><th>Conservative</th><th>Aggressive</th><th>Score</th><th>Version</th></tr>{journal_html}</table></main></body></html>"""
    (PUBLIC_DIR / "research.html").write_text(research, encoding="utf-8")
    return out
