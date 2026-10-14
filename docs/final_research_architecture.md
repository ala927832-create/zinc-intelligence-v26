# Final research dashboard architecture

## Reading flow

1. **Today (`index.html`)** — a ten-second decision layer led by six quote cards: LME Zinc Cash (3M secondary), SHFE Zinc, COMEX Gold, USD/JPY, DXY and US Treasury. Treasury remains `N/A / SOURCE PENDING` until a verified source exists. Posture, changes, the primary watch, zinc context and action rules follow the prices.
2. **Markets (`markets.html`)** — chart first, then interpretation. Each market opens with price identity, 20D/60D/120D/1Y/all controls, moving averages, close-based RSI14 and conditional levels. LME remains Close-only; its linked SHFE candlestick is clearly labelled as a separate market. Asset-specific evidence, gates and the eight-question audit follow the charts.
3. **Radar (`radar.html`)** — cross-market direction, evidence agreement and event discipline.
4. **Journal (`journal.html`)** — daily facts, interpretation, invalidation and next observation.
5. **System status (`system-status.html`)** — operations-only data health page. It is not linked from normal navigation. GitHub Pages does not provide authentication, so this is navigation hiding rather than access control.

The primary navigation contains pages only. Market names, inventory, TC and methodology are detail content rather than mixed page/anchor navigation. Radar and Journal retain their existing scope until their separate information-architecture review.

## Price boundary

The daily plan may publish Setup Zone, Trigger Price, Maximum Entry, Hard Stop, Close Invalidation, T1/T2, planned R:R and conditional order type. These are research levels calculated from completed sessions.

Bid/Ask, spread, actual fill, slippage, actual R:R and contract quantity belong to the execution-time layer. A plan cannot become executable until these fields are checked and Actual R:R is at least 1:2.

## Four-stage decision chain

1. **Asset-specific evidence** — price identity, as-of, source grade and the drivers relevant to that asset. Missing OI, yield spreads, COT, ETF flow or arbitrage costs are shown as `NOT_INTEGRATED`; technical indicators alone are never labelled full evidence agreement.
2. **Conditional plan** — setup zone, trigger, maximum entry, structural stop, close invalidation, T1/T2 and planned R:R. For true-OHLC markets the trigger-to-stop distance must not exceed 3 ATR; otherwise the output is `NO_TRADE`. A level is a research candidate, not a fill.
3. **Private execution approval** — the loopback-only tool validates timestamped Bid/Ask, spread, risk budget, multiplier, fees, slippage, whole contract quantity and T1 R:R ≥ 2. It never transmits an order.
4. **Post-trade review** — actual fill, exit, fees, slippage, net P&L, Actual R and rule adherence are written outside the repository. Fewer than 30 closed records remains an insufficient performance sample.

Every market must answer: direction, evidence consistency, risk location, entry permission, loss if wrong, exit plan, planned R:R and No-Trade reason. The deploy gate rejects a missing answer or an incomplete conditional plan.

## Data identities

- LME Zinc shows Cash as the headline spot reference and 3M as the close-only technical series. It can publish a daily-close trigger but cannot generate a candle pattern or ATR trigger.
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

## Critical limitations

- Evidence availability is not accuracy, confidence or win probability.
- Free public data can be rate-limited; the affected asset must degrade to carry-forward or `MISSING / NO_TRADE` rather than fabricate a current price.
- Continuous-futures references are unsuitable for claiming an executable contract price until the broker contract and live quote are verified.
- LME Close-only levels cannot answer candle-pattern questions. A true LME candle trigger remains unavailable until licensed or otherwise permitted OHLC is integrated.
