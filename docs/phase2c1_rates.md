# Phase 2C-1: Treasury and real-yield evidence

Source: US Treasury official daily XML. No API key required.
Nominal par yields: BC_2YEAR, BC_10YEAR, BC_30YEAR.
Real par yield: TC_10YEAR, independently published, not CPI-subtracted nominal.
Documentation: https://home.treasury.gov/treasury-daily-interest-rate-xml-feed

Each series preserves source URL, grade, original observation date, age, count,
history, largest calendar gap and retrieval status. Rates are percent; differences
are basis points (100 * percentage-point difference). 1D/5D mean published
observations, not calendar days. Long gaps suppress change calculations.
Current/future dates and nonfinite/out-of-range observations are rejected.
Provider failure can carry forward validated Treasury-only history up to seven
calendar days, with an explicit carry-forward label. Older data is STALE and
excluded from cross-market confirmation. Missing rows are never interpolated.

Radar compares rates and prices only when their latest dates are identical and
the prior observation date is shared. Direction agreement is not causation.
No trade rules, trend formulae, trigger gates or position sizes are changed.
US-Japan rate spreads remain unavailable without Japanese rates. News, event
calendars, CFTC, ETF flows, and OI additions are outside this phase.

Persistence uses the existing single-writer snapshot workflow. Official history
is refetched on each run, so source revisions are accepted; committed snapshots
retain prior vintages. No separate historical data writer is introduced.
