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


def _paper_card(rec: dict, label: str) -> str:
    p = rec.get("probability", {})
    return f"""
    <div class='paper-card'>
      <div class='eyebrow'>{_esc(label)}</div>
      <div class='paper-action'>{_esc(rec.get('action'))}</div>
      <div class='muted'>{_esc(rec.get('reason'))}</div>
      <div class='kv'><span>Score</span><b>{fmt(rec.get('strategy_score'),1)}</b></div>
      <div class='kv'><span>Probability</span><b>{pct(p.get('p_profit'))}</b></div>
      <div class='kv'><span>Reference</span><b>{fmt(rec.get('reference_price'),1)}</b></div>
      <div class='source'>PAPER RESEARCH ONLY</div>
    </div>"""


def build_dashboard_v27(snapshot: dict, candle_frames: dict[str, pd.DataFrame], trades: list[dict], perf: dict) -> Path:
    # Keep legacy research.html and chart image generation, then replace index.html with V2.7.
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
    candle_block = ""
    if candle_daily.exists():
        candle_block += "<img src='assets/candle_daily.png' alt='Daily zinc candle'>"
    elif technical_mode == "CLOSE_ONLY":
        candle_block += "<div class='notice warn'>Close-only mode：可計算 EMA / RSI / ROC，但沒有真實 Open/High/Low，所以不產生假 K 線、ATR 或 Paper Trade execution。</div>"
    else:
        candle_block += "<div class='notice bad'>No verified OHLC source. Technical execution remains blocked.</div>"
    if candle_weekly.exists():
        candle_block += "<details><summary>Weekly chart</summary><img src='assets/candle_weekly.png' alt='Weekly zinc candle'></details>"

    page = f"""<!doctype html>
<html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Zinc Intelligence V2.7</title>
<style>
:root{{--bg:#06111f;--panel:#0b1d31;--panel2:#0e263f;--line:#1c4668;--text:#edf7ff;--muted:#8ca9c1;--cyan:#5cd4ff;--green:#2ce6a6;--orange:#ffb253;--red:#ff6879}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 10% 0,#123454 0,#06111f 36%);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}}
a{{color:#8addff}}.wrap{{max-width:1600px;margin:auto;padding:18px}}.top{{display:flex;justify-content:space-between;gap:16px;align-items:flex-end;padding:8px 2px 18px;border-bottom:1px solid var(--line);margin-bottom:14px}}
h1{{margin:0;font-size:26px}}h2{{font-size:14px;letter-spacing:.08em;color:#9edfff;margin:0 0 12px}}.muted{{color:var(--muted)}}.eyebrow{{font-size:11px;letter-spacing:.08em;color:#91b8d4;text-transform:uppercase}}.grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:12px}}.panel{{background:linear-gradient(180deg,rgba(14,38,63,.98),rgba(8,26,45,.98));border:1px solid var(--line);border-radius:12px;padding:14px;box-shadow:0 12px 30px rgba(0,0,0,.16)}}.s12{{grid-column:span 12}}.s8{{grid-column:span 8}}.s6{{grid-column:span 6}}.s4{{grid-column:span 4}}.s3{{grid-column:span 3}}.hero{{font-size:31px;font-weight:850;color:var(--green)}}.market-cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}.mcard,.tc-card,.paper-card{{background:#081a2d;border:1px solid #183f60;border-radius:10px;padding:12px}}.mvalue,.tc-value{{font-size:23px;font-weight:800;margin:4px 0}}small{{font-size:11px;color:var(--muted)}}.meta,.kv{{display:flex;justify-content:space-between;gap:8px;margin-top:7px;font-size:12px}}.source{{font-size:10px;color:#7192ad;margin-top:8px}}.pill{{display:inline-block;padding:3px 7px;border-radius:99px;font-size:10px;font-weight:750}}.ok{{color:var(--green);background:#073d34}}.warn{{color:var(--orange);background:#452f0e}}.bad{{color:#ff8a98;background:#48151c}}table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border-bottom:1px solid #173b59;text-align:left;vertical-align:top}}th{{font-size:11px;color:#8fbad7}}.tc-grid,.paper-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}.paper-grid{{grid-template-columns:1fr 1fr}}.paper-action{{font-size:18px;font-weight:800;color:var(--cyan);margin:5px 0}}.notice{{padding:12px;border-radius:9px;margin:8px 0}}img{{width:100%;border-radius:9px}}details{{margin-top:8px}}.footer{{text-align:center;color:#6786a0;padding:24px}}@media(max-width:1000px){{.s8,.s6,.s4,.s3{{grid-column:span 12}}.market-cards,.tc-grid,.paper-grid{{grid-template-columns:1fr}}}}
</style></head><body><div class='wrap'>
<div class='top'><div><h1>Zn · ZINC INTELLIGENCE V2.7</h1><div class='muted'>Accuracy-first · Official-first · Freshness-aware · Procurement privacy preserved</div></div><div><b>{_esc(snapshot.get('run_date'))}</b><br><span class='muted'>Model {_esc(snapshot.get('model_version'))}</span></div></div>
<div class='grid'>
<section class='panel s3'><h2>CORE DATA GATE</h2><div class='hero'>{_esc(gate.get('status'))}</div><span class='pill {gate_class}'>{len(gate.get('usable_core',[]))} core usable</span><p class='muted'>Stale: {_esc(', '.join(gate.get('stale_core',[])) or 'None')}<br>Missing: {_esc(', '.join(gate.get('missing_core',[])) or 'None')}</p></section>
<section class='panel s3'><h2>MARKET REGIME</h2><div class='hero'>{_esc(snapshot.get('market_regime'))}</div><div>ZTI / Score <b>{fmt(snapshot.get('market_score'),1)}</b></div><div>Confidence <b>{fmt(iq.get('confidence'),0)}/100</b></div></section>
<section class='panel s6'><h2>LME ZINC · CORE REFERENCES</h2><div class='market-cards'>
<div class='mcard'><div class='eyebrow'>Cash</div><div class='mvalue'>{fmt(market.get('lme_cash'),1)} <small>USD/t</small></div><div class='muted'>Cash−3M {fmt(market.get('cash_3m'),1)}</div></div>
<div class='mcard'><div class='eyebrow'>3M</div><div class='mvalue'>{fmt(market.get('lme_3m'),1)} <small>USD/t</small></div><div class='muted'>Technical mode {_esc(technical_mode)}</div></div>
<div class='mcard'><div class='eyebrow'>Inventory</div><div class='mvalue'>{fmt(market.get('lme_inventory_t'),0)} <small>t</small></div><div class='muted'>Live {fmt(market.get('live_warrants_t'),0)} · Cancelled {fmt(market.get('cancelled_warrants_t'),0)} · Ratio {fmt(market.get('cancelled_ratio_pct'),1)}%</div></div>
</div></section>
<section class='panel s12'><h2>DATA HEALTH · SOURCE / AS-OF / DELAY</h2><table><tr><th>Field</th><th>As of</th><th>Age</th><th>Expected update</th><th>Source grade / provider</th><th>Freshness</th></tr>{_health_rows(snapshot)}</table></section>
<section class='panel s12'><h2>CHINA ZINC CONCENTRATE TC</h2><div class='tc-grid'>{tc_html}</div><p class='muted'>不同 basis 不混算：Import TC、Domestic TC、Annual Benchmark 分開保存與判讀。延遲一日/一週/月度可接受，但日期與來源必須可追溯。</p></section>
<section class='panel s6'><h2>🏭 PROCUREMENT</h2>{"<div class='notice warn'>Public privacy mode：精確庫存、60D需求與建議採購噸數已遮罩。</div>" if not include_private else ''}<div class='market-cards'>
<div class='mcard'><div class='eyebrow'>Coverage</div><div class='mvalue'>{fmt(proc.get('coverage_days'),1)} <small>days</small></div><div class='muted'>{_esc(proc.get('inventory_band'))}</div></div>
<div class='mcard'><div class='eyebrow'>Action</div><div class='mvalue'>{_esc(proc.get('action'))}</div><div class='muted'>Input {_esc(proc_q.get('status'))}</div></div>
<div class='mcard'><div class='eyebrow'>Private inputs</div><div class='mvalue'>{private_value(proc_state.get('current_inventory_t'),0)} / {private_value(proc_state.get('demand_60d_t'),0)}</div><div class='muted'>inventory / 60D demand</div></div>
</div></section>
<section class='panel s6'><h2>📈 PAPER RESEARCH</h2><div class='paper-grid'>{_paper_card(inv.get('conservative',{}),'Conservative')}{_paper_card(inv.get('aggressive',{}),'Aggressive')}</div></section>
<section class='panel s8'><h2>TECHNICAL DATA</h2>{candle_block}</section>
<section class='panel s4'><h2>MODEL / PIPELINE STATUS</h2><table><tr><td>Technical mode</td><td>{_esc(technical_mode)}</td></tr><tr><td>Close-history points</td><td>{_esc(snapshot.get('free_close_history_points'))}</td></tr><tr><td>Market confidence</td><td>{fmt(iq.get('confidence'),0)}</td></tr><tr><td>Provider failures</td><td>{sum(1 for v in market.get('provider_status',{}).values() if str(v.get('status')).upper()=='ERROR')}</td></tr></table><p><a href='research.html'>Research Lab →</a></p></section>
</div><div class='footer'>Zinc Intelligence V2.7 · Public dashboard uses masked procurement inputs · Investment module is paper research only.</div></div></body></html>"""

    out = PUBLIC_DIR / "index.html"
    out.write_text(page, encoding="utf-8")
    return out
