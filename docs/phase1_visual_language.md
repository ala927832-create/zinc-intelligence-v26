# Phase 1 — Public visual language and data identity

This phase changes presentation only. It does not change market values,
indicator formulae, trend scores, source priority, decision gates or trading
rules.

## Market identity

Every supported market has one SVG icon and one stable key:

| Key | Visible identity | Role |
|---|---|---|
| `lme_zinc` | Zn | LME zinc, Cash headline and 3M technical reference |
| `shfe_zinc` | 沪 | Separate SHFE zinc contract series |
| `gold` / `gold_spot` | Au | COMEX reference / spot research |
| `usdjpy` | $¥ | USD/JPY FX series |
| `dxy` / `usd_basket` | DXY / USD | Dollar index / research basket |
| `us_treasury` | 10Y | Treasury series placeholder until a source is verified |

## Chart series

Series colour and line shape are defined once in
`zincintel/visual_language.py`. Close is a heavy solid cyan line; EMA20 is a
solid violet line; SMA14/20 and SMA30 use different green/orange dash patterns;
SMA50/60 have their own violet/pink patterns; RSI14 is yellow. Up and down
candles are green and red. Every rendered chart carries a visible swatch
legend.

## Data identity

The user-facing badge is derived from existing provenance metadata without
upgrading it:

| Badge | Meaning |
|---|---|
| `OFFICIAL` | Existing A-grade / official exchange metadata |
| `PUBLIC API` | Existing `B_PUBLIC_API` metadata |
| `PUBLIC REFERENCE` | Existing B-grade public reference metadata |
| `MARKET SOURCE` | Existing market-source or verified-benchmark metadata |
| `DERIVED` | Calculated from identified inputs |
| `CARRY FORWARD` | Last verified observation is being reused |
| `MISSING` | Required source or value is unavailable |

The exact raw source grade remains in the HTML `data-source-grade` attribute
and tooltip for auditability. A carry-forward status overrides the normal
source badge so stale reuse cannot look current.

## Guardrails

`test_visual_language.py` verifies stable mappings, accessible market icons,
source classification, chart legends and full-page application. The test is
also a required GitHub Actions step.
