import pandas as pd
import tempfile
import unittest

from private_lme_transparency import reconstruct


class PrivateLmeTests(unittest.TestCase):
 def test_private_reconstruction_applies_cancel_and_stays_labelled(self):
    tmp = tempfile.TemporaryDirectory(); tmp_path = __import__('pathlib').Path(tmp.name)
    trades=tmp_path/"trades.csv"; instruments=tmp_path/"instruments.csv"; output=tmp_path/"out.csv"
    pd.DataFrame([
        {"trade_id":"a","trade_date":"2026-09-14","event_time":"2026-09-14T08:00:00Z","isin":"x","price":2800,"volume":1,"action":"NEW"},
        {"trade_id":"b","trade_date":"2026-09-14","event_time":"2026-09-14T09:00:00Z","isin":"x","price":2850,"volume":1,"action":"NEW"},
        {"trade_id":"b","trade_date":"2026-09-14","event_time":"2026-09-14T10:00:00Z","isin":"x","price":2850,"volume":1,"action":"CANCEL"},
        {"trade_id":"c","trade_date":"2026-09-14","event_time":"2026-09-14T11:00:00Z","isin":"x","price":2820,"volume":2,"action":"NEW"},
    ]).to_csv(trades,index=False)
    pd.DataFrame([{"isin":"x","metal":"ZINC","venue":"LMEselect","contract":"3M"}]).to_csv(instruments,index=False)
    result=reconstruct(trades,instruments,output)
    self.assertEqual(result.iloc[0]["open"], 2800)
    self.assertEqual(result.iloc[0]["high"], 2820)
    self.assertEqual(result.iloc[0]["close"], 2820)
    self.assertEqual(result.iloc[0]["status"], "RECONSTRUCTED_NOT_OFFICIAL")
    tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
