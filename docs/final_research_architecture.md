# Final research dashboard architecture

## Reading flow

1. **Today (`index.html`)** — zinc core data, daily conclusion and links to detail.
2. **Markets (`markets.html`)** — LME Zinc, SHFE Zinc, Gold, USD/JPY and DXY. Each market uses the same six gates: Data, Regime, Strategy, Trigger, Execution/Risk and Review.
3. **Radar (`radar.html`)** — cross-market direction, evidence agreement and event discipline.
4. **Journal (`journal.html`)** — daily facts, interpretation, invalidation and next observation.
5. **System status (`system-status.html`)** — operations-only data health page. It is not linked from normal navigation. GitHub Pages does not provide authentication, so this is navigation hiding rather than access control.

## Price boundary

The daily plan may publish Setup Zone, Trigger Price, Maximum Entry, Hard Stop, Close Invalidation, T1/T2, planned R:R and conditional order type. These are research levels calculated from completed sessions.

Bid/Ask, spread, actual fill, slippage, actual R:R and contract quantity belong to the execution-time layer. A plan cannot become executable until these fields are checked and Actual R:R is at least 1:2.

## Data identities

- LME Zinc remains a same-source close-only reference. It cannot generate a candle pattern or ATR trade trigger.
- SHFE Zinc uses official daily OHLC and retains representative-contract and roll identity.
- Gold (`GC=F`), USD/JPY (`JPY=X`) and DXY (`DX-Y.NYB`) are delayed public references. They are not exchange-certified settlements or live executable quotes.
- When `ALPHA_VANTAGE_API_KEY` is configured, USD/JPY daily OHLC becomes the preferred public API series. Gold historical data is retained separately as `Gold spot research / Close-only`; it never replaces COMEX futures OHLC.
- `USD Research Basket` is derived from six Alpha Vantage FX closes using published dollar-index weights. It is explicitly labelled `NOT OFFICIAL ICE DXY` and remains Close-only.
- A same-date USD/JPY deviation above 0.50% between providers becomes `DATA_CONFLICT` and blocks a plan.
- A public-source outage produces `MISSING / NO_TRADE`. A previously verified cross-asset series may be carried forward for at most five days with its original as-of date and explicit carry-forward label.

## LINE setup

LINE Notify is retired. The pipeline uses the LINE Messaging API push endpoint. Configure these GitHub Actions repository secrets:

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_USER_ID`
- `ALPHA_VANTAGE_API_KEY`

The daily message includes the five market closes/references and state. A second alert is sent only when a market direction changes. Both messages state that the alert is not execution confirmation.

## Non-negotiable rules

> No complete data, no signal. No trigger, no order. No acceptable Bid/Ask, no executable price. Actual R:R below 1:2, reject. Unclear structure, No Trade.

The system does not publish uncalibrated win rates, profit probabilities or invented LME OHLC.
