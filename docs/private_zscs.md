# Private Cnyes ZSCS reference archive

This is a separate, unverified cash-reference series, not official LME Cash
trade OHLC, not Westmetall 3M, and not SHFE. It must never supply public trading
signals, ATR or order triggers. Source basis, session, timezone, original vendor
instrument and personal automated-use permission remain unconfirmed.

## Manual private import

After confirming the permitted use, save the actual ZSCS chart-frame HTML using
the website's normal daily/two-year selection. The outer quote page alone has
no historical rows and will be rejected. Store the file outside all Git checkouts.

```bash
python private_zscs.py --input /absolute/private/zscs-source.html --private-dir /absolute/private/zscs-research
```

Open the generated `index.html` in a browser. It is self-contained and makes no
network requests. The JSON archive remains beside it, with source URL/hash,
import timestamp, unverified metadata and revision history. A failed/empty import
does not replace the last valid archive. Duplicate dates, wrong instruments,
nonfinite/range-invalid prices, and current/future source dates are rejected.
Importing another copy of unchanged bars does not duplicate them. A historical
price revision aborts unless reviewed and explicitly accepted using
`--accept-revisions`; previous and replacement rows are then retained.

Known LME holiday conflicts (2025-12-25 and 2026-04-03) and weekend source dates
remain in the archive, flagged, and excluded from the chart by default. Calendar
audit is partial; remaining dates are not automatically certified exchange dates.
Moving averages use selected reference rows, not a verified session calendar.

## Deployment boundary

Public GitHub contains code, an empty chart template, and synthetic tests only.
Actual archives, saved source HTML and generated charts stay outside this repo.
Do not put them in public Actions logs, artifacts, caches or Pages. GitHub ignores
are supplementary; the importer rejects output inside Git checkouts or public/
dist directories, and the public deployment validator rejects ZSCS archive markers.
The existing public workflow only runs offline tests; it does not fetch ZSCS.

The separate owner-private Site currently contains a manually published snapshot.
Running this importer does not synchronize that Site. A future private storage
and authenticated update route requires separate implementation after permission
and data definitions are established. No daily acquisition is enabled here.
