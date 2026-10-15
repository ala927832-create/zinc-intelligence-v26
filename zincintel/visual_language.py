"""Shared visual and data-identity language for every public research page.

This module is presentation-only.  It must never infer market values, change
indicator formulae, or upgrade a source grade.
"""

from __future__ import annotations

import html


SERIES_STYLES = {
    "close": {"label": "Close", "color": "#59D7FF", "dash": "", "width": 2.8},
    "sma14": {"label": "SMA14", "color": "#4ED6A5", "dash": "8 5", "width": 1.8},
    "sma20": {"label": "SMA20", "color": "#4ED6A5", "dash": "8 5", "width": 1.8},
    "sma30": {"label": "SMA30", "color": "#FFB454", "dash": "12 6", "width": 1.8},
    "sma50": {"label": "SMA50", "color": "#C69CFF", "dash": "3 4", "width": 1.8},
    "sma60": {"label": "SMA60", "color": "#F48FB1", "dash": "2 5", "width": 1.8},
    "ema20": {"label": "EMA20", "color": "#C69CFF", "dash": "", "width": 2.0},
    "rsi14": {"label": "RSI14", "color": "#F4D35E", "dash": "", "width": 2.2},
    "up": {"label": "Up candle", "color": "#4ED6A5", "dash": "", "width": 2.0},
    "down": {"label": "Down candle", "color": "#FF7B85", "dash": "", "width": 2.0},
}


ASSETS = {
    "lme_zinc": {"label": "LME Zinc", "short": "Zn", "kind": "METAL", "accent": "zinc"},
    "shfe_zinc": {"label": "SHFE Zinc", "short": "沪", "kind": "METAL", "accent": "shfe"},
    "gold": {"label": "COMEX Gold", "short": "Au", "kind": "METAL", "accent": "gold"},
    "gold_spot": {"label": "Gold Spot", "short": "Au", "kind": "METAL", "accent": "gold"},
    "usdjpy": {"label": "USD/JPY", "short": "$¥", "kind": "FX", "accent": "fx"},
    "dxy": {"label": "US Dollar Index", "short": "DXY", "kind": "FX INDEX", "accent": "dxy"},
    "usd_basket": {"label": "USD Research Basket", "short": "USD", "kind": "FX BASKET", "accent": "dxy"},
    "us_treasury": {"label": "US Treasury 10Y", "short": "10Y", "kind": "RATES", "accent": "rates"},
}


def asset_icon(key: str, *, compact: bool = False) -> str:
    """Return a deterministic inline SVG icon for a known market."""
    asset = ASSETS.get(key, {"label": key, "short": "?", "kind": "MARKET", "accent": "neutral"})
    size_class = " asset-icon--compact" if compact else ""
    label = html.escape(asset["label"])
    short = html.escape(asset["short"])
    accent = html.escape(asset["accent"])
    return (
        f"<svg class='asset-icon asset-icon--{accent}{size_class}' viewBox='0 0 44 44' "
        f"role='img' aria-label='{label} icon' data-asset-icon='{html.escape(key)}'>"
        "<rect x='1' y='1' width='42' height='42' rx='10' class='asset-icon-bg'/>"
        "<path d='M8 32 L15 25 L21 28 L28 17 L36 12' class='asset-icon-path'/>"
        f"<text x='22' y='24' text-anchor='middle' class='asset-icon-text'>{short}</text></svg>"
    )


def source_identity(grade: str | None, status: str | None = None) -> dict[str, str]:
    """Classify, but never upgrade, the supplied provenance metadata."""
    grade_text = str(grade or "").strip().upper()
    status_text = str(status or "").strip().upper()
    unavailable_states = {"MISSING", "NOT_AVAILABLE", "UNAVAILABLE", "NOT_INTEGRATED", "NO_DATA"}
    if (status_text in unavailable_states or grade_text in unavailable_states
            or grade_text in {"", "—", "N/A", "NONE"}):
        return {"key": "missing", "label": "MISSING", "grade": grade_text or "NO_GRADE"}
    if "CARRY_FORWARD" in status_text or grade_text.startswith("C_"):
        return {"key": "carry", "label": "CARRY FORWARD", "grade": grade_text}
    if "DERIVED" in grade_text:
        return {"key": "derived", "label": "DERIVED", "grade": grade_text}
    if grade_text.startswith("A_") or "OFFICIAL" in grade_text:
        return {"key": "official", "label": "OFFICIAL", "grade": grade_text}
    if "PUBLIC_API" in grade_text:
        return {"key": "api", "label": "PUBLIC API", "grade": grade_text}
    if "MARKET_SOURCE" in grade_text or "VERIFIED_BENCHMARK" in grade_text:
        return {"key": "market", "label": "MARKET SOURCE", "grade": grade_text}
    if grade_text.startswith("B_") or "REFERENCE" in grade_text:
        return {"key": "reference", "label": "PUBLIC REFERENCE", "grade": grade_text}
    return {"key": "unclassified", "label": "UNCLASSIFIED", "grade": grade_text}


def source_badge(grade: str | None, status: str | None = None) -> str:
    identity = source_identity(grade, status)
    return (
        f"<span class='source-badge source-badge--{identity['key']}' "
        f"data-source-kind='{identity['key']}' data-source-grade='{html.escape(identity['grade'])}' "
        f"title='{html.escape(identity['grade'])}'>{html.escape(identity['label'])}</span>"
    )


def source_legend() -> str:
    items = (
        ("official", "OFFICIAL"), ("api", "PUBLIC API"), ("reference", "PUBLIC REFERENCE"),
        ("derived", "DERIVED"), ("carry", "CARRY FORWARD"), ("missing", "MISSING"),
    )
    return "<aside class='source-identity-key' aria-label='Data identity key'><b>DATA IDENTITY</b>" + "".join(
        f"<span class='source-badge source-badge--{key}'>{label}</span>" for key, label in items
    ) + "</aside>"


def series_legend(keys: list[str], *, extra: str = "") -> str:
    items = []
    for key in keys:
        style = SERIES_STYLES[key]
        dash = f"stroke-dasharray:{style['dash']};" if style["dash"] else ""
        items.append(
            "<span class='series-legend-item'>"
            f"<svg viewBox='0 0 34 8' aria-hidden='true'><line x1='1' y1='4' x2='33' y2='4' "
            f"style='stroke:{style['color']};stroke-width:{style['width']};{dash}'/></svg>"
            f"{html.escape(style['label'])}</span>"
        )
    if extra:
        items.append(f"<span class='series-legend-note'>{html.escape(extra)}</span>")
    return "<div class='series-legend' aria-label='Chart series legend'>" + "".join(items) + "</div>"


VISUAL_CSS = """
:root{
  --canvas:#f4f1e9;--surface:#ffffff;--surface-soft:#f8f6f0;--ink:#153552;--muted:#687e90;
  --border:#d5dde3;--navy:#0b2f4f;--navy-deep:#071f35;--accent:#c8783d;
  --series-close:#59d7ff;--series-sma14:#4ed6a5;--series-sma30:#ffb454;
  --series-ema20:#c69cff;--series-sma60:#f48fb1;--series-rsi:#f4d35e;
  --bull:#087b70;--bear:#d94a4f;--neutral:#71808b;
  --official:#087b70;--api:#147fa3;--reference:#b56a2e;--derived:#6d4cc9;
  --carry:#8a552e;--missing:#a7333a;
}
.asset-identity{display:flex;align-items:center;gap:9px;min-width:0}.asset-icon{width:42px;height:42px;flex:0 0 42px;overflow:visible}.asset-icon--compact{width:28px;height:28px;flex-basis:28px}.asset-icon-bg{fill:#e9f0f4;stroke:#adc0cc;stroke-width:1.4}.asset-icon-path{fill:none;stroke:#5e7d91;stroke-width:1.7;opacity:.45}.asset-icon-text{fill:#164f78;font-size:11px;font-weight:850;font-family:Inter,Segoe UI,Arial,sans-serif}.asset-icon--gold .asset-icon-bg{fill:#fff0c7;stroke:#d4aa45}.asset-icon--gold .asset-icon-text{fill:#8a5b00}.asset-icon--fx .asset-icon-bg{fill:#e8efff;stroke:#7998cf}.asset-icon--fx .asset-icon-text{fill:#345c9b}.asset-icon--dxy .asset-icon-bg{fill:#e8edf1;stroke:#71808b}.asset-icon--dxy .asset-icon-text{fill:#344b5e;font-size:8px}.asset-icon--rates .asset-icon-bg{fill:#f3e9fa;stroke:#9b77b7}.asset-icon--rates .asset-icon-text{fill:#694786;font-size:9px}.asset-icon--shfe .asset-icon-bg{fill:#e5f4ee;stroke:#5b9c83}.asset-icon--shfe .asset-icon-text{fill:#17664e}
.source-badge{display:inline-flex;align-items:center;gap:4px;border:1px solid currentColor;border-radius:99px;padding:3px 7px;font-size:9px;font-weight:800;line-height:1.2;letter-spacing:.045em;white-space:nowrap;background:#fff}.source-badge--official{color:var(--official);background:#e0f2ee}.source-badge--api{color:var(--api);background:#e5f3f7}.source-badge--reference{color:var(--reference);background:#fff0e0}.source-badge--market{color:#8a552e;background:#fae9d9}.source-badge--derived{color:var(--derived);background:#f0eafd}.source-badge--carry{color:var(--carry);background:#fff3e8}.source-badge--missing{color:var(--missing);background:#fae0e2}.source-badge--unclassified{color:#5d6971;background:#edf0f2}
.source-identity-key{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:10px 12px;margin:0 0 12px;background:var(--surface);border:1px solid var(--border);border-radius:7px;color:var(--muted);font-size:10px}.source-identity-key>b{color:var(--ink);margin-right:4px;letter-spacing:.06em}
.series-legend{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:8px 0;color:#bed0dc;font-size:11px}.series-legend-item{display:inline-flex;align-items:center;gap:5px}.series-legend-item svg{width:34px;height:8px;overflow:visible}.series-legend-note{color:#9bb3c4;border-left:1px solid #315c7d;padding-left:10px}
.chart-line.close{stroke:var(--series-close)!important}.chart-line.sma14,.chart-line.sma20{stroke:var(--series-sma14)!important;stroke-dasharray:8 5}.chart-line.sma30{stroke:var(--series-sma30)!important;stroke-dasharray:12 6}.chart-line.ema20{stroke:var(--series-ema20)!important}.chart-line.sma50{stroke:var(--series-ema20)!important;stroke-dasharray:3 4}.chart-line.sma60{stroke:var(--series-sma60)!important;stroke-dasharray:2 5}.chart-line.rsi{stroke:var(--series-rsi)!important}
.close-chart .chart-frame{fill:var(--navy-deep);stroke:#315c7d}.close-chart .chart-grid{stroke:#244967}.close-chart .chart-time-grid,.close-chart .chart-day-grid{stroke:#163a57}.close-chart .chart-week-grid{stroke:#456982}.close-chart .chart-label,.close-chart .chart-day-label,.close-chart .chart-axis-title{fill:#bed0dc}.close-chart .chart-axis-title{fill:#dceaf2}
.market-tabs a,.market-index a{display:flex;align-items:center;justify-content:center;gap:6px}.market-summary>.asset-identity{display:inline-flex}.quote-foot .source-badge{margin-left:auto}.radar-market,.journal h2{display:flex;align-items:center;gap:8px}
@media(max-width:620px){.source-identity-key{align-items:flex-start}.series-legend{gap:8px}.asset-icon{width:38px;height:38px;flex-basis:38px}}
"""
