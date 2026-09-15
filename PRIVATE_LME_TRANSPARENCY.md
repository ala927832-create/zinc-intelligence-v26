# Private LME 3M transparency reconstruction

This optional Plan B workflow is private-only. It does not feed the public
dashboard and does not claim to reproduce the licensed official LME OHLC
product. Obtain and use LME transparency/TIF files only under the applicable
LME licence.

Normalize two CSV inputs:

* trades: `trade_id,trade_date,event_time,isin,price,volume,action`
* instruments: `isin,metal,venue,contract`

Set `ZINC_PRIVATE_DIR` to a directory outside the repository, then run:

```bash
python private_lme_transparency.py --trades /private/trades.csv --instruments /private/instruments.csv
```

Corrections replace the prior `trade_id`; cancellations remove it. Eligible
Zinc / LMEselect / 3M trades are aggregated in timestamp order into daily
first, maximum, minimum and last prices. The result is labelled
`RECONSTRUCTED_NOT_OFFICIAL` and must not be copied into `data/` or `public/`.
