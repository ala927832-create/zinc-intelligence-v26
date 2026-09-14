# V2.6.1 Data Adapters

V2.6.1 keeps the procurement, paper-trading, Discord and dashboard layers unchanged. It replaces the single manual market input with independent provider adapters and a field-level fallback chain.

## Provider priority

### LME prices
1. LME Next-Day XML `OFS` for contract `ZS` (Zinc)
2. Existing generic `ZINC_MARKET_API_URL`
3. `data/manual_market.json`

The adapter stores Cash/Settlement, Cash bid/offer, 3M bid/offer and the normalized `lme_cash` / `lme_3m` fields used by the existing model.

### LME warehouse / inventory
1. LME Next-Day XML `WSM` for contract `ZS`
2. Official/licensed warehouse XLSX/CSV via `LME_WAREHOUSE_REPORT_URL` or local `data/lme_warehouse_stock.xlsx`
3. Existing generic API / manual fallback

Fields include opening/closing stock, live warrants, cancelled warrants and delivered-in/out when supplied by the report. `cancelled_ratio_pct` is calculated from the normalized stock denominator.

### Treatment Charge (TC)
1. Licensed/API gateway: `TC_API_URL` + optional `TC_API_KEY`
2. `data/tc_manual.csv`
3. Existing generic/manual market fallback

Accepted normalized TC keys:
- `tc_usd_t`
- `tc_smelter_usd_t`
- `tc_trader_usd_t`
- `tc_annual_benchmark_usd_t`

When smelter-purchase TC is available, it is preferred for `tc_usd_t`; trader and annual benchmark values remain available for research.

Example manual CSV:

```csv
date,tc_usd_t,tc_smelter_usd_t,tc_trader_usd_t,tc_annual_benchmark_usd_t
2026-09-11,,-95,-110,85
```

## LME XML Secrets

The LME XML service is licensed. Put credentials in GitHub repository Secrets, not source code:

- `LME_XML_USERNAME`
- `LME_XML_PASSWORD`
- optionally `LME_XML_CLIENT_ID` (defaults to `xmlfeeds` in code)

The adapter authenticates against the LME SSO token endpoint and then requests the official Next-Day XML feed. Missing credentials do not break the pipeline; the provider is marked `NOT_CONFIGURED` and lower-priority sources are tried.

## Candlestick feeds

V2.6.1 accepts CSV, XLS/XLSX or JSON full-OHLC data for LME Zinc 3M:

- `ZINC_DAILY_CANDLE_URL`
- `ZINC_1H_CANDLE_URL`
- `ZINC_15M_CANDLE_URL`
- optional `CANDLE_API_KEY`

Local fallbacks:
- `data/lme_zinc_3m_daily.csv`
- `data/lme_zinc_3m_1h.csv`
- `data/lme_zinc_3m_15m.csv`

Required columns are a timestamp/date plus Open, High, Low and Close. Volume is optional. Close-only series are rejected: the system does not fabricate candle ranges or ATR.

## Data provenance

`fetch_market_snapshot()` now includes:

- `field_sources`: provider/status/as-of metadata for each populated market field
- `provider_status`: success/error/not-configured status for each adapter

This is retained in `latest_snapshot.json` so future model reviews can reconstruct which data source produced each signal.

## Licensing / publication

LME, Fastmarkets, SMM and other commercial market data can have redistribution restrictions. Keep raw licensed data and credentials private unless your licence explicitly permits public redistribution. The public GitHub Pages dashboard should prefer derived signals and masked enterprise procurement data.
# Verified daily OHLC chart input

The public daily candlestick chart accepts only a dated LME zinc 3M series.
`ZINC_DAILY_CANDLE_FILE` or `ZINC_DAILY_CANDLE_URL` may provide CSV, JSON or Excel
with these columns on **every row**: `date,open,high,low,close,market,contract,currency,source,public_display_allowed`.
Use `YYYY-MM-DD`, `LME`, `ZINC_3M`, `USD`, an identifiable source name, and
`public_display_allowed=true` only after verifying permission to store the
rows in this public repository and show the chart on public Pages. This flag
records the operator's rights check; the program cannot grant usage rights.

The importer rejects the whole batch if it contains an incomplete, current-day,
contradictory, misidentified or undated bar. It retains verified historical
rows in `data/history/lme_zinc_3m_ohlc.csv`; a conflicting correction requires
review. Close-only reference history remains separate and is never converted
to candlesticks. A short OHLC history may show a chart while long-history
research remains unavailable. No synthetic OHLC test data is committed.
