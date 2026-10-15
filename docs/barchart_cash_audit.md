# Barchart Cash OHLC audit — 2026-10-15

Status: SAMPLE_NOT_OBTAINED / PUBLIC_INGESTION_NOT_APPROVED.

Candidates: O0Y00 (Zinc High Grade Cash), L4ZY00 (LME Zinc Cash Official).
These names alone do not establish equivalent series identity or genuine OHLC.

The historical endpoints returned a JavaScript robot-verification page. No dated
multi-row OHLC numeric sample was obtained. No protections were bypassed.

The Barchart getHistory documentation defines daily open/high/low/close fields,
but does not establish entitlement or coverage for either candidate symbol.

Terms reviewed at https://www.barchart.com/terms prohibit robot/data-mining
extraction. Offered downloads are for personal use subject to applicable rules;
public redistribution of raw values or regenerated charts is not established.
The terms separately permit certain attributed static screenshots; that is not
permission to ingest numeric OHLC or turn screenshots into raw observations.

Next acceptable evidence: a CSV downloaded through an offered download function,
with symbol identity, dates, timezone/session, units, close-vs-settlement basis,
and applicable use permissions. Validate privately first. Public use needs an
appropriate express permission or license. No Barchart values entered state.

References:
- https://www.barchart.com/futures/quotes/O0Y00/price-history/historical
- https://www.barchart.com/futures/quotes/L4ZY00/price-history/historical
- https://www.barchart.com/ondemand/api/getHistory
- https://help.barchart.com/support/solutions/articles/247949-how-can-i-download-chart-data-
- https://www.barchart.com/terms
