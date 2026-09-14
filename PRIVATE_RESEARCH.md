# Private OHLC research (A + local-first B)

The public GitHub Pages pipeline does **not** ingest or publish this archive. This
standalone script contains no real OHLC or credentials and uses only the Python
standard library. Do not place the input CSV in this repository.

## A: private local master archive

Set `ZINC_PRIVATE_DIR` to an **absolute path outside this checkout and its parent
directories** on your own device, then run:

`python private_research.py import /absolute/path/to/your/verified_ohlc.csv`

Input columns: `date,open,high,low,close,market,contract,currency,source`. The
series must be real, completed LME ZINC_3M USD daily bars. A source attribution
must be present on every row. Import rejects incomplete bars, duplicate dates,
conflicting revisions, mixed contracts, today's date, and invalid price ranges.
No sample market prices are shipped. The archive lives under your chosen private
directory as `lme_zinc_3m_ohlc.csv`; back it up separately, subject to your
source's storage and sharing terms. Import is deliberately manual: no unverified
feed is claimed to be available.

## B: interactive local research view

`python private_research.py serve`

Open `http://127.0.0.1:8765/` on the same device. Hover a bar for its full
OHLC and source; choose 30/60/120/all sessions, browse older windows, and toggle
MA5 / MA20 / MA50 computed from completed daily closes. These are not your
factory's volume-weighted purchase cost. A shorter series still shows the
available bars, while each MA requires its full 5/20/50-session window. No
signals, probabilities, synthetic bars, remote JavaScript, or public exports.

This service binds **only to loopback** and has **no login system**. Never port
forward it or bind it to `0.0.0.0`. Remote browser access is **not deployed**:
it requires a separate authenticated hosting environment, reviewed access
policies, TLS, backups, and confirmation that the data licence permits storing
and displaying OHLC there. A private Discord or private GitHub repository alone
is not proof of these protections. Public Pages must remain unchanged.

## Separate chart observations

Below the local chart, record the source's HTTPS chart URL, the actual market
and contract displayed on that site, observation date, last trading day,
MA5/MA20/MA50 selection, `已核對` or `待核對`, and an optional description.
These entries are stored as `research_notes.jsonl` in `ZINC_PRIVATE_DIR`, never
in the OHLC CSV. `已核對` is a user-selected label, not automated validation.
The optional attachment field is only a filename reference; the app does not
download, upload, or copy website images. Confirm permission first, then save
an allowed image manually in a separate private `attachments` folder. Notes
and images do not supply OHLC values or change the displayed candle chart.
