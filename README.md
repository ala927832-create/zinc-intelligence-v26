# Zinc Procurement & Investment Intelligence V2.6

A static, auditable zinc decision-support system designed around:

**Predict → Freeze → Simulate → Observe → Score → Diagnose → Improve**

## What V2.6 does

- **Procurement Book**: manually update current usable zinc inventory and next-60-day zinc demand. Blank daily input carries forward the last valid value.
- **Production Safety Override**: low coverage can override a bearish market view so procurement never recommends waiting into a shortage.
- **Market Intelligence Core**: market structure, TC/smelter economics, physical premium, macro, technicals, and Event Risk Overlay.
- **Candle Lab**: uses real user/API-provided LME Zinc 3M OHLC. It deliberately does **not** create synthetic zinc candles.
- **Two investment research strategies**: Conservative and Aggressive, tracked as **paper simulations only**.
- **Paper Trade Ledger**: Pending → Open → Closed, next-session execution, conservative same-bar TP/SL handling, MAE/MFE, time exits, fees/slippage.
- **Signal Journal**: freezes each day's model version, market regime, strategy actions and probabilities for later diagnosis.
- **GitHub Pages**: dark V2.6 dashboard with Procurement, Investment, Candle Lab, Event Risk, Macro, Paper Trades and Strategy Performance.
- **Discord**: compact daily Procurement + Paper Research summary.

## Important design constraint

The investment module is intentionally research/paper-trading only. There is no broker login, order API, or live leveraged execution logic.


## Security / privacy before publishing

**Recommended: keep the repository private.** The persisted `data/` files can contain proprietary inventory, demand, and procurement history.

GitHub Pages is normally public on the internet even when the source repository is private, unless your organization has GitHub Enterprise Cloud access-control configured for a privately published Pages site. Therefore V2.6 masks exact procurement inventory, demand, suggested tonnes, and equivalent lots on the public dashboard by default.

Only set `PUBLIC_DASHBOARD_INCLUDE_PRIVATE=true` when the destination site itself has appropriate access control. For most deployments, leave the public site masked and use the private Discord output / repository records for exact values.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Open `public/index.html`.

## First procurement input

For a local run:

```bash
CURRENT_INVENTORY_T=420 DEMAND_60D_T=1200 python main.py
```

On Windows PowerShell:

```powershell
$env:CURRENT_INVENTORY_T="420"
$env:DEMAND_60D_T="1200"
python main.py
```

After the first valid input, blank values carry forward the saved state in `data/procurement_state.json`.

## Market data

### Core LME / zinc fundamentals

V2.6 accepts either:

1. `ZINC_MARKET_API_URL` returning JSON keys matching `data/manual_market.json`, or
2. manually maintained `data/manual_market.json`.

This is deliberate: V2.6 does not pretend an unrelated public proxy is official LME zinc data.

Expected keys include:

- `lme_cash`
- `lme_3m`
- `lme_inventory_t`
- `cancelled_warrants_t`
- `tc_usd_t`
- `physical_premium_usd_t`
- `smelter_margin_usd_t`
- `china_demand_yoy_pct`
- `global_balance_kt`
- `smelter_utilization_pct`

### Candles

Provide real LME Zinc 3M OHLC as CSV:

```text
timestamp,Open,High,Low,Close,Volume
2026-09-01T18:00:00Z,....
```

Default local file:

`data/lme_zinc_3m_daily.csv`

Optional intraday files are reserved for the Candle Lab:

- `data/lme_zinc_3m_1h.csv`
- `data/lme_zinc_3m_15m.csv`

Or set the matching `*_CSV_URL` secrets.

Store timestamps in UTC. Treat exchange session logic as Europe/London and display as Asia/Taipei when needed.

## Event Risk Overlay

Edit `data/event_risk.json` as a list:

```json
[
  {
    "type": "Mine disruption",
    "severity": "HIGH",
    "status": "ACTIVE",
    "description": "Example only"
  }
]
```

Events do not mechanically add bullish/bearish points. Higher event risk lowers confidence and flags uncertainty so later market data can confirm direction.

## GitHub Actions + Pages

The included workflow:

- runs Mon–Fri at 20:30 UTC,
- supports manual inventory / 60-day-demand inputs,
- persists `data/` and generated `public/`,
- deploys `public/` to GitHub Pages,
- sends Discord if `DISCORD_WEBHOOK_URL` is configured.

In Repository Settings → Pages, choose **GitHub Actions** as the source.

### Suggested repository secrets

- `DISCORD_WEBHOOK_URL`
- `ZINC_MARKET_API_URL`
- `ZINC_MARKET_API_KEY`
- `ZINC_DAILY_CSV_URL`
- `ZINC_1H_CSV_URL`
- `ZINC_15M_CSV_URL`

## Research records

- `data/latest_snapshot.json` — latest frozen state
- `data/snapshots/YYYY-MM-DD.json` — daily frozen snapshot
- `data/history.json` — daily market/procurement history
- `data/signal_journal.json` — both strategy decisions every day
- `data/paper_trades.json` — pending/open/closed paper trades with model version

These are meant to support future walk-forward testing, calibration, ablation tests, regime studies, and Champion/Challenger model comparison.

## Current limitations / next integrations

- Official/licensed LME intraday and historical data must be supplied through your approved data source.
- TC, physical premium, smelter utilization, and supply-demand data need a reliable commercial/manual/API feed.
- Intraday 15m/1h chart pages are data interfaces in the package, but the first dashboard currently renders the daily candle chart.
- Probability is marked PROVISIONAL until sufficient closed paper-trade observations exist; it is not presented as a guaranteed win probability.

## Smoke test

Run `python smoke_test.py` before deployment.
