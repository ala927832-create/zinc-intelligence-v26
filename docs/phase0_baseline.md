# Phase 0 · Baseline and protection record

Baseline date: **2026-10-14**

Baseline source commit: **645dc92** (`origin/main`)

Scope: record and protect the current system before the visual-language, Today,
Markets, Radar and data-source phases. This phase changes no market formula,
decision rule, generated public page or production data.

## 1. Public information architecture

| Page | Current role | Baseline finding |
|---|---|---|
| Today (`index.html`) | Six-card first look, posture, watch list, primary setup and zinc context split | Prices are first, but cards do not yet show daily/weekly change, technical position, icons or a concise per-market change sentence. |
| Markets (`markets.html`) | Chart-first market detail, periods, RSI, key levels, evidence and eight-question audit | Period controls and research levels exist. Line identity is not sufficiently visible and exact hover lookup is not yet available. |
| Radar (`radar.html`) | Cross-market direction/evidence/state table plus macro/event reminders | It is currently a table, not yet a change/conflict heatmap or dated event clock. |
| Journal (`journal.html`) | Daily direction, evidence and next observation | It preserves the public/private review boundary but remains brief. |
| System Status (`system-status.html`) | Operations-only data health | Present but intentionally absent from the four-item public navigation. GitHub Pages hiding is not authentication. |

Visible navigation is fixed at **Today / Markets / Radar / Journal** for the
next phases unless a separately approved information-architecture change is
made.

## 2. Frozen data identity

| Series | As of | Coverage / observations | Identity and source grade | Mode |
|---|---|---:|---|---|
| LME Zinc Cash | 2026-10-13 | latest snapshot | Public day-delayed reference, `B_PUBLIC_REFERENCE` | headline spot reference |
| LME Zinc 3M | 2026-10-13 | 451 closes from 2025-01-02 | Westmetall LME 3M reference, `B_PUBLIC_REFERENCE` | `CLOSE_ONLY` |
| SHFE Zinc | 2026-10-13 | 428 sessions from 2025-01-02 | SHFE official daily trading data, `A_OFFICIAL_EXCHANGE` | verified daily OHLC |
| COMEX Gold continuous reference | 2026-10-13 | 378 sessions | Yahoo public continuous-futures reference, `B_PUBLIC_REFERENCE` | delayed OHLC research reference |
| USD/JPY | 2026-10-13 | 5,000 sessions | Alpha Vantage FX daily, `B_PUBLIC_API` | delayed OHLC research reference |
| DXY | 2026-10-13 | 378 sessions | Yahoo index reference, `B_PUBLIC_REFERENCE` | delayed OHLC research reference |
| U.S. Treasury | not integrated | 0 | source pending | no chart or conclusion |

The baseline Core Data Gate is `HEALTHY`. The LME 3M close series has no
material gap over seven days and reports 451 validated observations. These
figures are a dated audit record, not constants that future market updates must
preserve.

## 3. Non-negotiable data boundaries

1. LME remains `CLOSE_ONLY` until real, permitted and contract-identified OHLC
   is integrated. No LME candle pattern, ATR or intraday range may be inferred.
2. SHFE OHLC remains explicitly labelled as a separate CNY/tonne exchange
   series. It must never be presented as LME OHLC.
3. Gold, USD/JPY and DXY public references are delayed research data, not broker
   quotes or exchange-certified executable settlements.
4. Bid/Ask, spread, fill, slippage, quantity, account risk and Actual R:R remain
   private execution inputs and must not enter public Pages.
5. Missing or stale data must degrade to a dated carry-forward or
   `MISSING / NO_TRADE`; no price or signal may be fabricated.
6. Evidence availability is not a win probability, confidence percentage or
   forecast probability.

## 4. Automation and ownership baseline

- Weekdays only: **10:30 and 17:30 Asia/Taipei** (`02:30` and `09:30` UTC).
- The build job is the single writer of generated `data/` and `public/` state.
- Pull requests run tests only; main runs test → build → deploy → production
  verification.
- 10:30 LINE mode is the full daily digest. 17:30 is alert-only. Duplicate
  sessions are suppressed.
- The deploy gate validates provenance, core-data health and public/private
  isolation before Pages deployment.

## 5. Baseline test result

All checks passed on 2026-10-14:

- Python compile
- smoke test
- LME Close-only / OHLC chart integrity
- market research and Westmetall multi-year history
- public/private isolation
- SHFE official daily OHLC identity
- private archive, reconstruction, notes and execution simulation
- Discord and LINE payload privacy
- decision framework, research pages and cross-asset research
- deploy validation and production verification
- **27 discovered unit tests passed** before adding the Phase 0 guardrails

The production verifier returned HTTP 200 and matched the deployed page to the
2026-10-14 snapshot with `Core Data Gate: HEALTHY`.

## 6. Guardrails added in this phase

`test_phase0_guardrails.py` protects durable boundaries without freezing visual
design or market values:

- four-page public navigation and hidden operations page;
- same frozen snapshot date across generated public pages;
- LME Close-only and SHFE official-exchange identity;
- provenance on available cross-asset series;
- weekday schedule, single-writer persistence and private-OHLC deploy gate.

## 7. Approved future-phase acceptance matrix

| Phase | Must improve | Must remain unchanged |
|---|---|---|
| 1 · Visual language | fixed colours, line styles, icons and source badges | formulas, market values and source grades |
| 2 · Today | daily/weekly change, technical position, date and change sentence | existing decision gates and privacy boundary |
| 3 · Markets | persistent legend, exact lookup, periods and plotted trade structure | LME Close-only; SHFE separate identity |
| 4 · Radar | heatmap, conflicts, changes and dated event clock | no headline-only trade trigger |
| 5 · Treasury | verified 2Y, 10Y, 2s10s and real yield | no conclusion when source/date validation fails |
| 6 · CFTC | weekly positioning and changes | never treat weekly COT as a daily trigger |
| 7 · Market evidence | instrument-specific evidence panels | no one-template-fits-all evidence claim |
| 8 · TradingView | labelled external interactive cross-check | no authenticated scraping or use as system-of-record |

Phase 1 should begin only after this baseline, test suite and production state
are accepted.
